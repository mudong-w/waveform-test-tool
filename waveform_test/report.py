from pathlib import Path
import csv
import json
import shutil
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from openpyxl import Workbook
from openpyxl.drawing.image import Image as SheetImage
from .analysis import read_trace, find_cycle, pulse_metrics
from .storage import write_json
from .profiles import active_windows, range_label, read_profiles, report_points


def time_label(seconds):
    return f"{seconds*1000:.1f} ms" if 0 < seconds < .1 else f"{seconds:.1f} s"


def screen_project(path, segments, t, volts, threshold, baseline):
    """Match digitized activity to the native 800x480 full-width CH1 display."""
    img = Image.open(path).convert("RGB")
    if img.size != (800,480):
        raise ValueError("仅支持 800×480 全宽原生截图；可省略 --screen 导出采样重绘图")
    pixels = np.asarray(img)[49:380].astype(float)
    cyan = (pixels[:,:,1]>150) & (pixels[:,:,2]>150) & (pixels[:,:,0]<95)
    if not cyan[:,:10].any() or not cyan[:,-10:].any():
        raise ValueError("屏幕两端未见 CH1 走线，请等待长记录铺满全宽")
    cyan[cyan.mean(axis=1)>.95] = False
    actual = cyan.sum(axis=0)>12
    indices = np.minimum(799, np.arange(len(t))*800//len(t))
    reference = np.bincount(indices, weights=(abs(volts-baseline)>=threshold), minlength=800)>0
    if np.mean(actual[:12] == reference[:12]) < .15 and not actual[:12].any():
        raise ValueError("屏幕左端与采样不符，请检查长记录是否铺满屏幕")
    def edges(mask):
        return np.flatnonzero(mask[1:] != mask[:-1])+1
    # Match gap edges with the same direction. Small packet gaps can add extra edges.
    wanted = [p for p in edges(reference) if 8<=p<792 and
              (not reference[p-7:p].any() or not reference[p:p+7].any())]
    if len(wanted)<2:
        raise ValueError("原生截图缺少可校准的间隔边缘")
    possible = range(-35,36)
    def cost(shift):
        bounds = np.arange(40,760)
        return np.mean(actual[bounds+shift] != reference[bounds])
    shift = min(possible,key=lambda s:(cost(s),abs(s)))
    boundaries = edges(actual)
    if cost(shift)>.12 or any(not np.any((abs(boundaries-p-shift)<=4) &
          (actual[boundaries]==reference[p])) for p in wanted):
        raise ValueError("原生截图与采样的间隔边界未对齐，检查是否为同一帧")
    def pixel(i):
        return round(i*800/len(t))+shift
    start,end = pixel(segments[0]["i"]),pixel(segments[-1]["j"])
    if start<0 or end>792 or not actual[end+2:].any():
        raise ValueError("原生截图未容纳完整周期和后续复现")
    objects = []
    def line(x1,x2,y,label,color):
        objects.append({
            "id": f"mark-{len(objects)+1}", "kind":"h-arrow",
            "x1":x1, "x2":x2, "y1":y, "y2":y, "text":label,
            "textDx":0, "textDy":0, "textBoxW":0, "textBoxH":0,
            "hidden":False, "locked":False, "autoMeasure":False, "measurePrefix":"",
            "color":color, "opacity":1, "shaftStyle":"solid", "headShape":"triangle",
            "arrowEnds":"both", "endTicks":True, "lineWidth":1.5, "arrowSize":5,
            "fillAlpha":.14, "fontFamily":"sans-serif", "fontSize":12,
            "fontWeight":"600", "italic":False, "textPos":"above",
            "textBgMode":"outline", "textLeader":False,
        })
    for row in segments:
        if row["stage"].startswith("t") or row is segments[0]:
            label = ("gap" if row is segments[0] else row["stage"])+" "+time_label(row["duration_s"])
            line(pixel(row["i"]),pixel(row["j"]),404,label,"#ffc857")
    line(start,end,431,"T = "+time_label(segments[-1]["end_s"]),"#46cbff")
    dt = (t[-1]-t[0])/(len(t)-1)
    return {"version":2, "objects":objects,
            "calX":{"pxPerUnit":800/(len(t)*dt),"unit":"s","decimals":"1","refVal":1},
            "calY":{"pxPerUnit":None,"unit":"V","decimals":"2","refVal":1}}


def analyze(csv_path,out,threshold,gap,packet_gap,stages,baseline,screen=None,durations=None,profile=None):
    if not np.isfinite(packet_gap) or not 0 < packet_gap < gap or (stages is not None and stages<1):
        raise ValueError("组间识别阈值须小于分段阈值；指定段数时必须为正数")
    t,v,dt = read_trace(csv_path)
    parts, repeat, visible = find_cycle(t,v,dt,threshold,gap,stages,baseline)
    settings = json.loads(Path(durations).read_text(encoding="utf-8-sig")) if durations else {}
    if not isinstance(settings,dict) or set(settings)-{p[0] for p in parts}:
        raise ValueError("时长校准键应与当前 gap1、t1 等阶段一致")
    profiles = read_profiles(profile, [key for key,_,_ in parts if key.startswith("t")])
    adopted = {}
    data = out/"data"
    data.mkdir()
    shutil.copyfile(csv_path,data/"waveform.csv")
    if screen:
        raw_screen = data/("screen-original"+Path(screen).suffix)
        shutil.copyfile(screen,raw_screen)
    rows, freq_points, envelope = [], [], []
    cursor = 0.
    for key,i,j in parts:
        measured = (j-i)*dt
        duration = float(settings.get(key,measured))
        if not np.isfinite(duration) or duration<=0:
            raise ValueError("校准阶段时长必须是有限正数")
        source = v[i:j]
        trace_t = t[i:j]
        is_active = key.startswith("t")
        ft,hz,group = pulse_metrics(trace_t,source,dt,threshold,baseline,packet_gap) if is_active else ([],[],None)
        curves = profiles.get(key, {})
        if curves:
            windows = active_windows(source,threshold,baseline,dt,packet_gap) if group is not None else None
            adopted[key] = {kind: report_points(points,cursor,duration,windows) for kind,points in curves.items()}
        # The bin width balances trend detail with enough samples to see both phases.
        bin_size = min(len(source),max(2,round(.1/dt)))
        bins = []
        for k in range(0,len(source),bin_size):
            chunk = source[k:k+bin_size]
            bins.append((cursor+duration*(k+len(chunk)/2)/len(source),float(np.ptp(chunk))))
        envelope.append(([cursor]+[x for x,_ in bins]+[cursor+duration],
                         [bins[0][1]]+[y for _,y in bins]+[bins[-1][1]]))
        freq_points.append(([cursor+(x-t[i])*duration/measured for x in ft],hz))
        rows.append(dict(stage=key,i=i,j=j,measured_s=measured,start_s=cursor,
                         end_s=cursor+duration,duration_s=duration,min_v=float(min(source)),
                         max_v=float(max(source)),vpp=float(np.ptp(source)),
                         pulse_hz_median=float(np.median(hz)) if hz else None,
                         group_hz=group,frequency_intervals=len(hz)))
        cursor += duration
    report = dict(measured_period_s=sum(r["measured_s"] for r in rows),period_s=cursor,
                  visible_next_output_s=visible,sample_rate_hz=1/dt,threshold_v=threshold,
                  baseline_v=baseline,stage_gap_s=gap,packet_gap_s=packet_gap,overrides=settings,
                  screen_source="instrument" if screen else "samples",segments=rows)
    if profiles:
        report["reviewed_profiles"] = profiles
    write_json(data/"report.json",report)
    def table(file,headers,items):
        with file.open("w",newline="",encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(items)
    table(data/"segments.csv",rows[0].keys(),[r.values() for r in rows])
    table(data/"frequency.csv",["stage","report_time_s","pulse_hz"],
          ((r["stage"],x,y) for r,(xx,yy) in zip(rows,freq_points) for x,y in zip(xx,yy)))
    table(data/"amplitude.csv",["stage","report_time_s","window_vpp"],
          ((r["stage"],x,y) for r,(xx,yy) in zip(rows,envelope) for x,y in zip(xx,yy)))
    if profiles:
        table(data/"reviewed-curves.csv",["stage","quantity","report_time_s","adopted_value"],
              ((name,kind,x,y) for name,curves in adopted.items()
               for kind,(xx,yy) in curves.items() for x,y in zip(xx,yy)))
    marked = out/"cycle.png"
    if screen:
        from .editor_export import export_marked_png
        project = screen_project(raw_screen,rows,t,v,threshold,baseline)
        project_path = data/"标注工程.json"
        write_json(project_path,project)
        export_marked_png(raw_screen,project_path,len(project["objects"]),marked)
    else:
        start,end = parts[0][1],parts[-1][2]
        right = min(len(t),repeat+max(2,round(visible/dt)),repeat+max(2,round(.35*(end-start))))
        fig,ax = plt.subplots(figsize=(10,3.5),layout="constrained")
        ax.plot(t[start:right]-t[start],v[start:right],lw=.45,color="#087d86")
        for r in rows:
            if r["stage"].startswith("t"):
                midpoint = (t[r["i"]]+t[r["j"]])/2-t[start]
                ax.text(midpoint,.95,r["stage"]+" "+time_label(r["duration_s"]),ha="center",va="top",transform=ax.get_xaxis_transform(),bbox=dict(facecolor="white",edgecolor="none",alpha=.8))
        ax.axvline(t[end]-t[start],color="#475569",ls="--")
        ax.set(xlabel="Measured time (s)",ylabel="Voltage (V)",title="Sample reconstruction   |   T = "+time_label(cursor))
        fig.savefig(marked,dpi=135)
        plt.close(fig)
    fig,axes = plt.subplots(2,1,sharex=True,figsize=(10,5),layout="constrained")
    for r,(x,y),(ft,hz) in zip(rows,envelope,freq_points):
        curves = adopted.get(r["stage"], {})
        if profiles and r["stage"].startswith("gap"):
            for ax,color in zip(axes,["#077d86","#2154a4"]):
                ax.plot([r["start_s"],r["end_s"]],[0,0],color=color)
        else:
            axes[0].plot(*curves.get("amplitude_vpp",(x,y)),color="#077d86")
            if "frequency_hz" in curves:
                axes[1].plot(*curves["frequency_hz"],color="#2154a4")
            else:
                axes[1].scatter(ft,hz,s=4,color="#2154a4")
        if r["stage"].startswith("t"):
            for ax in axes:
                ax.axvspan(r["start_s"],r["end_s"],color="#4982ac",alpha=.08)
            axes[0].text((r["start_s"]+r["end_s"])/2,.98,r["stage"],transform=axes[0].get_xaxis_transform(),ha="center",va="top")
    axes[0].set_ylabel("Amplitude (Vpp)")
    axes[1].set(ylabel="Pulse frequency (Hz)",xlabel="Cycle time (s)",xlim=(0,cursor))
    trend = out/"trends.png"
    fig.savefig(trend,dpi=135)
    plt.close(fig)
    lines = [f"每轮 {time_label(cursor)}。"]
    for r in rows:
        if r["stage"].startswith("gap"):
            lines.append(f'间隔 {time_label(r["duration_s"])}。')
            continue
        hz,group = r["pulse_hz_median"],r["group_hz"]
        hz_text = f"脉冲频率中位数 {hz:.0f} Hz" if hz else "可解析的脉冲间距不足"
        group_text = f"，组重复频率 {group:.0f} Hz" if group else ""
        curves = profiles.get(r["stage"], {})
        amp_text = f'峰峰值 {r["vpp"]:.0f} Vpp'
        if "amplitude_vpp" in curves:
            amp_text = "采用峰峰值 " + range_label(curves["amplitude_vpp"],"Vpp")
        if "frequency_hz" in curves:
            hz_text = "采用脉冲频率 " + range_label(curves["frequency_hz"],"Hz")
        lines.append(f'{r["stage"]} 输出 {time_label(r["duration_s"])}，{amp_text}，{hz_text}{group_text}。')
    (out/"说明.txt").write_text("\n".join(lines)+"\n",encoding="utf-8-sig")
    wb = Workbook()
    ws = wb.active
    ws.title = "参数"
    ws.append(["周期 (s)",cursor,"实测周期 (s)",report["measured_period_s"]])
    ws.append(["阶段","起始 (s)","结束 (s)","采用时长 (s)","实测时长 (s)","峰峰值 (Vpp)","脉冲频率中位数 (Hz)","组重复频率 (Hz)"])
    keys = ["stage","start_s","end_s","duration_s","measured_s","vpp","pulse_hz_median","group_hz"]
    for r in rows:
        ws.append([r[k] for k in keys])
    for col in "ABCDEFGH":
        ws.column_dimensions[col].width=23
    for name,path in [("周期标记",marked),("幅频趋势",trend)]:
        sheet = wb.create_sheet(name)
        sheet.add_image(SheetImage(str(path)),"A1")
    if profiles:
        sheet = wb.create_sheet("幅频采用值")
        sheet.append(["阶段","量","段内进度","周期内时间 (s)","采用值","单位"])
        for row in rows:
            for kind,points in profiles.get(row["stage"],{}).items():
                for fraction,value in points:
                    sheet.append([row["stage"],kind,fraction,row["start_s"]+fraction*row["duration_s"],
                                  value,"Vpp" if kind=="amplitude_vpp" else "Hz"])
        for col in "ABCDEF":
            sheet.column_dimensions[col].width = 21
    wb.save(out/"汇总表.xlsx")
    return {k:v for k,v in report.items() if k!="segments"}

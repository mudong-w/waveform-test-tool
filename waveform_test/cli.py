import argparse
import json
from pathlib import Path
from .storage import new_run


def main():
    parser = argparse.ArgumentParser(prog="waveform-test",description="波形测试工具")
    sub = parser.add_subparsers(dest="action",required=True)
    sub.add_parser("devices",help="列出支持的 USB 设备")
    editor = sub.add_parser("annotate",help="打开离线标定画图工具")
    editor.add_argument("--path",action="store_true",help="仅显示 HTML 文件位置")
    capture = sub.add_parser("capture",help="保存当前长记录与原生截屏")
    capture.add_argument("--resource")
    demo = sub.add_parser("demo",help="生成合成演示 CSV")
    run = sub.add_parser("analyze",help="识别周期并导出图、表和说明")
    integrated = sub.add_parser("run",help="一次完成采集或回放、原生标定、幅频分析与报告交付")
    integrated.add_argument("--out",type=Path,help="新报告目录，默认在 runs 下创建")
    integrated.add_argument("--resource")
    integrated.add_argument("--csv",type=Path,help="回放已保存的波形 CSV")
    integrated.add_argument("--capture-file",type=Path,help="回放记录的配套采集参数 JSON")
    for cmd in [capture,demo,run]:
        cmd.add_argument("--out",required=True,type=Path,help="新的输出目录")
    run.add_argument("csv",type=Path)
    for cmd in [run,integrated]:
        cmd.add_argument("--threshold",type=float,required=cmd is run,help="相对空闲基线的识别阈值 (V)")
        cmd.add_argument("--baseline",type=float,default=0)
        cmd.add_argument("--stage-gap",type=float,default=.35)
        cmd.add_argument("--packet-gap",type=float,default=.05)
        cmd.add_argument("--stages",type=int,help="每轮输出段数")
        cmd.add_argument("--screen",type=Path,help="同帧的 800x480 全宽原生截图")
        cmd.add_argument("--durations",type=Path,help="按阶段指定报告采用时长的 JSON")
        cmd.add_argument("--profile",type=Path,help="经复核的分段幅频曲线 JSON")
    args = parser.parse_args()
    try:
        if args.action == "run":
            from .workflow import run_waveform_test
            result = run_waveform_test(output_directory=args.out, resource=args.resource,
                                       csv_file=args.csv, screen_file=args.screen, threshold_v=args.threshold,
                                       baseline_v=args.baseline, stage_gap_s=args.stage_gap,
                                       packet_gap_s=args.packet_gap, stages=args.stages,
                                       durations_file=args.durations, profile_file=args.profile,
                                       capture_file=args.capture_file)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            if result["status"] != "complete":
                parser.exit(2)
            return
        if args.action == "annotate":
            page = Path(__file__).resolve().parent / "annotator" / "示波器标定画图工具.html"
            if not page.is_file():
                raise FileNotFoundError(page)
            print(page)
            if not args.path:
                import webbrowser
                if not webbrowser.open(page.as_uri()):
                    parser.exit(1, "请用浏览器打开上面的 HTML 文件。\n")
            return
        if args.action == "devices":
            from .scope import devices
            print(json.dumps(devices()))
            return
        with new_run(args.out) as out:
            if args.action=="capture":
                from .scope import export
                export(out,args.resource)
            elif args.action=="demo":
                from .demo import demo
                demo(out)
            else:
                from .report import analyze
                summary = analyze(args.csv,out,args.threshold,args.stage_gap,args.packet_gap,args.stages,args.baseline,args.screen,args.durations,args.profile)
                print(json.dumps(summary,ensure_ascii=False))
        print(args.out.resolve())
    except (ValueError,OSError,ImportError) as error:
        parser.exit(1, f"waveform-test: {error}\n")


if __name__=="__main__":
    main()

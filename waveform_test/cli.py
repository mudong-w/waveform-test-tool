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
    for cmd in [capture,demo,run]:
        cmd.add_argument("--out",required=True,type=Path,help="新的输出目录")
    run.add_argument("csv",type=Path)
    run.add_argument("--threshold",type=float,required=True,help="相对空闲基线的脉冲识别阈值，单位 V")
    run.add_argument("--baseline",type=float,default=0)
    run.add_argument("--stage-gap",type=float,default=.35)
    run.add_argument("--packet-gap",type=float,default=.05)
    run.add_argument("--stages",type=int,help="每轮输出段数")
    run.add_argument("--screen",type=Path,help="同一次采集的全宽 800x480 原生截图")
    run.add_argument("--durations",type=Path,help="按阶段指定报告时长的 JSON 文件")
    run.add_argument("--profile",type=Path,help="经复核的分段幅频曲线 JSON，横坐标为段内进度 0 到 1")
    args = parser.parse_args()
    try:
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

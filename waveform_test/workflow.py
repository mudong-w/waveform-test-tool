"""One acquisition or replay, one calibrated report, one delivery directory."""
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import json
import shutil

from .report import analyze
from .storage import new_run


def run_waveform_test(output_directory: str | None = None, resource: str | None = None,
                      csv_file: str | None = None, screen_file: str | None = None,
                      threshold_v: float | None = None, baseline_v: float = 0,
                      stage_gap_s: float = .35, packet_gap_s: float = .05,
                      stages: int | None = None, durations_file: str | None = None,
                      profile_file: str | None = None, capture_file: str | None = None) -> dict:
    """采集 CH1 和同帧截图，调用内置标定工具并交付图、文字和 Excel。csv_file 用于离线回放。
    成功时返回文字和文件绝对路径。需要补采或复核时返回原因和已保存的数据目录。
    """
    if (csv_file and resource) or (not csv_file and (screen_file or capture_file)):
        raise ValueError("USB 采集自动保存同帧截图和仪器参数；回放时请提供配套的 CSV。")
    default = Path("runs") / (datetime.now().strftime("波形测试-%Y%m%d-%H%M%S-") + uuid4().hex[:8])
    target = Path(output_directory or default).resolve()
    with new_run(target) as out:
        raw = out / "数据"
        raw.mkdir()
        csv = raw / "waveform.csv"
        screen = raw / "screen-original.bmp"
        metadata = raw / "capture.json"
        if csv_file:
            source = Path(csv_file)
            shutil.copyfile(source, csv)
            # Auto-pair only the adapter's canonical acquisition layout.
            canonical = source.name == "waveform.csv"
            image = Path(screen_file) if screen_file else source.with_name("screen-original.bmp")
            screen = None
            if screen_file or (canonical and image.is_file()):
                screen = raw / ("screen-original" + image.suffix)
                shutil.copyfile(image, screen)
            info = Path(capture_file) if capture_file else source.with_name("capture.json")
            if capture_file or (canonical and info.is_file()):
                shutil.copyfile(info, metadata)
        else:
            from .scope import export
            export(raw, resource)

        result = {"data_directory": str(target / "数据")}
        with TemporaryDirectory(dir=out) as temporary:
            report = Path(temporary)
            try:
                info = json.loads(metadata.read_text(encoding="utf-8-sig")) if metadata.exists() else {}
                if info.get("full_scale_adc_samples", 0):
                    raise ValueError("采样达到 ADC 量程端点，请核对削顶并调整量程补采。")
                summary = analyze(csv, report, threshold_v, stage_gap_s, packet_gap_s, stages,
                                  baseline_v, screen, durations_file, profile_file,
                                  volts_per_div=info.get("volts_per_div"))
            except (ValueError, OSError, RuntimeError, ImportError) as error:
                result.update(status="needs_review", reason=str(error))
            else:
                for item in (report / "data").iterdir():
                    if not (raw / item.name).exists():
                        item.rename(raw / item.name)
                files = {"cycle_image": "cycle.png", "trend_image": "trends.png",
                         "description_file": "说明.txt", "workbook": "汇总表.xlsx"}
                for name in files.values():
                    (report / name).rename(out / name)
                result.update(status="complete", screen_source=summary["screen_source"],
                              description=(out / "说明.txt").read_text(encoding="utf-8-sig"),
                              files={key: str(target / name) for key, name in files.items()})
    return result

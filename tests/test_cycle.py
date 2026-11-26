import json
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from waveform_test.demo import demo
from waveform_test.analysis import read_trace, find_cycle, pulse_metrics


class PulseRecordTest(unittest.TestCase):
    def test_native_report_embeds_editor_output_verbatim(self):
        from PIL import Image
        from openpyxl import load_workbook
        from waveform_test.report import analyze
        from waveform_test.storage import new_run
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            demo(root)
            csv_path = root / "waveform.csv"
            _, volts, _ = read_trace(csv_path)
            columns = np.minimum(799, np.arange(len(volts))*800//len(volts))
            active = np.bincount(columns, weights=np.abs(volts)>=3, minlength=800)>0
            raster = np.zeros((480,800,3), dtype=np.uint8)
            raster[240,:,1:] = 255
            raster[150:225,active,1:] = 255
            screen = root / "screen.bmp"
            Image.fromarray(raster).save(screen)
            target = root / "report"
            def editor(source, project_file, count, output):
                self.assertEqual(source.read_bytes(),screen.read_bytes())
                project = json.loads(project_file.read_text(encoding="utf-8"))
                self.assertEqual(count,len(project["objects"]))
                self.assertEqual(count,3)
                Image.new("RGB",(800,480),"navy").save(output)
            with patch("waveform_test.editor_export.export_marked_png",side_effect=editor) as export:
                with new_run(target) as out:
                    analyze(csv_path,out,3,.35,.05,1,0,screen)
            export.assert_called_once()
            wb = load_workbook(target/"汇总表.xlsx")
            try:
                picture, = wb["周期标记"]._images
                self.assertEqual(picture._data(),(target/"cycle.png").read_bytes())
            finally:
                wb.close()

    def test_physical_units_and_partial_first_cycle(self):
        with TemporaryDirectory() as tmp:
            demo(Path(tmp))
            t,v,dt = read_trace(Path(tmp)/"waveform.csv")
        parts,repeat,visible = find_cycle(t,v,dt,3,.35,None,0)
        self.assertEqual([p[0] for p in parts],["gap1","t1"])
        self.assertAlmostEqual((parts[-1][2]-parts[0][1])*dt,4,places=2)
        self.assertGreater(visible,.25)
        _,a,b = parts[1]
        _,hz,rate = pulse_metrics(t[a:b],v[a:b],dt,3,0,.05)
        self.assertAlmostEqual(float(np.median(hz)),100,places=1)
        self.assertAlmostEqual(rate,5,places=1)
        self.assertEqual(np.ptp(v[a:b]),20)
        with self.assertRaises(ValueError):
            find_cycle(t[:repeat],v[:repeat],dt,3,.35,None,0)

    def test_report_uses_calibrated_duration_and_preserves_input(self):
        from openpyxl import load_workbook
        from zipfile import ZipFile
        from waveform_test.report import analyze
        from waveform_test.storage import new_run
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            demo(folder)
            source = folder / "waveform.csv"
            calibration = folder / "calibration.json"
            calibration.write_text('{"gap1": 1, "t1": 3.1}', encoding="utf-8")
            target = folder / "report"
            with new_run(target) as out:
                analyze(source, out, 3, .35, .05, 1, 0, durations=calibration)
            meta = json.loads((target/"data/report.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(meta["period_s"],4.1)
            self.assertAlmostEqual(meta["measured_period_s"],4)
            self.assertEqual((target/"data/waveform.csv").read_bytes(),source.read_bytes())
            self.assertIn("4.1 s",(target/"说明.txt").read_text(encoding="utf-8-sig"))
            book = target/"汇总表.xlsx"
            wb = load_workbook(book)
            self.assertAlmostEqual(wb["参数"]["B1"].value,4.1)
            self.assertAlmostEqual(wb["参数"]["C4"].value,4.1)
            wb.close()
            with ZipFile(book) as archive:
                images = [archive.read(k) for k in archive.namelist() if k.startswith("xl/media/")]
            self.assertCountEqual(images,[(target/n).read_bytes() for n in ("cycle.png","trends.png")])
            with self.assertRaises(ValueError):
                with new_run(target):
                    pass

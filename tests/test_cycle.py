import json
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest
import numpy as np
from waveform_test.demo import demo
from waveform_test.analysis import read_trace, find_cycle, pulse_metrics


class PulseRecordTest(unittest.TestCase):
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

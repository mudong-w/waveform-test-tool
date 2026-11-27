import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import load_workbook

from waveform_test.demo import demo
from waveform_test.profiles import read_profiles, report_points
from waveform_test.report import analyze
from waveform_test.storage import new_run


class ReviewedProfilesTest(unittest.TestCase):
    def test_steps_and_measurement_evidence(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            demo(root)
            config = root / "profile.json"
            config.write_text(json.dumps({"t1":{"amplitude_vpp":[[0,18],[1,18]],
                                                "frequency_hz":[[0,98],[1,98]]}}))
            with new_run(root/"report") as out:
                analyze(root/"waveform.csv",out,3,.35,.05,1,0,profile=config)
            out = root/"report"
            raw = json.loads((out/"data/report.json").read_text())
            self.assertEqual(raw["segments"][1]["vpp"],20)
            self.assertIn("18 Vpp",(out/"说明.txt").read_text(encoding="utf-8-sig"))
            with (out/"data/reviewed-curves.csv").open(encoding="utf-8-sig") as f:
                levels = {float(row["adopted_value"]) for row in csv.DictReader(f) if row["quantity"]=="amplitude_vpp"}
            self.assertEqual(levels,{0,18})
            book = load_workbook(out/"汇总表.xlsx")
            self.assertEqual(book["幅频采用值"]["E2"].value,18)
            for name,file in [("周期标记","cycle.png"),("幅频趋势","trends.png")]:
                self.assertEqual(book[name]._images[0]._data(),(out/file).read_bytes())
            book.close()
        self.assertEqual(report_points([[0,5],[.5,10],[.5,7],[1,7]],1,2,None),
                         ([1,2,2,3],[5,10,7,7]))

    def test_invalid_profiles(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"p.json"
            for spec in ({"t2":{}},{"t1":{"amplitude_vpp":[[.1,3],[1,3]]}},
                         {"t1":{"frequency_hz":[[0,-1],[1,3]]}},
                         {"t1":{"frequency_hz":[[0,1],[.8,1],[.2,1],[1,1]]}}):
                path.write_text(json.dumps(spec))
                with self.assertRaises(ValueError):
                    read_profiles(path,["t1"])

import asyncio
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from waveform_test.demo import demo
from waveform_test.server import server
from waveform_test.workflow import run_waveform_test


class UnifiedWorkflowTest(unittest.TestCase):
    def test_single_mcp_tool_and_replay_delivery(self):
        tools = asyncio.run(server.list_tools())
        self.assertEqual([tool.name for tool in tools], ["run_waveform_test"])
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            demo(root)
            report = root / "report"
            reply = run_waveform_test(str(report), csv_file=str(root/"waveform.csv"))
            self.assertEqual(reply["status"], "complete")
            self.assertEqual(reply["screen_source"], "samples")
            with (report/"数据"/"packet-amplitude.csv").open(encoding="utf-8-sig") as stream:
                levels = {float(row["window_vpp"]) for row in csv.DictReader(stream)}
            self.assertEqual(levels, {0.,20.})
            self.assertTrue(all(Path(p).is_file() for p in reply["files"].values()))
            self.assertEqual(reply["description"], (report/"说明.txt").read_text(encoding="utf-8-sig"))
            self.assertEqual(set(p.name for p in report.iterdir()),
                             {"cycle.png", "trends.png", "说明.txt", "汇总表.xlsx", "数据"})
            with self.assertRaises(ValueError):
                run_waveform_test(str(report), csv_file=str(root/"waveform.csv"))

    def test_failed_native_calibration_preserves_frozen_frame(self):
        def capture(folder, resource):
            self.assertEqual(resource, "simulated")
            demo(folder)
            (folder/"screen-original.bmp").write_bytes(b"invalid image")
            (folder/"capture.json").write_text(json.dumps({"volts_per_div": 2}))
        with TemporaryDirectory() as tmp, patch("waveform_test.scope.export", side_effect=capture) as export:
            report = Path(tmp)/"report"
            result = run_waveform_test(str(report), resource="simulated")
            export.assert_called_once()
            self.assertEqual(result["status"], "needs_review")
            self.assertEqual(list(report.iterdir()), [report/"数据"])
            for name in ["waveform.csv", "capture.json", "screen-original.bmp"]:
                self.assertTrue((report/"数据"/name).is_file())

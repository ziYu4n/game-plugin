import json
import os
import tempfile
import unittest
from unittest import mock

import gui


class RepeatScheduleTests(unittest.TestCase):
    def test_repeat_schedule_persists_and_restores(self):
        with tempfile.TemporaryDirectory() as folder:
            schedule = os.path.join(folder, "schedule.json")
            queue = os.path.join(folder, "queue.json")
            with mock.patch.object(gui, "SCHEDULE_FILE", schedule), mock.patch.object(
                gui, "QUEUE_FILE", queue
            ):
                app = gui.App()
                ok, error = app.set_repeat_moyu(True)

                self.assertTrue(ok)
                self.assertEqual(error, "")
                self.assertTrue(app.repeat_snapshot()["enabled"])
                self.assertEqual(
                    app.repeat_snapshot()["interval_seconds"], 30 * 60
                )
                with open(schedule, "r", encoding="utf-8") as handle:
                    saved = json.load(handle)
                self.assertTrue(saved["moyu_enabled"])

                restored = gui.App()
                self.assertTrue(restored.repeat_snapshot()["enabled"])
                self.assertGreater(restored.repeat_snapshot()["next_at"], 0)

                restored.set_repeat_moyu(False)
                self.assertFalse(restored.repeat_snapshot()["enabled"])
                self.assertEqual(restored.repeat_snapshot()["next_at"], 0)

    def test_launcher_starts_python_without_terminal(self):
        path = os.path.join(gui.ROOT, "scripts", "launcher.swift")
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("后台启动 python（不打开终端）", source)
        self.assertIn("FileHandle.nullDevice", source)
        self.assertNotIn("task.arguments = [startCommand]", source)

    def test_web_launcher_reuses_one_server_and_opens_browser(self):
        path = os.path.join(gui.ROOT, "start.command")
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn('"$ROOT/gui.py" --serve', source)
        self.assertIn("logs/gui.url", source)
        self.assertIn("open_existing", source)
        self.assertIn('ps -p "$pid" -o command=', source)
        self.assertIn("launchctl submit", source)
        self.assertNotIn("nohup ", source)
        self.assertIn('/usr/bin/open "$url"', source)


if __name__ == "__main__":
    unittest.main()

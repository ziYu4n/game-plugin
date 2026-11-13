import json
import os
import tempfile
import unittest

import coords


class CoordinateTests(unittest.TestCase):
    def test_outer_screen_round_trip(self):
        metrics = coords.build_metrics(
            {
                "outer": {"x": 100, "y": 50, "w": 400, "h": 800},
                "content": {"x": 100, "y": 78, "w": 400, "h": 772},
            },
            800,
            1600,
        )

        sx, sy = coords.outer_to_screen(0.25, 0.75, metrics)
        self.assertEqual((sx, sy), (200.0, 650.0))
        fx, fy = coords.screen_to_outer(sx, sy, metrics)
        self.assertAlmostEqual(fx, 0.25)
        self.assertAlmostEqual(fy, 0.75)
        self.assertEqual(metrics.shot_space, "outer")

    def test_resolve_screen_tracks_window_move(self):
        metrics = coords.build_metrics(
            {
                "outer": {"x": 130, "y": 80, "w": 400, "h": 800},
                "content": {"x": 130, "y": 108, "w": 400, "h": 772},
            },
            800,
            1600,
        )
        step = {
            "fx": 0.5,
            "fy": 0.5,
            "cg_x": 300,
            "cg_y": 450,
            "outer": {"x": 100, "y": 50, "w": 400, "h": 800},
        }

        self.assertEqual(coords.resolve_mode(step, metrics), "cg+delta")
        self.assertEqual(coords.resolve_screen(step, metrics), (330.0, 480.0))

    def test_resolve_screen_falls_back_to_relative_after_resize(self):
        metrics = coords.build_metrics(
            {
                "outer": {"x": 100, "y": 50, "w": 500, "h": 900},
                "content": {"x": 100, "y": 78, "w": 500, "h": 872},
            },
            1000,
            1800,
        )
        step = {
            "fx": 0.25,
            "fy": 0.75,
            "cg_x": 300,
            "cg_y": 450,
            "outer": {"x": 100, "y": 50, "w": 400, "h": 800},
        }

        self.assertEqual(coords.resolve_mode(step, metrics), "fxfy")
        self.assertEqual(coords.resolve_screen(step, metrics), (225.0, 725.0))

    def test_save_metrics_returns_and_persists_payload(self):
        metrics = coords.build_metrics(
            {
                "outer": {"x": 0, "y": 0, "w": 400, "h": 800},
                "content": {"x": 0, "y": 28, "w": 400, "h": 772},
            },
            800,
            1600,
        )
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "metrics.json")

            result = coords.save_metrics_config(path, metrics)

            with open(path, "r", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), result)
            self.assertEqual(result["shot_space"], "outer")


if __name__ == "__main__":
    unittest.main()

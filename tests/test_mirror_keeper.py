import os
import unittest
from unittest import mock

import mirror_keeper as mk


class TemplateConfigurationTests(unittest.TestCase):
    def test_moyu_transition_resynchronizes_recognized_prior_pages(self):
        self.assertEqual(mk.moyu_transition_status("hud", "hud"), "same")
        self.assertEqual(mk.moyu_transition_status("hud", "unknown"), "pending")
        self.assertEqual(mk.moyu_transition_status("hud", "tongyou"), "forward")
        self.assertEqual(mk.moyu_transition_status("zhige", "matching"), "forward")
        self.assertEqual(mk.moyu_transition_status("juezhanglin", "hud"), "resync")
        self.assertEqual(mk.moyu_transition_status("match_ready", "home"), "resync")

    def test_queue_checks_screen_permission_before_restarting_mirror(self):
        with mock.patch.object(mk, "ensure_screen_capture_access", return_value=False), \
             mock.patch.object(mk, "restart_mirror") as restart:
            ok = mk.run_queue([], {"kill_mirror": "always"})

        self.assertFalse(ok)
        restart.assert_not_called()

    def test_continue_templates_are_defined_and_present(self):
        expected = {
            "continue_game_port.png",
            "continue_game_land.png",
            "continue_game_land_alt.png",
        }

        paths = mk.continue_templates()

        self.assertEqual({os.path.basename(path) for path in paths}, expected)
        self.assertTrue(all(os.path.isfile(path) for path in paths))

    def test_gameplay_hud_is_recognized_without_game_title(self):
        items = [
            {"text": "需前往目标场"},
            {"text": "返回任务点"},
            {"text": "位移"},
            {"text": "轻击"},
            {"text": "闪避"},
        ]

        self.assertTrue(mk.looks_like_game(items))
        self.assertTrue(mk.looks_like_gameplay_hud(items))

    def test_single_generic_hud_word_is_not_enough(self):
        self.assertFalse(mk.looks_like_game([{"text": "到达"}]))
        self.assertFalse(mk.looks_like_gameplay_hud([{"text": "到达"}]))

    def test_online_account_dialog_is_recognized_as_game(self):
        items = [{"text": "账号已在线，是否继续登录？"}]

        self.assertTrue(mk.looks_like_game(items))

    def test_moyu_progress_uses_furthest_visible_stage(self):
        self.assertEqual(mk.moyu_progress([{"text": "位移"}, {"text": "轻击"}]), "hud")
        self.assertEqual(mk.moyu_progress([{"text": "天气"}, {"text": "日历"}]), "home")
        self.assertEqual(mk.moyu_progress([{"text": "33°"}, {"text": "g&GSS"}]), "unknown")
        self.assertEqual(mk.moyu_progress([{"text": "同游"}]), "tongyou")
        self.assertEqual(mk.moyu_progress([{"text": "止戈"}, {"text": "觉障林"}]), "juezhanglin")
        self.assertEqual(mk.moyu_progress([{"text": "开始匹配"}]), "match_ready")
        self.assertEqual(mk.moyu_progress([{"text": "退出匹配"}]), "matching")

    def test_moyu_progress_handles_launch_and_login_pages(self):
        self.assertEqual(mk.moyu_progress([{"text": "本游戏建议18岁以上"}]), "launching")
        self.assertEqual(mk.moyu_progress([{"text": "2.8.5版本更新公告"}]), "announcement")
        self.assertEqual(mk.moyu_progress([{"text": "继续游戏"}]), "continue_game")
        self.assertEqual(mk.moyu_progress([{"text": "账号已登录，是否继续登录"}]), "online_confirm")
        self.assertEqual(mk.moyu_progress([{"text": "进入江湖"}]), "enter_game")

    def test_home_labels_win_over_stale_landscape_geometry(self):
        items = [
            {"text": "番禺区"}, {"text": "33°"}, {"text": "天气"},
            {"text": "FaceTime通话"}, {"text": "周一"}, {"text": "12"}, {"text": "日历"},
        ]

        self.assertEqual(mk.classify_phone_screen(items, land=True, relaxed_home=True), "home")

    def test_empty_ocr_is_not_treated_as_home(self):
        self.assertEqual(mk.classify_phone_screen([], land=False, relaxed_home=True), "unknown")

    def test_relaxed_home_does_not_accept_long_standby_copy(self):
        items = [{"text": "ID:0422791884"}, {"text": "仗剑长啸万里同行"}]

        self.assertEqual(mk.classify_phone_screen(items, land=False, relaxed_home=True), "app")

    def test_login_config_resumes_current_page_until_playing(self):
        config = mk.load_config_file(os.path.join(mk.ROOT, "configs", "yanyun_login.json"))

        self.assertTrue(config["resume_from_current"])
        self.assertFalse(config["use_common"])
        self.assertFalse(config["fresh_launch"])
        self.assertFalse(config["restart_mirror_before_run"])
        self.assertFalse(config["kill_game_background_before_open"])
        self.assertFalse(config["require_landscape"])
        self.assertEqual(config["wake_clicks"], 3)
        self.assertEqual(config["wake_wait"], 5.0)
        self.assertEqual(len(config["steps"]), 1)
        flow = config["steps"][0]
        self.assertEqual(flow["type"], "yanyun_flow")
        self.assertEqual(flow["goal"], "playing")
        self.assertEqual(flow["stage_confirmations"], 2)
        self.assertEqual(flow["max_recoveries"], 3)
        self.assertTrue(flow["required"])

    def test_moyu_config_requires_stage_and_matching_confirmation(self):
        config = mk.load_config_file(os.path.join(
            mk.ROOT, "configs", "yanyun", "yanyun_moyu.json",
        ))

        flow = next(step for step in config["steps"] if step["type"] == "moyu_flow")
        self.assertTrue(config["resume_from_current"])
        self.assertFalse(config["use_common"])
        self.assertEqual(flow["stage_confirmations"], 2)
        self.assertEqual(flow["matching_confirmations"], 2)
        self.assertGreaterEqual(flow["transition_timeout"], 5)
        self.assertEqual(flow["max_recoveries"], 3)

    def test_hid_idle_time_parser(self):
        text = '| |   "HIDIdleTime" = 1250000000'
        self.assertEqual(mk._hid_idle_seconds_from_text(text), 1.25)
        self.assertIsNone(mk._hid_idle_seconds_from_text("missing"))


if __name__ == "__main__":
    unittest.main()

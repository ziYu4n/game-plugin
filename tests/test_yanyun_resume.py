"""Device-free regression coverage for resuming the Yanyun state machine."""

import contextlib
import unittest
from unittest import mock

import mirror_keeper as mk


def words(*texts):
    return [
        {"text": text, "x": 0.42, "y": 0.66, "w": 0.16, "h": 0.04}
        for text in texts
    ]


class YanyunRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.orientation = mock.patch.object(mk, "is_landscape", return_value=False)
        self.orientation.start()
        self.addCleanup(self.orientation.stop)

    def test_recognizes_mirror_and_phone_entry_states(self):
        cases = (
            ("connecting", words("正在连接 iPhone")),
            ("connection_failed", words("连接失败，请重试")),
            ("lock", words("解锁 iPhone 以继续")),
            ("search", words("搜索", "取消", "Siri建议")),
            ("wrong_app", words("微信", "聊天")),
            ("splash", words("ID:0422791884", "仗剑长啸万里同行")),
            ("start_game", words("开始游戏")),
        )
        for expected, items in cases:
            with self.subTest(state=expected):
                self.assertEqual(mk.moyu_progress(items), expected)

    def test_online_confirmation_overrides_underlying_menu_and_matching(self):
        for background in ("同游", "觉障林", "开始匹配", "退出匹配"):
            with self.subTest(background=background):
                self.assertEqual(
                    mk.moyu_progress(words(background, "账号已在线，是否继续登录？")),
                    "online_confirm",
                )

    def test_announcement_overrides_underlying_menu_and_matching(self):
        for background in ("同游", "止戈", "开始匹配", "正在匹配"):
            with self.subTest(background=background):
                self.assertEqual(
                    mk.moyu_progress(words(background, "2.8.5版本更新公告")),
                    "announcement",
                )

    def test_split_continue_button_is_recognized_and_tapped_from_its_box(self):
        items = [
            {"text": "继续", "x": 0.42, "y": 0.66, "w": 0.08, "h": 0.04},
            {"text": "游戏", "x": 0.51, "y": 0.66, "w": 0.08, "h": 0.04},
        ]
        self.assertEqual(mk.moyu_progress(items), "continue_game")
        with mock.patch.object(mk, "log"), \
             mock.patch.object(mk, "in_window_safe", return_value=True), \
             mock.patch.object(mk, "find_continue_icon", return_value=None) as icon:
            fx, fy, source = mk.find_continue_target(items)
        self.assertAlmostEqual(fx, 0.505)
        self.assertAlmostEqual(fy, 0.68)
        self.assertEqual(source, "ocr")
        icon.assert_not_called()

    def test_backwards_observations_request_resync(self):
        for before, after in (
            ("juezhanglin", "hud"), ("match_ready", "home"),
            ("hud", "announcement"), ("matching", "online_confirm"),
        ):
            with self.subTest(before=before, after=after):
                self.assertEqual(mk.moyu_transition_status(before, after), "resync")
        self.assertEqual(mk.moyu_transition_status("hud", "unknown"), "pending")
        self.assertEqual(mk.moyu_transition_status("hud", "hud"), "same")
        self.assertEqual(mk.moyu_transition_status("hud", "tongyou"), "forward")

    def test_low_signal_text_does_not_guess_home_lock_or_connection_failure(self):
        for items in ([], words("设置"), words("输入密码"), words("重试"), words("前往", "目标")):
            with self.subTest(items=items):
                self.assertEqual(mk.moyu_progress(items), "unknown")


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        self.now += 0.01
        return self.now

    monotonic = time

    def sleep(self, seconds):
        self.now += max(0.01, seconds)

    def sleep_wait(self, seconds):
        self.sleep(seconds)
        return True


class YanyunFlowResumeTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.clock = FakeClock()
        self.stack.enter_context(mock.patch.object(mk, "time", self.clock))
        self.stack.enter_context(mock.patch.object(mk, "app_phase", "idle"))
        self.calls = {}
        returns = {
            "log": None, "save_shot": None, "set_phase": None,
            "record_error": None, "ensure_mirror_ready": True,
            "wait_mirror_ready": True, "unlock_if_needed": True,
            "wait_if_paused": True, "should_stop": False,
            "screen_tcc_denied": False, "capture_denied": False,
            "has_window": True, "capture_window": True,
            "is_landscape": False, "is_portrait_window": True,
            "point_in_window": (300, 400), "resolve_moyu_tap": None,
            "back_button_pos": (0.9, 0.1), "find_continue_target": (0.5, 0.7, "ocr"),
            "ocr_hit_to_outer": (0.5, 0.7), "continue_fallback_point": (0.5, 0.7),
            "silent_click_screen": True, "game_click_screen": True,
            "tap_text": True,
            "open_search": True, "type_search_and_open": True,
            "_wake_moyu_screen": True, "go_home": True,
            "try_unlock": True, "restart_mirror": True,
            "open_mirror": True, "kill_game_background": True,
            "read_account": True, "username_near": (None, None),
            "send_hotkey": True, "set_current_account": None,
            "find_back_button": None, "tap_point": True,
        }
        for name, result in returns.items():
            self.calls[name] = self.stack.enter_context(
                mock.patch.object(mk, name, return_value=result)
            )
        self.stack.enter_context(
            mock.patch.object(mk, "sleep_wait", side_effect=self.clock.sleep_wait)
        )
        self.stack.enter_context(mock.patch.object(mk, "ALLOW_SCREEN_CAPTURE", True))

    def run_flow(self, states, **options):
        frames = iter(states)
        last = [states[-1]]
        samples = {
            "connecting": words("正在连接 iPhone"),
            "connection_failed": words("连接失败，请重试"),
            "lock": words("解锁 iPhone 以继续"),
            "home": words("天气", "日历"),
            "search": words("搜索", "取消", "Siri建议"),
            "wrong_app": words("微信", "聊天"),
            "launching": words("正在加载"),
            "splash": words("光敏性癫痫"),
            "start_game": words("开始游戏"),
            "announcement": words("2.8.5版本更新公告"),
            "continue_game": words("继续游戏"),
            "online_confirm": words("账号已在线，是否继续登录？"),
            "enter_game": words("进入江湖"),
            "hud": words("位移", "轻击"),
            "tongyou": words("同游"),
            "zhige": words("止戈"),
            "juezhanglin": words("觉障林"),
            "match_ready": words("开始匹配"),
            "matching": words("退出匹配"),
            "unknown": [],
        }

        def read_frame(*args, **kwargs):
            last[0] = next(frames, last[0])
            self.clock.sleep(0.1)
            return samples[last[0]]

        with mock.patch.object(mk, "ocr_items", side_effect=read_frame):
            return mk.run_moyu_flow({
                "timeout": 20, "interval": 0.2,
                "stage_confirmations": 2, "matching_confirmations": 2,
                "transition_timeout": 3, **options,
            })

    def assert_no_phone_actions(self):
        for name in (
            "silent_click_screen", "game_click_screen", "tap_text",
            "open_search", "type_search_and_open", "_wake_moyu_screen", "go_home",
            "try_unlock", "restart_mirror", "kill_game_background",
            "send_hotkey", "tap_point",
        ):
            with self.subTest(action=name):
                self.calls[name].assert_not_called()

    def test_playing_goal_finishes_from_each_confirmed_in_game_page(self):
        for state in ("hud", "tongyou", "zhige", "juezhanglin", "match_ready", "matching"):
            with self.subTest(state=state):
                for call in self.calls.values():
                    call.reset_mock()
                self.assertTrue(self.run_flow([state, state], goal="playing"))
                self.assert_no_phone_actions()
                self.calls["ensure_mirror_ready"].assert_called_once_with(wait_connected=False)

    def test_playing_goal_requires_confirmation_before_finishing(self):
        self.assertTrue(self.run_flow(["hud", "unknown", "hud", "hud"], goal="playing"))
        self.assert_no_phone_actions()

    def test_default_goal_kills_only_after_matching_is_confirmed(self):
        self.assertTrue(self.run_flow(["matching", "unknown", "matching", "matching"]))
        self.calls["kill_game_background"].assert_called_once()
        self.calls["tap_text"].assert_not_called()
        self.calls["game_click_screen"].assert_not_called()

    def test_progress_regression_after_click_resumes_from_visible_page(self):
        self.assertTrue(self.run_flow([
            "match_ready", "match_ready", "hud", "hud", "matching", "matching",
        ]))
        self.calls["silent_click_screen"].assert_called_once()
        self.assertEqual(self.calls["silent_click_screen"].call_args.kwargs["tag"], "(start_match)")
        self.calls["game_click_screen"].assert_called_once()
        self.calls["kill_game_background"].assert_called_once()

    def test_stale_home_phase_does_not_override_current_game_page(self):
        with mock.patch.object(mk, "app_phase", "home"):
            self.assertTrue(self.run_flow(["hud", "hud"], goal="playing"))
        self.assert_no_phone_actions()

    def test_in_progress_connection_can_reach_game_without_initial_unlock(self):
        for state in ("connecting", "launching"):
            with self.subTest(state=state):
                for call in self.calls.values():
                    call.reset_mock()
                self.assertTrue(self.run_flow([state, state, "hud", "hud"], goal="playing"))
                self.calls["wait_mirror_ready"].assert_not_called()
                self.calls["unlock_if_needed"].assert_not_called()
                self.assert_no_phone_actions()

    def test_matching_goal_resumes_each_menu_without_reopening_earlier_pages(self):
        for state, tag in (
            ("tongyou", "(tongyou)"), ("zhige", "(zhige)"),
            ("juezhanglin", "(juezhanglin)"), ("match_ready", "(start_match)"),
        ):
            with self.subTest(state=state):
                for call in self.calls.values():
                    call.reset_mock()
                self.assertTrue(self.run_flow([state, state, "matching", "matching"]))
                self.calls["silent_click_screen"].assert_called_once()
                self.assertEqual(self.calls["silent_click_screen"].call_args.kwargs["tag"], tag)
                self.calls["game_click_screen"].assert_not_called()
                self.calls["open_search"].assert_not_called()
                self.calls["kill_game_background"].assert_called_once()

    def test_each_known_entry_page_executes_its_own_next_action(self):
        cases = (
            ("home", "open_search"), ("search", "send_hotkey"),
            ("lock", "unlock_if_needed"), ("splash", "_wake_moyu_screen"),
            ("announcement", "silent_click_screen"),
            ("continue_game", "silent_click_screen"),
            ("online_confirm", "silent_click_screen"),
            ("enter_game", "silent_click_screen"), ("start_game", "silent_click_screen"),
        )
        for state, action in cases:
            with self.subTest(state=state):
                for call in self.calls.values():
                    call.reset_mock()
                self.assertTrue(self.run_flow([state, state, "hud", "hud"], goal="playing"))
                self.calls[action].assert_called_once()
                self.calls["kill_game_background"].assert_not_called()
                if state != "home":
                    self.calls["open_search"].assert_not_called()

    def test_connection_failure_reconnects_then_resumes_current_game_page(self):
        self.assertTrue(self.run_flow(
            ["connection_failed", "connection_failed", "hud", "hud"], goal="playing",
        ))
        self.calls["restart_mirror"].assert_called_once()
        self.calls["go_home"].assert_not_called()
        self.calls["kill_game_background"].assert_not_called()

    def test_wrong_app_recovers_through_home_before_resuming(self):
        self.assertTrue(self.run_flow(["wrong_app", "wrong_app", "hud", "hud"], goal="playing"))
        self.calls["go_home"].assert_called_once()
        self.calls["restart_mirror"].assert_not_called()
        self.calls["kill_game_background"].assert_not_called()

    def test_blank_transient_after_click_waits_for_recognizable_page(self):
        self.assertTrue(self.run_flow([
            "continue_game", "continue_game", "unknown", "unknown", "hud", "hud",
        ], goal="playing"))
        self.calls["silent_click_screen"].assert_called_once()
        self.calls["go_home"].assert_not_called()
        self.calls["restart_mirror"].assert_not_called()
        self.calls["_wake_moyu_screen"].assert_not_called()

    def test_unknown_page_stops_when_recovery_budget_is_zero(self):
        self.assertFalse(self.run_flow(["unknown"], max_recoveries=0))
        self.assert_no_phone_actions()

    def test_wrong_app_recovery_is_bounded(self):
        self.assertFalse(self.run_flow(["wrong_app"], max_recoveries=1))
        self.calls["go_home"].assert_called_once()
        self.calls["restart_mirror"].assert_not_called()
        self.calls["kill_game_background"].assert_not_called()

    def test_unchanged_button_does_not_repeat_without_limit(self):
        self.assertFalse(self.run_flow(["match_ready"], max_same_actions=1, max_recoveries=0))
        self.calls["silent_click_screen"].assert_called_once()
        self.calls["kill_game_background"].assert_not_called()
        self.calls["go_home"].assert_not_called()

    def test_capture_permission_loss_stops_before_any_recovery_action(self):
        self.calls["capture_denied"].return_value = True
        self.assertFalse(self.run_flow(["wrong_app"]))
        self.assert_no_phone_actions()

    def test_stop_request_does_not_finish_or_click_even_on_matching_page(self):
        self.calls["should_stop"].return_value = True
        self.assertFalse(self.run_flow(["matching", "matching"]))
        self.assert_no_phone_actions()


class YanyunTaskEntryTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.calls = {}
        returns = {
            "log": None, "log_window_geom": None, "record_error": None,
            "start_run_session": None, "remove_pid": None,
            "ensure_screen_capture_access": True, "should_stop": False,
            "restart_mirror": True, "prepare_task_home": True,
            "open_game_once": True, "run_steps": True, "watch_loop": None,
        }
        for name, result in returns.items():
            self.calls[name] = self.stack.enter_context(
                mock.patch.object(mk, name, return_value=result)
            )
        self.stack.enter_context(mock.patch.object(mk, "current_account", ""))

    @staticmethod
    def config(resume=True):
        return {
            "id": "yanyun_resume_test", "name": "Resume regression",
            "resume_from_current": resume, "restart_mirror_before_run": True,
            "use_common": True, "search": "燕云十六声",
            "steps": [{"type": "moyu_flow", "goal": "playing"}],
        }

    def test_task_resume_preserves_current_page_and_runs_flow_directly(self):
        config = self.config()
        self.assertTrue(mk.run_task(config, manage_session=False))
        self.calls["prepare_task_home"].assert_not_called()
        self.calls["restart_mirror"].assert_not_called()
        self.calls["open_game_once"].assert_not_called()
        self.calls["run_steps"].assert_called_once_with(config["steps"], config)

    def test_queue_resume_does_not_force_restart_or_home_preparation(self):
        config = self.config()
        self.assertTrue(mk.run_queue([config]))
        self.calls["prepare_task_home"].assert_not_called()
        self.calls["restart_mirror"].assert_not_called()
        self.calls["open_game_once"].assert_not_called()
        self.calls["run_steps"].assert_called_once()

    def test_explicit_restart_option_is_respected_for_task_resume(self):
        self.assertTrue(mk.run_task(self.config(), {"kill_mirror": "always"}, manage_session=False))
        self.calls["restart_mirror"].assert_called_once()
        self.calls["prepare_task_home"].assert_not_called()

    def test_explicit_restart_option_is_respected_for_queue_resume(self):
        self.assertTrue(mk.run_queue([self.config()], {"kill_mirror": "always"}))
        self.calls["restart_mirror"].assert_called_once()
        self.calls["prepare_task_home"].assert_not_called()

    def test_non_resume_task_keeps_home_preparation(self):
        self.assertTrue(mk.run_task(self.config(resume=False), manage_session=False))
        self.calls["restart_mirror"].assert_called_once()
        self.calls["prepare_task_home"].assert_called_once()
        self.calls["open_game_once"].assert_called_once()

    def test_queue_permission_failure_has_no_phone_side_effects(self):
        self.calls["ensure_screen_capture_access"].return_value = False
        self.assertFalse(mk.run_queue([self.config()], {"kill_mirror": "always"}))
        self.calls["restart_mirror"].assert_not_called()
        self.calls["prepare_task_home"].assert_not_called()
        self.calls["run_steps"].assert_not_called()
        self.calls["start_run_session"].assert_not_called()


if __name__ == "__main__":
    unittest.main()

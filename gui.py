#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用本地网页窗口做界面，避开 macOS 上 Tk 文字/列表空白的问题。"""

import atexit
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mirror_keeper as mk

ROOT = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(ROOT, "logs", "gui.pid")
UI_FILE = os.path.join(ROOT, "ui", "index.html")
APPWIN_SRC = os.path.join(ROOT, "scripts", "appwin.swift")
APPWIN_BIN = os.path.join(ROOT, "scripts", "appwin")
OVERLAY_SRC = os.path.join(ROOT, "scripts", "overlay.swift")
OVERLAY_BIN = os.path.join(ROOT, "scripts", "overlay")
OVERLAY_CTRL = os.path.join(ROOT, "data", "overlay.lock")
WATCH_SRC = os.path.join(ROOT, "scripts", "clickwatch.swift")
WATCH_BIN = os.path.join(ROOT, "scripts", "clickwatch")
WATCH_CTRL = os.path.join(ROOT, "data", "clickwatch.lock")
QUEUE_FILE = os.path.join(ROOT, "data", "queue.json")

STATE_TEXT = {
    "idle": "未开始",
    "running": "运行中",
    "paused": "已暂停",
    "stop": "正在停止",
}


class App:
    def __init__(self):
        self.lock = threading.Lock()
        self.queue_items = []
        self.logs = []
        self.worker = None
        self.overlay_proc = None
        self.overlay_locked = False
        self.watch_proc = None
        self.last_calibrate = None
        self.recording = False
        self.recording_count = 0
        self.recording_name = ""
        self.calib_target = ""  # 手校当前选中 key
        self.calib_retap = True  # 校准后是否自动复点（白名单内）
        self._calib_busy_until = 0.0  # 防抖：避免 HID 复点再打到遮罩连环触发
        self.api_base = ""
        mk.log_hook = self.enqueue_log
        self.load_queue()

    def enqueue_log(self, line):
        with self.lock:
            self.logs.append(line)
            if len(self.logs) > 300:
                self.logs = self.logs[-300:]

    def save_queue(self):
        os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
        with self.lock:
            ids = [item.get("id") for item in self.queue_items if item.get("id")]
        try:
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump({"ids": ids}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.enqueue_log("保存执行列表失败：%s" % e)

    def load_queue(self):
        if not os.path.isfile(QUEUE_FILE):
            return
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        ids = data.get("ids") if isinstance(data, dict) else data
        if not isinstance(ids, list):
            return
        items = []
        for sid in ids:
            cfg = self.find_script(sid)
            if not cfg:
                continue
            item = dict(cfg)
            for g in mk.list_groups():
                if g.get("id") == item.get("group"):
                    item["name"] = "%s · %s" % (g.get("name"), item.get("name") or item.get("id"))
                    break
            items.append(item)
        self.queue_items = items
        if items:
            self.enqueue_log("已恢复执行列表 %s 项" % len(items))

    def make_queue_item(self, sid):
        cfg = self.find_script(sid)
        if not cfg:
            return None
        item = dict(cfg)
        for g in mk.list_groups():
            if g.get("id") == item.get("group"):
                item["name"] = "%s · %s" % (g.get("name"), item.get("name") or item.get("id"))
                break
        return item

    def enqueue_log(self, line):
        with self.lock:
            self.logs.append(line)
            if len(self.logs) > 300:
                self.logs = self.logs[-300:]

    def ui_state(self):
        if self.worker and self.worker.is_alive():
            if mk.run_mode == "paused":
                return "paused"
            if mk.run_mode == "stop":
                return "stop"
            return "running"
        return "idle"

    def scripts(self):
        return mk.list_groups()

    def find_script(self, sid):
        for cfg in mk.list_configs():
            if cfg.get("id") == sid:
                return cfg
        return None

    def snapshot(self):
        if self.worker and not self.worker.is_alive():
            self.worker = None
        with self.lock:
            queue_items = [
                {"id": item.get("id"), "name": item.get("name") or item.get("id")}
                for item in self.queue_items
            ]
            logs = list(self.logs)
        errors = mk.load_errors().get("items") or []
        return {
            "state": self.ui_state(),
            "error_count": len(errors),
            "groups": self.scripts(),
            "queue": queue_items,
            "logs": logs,
            "account": mk.current_account or "",
            "account_ts": int(os.path.getmtime(mk.ACCOUNT_IMG)) if os.path.isfile(mk.ACCOUNT_IMG) else 0,
            "shot_ts": int(os.path.getmtime(mk.LAST_SHOT)) if os.path.isfile(mk.LAST_SHOT) else 0,
            "shot_w": (mk._last_metrics.shot_w if mk._last_metrics else None),
            "shot_h": (mk._last_metrics.shot_h if mk._last_metrics else None),
            "shot_px": (mk._last_click or {}).get("shot_px") if isinstance(mk._last_click, dict) else None,
            "shot_py": (mk._last_click or {}).get("shot_py") if isinstance(mk._last_click, dict) else None,
            "shot_fx": (mk._last_click or {}).get("fx") if isinstance(mk._last_click, dict) else None,
            "shot_fy": (mk._last_click or {}).get("fy") if isinstance(mk._last_click, dict) else None,
            "shot_run": getattr(mk, "_shot_run", "") or "",
            "shot_last": getattr(mk, "_last_saved_shot", None),
            "shot_thumbs": mk.list_shot_thumbs(16),
            "overlay_locked": self.overlay_locked,
            "last_calibrate": self.last_calibrate,
            "recording": self.recording,
            "recording_count": self.recording_count,
            "recording_name": self.recording_name,
            "phase": getattr(mk, "app_phase", "") or "",
            "perm_hint": getattr(mk, "_perm_hint", "") or "",
            "calib_target": self.calib_target or "",
            "calib_retap": bool(self.calib_retap),
            "moyu_points": mk.moyu_points_summary(),
        }

    def write_overlay_ctrl(self, locked):
        os.makedirs(os.path.dirname(OVERLAY_CTRL), exist_ok=True)
        with open(OVERLAY_CTRL, "w") as f:
            f.write("1" if locked else "0")

    def write_watch_ctrl(self, on):
        os.makedirs(os.path.dirname(WATCH_CTRL), exist_ok=True)
        with open(WATCH_CTRL, "w") as f:
            f.write("1" if on else "0")

    def ensure_overlay(self):
        if self.overlay_proc and self.overlay_proc.poll() is None:
            return True
        if not ensure_overlay_bin():
            self.enqueue_log("[校准] 遮罩工具编译失败")
            return False
        if not self.api_base:
            return False
        callback = self.api_base.rstrip("/") + "/api/calibrate/click"
        try:
            self.overlay_proc = subprocess.Popen(
                [OVERLAY_BIN, OVERLAY_CTRL, callback],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            self.enqueue_log("[校准] 启动遮罩失败：%s" % e)
            return False

    def ensure_clickwatch(self):
        if self.watch_proc and self.watch_proc.poll() is None:
            return True
        if not ensure_clickwatch_bin():
            self.enqueue_log("[录制] 点击监听编译失败")
            return False
        if not self.api_base:
            return False
        callback = self.api_base.rstrip("/") + "/api/calibrate/click"
        try:
            self.watch_proc = subprocess.Popen(
                [WATCH_BIN, WATCH_CTRL, callback],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.25)
            return True
        except Exception as e:
            self.enqueue_log("[录制] 启动点击监听失败：%s" % e)
            return False

    def stop_clickwatch(self):
        self.write_watch_ctrl(False)
        proc = self.watch_proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        self.watch_proc = None

    def set_overlay_locked(self, locked):
        if self.recording and locked:
            return False, "录制中请不要开遮罩，直接点镜像窗口"
        self.overlay_locked = bool(locked)
        self.write_overlay_ctrl(self.overlay_locked)
        if self.overlay_locked:
            if not self.ensure_overlay():
                return False, "遮罩启动失败，请确认已打开 iPhone 镜像"
            self.enqueue_log("[校准] 已锁定：白半透明遮罩盖在镜像窗口上，点一下就会记坐标")
        else:
            self.enqueue_log("[校准] 已解锁：遮罩已隐藏")
        return True, ""

    def record_calibrate(self, data):
        # HID 复点若打在遮罩上会连环触发；先防抖
        now = time.time()
        if now < float(getattr(self, "_calib_busy_until", 0) or 0):
            return True, ""
        cg = None
        if data.get("cg_x") is not None and data.get("cg_y") is not None:
            try:
                cg = (float(data.get("cg_x")), float(data.get("cg_y")))
            except Exception:
                cg = None
        outer = data.get("outer")
        if not isinstance(outer, dict) and data.get("outer_x") is not None:
            try:
                outer = {
                    "x": float(data.get("outer_x")),
                    "y": float(data.get("outer_y")),
                    "w": float(data.get("outer_w") or data.get("w") or 0),
                    "h": float(data.get("outer_h") or data.get("h") or 0),
                }
            except Exception:
                outer = None
        mk.capture_window(force=False)
        m = mk.current_metrics() or mk.refresh_metrics()
        fx = fy = None
        if data.get("fx") is not None and data.get("fy") is not None:
            try:
                fx = float(data.get("fx"))
                fy = float(data.get("fy"))
            except Exception:
                fx = fy = None
        spx = spy = None
        if cg and m:
            fx, fy = mk.coordlib.screen_to_outer(cg[0], cg[1], m)
            spx, spy = mk.coordlib.screen_to_shot(cg[0], cg[1], m)
        elif fx is not None and fy is not None and m:
            cg = mk.coordlib.outer_to_screen(fx, fy, m)
            spx, spy = mk.coordlib.screen_to_shot(cg[0], cg[1], m)
        elif fx is None or fy is None:
            return False, "坐标无效（需要 cg 或 fx/fy）"
        else:
            info = mk.window_info()
            if cg is None and info:
                ox, oy, ow, oh = info["outer"]
                cg = (ox + ow * fx, oy + oh * fy)
        screen_click = cg
        self.last_calibrate = {
            "fx": round(fx, 4),
            "fy": round(fy, 4),
            "space": "outer",
            "cg_x": round(screen_click[0], 1) if screen_click else None,
            "cg_y": round(screen_click[1], 1) if screen_click else None,
            "shot_px": round(spx, 1) if spx is not None else None,
            "shot_py": round(spy, 1) if spy is not None else None,
            "w": (outer or {}).get("w") if isinstance(outer, dict) else data.get("w"),
            "h": (outer or {}).get("h") if isinstance(outer, dict) else data.get("h"),
            "outer": outer or (m.outer.as_dict() if m else None),
            "cg_click": [round(screen_click[0], 1), round(screen_click[1], 1)] if screen_click else None,
        }
        if self.recording:
            step, err = mk.append_hand_click(fx=fx, fy=fy, cg=cg, outer=outer, verify=False)
            if not step:
                return False, err or "录制失败"
            self.recording_count = int(step.get("i") or self.recording_count + 1)
            self.enqueue_log(
                "[录制] 第 %s 步 outer=%.4f,%.4f screen=%.1f,%.1f shot=%.0f,%.0f"
                % (
                    self.recording_count, fx, fy,
                    screen_click[0] if screen_click else 0,
                    screen_click[1] if screen_click else 0,
                    step.get("shot_px") or 0, step.get("shot_py") or 0,
                )
            )
            return True, ""
        line = "[校准] outer=%.4f,%.4f" % (fx, fy)
        if screen_click:
            line += " screen=%.1f,%.1f" % (screen_click[0], screen_click[1])
        if spx is not None:
            line += " shot=%.0f,%.0f" % (spx, spy)
        self.enqueue_log(line)
        mk.log("INFO", line.replace("[校准] ", "校准 "))
        # 刷么鱼：选了校准目标则写入手校点位，并 HID 复点一次
        target = (self.calib_target or "").strip()
        if target:
            # 立刻占用防抖窗口，挡住后续连环回调
            self._calib_busy_until = time.time() + 1.8
            try:
                outer_dict = None
                if isinstance(outer, dict):
                    outer_dict = outer
                elif m and getattr(m, "outer", None):
                    outer_dict = m.outer.as_dict()
                mk.save_moyu_point(target, fx, fy, cg=cg, outer=outer_dict)
                label = mk.moyu_point_label(target)
                self.enqueue_log("[手校] 已保存「%s」点位 %.4f, %.4f（含锚点）" % (label, fx, fy))
            except Exception as e:
                self.enqueue_log("[手校] 保存失败：%s" % e)
                return True, ""

            do_retap = bool(self.calib_retap) and (target in mk.CALIB_RETAP_SAFE)
            if bool(self.calib_retap) and target not in mk.CALIB_RETAP_SAFE:
                self.enqueue_log("[手校] 「%s」不在复点白名单，只存坐标不复点（防误触）" % label)
                self.write_overlay_ctrl(False)
                self.overlay_locked = False
                return True, ""
            if not do_retap:
                self.write_overlay_ctrl(False)
                self.overlay_locked = False
                self.enqueue_log("[手校] 已保存并解锁（未勾选校准后复点）")
                return True, ""

            def _one_retap():
                # 必须先藏遮罩，否则 HID 再打到遮罩 → 连环复点、鼠标像被锁
                self.write_overlay_ctrl(False)
                self.overlay_locked = False
                time.sleep(0.18)
                try:
                    resolved = mk.resolve_moyu_tap(target)
                    if resolved:
                        fx2, fy2, step_hit = resolved
                        mk.tap_point(fx2, fy2, step=step_hit, source="calibrate")
                    else:
                        mk.tap_point(fx, fy, cg=cg, source="calibrate")
                finally:
                    try:
                        mk.restore_mouse()
                    except Exception:
                        pass
                    self.enqueue_log("[手校] 已复点 1 次并解锁；换目标后再点「锁定游戏」")

            threading.Thread(target=_one_retap, daemon=True).start()
            return True, ""
        # 未选手校目标
        self.enqueue_log("[手校] 请先在列表选中一行再点")
        return True, ""

    def start_recording(self):
        if self.ui_state() != "idle":
            return False, "正在运行，不能录制"
        if self.recording:
            return False, "已经在录制"
        rec, err = mk.start_hand_recording()
        if not rec:
            return False, err or "无法开始录制"
        # 关掉遮罩，改用无遮罩点击监听
        self.write_overlay_ctrl(False)
        self.overlay_locked = False
        self.recording = True
        self.recording_count = 0
        self.recording_name = rec.get("name") or ""
        self.write_watch_ctrl(True)
        if not self.ensure_clickwatch():
            mk.cancel_hand_recording()
            self.recording = False
            self.write_watch_ctrl(False)
            return False, "点击监听启动失败（需辅助功能权限）"
        self.enqueue_log("—— 开始手点录制：%s ——" % self.recording_name)
        self.enqueue_log("[录制] 无遮罩：直接点 iPhone 镜像窗口，页面会正常变化，每点一步自动记坐标+截图")
        self.enqueue_log("[录制] 若点了没反应到日志，请给「脚本合集/终端/Python」开辅助功能")
        return True, ""

    def stop_recording(self):
        if not self.recording:
            return False, "当前没有在录制", None
        self.stop_clickwatch()
        draft, err = mk.finish_hand_recording()
        self.recording = False
        self.recording_count = 0
        self.recording_name = ""
        if not draft:
            return False, err or "结束录制失败", None
        n = int(draft.get("steps") or 0)
        self.enqueue_log("—— 录制结束：%s，共 %s 步 ——请在弹窗里选燕云/星穹铁道并保存（点「稍后」不会删）" % (draft.get("name"), n))
        return True, "", {
            "id": draft.get("id"),
            "name": draft.get("name") or "",
            "steps": n,
        }

    def save_recording(self, data):
        rid = (data or {}).get("id") or ""
        name = (data or {}).get("name")
        group = (data or {}).get("group") or "yanyun"
        result, err = mk.save_hand_recording(rid, name=name, group=group)
        if not result:
            return False, err or "保存失败", None
        rel = result.get("rel") or ""
        gname = result.get("group_name") or group
        cfg = result.get("cfg") or {}
        self.enqueue_log("—— 已保存：%s · %s → %s ——" % (gname, cfg.get("name"), rel))
        self.enqueue_log("[录制] 请到左侧「%s」里找到脚本，加入队列后点开始回放（不截图、不锁遮罩）" % gname)
        return True, "", {"path": rel, "id": cfg.get("id"), "group": group}

    def discard_recording(self, data):
        rid = (data or {}).get("id") or ""
        ok, err = mk.discard_hand_recording(rid)
        if ok:
            self.enqueue_log("[录制] 已丢弃未保存的录制：%s" % rid)
        return ok, err or ""

    def cancel_recording(self):
        if not self.recording:
            return False, "当前没有在录制"
        self.stop_clickwatch()
        mk.cancel_hand_recording()
        self.recording = False
        self.recording_count = 0
        self.recording_name = ""
        self.enqueue_log("[录制] 已取消")
        return True, ""

    def add_queue(self, sid):
        if self.ui_state() != "idle":
            return False, "正在运行"
        item = self.make_queue_item(sid)
        if not item:
            return False, "找不到脚本"
        with self.lock:
            self.queue_items.append(item)
        self.save_queue()
        self.enqueue_log("已加入队列：%s" % (item.get("name") or item.get("id")))
        return True, ""

    def remove_queue(self, index):
        if self.ui_state() != "idle":
            return False, "正在运行"
        with self.lock:
            if index < 0 or index >= len(self.queue_items):
                return False, "没有这项"
            item = self.queue_items.pop(index)
        self.save_queue()
        self.enqueue_log("已取消：%s" % (item.get("name") or item.get("id")))
        return True, ""

    def move_queue(self, index, direction):
        if self.ui_state() != "idle":
            return False, "正在运行"
        with self.lock:
            dest = index + int(direction)
            if index < 0 or index >= len(self.queue_items):
                return False, "没有这项"
            if dest < 0 or dest >= len(self.queue_items):
                return False, "到头了"
            self.queue_items[index], self.queue_items[dest] = self.queue_items[dest], self.queue_items[index]
        self.save_queue()
        return True, ""

    def clear_queue(self):
        if self.ui_state() != "idle":
            return False, "正在运行"
        with self.lock:
            self.queue_items = []
        self.save_queue()
        self.enqueue_log("已清空执行列表")
        return True, ""

    def start(self, options):
        if self.ui_state() != "idle":
            return False, "正在运行"
        if self.recording:
            return False, "请先结束或取消录制"
        with self.lock:
            if not self.queue_items:
                return False, "请先从左侧加入脚本"
            jobs = []
            for item in self.queue_items:
                # 开始前按 id 重新读配置，避免内存里旧步骤（如强制校验）卡住
                fresh = self.make_queue_item(item.get("id")) if item.get("id") else None
                jobs.append(dict(fresh or item))
            self.queue_items = [dict(j) for j in jobs]
        mk.run_mode = "running"
        names = " → ".join(item.get("name") or item.get("id") for item in jobs)
        self.enqueue_log("—— 开始队列：%s ——" % names)
        # 纯手点回放：不要锁遮罩（遮罩会挡视线，也容易误以为没点上）
        only_hand = True
        for job in jobs:
            for step in job.get("steps") or []:
                if step.get("type") != "replay_recording":
                    only_hand = False
                    break
            if not only_hand:
                break
        if only_hand:
            self.set_overlay_locked(False)
            self.enqueue_log("[回放] 手点脚本：已关遮罩；会把镜像置前再点（焦点不切回）")
        else:
            # 自动点击时遮罩会挡住游戏；默认不锁，需要校准再手动「锁定游戏」
            self.set_overlay_locked(False)
            self.enqueue_log("[提示] 已关遮罩，避免自动点击点到白色层；遍历时会出现红色圆点从左到右/从上到下移动")
        self.worker = threading.Thread(target=self.run_keeper, args=(jobs, options), daemon=True)
        self.worker.start()
        return True, ""

    def run_keeper(self, jobs, options):
        try:
            mk.run_queue(jobs, options)
        except Exception as e:
            mk.log("ERROR", "任务异常退出: %s" % e)
        finally:
            mk.run_mode = "idle"

    def pause(self):
        if not (self.worker and self.worker.is_alive()):
            return False, "没有在跑"
        if mk.run_mode == "paused":
            mk.run_mode = "running"
            mk.log("INFO", "继续任务")
        else:
            mk.run_mode = "paused"
            mk.log("INFO", "已暂停")
        return True, ""

    def stop(self):
        if not (self.worker and self.worker.is_alive()):
            return False, "没有在跑"
        mk.emergency_stop("界面终止")
        return True, ""


APP = App()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _json(self, code, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _html(self):
        with open(UI_FILE, "rb") as f:
            raw = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            return {}

    def do_GET(self):
        path = (self.path or "/").split("?")[0]
        if path in ("/", "/index.html"):
            self._html()
            return
        if path == "/api/state":
            self._json(200, APP.snapshot())
            return
        if path == "/api/account.png":
            if not os.path.isfile(mk.ACCOUNT_IMG):
                self._json(404, {"ok": False, "error": "no account"})
                return
            with open(mk.ACCOUNT_IMG, "rb") as f:
                raw = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/api/shot.png":
            if not os.path.isfile(mk.LAST_SHOT):
                self._json(404, {"ok": False, "error": "no shot"})
                return
            with open(mk.LAST_SHOT, "rb") as f:
                raw = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/api/shot/file":
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            run_id = (qs.get("run") or [""])[0]
            name = (qs.get("name") or [""])[0]
            fpath = mk.resolve_shot_file(run_id, name)
            if not fpath:
                self._json(404, {"ok": False, "error": "no shot file"})
                return
            with open(fpath, "rb") as f:
                raw = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
            return
        self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        data = self._body()
        path = (self.path or "/").split("?")[0]
        ok, err = False, "未知接口"
        if path == "/api/queue/add":
            ok, err = APP.add_queue(data.get("id"))
        elif path == "/api/queue/remove":
            ok, err = APP.remove_queue(int(data.get("index", -1)))
        elif path == "/api/queue/move":
            ok, err = APP.move_queue(int(data.get("index", -1)), int(data.get("dir", 0)))
        elif path == "/api/queue/clear":
            ok, err = APP.clear_queue()
        elif path == "/api/start":
            options = {
                # 勾选=auto（已横屏不杀）；不勾选=never
                "kill_mirror": "auto" if data.get("kill_mirror", True) else False,
                "watch_lost": bool(data.get("watch_lost", True)),
                "reconnect": bool(data.get("reconnect", False)),
            }
            ok, err = APP.start(options)
        elif path == "/api/pause":
            ok, err = APP.pause()
        elif path == "/api/stop":
            ok, err = APP.stop()
        elif path == "/api/clear-errors":
            mk.clear_errors()
            ok, err = True, ""
        elif path == "/api/overlay/lock":
            ok, err = APP.set_overlay_locked(True)
        elif path == "/api/overlay/unlock":
            ok, err = APP.set_overlay_locked(False)
        elif path == "/api/calib/target":
            key = ((data or {}).get("key") or "").strip()
            keys = {p["key"] for p in mk.moyu_points_summary()}
            if key and key not in keys:
                ok, err = False, "未知校准目标，请先在列表里添加"
            else:
                APP.calib_target = key
                if key:
                    APP.enqueue_log("[手校] 目标设为「%s」→ 点「锁定游戏」→ 在镜像上点该按钮" % mk.moyu_point_label(key))
                else:
                    APP.enqueue_log("[手校] 已清空目标")
                ok, err = True, ""
        elif path == "/api/calib/retap":
            APP.calib_retap = bool((data or {}).get("enabled", True))
            APP.enqueue_log("[手校] 校准后复点：" + ("开（仅白名单）" if APP.calib_retap else "关"))
            ok, err = True, ""
        elif path == "/api/calib/add":
            item, err = mk.add_moyu_point((data or {}).get("label"))
            if item:
                APP.calib_target = item["key"]
                APP.enqueue_log("[手校] 已新增「%s」，选中后锁定再点即可校准" % item.get("label"))
                self._json(200, {"ok": True, "item": item, "moyu_points": mk.moyu_points_summary()})
                return
            ok, err = False, err or "新增失败"
        elif path == "/api/calib/rename":
            ok, err = mk.rename_moyu_point((data or {}).get("key"), (data or {}).get("label"))
            if ok:
                self._json(200, {"ok": True, "moyu_points": mk.moyu_points_summary()})
                return
        elif path == "/api/calib/delete":
            key = ((data or {}).get("key") or "").strip()
            ok, err = mk.delete_moyu_point(key)
            if ok:
                if APP.calib_target == key:
                    APP.calib_target = ""
                self._json(200, {"ok": True, "moyu_points": mk.moyu_points_summary()})
                return
        elif path == "/api/calib/clear":
            ok, err = mk.clear_moyu_point_coords((data or {}).get("key"))
            if ok:
                self._json(200, {"ok": True, "moyu_points": mk.moyu_points_summary()})
                return
        elif path == "/api/calib/move":
            ok, err = mk.move_moyu_point((data or {}).get("key"), (data or {}).get("dir", 0))
            if ok:
                self._json(200, {"ok": True, "moyu_points": mk.moyu_points_summary()})
                return
        elif path == "/api/calibrate/click":
            ok, err = APP.record_calibrate(data)
        elif path == "/api/record/start":
            ok, err = APP.start_recording()
        elif path == "/api/record/stop":
            ok, err, pending = APP.stop_recording()
            if ok:
                self._json(200, {
                    "ok": True,
                    "recording": APP.recording,
                    "recording_count": APP.recording_count,
                    "pending_save": pending,
                })
            else:
                self._json(400, {"ok": False, "error": err})
            return
        elif path == "/api/record/save":
            ok, err, extra = APP.save_recording(data)
            if ok:
                self._json(200, {"ok": True, "saved": extra})
            else:
                self._json(400, {"ok": False, "error": err})
            return
        elif path == "/api/record/discard":
            ok, err = APP.discard_recording(data)
            if ok:
                self._json(200, {"ok": True})
            else:
                self._json(400, {"ok": False, "error": err})
            return
        elif path == "/api/script/delete":
            ok, err = mk.delete_script((data or {}).get("id"))
            if ok:
                APP.enqueue_log("[脚本] 已删除手点脚本：%s" % ((data or {}).get("id") or ""))
                # 若队列里有同名项一并去掉
                try:
                    with APP.lock:
                        APP.queue_items = [
                            q for q in APP.queue_items
                            if (q.get("id") != (data or {}).get("id"))
                        ]
                except Exception:
                    pass
                self._json(200, {"ok": True})
            else:
                self._json(400, {"ok": False, "error": err or "删除失败"})
            return
        elif path == "/api/record/cancel":
            ok, err = APP.cancel_recording()
        elif path == "/api/perm-check":
            # 默认不 force 截图像素探针，避免点自检就弹屏幕录制
            report = mk.permission_report(probe_screen=False)
            APP.enqueue_log("[权限] " + report.get("hint", ""))
            ok, err = True, ""
            self._json(200, {"ok": True, "perm": report})
            return
        if ok:
            self._json(200, {
                "ok": True,
                "calibrate": APP.last_calibrate,
                "recording": APP.recording,
                "recording_count": APP.recording_count,
            })
        else:
            self._json(400, {"ok": False, "error": err})


def pick_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def ensure_appwin():
    if os.path.isfile(APPWIN_BIN) and os.path.getmtime(APPWIN_BIN) >= os.path.getmtime(APPWIN_SRC):
        return True
    code = subprocess.call(["swiftc", "-O", "-o", APPWIN_BIN, APPWIN_SRC], cwd=ROOT)
    return code == 0 and os.path.isfile(APPWIN_BIN)


def ensure_overlay_bin():
    if os.path.isfile(OVERLAY_BIN) and os.path.getmtime(OVERLAY_BIN) >= os.path.getmtime(OVERLAY_SRC):
        return True
    code = subprocess.call(["swiftc", "-O", "-o", OVERLAY_BIN, OVERLAY_SRC, "-framework", "Cocoa"], cwd=ROOT)
    return code == 0 and os.path.isfile(OVERLAY_BIN)


def ensure_clickwatch_bin():
    if os.path.isfile(WATCH_BIN) and os.path.getmtime(WATCH_BIN) >= os.path.getmtime(WATCH_SRC):
        return True
    code = subprocess.call(["swiftc", "-O", "-o", WATCH_BIN, WATCH_SRC, "-framework", "Cocoa"], cwd=ROOT)
    return code == 0 and os.path.isfile(WATCH_BIN)


def stop_overlay():
    APP.write_overlay_ctrl(False)
    proc = APP.overlay_proc
    if proc and proc.poll() is None:
        try:
            proc.terminate()
        except Exception:
            pass
    APP.overlay_proc = None
    APP.overlay_locked = False
    APP.stop_clickwatch()


def run_gui():
    port = pick_port()
    url = "http://127.0.0.1:%s/" % port
    APP.api_base = "http://127.0.0.1:%s" % port
    APP.write_overlay_ctrl(False)
    APP.write_watch_ctrl(False)
    atexit.register(stop_overlay)
    atexit.register(mk.stop_f12_guardian)
    atexit.register(mk.restore_mouse)
    atexit.register(mk.stop_dotmark)
    ensure_overlay_bin()
    ensure_clickwatch_bin()

    def f12_start_from_idle():
        # 空闲按 F12 = 点「开始」（沿用界面勾选的默认：不杀镜像、看守）
        if APP.ui_state() != "idle":
            return
        ok, err = APP.start({
            "kill_mirror": False,
            "watch_lost": True,
            "reconnect": False,
        })
        if not ok:
            mk.log("WARN", "F12 开始失败：%s" % (err or "未知"))

    mk.start_f12_guardian(start_cb=f12_start_from_idle)
    mk.run_mode = "idle"
    APP.enqueue_log("全局快捷键：F12=砸开终止（立刻恢复鼠标）；F8=手动点完继续；空闲再按 F12=开始")
    try:
        report = mk.permission_report()
        print("[权限] " + report.get("hint", ""), flush=True)
        APP.enqueue_log("[权限] " + report.get("hint", ""))
    except Exception as e:
        print("权限自检跳过: %s" % e, flush=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    print("GUI_URL=%s" % url, flush=True)
    print("界面地址：%s" % url, flush=True)
    print("提示：随时按 F12 可紧急终止并恢复鼠标", flush=True)
    if "--serve" in sys.argv:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        httpd.shutdown()
        return
    opened = False
    if ensure_appwin():
        try:
            proc = subprocess.Popen([APPWIN_BIN, url])
            opened = True
            proc.wait()
        except Exception as e:
            print("打开窗口失败：%s" % e, flush=True)
    if not opened:
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    httpd.shutdown()


def write_pid():
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def clear_pid():
    try:
        if not os.path.isfile(PID_FILE):
            return
        with open(PID_FILE) as f:
            if f.read().strip() == str(os.getpid()):
                os.remove(PID_FILE)
    except Exception:
        pass


if __name__ == "__main__":
    write_pid()
    atexit.register(clear_pid)
    run_gui()


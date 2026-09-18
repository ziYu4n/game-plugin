#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iPhone 镜像保活：打开应用、断线重连、锁屏才输入密码、写日志和错误暂存。"""

import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

import coords as coordlib

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(ROOT, "logs")
DATA_DIR = os.path.join(ROOT, "data")
ERROR_FILE = os.path.join(DATA_DIR, "errors.json")
PID_FILE = os.path.join(DATA_DIR, "keeper.pid")
SCREENSHOT = os.path.join(DATA_DIR, "mirror_window.png")
LAST_SHOT = os.path.join(DATA_DIR, "last_shot.png")
ACCOUNT_IMG = os.path.join(DATA_DIR, "account.png")
SHOT_DIR = os.path.join(LOG_DIR, "shots")
RECORD_DIR = os.path.join(DATA_DIR, "recordings")
COORD_CONFIG = os.path.join(DATA_DIR, "coord_config.json")
APPLESCRIPT = os.path.join(ROOT, "scripts", "mirror.applescript")
OCR_SRC = os.path.join(ROOT, "scripts", "ocr.swift")
OCR_BIN = os.path.join(ROOT, "scripts", "ocr")
WININFO_SRC = os.path.join(ROOT, "scripts", "wininfo.swift")
WININFO_BIN = os.path.join(ROOT, "scripts", "wininfo")
CLICK_SRC = os.path.join(ROOT, "scripts", "click.swift")
CLICK_BIN = os.path.join(ROOT, "scripts", "click")
HOTKEY_SRC = os.path.join(ROOT, "scripts", "hotkey.swift")
HOTKEY_BIN = os.path.join(ROOT, "scripts", "hotkey")
F12_PULSE = os.path.join(DATA_DIR, "f12_pulse")
F8_PULSE = os.path.join(DATA_DIR, "f8_pulse")
DOTMARK_SRC = os.path.join(ROOT, "scripts", "dotmark.swift")
DOTMARK_BIN = os.path.join(ROOT, "scripts", "dotmark")
DOT_MARK_FILE = os.path.join(DATA_DIR, "dot_mark.txt")
OVERLAY_LOCK = os.path.join(DATA_DIR, "overlay.lock")
MATCH_PY = os.path.join(ROOT, "scripts", "match.py")
BACK_ICON = os.path.join(ROOT, "icons", "back.png")
BACK_ICON_ALT = os.path.join(ROOT, "icons", "back_alt.png")
BACK_ICON_LAND = os.path.join(ROOT, "icons", "back_land.png")
BACK_ICON_PORT = os.path.join(ROOT, "icons", "back_port.png")
BACK_ICON_PORT_CCW = os.path.join(ROOT, "icons", "back_port_ccw.png")
BACK_ICON_LAND_1X2 = os.path.join(ROOT, "icons", "back_land_1x2.png")
BACK_ICON_LAND_0X8 = os.path.join(ROOT, "icons", "back_land_0x8.png")
POPUP_CLOSE_ICON = os.path.join(ROOT, "icons", "popup_close.png")
POPUP_CLOSE_ALT = os.path.join(ROOT, "icons", "popup_close_alt.png")
ANNOUNCE_CLOSE = os.path.join(ROOT, "icons", "announce_close.png")
ANNOUNCE_CLOSE_BW = os.path.join(ROOT, "icons", "announce_close_bw.png")
ANNOUNCE_CLOSE_HI = os.path.join(ROOT, "icons", "announce_close_hi.png")
ANNOUNCE_CLOSE_90 = os.path.join(ROOT, "icons", "announce_close_90.png")
ANNOUNCE_CLOSE_180 = os.path.join(ROOT, "icons", "announce_close_180.png")
ANNOUNCE_CLOSE_270 = os.path.join(ROOT, "icons", "announce_close_270.png")
ANNOUNCE_CLOSE_BW_90 = os.path.join(ROOT, "icons", "announce_close_bw_90.png")
ANNOUNCE_CLOSE_BW_180 = os.path.join(ROOT, "icons", "announce_close_bw_180.png")
ANNOUNCE_CLOSE_BW_270 = os.path.join(ROOT, "icons", "announce_close_bw_270.png")
MOYU_MENU = os.path.join(ROOT, "icons", "moyu_menu.png")
MOYU_TONGYOU = os.path.join(ROOT, "icons", "moyu_tongyou.png")
MOYU_ZHIGE = os.path.join(ROOT, "icons", "moyu_zhige.png")
MOYU_JUEZHANGLIN = os.path.join(ROOT, "icons", "moyu_juezhanglin.png")
CONFIG_DIR = os.path.join(ROOT, "configs")
KEYCHAIN_SERVICE = "game-plugin.iphone-passcode"

# content 仅日志/兜底估算，不全链路改 content
TITLEBAR_INSET = 28
SIDE_INSET = 0
BOTTOM_INSET = 0
EDGE_MARGIN = 0.04
BACK_BUTTON = (0.919, 0.068)  # 横屏公共弹窗右上角 «（用户红框）
BACK_BUTTON_LAND = (0.919, 0.068)
BACK_BUTTON_PORT = (0.923, 0.912)
# 关完公告后「继续游戏」兜底（按窗口横竖）
CONTINUE_POINT_PORT = (0.50, 0.78)
CONTINUE_POINT_LAND = (0.78, 0.48)
BACK_CALIB_FILE = os.path.join(DATA_DIR, "back_button.json")
MOYU_POINTS_FILE = os.path.join(DATA_DIR, "moyu_points.json")
# 默认种子：新文件或空列表时写入；用户可增删改排序
MOYU_POINT_KEYS = [
    ("menu", "菜单按钮"),
    ("tongyou", "同游"),
    ("zhige", "止戈"),
    ("juezhanglin", "觉障林"),
    ("start_match", "开始匹配"),
]
# 手校自动复点白名单（防误触不可逆按钮）；白名单外仅存坐标不复点
CALIB_RETAP_SAFE = {
    "menu", "tongyou", "zhige", "juezhanglin", "start_match", "back_button",
}

APP_NAME = "iPhone Mirroring"
APP_OWNER = "iPhone镜像"
CHECK_INTERVAL = 8
WINDOW_WAIT = 15
UNLOCK_MAX_TRIES = 3
UNLOCK_COOLDOWN = 60
ERROR_DEDUP_SECONDS = 30

LOCK_WORDS = [
    "滑动来解锁",
    "滑动解锁",
    "slide to unlock",
    "enter passcode",
    "输入密码",
    "使用密码",
    "use passcode",
    "face id",
    "密码",
    "passcode",
    "紧急情况",
    "emergency",
]
CONNECT_FAIL_WORDS = [
    "无法连接",
    "连接失败",
    "找不到",
    "未找到",
    "can't connect",
    "cannot connect",
    "couldn't connect",
    "could not connect",
    "not found",
    "try again",
    "重试",
]
CONNECTING_WORDS = [
    "正在连接",
    "connecting",
    "准备中",
]

_ax_warned = False
run_mode = "idle"
log_hook = None
current_account = ""
_shot_run = ""
_shot_seq = 0
_last_saved_shot = None
_last_click = None  # dict: shot_px/shot_py/fx/fy/sx/sy
_last_metrics = None
_active_recording = None
_wrong_app_cooldown_until = 0
_perm_hint = ""
app_phase = "idle"  # connecting|home|spotlight_search|game_announcement|game_playing|error|idle


def set_phase(name):
    global app_phase
    if name and name != app_phase:
        app_phase = name
        log("INFO", "阶段 → %s" % name)


def now_text():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dirs():
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)


def log(level, message):
    ensure_dirs()
    line = "[%s] %s %s" % (now_text(), level, message)
    print(line)
    sys.stdout.flush()
    path = os.path.join(LOG_DIR, datetime.datetime.now().strftime("%Y-%m-%d") + ".log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if log_hook:
        try:
            log_hook(line)
        except Exception:
            pass


def load_errors():
    ensure_dirs()
    if not os.path.exists(ERROR_FILE):
        return {"cleared_at": None, "items": []}
    try:
        with open(ERROR_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"cleared_at": None, "items": []}
        data.setdefault("cleared_at", None)
        data.setdefault("items", [])
        return data
    except Exception:
        return {"cleared_at": None, "items": []}


def save_errors(data):
    ensure_dirs()
    with open(ERROR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_error(message, detail=""):
    data = load_errors()
    items = data.get("items") or []
    if items:
        last = items[-1]
        if last.get("message") == message:
            try:
                last_time = datetime.datetime.strptime(last.get("time", ""), "%Y-%m-%d %H:%M:%S")
                delta = (datetime.datetime.now() - last_time).total_seconds()
            except Exception:
                delta = ERROR_DEDUP_SECONDS + 1
            if delta <= ERROR_DEDUP_SECONDS:
                last["count"] = int(last.get("count") or 1) + 1
                last["time"] = now_text()
                if detail:
                    last["detail"] = detail
                save_errors(data)
                log("ERROR", message)
                return
    items.append({
        "time": now_text(),
        "message": message,
        "detail": detail or "",
        "count": 1,
    })
    data["items"] = items
    save_errors(data)
    log("ERROR", message)


def clear_errors():
    data = load_errors()
    data["items"] = []
    data["cleared_at"] = now_text()
    save_errors(data)
    log("INFO", "已手动清空错误记录")


def run_cmd(args, timeout=20):
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        return result.returncode, out, err
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


def note_ax_denied(text):
    global _ax_warned
    if "不允许辅助访问" not in (text or ""):
        return False
    if not _ax_warned:
        record_error(
            "系统未授权辅助功能",
            "请到 系统设置 → 隐私与安全性 → 辅助功能，勾选「终端」或你用来启动脚本的程序",
        )
        _ax_warned = True
    return True


def osascript(command):
    code, out, err = run_cmd(["osascript", APPLESCRIPT, command], timeout=8)
    text = out or err
    if code != 0 and not text:
        text = "ERR:osascript-failed"
    note_ax_denied(text)
    return text


def compile_tool(src, bin_path, label, frameworks=None, ident=None):
    need_build = not (os.path.isfile(bin_path) and os.path.getmtime(bin_path) >= os.path.getmtime(src))
    if not need_build:
        return True
    log("INFO", "正在编译 %s" % label)
    cmd = ["swiftc", "-O", "-o", bin_path, src]
    for fw in (frameworks or []):
        cmd.extend(["-framework", fw])
    code, out, err = run_cmd(cmd, timeout=120)
    if code != 0:
        log("WARN", "%s 编译失败: %s" % (label, err or out))
        if os.path.isfile(bin_path):
            log("WARN", "先继续用已经编好的 %s" % label)
            os.utime(bin_path, None)
            return True
        return False
    # 故意不 codesign：--force 重签会换 CDHash，系统当新程序，屏幕录制/辅助功能再弹窗卡住
    log("INFO", "%s 已编译（跳过重签名，避免权限弹窗）" % label)
    return True


def ensure_wininfo_bin():
    return compile_tool(WININFO_SRC, WININFO_BIN, "窗口检测工具")


def ensure_click_bin():
    return compile_tool(CLICK_SRC, CLICK_BIN, "模拟点击工具")


def ensure_hotkey_bin():
    return compile_tool(HOTKEY_SRC, HOTKEY_BIN, "F12 热键工具", frameworks=["Cocoa"])


def ensure_dotmark_bin():
    return compile_tool(DOTMARK_SRC, DOTMARK_BIN, "红点指示器", frameworks=["Cocoa"])


_dotmark_proc = None


def set_overlay_unlocked_for_clicks():
    """脚本自动点时必须关掉遮罩，否则点到的是白色遮罩（会误校准）。"""
    try:
        ensure_dirs()
        with open(OVERLAY_LOCK, "w") as f:
            f.write("0")
    except Exception:
        pass


def show_screen_dot(sx, sy):
    """在屏幕绝对坐标显示红色指示点（看得见的从左到右/从上到下）。"""
    global _dotmark_proc
    ensure_dirs()
    if not ensure_dotmark_bin():
        return False
    try:
        with open(DOT_MARK_FILE, "w") as f:
            f.write("%.1f,%.1f\n" % (float(sx), float(sy)))
    except Exception:
        return False
    if _dotmark_proc is None or _dotmark_proc.poll() is not None:
        try:
            _dotmark_proc = subprocess.Popen(
                [DOTMARK_BIN, DOT_MARK_FILE],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            log("WARN", "红点指示器启动失败: %s" % e)
            return False
    return True


def hide_screen_dot():
    try:
        with open(DOT_MARK_FILE, "w") as f:
            f.write("hide\n")
    except Exception:
        pass


def stop_dotmark():
    global _dotmark_proc
    hide_screen_dot()
    if _dotmark_proc and _dotmark_proc.poll() is None:
        try:
            _dotmark_proc.terminate()
        except Exception:
            pass
    _dotmark_proc = None


_f12_proc = None
_f12_thread = None
_f12_start_cb = None
_f12_last_mtime = 0
_f8_last_mtime = 0
_f12_lock = None
_f8_waiters = 0


def restore_mouse():
    """紧急恢复鼠标↔光标关联，防止 HID 卡死。"""
    try:
        if ensure_click_bin():
            run_cmd([CLICK_BIN, "--fix-mouse"], timeout=3)
    except Exception:
        pass
    try:
        # 兜底：再调一次系统关联（失败忽略）
        subprocess.call([
            "python3", "-c",
            "import ctypes; ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')"
            ".CGAssociateMouseAndMouseCursorPosition(True)",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
    except Exception:
        pass


def emergency_stop(reason="F12"):
    """紧急砸开：停任务 + 多次恢复鼠标 + 杀掉卡住的 click。"""
    global run_mode, _f8_waiters
    run_mode = "stop"
    _f8_waiters = 0
    hide_screen_dot()
    for _ in range(3):
        restore_mouse()
        time.sleep(0.05)
    try:
        subprocess.call(["pkill", "-f", os.path.join("scripts", "click")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    try:
        # 避免 HID 关联残留
        subprocess.call([CLICK_BIN, "--fix-mouse"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
    except Exception:
        pass
    log("WARN", "%s：已砸开（终止任务 + 恢复鼠标）" % reason)


def handle_f12_toggle():
    """F12 全局砸开：优先强制终止；仅真正空闲时才开始。"""
    global run_mode
    restore_mouse()
    # 运行中 / 暂停 / 正在停 / 等人手确认 → 一律砸开终止
    if run_mode in ("running", "paused", "stop") or _f8_waiters > 0:
        emergency_stop("F12")
        return
    cb = _f12_start_cb
    if cb:
        log("INFO", "F12：尝试开始任务")
        try:
            cb()
        except Exception as e:
            log("WARN", "F12 开始失败: %s" % e)
    else:
        # 空闲也恢复一次鼠标，防止残留锁
        restore_mouse()
        log("INFO", "F12：已恢复鼠标（当前空闲）")


def _f12_poll_loop():
    global _f12_last_mtime, _f8_last_mtime
    ensure_dirs()
    while True:
        try:
            if os.path.isfile(F12_PULSE):
                mtime = os.path.getmtime(F12_PULSE)
                if mtime > _f12_last_mtime + 0.05:
                    _f12_last_mtime = mtime
                    handle_f12_toggle()
            if os.path.isfile(F8_PULSE):
                mtime = os.path.getmtime(F8_PULSE)
                if mtime > _f8_last_mtime + 0.05:
                    _f8_last_mtime = mtime
                    # F8 只唤醒「等人手点完」的等待；不终止任务
                    if _f8_waiters <= 0:
                        log("INFO", "F8：当前没有在等手动确认")
        except Exception:
            pass
        time.sleep(0.12)


def consume_f8_since(since_mtime):
    """若 F8 在 since_mtime 之后按下，返回 True。"""
    global _f8_last_mtime
    try:
        if not os.path.isfile(F8_PULSE):
            return False
        mtime = os.path.getmtime(F8_PULSE)
        if mtime > since_mtime + 0.02:
            _f8_last_mtime = mtime
            return True
    except Exception:
        pass
    return False


def wait_f8_continue(hint, timeout=90):
    """等人手点完后按 F8 继续（不抢鼠标）。"""
    global _f8_waiters
    ensure_dirs()
    start_f12_guardian(_f12_start_cb)
    try:
        baseline = os.path.getmtime(F8_PULSE) if os.path.isfile(F8_PULSE) else time.time()
    except Exception:
        baseline = time.time()
    log("WARN", "—— 请手动点击镜像 ——")
    log("WARN", hint)
    log("WARN", "点完后按 F8 继续（F12=紧急终止）。最多等 %.0f 秒" % float(timeout))
    try:
        subprocess.Popen(["afplay", "/System/Library/Sounds/Purr.aiff"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    _f8_waiters += 1
    end = time.time() + float(timeout)
    try:
        while time.time() < end:
            if should_stop():
                return False
            if consume_f8_since(baseline):
                log("INFO", "已收到 F8，继续脚本")
                return True
            time.sleep(0.15)
    finally:
        _f8_waiters = max(0, _f8_waiters - 1)
    log("WARN", "等待 F8 超时")
    return False


def start_f12_guardian(start_cb=None):
    """后台监听 F12/F8。"""
    global _f12_proc, _f12_thread, _f12_start_cb, _f12_last_mtime, _f8_last_mtime, _f12_lock
    import threading
    if _f12_lock is None:
        _f12_lock = threading.Lock()
    with _f12_lock:
        if start_cb is not None:
            _f12_start_cb = start_cb
        if not ensure_hotkey_bin():
            log("WARN", "热键工具不可用（需要辅助功能权限）")
            return False
        ensure_dirs()
        try:
            if not os.path.isfile(F12_PULSE):
                with open(F12_PULSE, "w") as f:
                    f.write("0")
            if not os.path.isfile(F8_PULSE):
                with open(F8_PULSE, "w") as f:
                    f.write("0")
            _f12_last_mtime = os.path.getmtime(F12_PULSE)
            _f8_last_mtime = os.path.getmtime(F8_PULSE)
        except Exception:
            _f12_last_mtime = 0
            _f8_last_mtime = 0
        if _f12_proc is None or _f12_proc.poll() is not None:
            try:
                ensure_click_bin()
                _f12_proc = subprocess.Popen(
                    [HOTKEY_BIN, F12_PULSE, F8_PULSE, CLICK_BIN],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                log("WARN", "启动热键监听失败: %s" % e)
                return False
        if _f12_thread is None or not _f12_thread.is_alive():
            _f12_thread = threading.Thread(target=_f12_poll_loop, daemon=True)
            _f12_thread.start()
        log("INFO", "全局热键已砸开：F12=强制终止并恢复鼠标；F8=点完继续")
        return True


def stop_f12_guardian():
    global _f12_proc
    if _f12_proc and _f12_proc.poll() is None:
        try:
            _f12_proc.terminate()
        except Exception:
            pass
    _f12_proc = None


def should_stop():
    return run_mode == "stop"


def sleep_wait(seconds):
    end = time.time() + seconds
    while time.time() < end:
        if should_stop():
            return False
        if run_mode == "paused":
            time.sleep(0.2)
            continue
        time.sleep(0.2)
    return not should_stop()


def get_mirror_pid():
    code, out, err = run_cmd(["pgrep", "-x", APP_NAME])
    if code == 0 and out:
        try:
            return int(out.split()[0])
        except Exception:
            return 0
    return 0


def window_bounds():
    if not ensure_wininfo_bin():
        bounds = osascript("bounds")
        if bounds and not bounds.startswith("ERR"):
            return bounds
        return ""
    args = [WININFO_BIN, APP_OWNER]
    code, out, err = run_cmd(["pgrep", "-x", APP_NAME])
    if code == 0 and out:
        args.extend(out.split())
    code, out, err = run_cmd(args, timeout=10)
    if code != 0:
        log("WARN", "窗口检测失败: %s" % (err or out))
        return ""
    if not out or out == "none" or out.startswith("ERR"):
        return ""
    lines = [line.strip() for line in out.splitlines() if line.strip() and line.strip() != "none"]
    if not lines:
        return ""
    last = lines[-1]
    if last.startswith("ERR") or "," not in last:
        return ""
    return last


def mirror_pids():
    pids = set()
    cmds = [
        ["pgrep", "-x", "iPhone Mirroring"],
        ["pgrep", "-x", "iPhone镜像"],
        ["pgrep", "-f", "/iPhone Mirroring.app/"],
    ]
    for args in cmds:
        code, out, err = run_cmd(args)
        if code == 0 and out:
            for part in out.split():
                try:
                    pids.add(int(part))
                except Exception:
                    pass
    return pids


def process_running():
    return bool(mirror_pids())


def quit_mirror_hard():
    log("INFO", "强制退出 iPhone 镜像（和系统强制退出一样）")
    pids = mirror_pids()
    for pid in pids:
        run_cmd(["kill", "-9", str(pid)], timeout=5)
    run_cmd(["killall", "-9", "iPhone Mirroring"], timeout=5)
    run_cmd(["killall", "-9", "iPhone镜像"], timeout=5)
    time.sleep(0.8)
    for _ in range(12):
        left = mirror_pids()
        if not left:
            log("INFO", "镜像已强制退出")
            time.sleep(1.2)
            return True
        for pid in left:
            run_cmd(["kill", "-9", str(pid)], timeout=5)
        time.sleep(0.35)
    log("WARN", "镜像进程可能还没退干净")
    return not process_running()


def restart_mirror():
    quit_mirror_hard()
    log("INFO", "重新打开镜像，让接下来第一次进游戏走横屏")
    if not open_mirror():
        return False
    if not wait_window(22):
        record_error("重启镜像后没有出现窗口")
        return False
    time.sleep(1.2)
    return True


def has_window():
    return bool(window_bounds())


def bring_front():
    run_cmd(["osascript", "-e", 'tell application "iPhone Mirroring" to activate'], timeout=8)


_last_mirror_front = 0


def ensure_mirror_front(force=False):
    """把镜像置前。焦点留在镜像，不切回脚本合集；不用 HID。"""
    global _last_mirror_front
    now = time.time()
    if not force and now - _last_mirror_front < 0.8:
        return
    bring_front()
    _last_mirror_front = time.time()
    time.sleep(0.15)


def open_mirror():
    log("INFO", "正在打开 iPhone 镜像")
    code, out, err = run_cmd(["open", "-a", APP_NAME], timeout=8)
    if code != 0:
        text = osascript("open")
        if text.startswith("ERR"):
            record_error("打开 iPhone 镜像失败", err or out or text)
            return False
    log("INFO", "已打开 iPhone 镜像")
    return True


def wait_window(seconds=WINDOW_WAIT):
    end = time.time() + seconds
    while time.time() < end:
        if should_stop():
            return False
        if run_mode == "paused":
            time.sleep(0.2)
            continue
        if has_window():
            return True
        time.sleep(0.5)
    return False


def keychain_account():
    return os.environ.get("USER") or os.environ.get("LOGNAME") or ""


def get_passcode():
    account = keychain_account()
    args = ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"]
    if account:
        args.extend(["-a", account])
    code, out, err = run_cmd(args)
    if code == 0 and out:
        return out
    return ""


def set_passcode(pin):
    pin = (pin or "").strip()
    if not pin:
        log("ERROR", "密码不能为空")
        return False
    account = keychain_account()
    args = [
        "security", "add-generic-password",
        "-s", KEYCHAIN_SERVICE,
        "-w", pin,
        "-U",
    ]
    if account:
        args.extend(["-a", account])
    code, out, err = run_cmd(args)
    if code != 0:
        log("ERROR", "写入钥匙串失败: %s" % (err or out))
        return False
    log("INFO", "锁屏密码已写入本机钥匙串")
    return True


def ensure_ocr_bin():
    return compile_tool(OCR_SRC, OCR_BIN, "OCR 工具")


def parse_bounds(text):
    """返回 (ox,oy,ow,oh,window_id,cx,cy,cw,ch)。旧 5 段格式自动推内容区。"""
    parts = [p.strip() for p in (text or "").split(",") if p.strip()]
    nums = []
    for p in parts:
        try:
            nums.append(int(float(p)))
        except Exception:
            return None
    if len(nums) < 4:
        return None
    ox, oy, ow, oh = nums[0], nums[1], nums[2], nums[3]
    window_id = nums[4] if len(nums) >= 5 else 0
    if len(nums) >= 9:
        cx, cy, cw, ch = nums[5], nums[6], nums[7], nums[8]
    else:
        cx = ox + SIDE_INSET
        cy = oy + TITLEBAR_INSET
        cw = max(1, ow - SIDE_INSET * 2)
        ch = max(1, oh - TITLEBAR_INSET - BOTTOM_INSET)
    return ox, oy, ow, oh, window_id, cx, cy, cw, ch


def window_info():
    raw = window_bounds()
    info = parse_bounds(raw)
    if not info:
        return None
    ox, oy, ow, oh, window_id, cx, cy, cw, ch = info
    return {
        "raw": raw,
        "window_id": window_id,
        "outer": (ox, oy, ow, oh),
        "content": (cx, cy, cw, ch),
        "outer_dict": {"x": ox, "y": oy, "w": ow, "h": oh},
        "content_dict": {"x": cx, "y": cy, "w": cw, "h": ch},
        "portrait": oh > ow * 1.08,
        "landscape": ow >= oh * 1.08,
    }


def window_info_json():
    """优先 wininfo --json；失败再退回 CSV 解析。"""
    if not ensure_wininfo_bin():
        return None
    code, out, err = run_cmd([WININFO_BIN, "--json", APP_OWNER], timeout=6)
    text_out = (out or "").strip()
    if code == 0 and text_out.startswith("{"):
        try:
            data = json.loads(text_out)
            if data.get("error") == "none" or not data.get("windowId"):
                return None
            outer = data.get("outer") or {}
            content = data.get("content") or {}
            ox, oy, ow, oh = float(outer["x"]), float(outer["y"]), float(outer["w"]), float(outer["h"])
            cx = float(content.get("x", ox))
            cy = float(content.get("y", oy))
            cw = float(content.get("w", ow))
            ch = float(content.get("h", oh))
            return {
                "window_id": int(data.get("windowId") or 0),
                "outer": (ox, oy, ow, oh),
                "content": (cx, cy, cw, ch),
                "outer_dict": {"x": ox, "y": oy, "w": ow, "h": oh},
                "content_dict": {"x": cx, "y": cy, "w": cw, "h": ch},
                "portrait": oh > ow * 1.08,
                "landscape": ow >= oh * 1.08,
            }
        except Exception as e:
            log("DEBUG", "wininfo --json 解析失败: %s" % e)
    return window_info()


def log_window_geom(tag=""):
    info = window_info()
    if not info:
        log("DEBUG", "窗口几何%s: 无" % ((" " + tag) if tag else ""))
        return None
    ox, oy, ow, oh = info["outer"]
    cx, cy, cw, ch = info["content"]
    orient = "竖屏" if info["portrait"] else ("横屏" if info["landscape"] else "方屏")
    log(
        "INFO",
        "窗口几何%s: id=%s outer=%s,%s %sx%s content=%s,%s %sx%s 方向=%s"
        % ((" " + tag) if tag else "", info["window_id"], ox, oy, ow, oh, cx, cy, cw, ch, orient),
    )
    return info


_last_cap_warn = 0
_capture_deny_until = 0
_capture_fail_streak = 0
CAPTURE_REUSE_SEC = 1.6


def _shot_size(path):
    try:
        from PIL import Image
        im = Image.open(path)
        return im.size
    except Exception:
        return None


def refresh_metrics(info=None, shot_path=None):
    """根据当前窗口 + 截图刷新全局 Metrics。"""
    global _last_metrics
    info = info or window_info()
    if not info:
        return None
    path = shot_path or SCREENSHOT
    size = _shot_size(path) if os.path.isfile(path) else None
    if not size:
        return _last_metrics
    try:
        m = coordlib.build_metrics(
            {"outer": info["outer_dict"], "content": info["content_dict"]},
            size[0], size[1],
            strict=False,
        )
    except Exception as e:
        log("WARN", "构建 metrics 失败: %s" % e)
        return _last_metrics
    _last_metrics = m
    if m.shot_space == "unknown":
        log("WARN", "截图仍非等比，已 best-effort：%s" % coordlib.metrics_log_line(m))
    else:
        log("INFO", coordlib.metrics_log_line(m))
    try:
        coordlib.save_metrics_config(COORD_CONFIG, m)
    except Exception:
        pass
    return m


def current_metrics(info=None):
    m = _last_metrics
    if m:
        return m
    return refresh_metrics(info=info)


def set_last_click(fx, fy, sx, sy, shot_px, shot_py, source=""):
    global _last_click
    _last_click = {
        "fx": round(float(fx), 4),
        "fy": round(float(fy), 4),
        "sx": round(float(sx), 1),
        "sy": round(float(sy), 1),
        "shot_px": round(float(shot_px), 1),
        "shot_py": round(float(shot_py), 1),
        "source": source or "",
    }
    return _last_click


def log_click(source, fx, fy, sx, sy, shot_px, shot_py, orient="", mode="", key=""):
    set_last_click(fx, fy, sx, sy, shot_px, shot_py, source=source)
    for line in coordlib.click_log_lines(
        source, fx, fy, sx, sy, shot_px, shot_py,
        orient=orient or current_orientation(),
        mode=mode, key=key,
    ):
        log("INFO", line)


def capture_denied():
    return time.time() < _capture_deny_until


def note_capture_fail(reason=""):
    """连续截图失败 → 冷却，避免权限弹窗叠一层又一层卡住。"""
    global _capture_fail_streak, _capture_deny_until, _last_cap_warn
    _capture_fail_streak += 1
    now = time.time()
    if now - _last_cap_warn > 5:
        _last_cap_warn = now
        log("WARN", "截图失败%s（若弹「屏幕录制」，勾选「脚本合集」后点允许；冷却中不再反复截）"
            % ((": " + reason) if reason else ""))
    if _capture_fail_streak >= 2:
        _capture_deny_until = now + 45
        log("WARN", "截图连续失败，暂停截图 45 秒，避免卡在权限窗")


def note_capture_ok():
    global _capture_fail_streak, _capture_deny_until
    _capture_fail_streak = 0
    _capture_deny_until = 0


def screenshot_fresh(max_age=None):
    max_age = CAPTURE_REUSE_SEC if max_age is None else float(max_age)
    if not (os.path.isfile(SCREENSHOT) and os.path.getsize(SCREENSHOT) > 1000):
        return False
    try:
        return (time.time() - os.path.getmtime(SCREENSHOT)) < max_age
    except Exception:
        return False


def capture_window(force=False):
    """截图统一去阴影：screencapture -x -o -l <windowId>。
    默认复用刚截过的图，失败进入冷却，避免权限弹窗连环卡住。
    """
    global _last_cap_warn
    if capture_denied() and not force:
        return False
    if (not force) and screenshot_fresh():
        return True
    info = window_info()
    if not info:
        return False
    ox, oy, ow, oh = info["outer"]
    window_id = info["window_id"]
    if ow <= 0 or oh <= 0:
        return False
    if os.path.exists(SCREENSHOT):
        try:
            os.remove(SCREENSHOT)
        except Exception:
            pass
    err, out = "", ""
    if window_id:
        # 超时要短：权限窗会挂起 screencapture，尽快放弃
        code, out, err = run_cmd(
            ["screencapture", "-x", "-o", "-l", str(window_id), SCREENSHOT],
            timeout=4,
        )
        if os.path.isfile(SCREENSHOT) and os.path.getsize(SCREENSHOT) > 1000:
            refresh_metrics(info=info, shot_path=SCREENSHOT)
            note_capture_ok()
            return True
        if err == "timeout" or code != 0:
            note_capture_fail(err or out or ("code=%s" % code))
            return False
    note_capture_fail(err or out or "无截图")
    return False


def image_to_content(fx, fy):
    """兼容旧调用：不做 content 全链路换算。"""
    return float(fx), float(fy)


def content_to_screen(fx, fy):
    m = current_metrics()
    if m:
        return coordlib.content_to_screen(fx, fy, m)
    info = window_info()
    if not info:
        return None
    cx, cy, cw, ch = info["content"]
    return cx + cw * float(fx), cy + ch * float(fy)


def outer_to_screen(fx, fy):
    m = current_metrics()
    if m:
        return coordlib.outer_to_screen(fx, fy, m)
    info = window_info()
    if not info:
        return None
    ox, oy, ow, oh = info["outer"]
    return ox + ow * float(fx), oy + oh * float(fy)


def in_content_safe(fx, fy):
    m = EDGE_MARGIN
    return m <= float(fx) <= 1.0 - m and m <= float(fy) <= 1.0 - m


def in_window_safe(fx, fy):
    """整窗坐标安全区：避开标题栏顶部和最外缘。"""
    return 0.02 <= float(fx) <= 0.98 and 0.06 <= float(fy) <= 0.98


def silent_click_screen(x, y, tag="", force_hid=False):
    """点击镜像。

    soft（默认）：只用 postToPid，绝不向屏幕发 HID（避免点到「脚本合集」的终止按钮）。
    assist：游戏内提示人手点，点完按 F8
    pid：同 soft
    hid：瞬移光标（会抢鼠标，不推荐）
    force_hid：回放/校准复点强制用 hid-nowarp
      —— cghidEventTap + 绝对坐标，不 warp 光标（见 click.swift 顶部说明）。
      镜像内 postToPid 常无效，所以游戏内脚本也走这条，不是「偷光标的旧 HID」。
    """
    if not ensure_click_bin():
        return False
    pid = get_mirror_pid()
    if not pid:
        return False
    ensure_mirror_front(force=False)
    mode = click_defaults()["mode"]
    if mode == "assist" and in_game_phase() and not force_hid:
        fx = fy = 0.5
        info = window_info()
        if info:
            ox, oy, ow, oh = info["outer"]
            if ow > 1 and oh > 1:
                fx = (float(x) - float(ox)) / float(ow)
                fy = (float(y) - float(oy)) / float(oh)
        return wait_f8_continue(
            "请点击镜像大约位置 %.0f%% , %.0f%%%s" % (
                max(0, min(100, fx * 100)), max(0, min(100, fy * 100)),
                (" " + tag) if tag else "",
            ),
            timeout=click_defaults()["manual_timeout"],
        )
    use_hid = force_hid or mode == "hid"
    if use_hid:
        ensure_mirror_front(force=True)
        time.sleep(0.06)
        # nowarp：不挪光标，比 restore 更稳，也不易点到脚本合集
        log("INFO", "脚本点击(HID) screen=%.1f,%.1f%s" % (float(x), float(y), (" " + tag) if tag else ""))
        code, out, err = run_cmd([CLICK_BIN, "--hid-nowarp", str(x), str(y)], timeout=8)
        if code != 0:
            code, out, err = run_cmd([CLICK_BIN, "--hid-restore", str(x), str(y)], timeout=8)
        if code != 0:
            code, out, err = run_cmd([CLICK_BIN, str(pid), str(x), str(y)], timeout=8)
    else:
        # soft / pid：只注入镜像进程
        log("INFO", "脚本点击(pid) screen=%.1f,%.1f%s" % (float(x), float(y), (" " + tag) if tag else ""))
        code, out, err = run_cmd([CLICK_BIN, str(pid), str(x), str(y)], timeout=8)
        # 游戏内 pid 常无效：自动补一枪 HID（仅当已在游戏阶段）
        if code == 0 and in_game_phase():
            ensure_mirror_front(force=True)
            run_cmd([CLICK_BIN, "--hid-nowarp", str(x), str(y)], timeout=8)
    if code != 0:
        log("WARN", "模拟点击失败: %s" % (err or out))
        return False
    return True


def in_game_phase():
    return (app_phase or "").startswith("game")


def wait_until_connected(timeout=25):
    """正在连接时禁止截图/点击，等到就绪或超时。"""
    end = time.time() + float(timeout)
    while time.time() < end:
        if should_stop():
            return False
        text = ocr_text()
        state = screen_state(text)
        if state == "connecting":
            set_phase("connecting")
            log("INFO", "镜像正在连接，等待就绪…")
            time.sleep(1.2)
            continue
        if state == "fail":
            log("WARN", "镜像连接失败")
            return False
        return True
    log("WARN", "等待镜像连接超时")
    return False


def ocr_text():
    if not ensure_ocr_bin():
        return ""
    if not capture_window():
        return ""
    code, out, err = run_cmd([OCR_BIN, SCREENSHOT], timeout=12)
    if code != 0:
        log("WARN", "OCR 识别失败: %s" % (err or out))
        return ""
    return out


def contains_any(text, words):
    low = (text or "").lower()
    for word in words:
        if word.lower() in low:
            return True
    return False


def screen_state(text):
    if contains_any(text, CONNECT_FAIL_WORDS):
        return "fail"
    if contains_any(text, CONNECTING_WORDS):
        return "connecting"
    if contains_any(text, LOCK_WORDS):
        return "lock"
    if text.strip():
        return "connected"
    return "unknown"


WRONG_APP_WORDS = ["微信", "WeChat", "转发截图", "企业微信"]
IN_GAME_WORDS = [
    "更新公告", "继续游戏", "选择角色", "白露沾衣",
    "进入江湖", "玩法内容", "版本更新",
    "适龄提示", "防沉迷", "实名", "燕云十六声", "燕云",
    "不删档", "十六巷", "游侠请",
    # 开屏健康提示 / 光敏提示（长文，勿当成进错 App）
    "光敏", "癫痫", "详细阅读", "抵制不良游戏", "适度游戏",
    "未成年人", "健康上网", "警告",
]


def wait_mirror_ready(timeout=35):
    log("INFO", "等待镜像真正连上，连上前不搜索、不点游戏")
    end = time.time() + timeout
    while time.time() < end:
        if not wait_if_paused():
            return False
        if not has_window():
            time.sleep(0.6)
            continue
        text = ocr_text()
        state = screen_state(text)
        if state == "connecting":
            log("INFO", "镜像还在连接，继续等")
            time.sleep(1.2)
            continue
        if state == "lock":
            log("INFO", "还在锁屏，先解锁")
            try_unlock()
            time.sleep(1.0)
            continue
        if state == "fail":
            log("WARN", "镜像显示连接失败")
            return False
        log("INFO", "镜像已连上")
        return True
    log("WARN", "等了很久镜像还没连好")
    return False


def is_wrong_app(items):
    global _wrong_app_cooldown_until
    names = [i.get("text") or "" for i in (items or [])]
    text = " ".join(names)
    if match_app_item(items, IN_GAME_WORDS):
        return ""
    if match_app_item(items, HOME_SCREEN_WORDS):
        return ""
    if contains_any(text, CONNECTING_WORDS):
        return "connecting"
    if contains_any(text, WRONG_APP_WORDS):
        return "wechat"
    long_lines = [n for n in names if len((n or "").replace(" ", "")) >= 8]
    if len(long_lines) >= 5:
        return "other"
    return ""


def note_wrong_app(kind):
    """识别到错误 App 后进入冷却，避免疯狂识图循环。"""
    global _wrong_app_cooldown_until
    _wrong_app_cooldown_until = time.time() + 4.0
    log("WARN", "检测到其他界面（%s），冷却 4 秒后再识图" % kind)


def wrong_app_cooling():
    return time.time() < _wrong_app_cooldown_until


def match_defaults():
    data = load_common() or {}
    cfg = data.get("match") or {}
    return {
        "back_min_score": float(cfg.get("back_min_score") if cfg.get("back_min_score") is not None else 0.85),
        "allow_fallback": bool(cfg.get("allow_fallback", True)),
        "max_fail": int(cfg.get("max_fail") if cfg.get("max_fail") is not None else 6),
    }


def click_defaults():
    """点击策略：
    soft=默认：HID 绝对坐标、不挪光标（推荐，进游戏可用）
    assist=游戏内提示人手点，点完按 F8
    pid=postToPid（不抢鼠标，进游戏常无效）
    hid=瞬移光标（会抢鼠标）
    """
    data = load_common() or {}
    cfg = data.get("click") or {}
    mode = (cfg.get("mode") or "soft").strip().lower()
    if mode not in ("assist", "hid", "pid", "soft"):
        mode = "soft"
    default_tries = 0 if mode == "assist" else 2
    return {
        "mode": mode,
        "auto_tries": int(cfg.get("auto_tries") if cfg.get("auto_tries") is not None else default_tries),
        "manual_timeout": float(cfg.get("manual_timeout") if cfg.get("manual_timeout") is not None else 90),
    }


def wait_manual_action(hint, done_fn, timeout=90, interval=1.2):
    """人机接力：提示用户手动点，脚本只负责识图确认。"""
    log("WARN", "—— 请手动操作 ——")
    log("WARN", hint)
    log("WARN", "点完后我会自动继续（最多等 %.0f 秒）" % float(timeout))
    try:
        # 响一声提醒（失败忽略）
        subprocess.Popen(["afplay", "/System/Library/Sounds/Purr.aiff"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    ensure_mirror_front(force=True)
    end = time.time() + float(timeout)
    while time.time() < end:
        if not wait_if_paused():
            return False
        if done_fn():
            log("INFO", "已检测到你手动操作成功，继续跑脚本")
            return True
        time.sleep(interval)
    log("WARN", "等待手动操作超时")
    return False


def back_templates():
    # 只传未旋转主图，由 match 现场四向旋转；避免模板爆炸导致卡顿
    paths = [
        ANNOUNCE_CLOSE_BW,
        ANNOUNCE_CLOSE_HI,
        ANNOUNCE_CLOSE,
        POPUP_CLOSE_ICON,
        POPUP_CLOSE_ALT,
        BACK_ICON_LAND,
        BACK_ICON_PORT,
    ]
    return [p for p in paths if os.path.isfile(p)]


def continue_templates():
    paths = [
        CONTINUE_ICON_PORT,
        CONTINUE_ICON_LAND,
        CONTINUE_ICON_LAND_ALT,
    ]
    return [p for p in paths if os.path.isfile(p)]


def find_icon(template_path, min_score=0.85, extra_templates=None):
    templates = []
    if template_path:
        templates.append(template_path)
    for p in (extra_templates or []):
        if p and p not in templates:
            templates.append(p)
    templates = [p for p in templates if os.path.isfile(p)]
    if not templates:
        return None
    fresh = screenshot_fresh(2.5)
    if not fresh:
        if capture_denied():
            return None
        if not capture_window(force=False):
            return None
    if not (os.path.isfile(SCREENSHOT) and os.path.getsize(SCREENSHOT) > 1000):
        return None
    args = [sys.executable, MATCH_PY, SCREENSHOT, templates[0], str(min_score)]
    for p in templates[1:]:
        args.extend(["--template", p])
    code, out, err = run_cmd(args, timeout=18)
    text = (out or "").strip()
    if not text or text.startswith("none"):
        if text:
            log("DEBUG", "图标未命中 %s" % text.replace("\t", " "))
        return None
    parts = text.split("\t")
    if len(parts) < 3:
        return None
    try:
        fx_img = float(parts[0])
        fy_img = float(parts[1])
        score = float(parts[2])
    except Exception:
        return None
    tmpl = parts[4] if len(parts) >= 5 else os.path.basename(templates[0])
    # match 输出的是截图归一化；经 coords 转到 outer
    m = current_metrics() or refresh_metrics()
    if m:
        sx, sy = coordlib.shot_norm_to_screen(fx_img, fy_img, m)
        fx, fy = coordlib.screen_to_outer(sx, sy, m)
        log_click("match", fx, fy, sx, sy, fx_img * m.shot_w, fy_img * m.shot_h)
    else:
        fx, fy = float(fx_img), float(fy_img)
    if not in_window_safe(fx, fy):
        log("WARN", "图标命中过靠边，丢弃 %.3f,%.3f score=%.2f" % (fx, fy, score))
        return None
    log("INFO", "图标命中 %s score=%.3f outer=%.3f,%.3f" % (tmpl, score, fx, fy))
    return fx, fy, score


def _slug_key(label, existing):
    """从中文名生成稳定 key；冲突则加数字后缀。"""
    raw = (label or "").strip()
    # 常用中文保留短英文 key，方便脚本 calib_key
    presets = {v: k for k, v in MOYU_POINT_KEYS}
    if raw in presets and presets[raw] not in existing:
        return presets[raw]
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", raw).strip("_").lower()
    if not base or base == "_":
        base = "p_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
    key = base
    n = 2
    while key in existing:
        key = "%s_%s" % (base, n)
        n += 1
    return key


def _normalize_moyu_store(raw):
    """统一为 {items:[{key,label,scope,portrait?,landscape?}]}；兼容旧 dict 格式。"""
    items = []
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        for it in raw["items"]:
            if not isinstance(it, dict):
                continue
            key = (it.get("key") or "").strip()
            if not key:
                continue
            items.append({
                "key": key,
                "label": (it.get("label") or key).strip() or key,
                "scope": (it.get("scope") or "shared").strip() or "shared",
                "portrait": _copy_orient_slot(it.get("portrait")),
                "landscape": _copy_orient_slot(it.get("landscape")),
            })
        return {"items": items}
    if isinstance(raw, dict):
        label_map = dict(MOYU_POINT_KEYS)
        seen = set()
        for key, label in MOYU_POINT_KEYS:
            slot = raw.get(key)
            if isinstance(slot, dict) and ("portrait" in slot or "landscape" in slot or "fx" in slot):
                items.append(_slot_to_item(key, label, slot))
                seen.add(key)
        for key, slot in raw.items():
            if key in seen or key in ("items", "order", "version"):
                continue
            if not isinstance(slot, dict):
                continue
            if not ("portrait" in slot or "landscape" in slot or "fx" in slot):
                continue
            items.append(_slot_to_item(key, label_map.get(key) or key, slot))
            seen.add(key)
    return {"items": items}


def _copy_orient_slot(slot):
    if not isinstance(slot, dict) or slot.get("fx") is None:
        return None
    out = {
        "fx": slot.get("fx"),
        "fy": slot.get("fy"),
        "updated_at": slot.get("updated_at") or "",
    }
    if slot.get("cg_x") is not None and slot.get("cg_y") is not None:
        out["cg_x"] = slot.get("cg_x")
        out["cg_y"] = slot.get("cg_y")
    if isinstance(slot.get("outer"), dict):
        out["outer"] = {
            "x": slot["outer"].get("x"),
            "y": slot["outer"].get("y"),
            "w": slot["outer"].get("w"),
            "h": slot["outer"].get("h"),
        }
    return out


def _slot_to_item(key, label, slot, scope="shared"):
    if "fx" in slot and "portrait" not in slot and "landscape" not in slot:
        return {
            "key": key,
            "label": label,
            "scope": scope,
            "portrait": _copy_orient_slot(slot),
            "landscape": None,
        }
    return {
        "key": key,
        "label": label,
        "scope": scope,
        "portrait": _copy_orient_slot(slot.get("portrait") if isinstance(slot.get("portrait"), dict) else None),
        "landscape": _copy_orient_slot(slot.get("landscape") if isinstance(slot.get("landscape"), dict) else None),
    }


def _orient_payload(fx, fy, cg=None, outer=None):
    """手校落盘：fx/fy + 绝对 CG + outer 锚点（窗口移动时用位移回放）。"""
    row = {
        "fx": round(float(fx), 4),
        "fy": round(float(fy), 4),
        "updated_at": now_text(),
    }
    if cg and len(cg) >= 2:
        row["cg_x"] = round(float(cg[0]), 1)
        row["cg_y"] = round(float(cg[1]), 1)
    if outer:
        if isinstance(outer, (list, tuple)) and len(outer) >= 4:
            row["outer"] = {
                "x": round(float(outer[0]), 1),
                "y": round(float(outer[1]), 1),
                "w": round(float(outer[2]), 1),
                "h": round(float(outer[3]), 1),
            }
        elif isinstance(outer, dict):
            row["outer"] = {
                "x": round(float(outer.get("x") or 0), 1),
                "y": round(float(outer.get("y") or 0), 1),
                "w": round(float(outer.get("w") or 0), 1),
                "h": round(float(outer.get("h") or 0), 1),
            }
    return row


def _ensure_back_button_migrated(store):
    """把 data/back_button.json 并入统一点位表（只迁一次）。"""
    have = {it["key"] for it in store["items"]}
    if "back_button" in have:
        return False
    old = load_back_calibrate()
    item = {
        "key": "back_button",
        "label": "关公告返回键",
        "scope": "yanyun_login",
        "portrait": _copy_orient_slot(old.get("portrait")) if isinstance(old.get("portrait"), dict) else None,
        "landscape": _copy_orient_slot(old.get("landscape")) if isinstance(old.get("landscape"), dict) else None,
    }
    store["items"].insert(0, item)
    return True


def load_moyu_points():
    """返回规范化 store；缺默认项时补上（不覆盖已有坐标）。"""
    existed = os.path.isfile(MOYU_POINTS_FILE)
    raw = {}
    if existed:
        try:
            with open(MOYU_POINTS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            raw = {}
    store = _normalize_moyu_store(raw)
    have = {it["key"] for it in store["items"]}
    changed = False
    if not store["items"]:
        store["items"] = [
            {"key": k, "label": lab, "scope": "yanyun_moyu",
             "portrait": None, "landscape": None}
            for k, lab in MOYU_POINT_KEYS
        ]
        changed = True
    else:
        is_v2plus = isinstance(raw, dict) and int(raw.get("version") or 0) >= 2
        if not is_v2plus:
            for k, lab in MOYU_POINT_KEYS:
                if k not in have:
                    store["items"].append({
                        "key": k, "label": lab, "scope": "yanyun_moyu",
                        "portrait": None, "landscape": None,
                    })
                    changed = True
    if _ensure_back_button_migrated(store):
        changed = True
    ver = int(raw.get("version") or 0) if isinstance(raw, dict) else 0
    if changed or (existed and ver < 3):
        write_moyu_store(store)
    return store


def write_moyu_store(store):
    ensure_dirs()
    items = []
    for it in (store or {}).get("items") or []:
        if not isinstance(it, dict) or not it.get("key"):
            continue
        row = {
            "key": it["key"],
            "label": (it.get("label") or it["key"]).strip() or it["key"],
            "scope": (it.get("scope") or "shared").strip() or "shared",
        }
        for orient in ("portrait", "landscape"):
            slot = _copy_orient_slot(it.get(orient))
            if slot:
                slot["fx"] = round(float(slot["fx"]), 4)
                slot["fy"] = round(float(slot["fy"]), 4)
                if slot.get("cg_x") is not None:
                    slot["cg_x"] = round(float(slot["cg_x"]), 1)
                    slot["cg_y"] = round(float(slot["cg_y"]), 1)
                row[orient] = slot
        items.append(row)
    data = {"version": 3, "items": items}
    with open(MOYU_POINTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def save_moyu_point(key, fx, fy, orient=None, cg=None, outer=None):
    """用手点手势保存某一步的准确坐标（含 cg + outer 锚点）。"""
    key = (key or "").strip()
    if not key:
        return None
    if orient is None:
        orient = current_orientation()
    store = load_moyu_points()
    found = None
    for it in store["items"]:
        if it["key"] == key:
            found = it
            break
    if not found:
        scope = "yanyun_login" if key == "back_button" else "yanyun_moyu"
        found = {
            "key": key,
            "label": dict(MOYU_POINT_KEYS).get(key) or ("关公告返回键" if key == "back_button" else key),
            "scope": scope,
            "portrait": None,
            "landscape": None,
        }
        store["items"].append(found)
    if outer is None:
        info = window_info()
        if info:
            ox, oy, ow, oh = info["outer"]
            outer = {"x": ox, "y": oy, "w": ow, "h": oh}
    if cg is None:
        pt = outer_to_screen(fx, fy)
        if pt:
            cg = pt
    found[orient] = _orient_payload(fx, fy, cg=cg, outer=outer)
    write_moyu_store(store)
    label = found.get("label") or key
    log("INFO", "已校准「%s」%s点位：%.4f, %.4f（含 cg/outer 锚点）" % (
        label, "竖屏" if orient == "portrait" else "横屏", float(fx), float(fy),
    ))
    return found[orient]


def get_moyu_point_slot(key):
    """读当前方向下手校 slot dict（含 fx/fy/cg/outer），没有则 None。"""
    key = (key or "").strip()
    if not key:
        return None
    store = load_moyu_points()
    found = None
    for it in store["items"]:
        if it["key"] == key:
            found = it
            break
    if not found:
        return None
    orient = current_orientation()
    item = found.get(orient) or found.get("portrait") or found.get("landscape")
    if not isinstance(item, dict) or item.get("fx") is None:
        return None
    return item


def get_moyu_point(key):
    """读当前方向下手校 outer 相对坐标 (fx, fy)。回放请用 resolve_moyu_tap。"""
    item = get_moyu_point_slot(key)
    if not item:
        return None
    try:
        return float(item["fx"]), float(item["fy"])
    except Exception:
        return None


def resolve_moyu_tap(key):
    """手校回放：优先 cg+outer 位移，尺寸变了退 fx/fy。

    返回 (fx, fy, step_dict) 或 None；step_dict 可直接交给 tap_point(..., step=)。
    """
    item = get_moyu_point_slot(key)
    if not item:
        return None
    orient = current_orientation()
    step = {
        "fx": float(item["fx"]),
        "fy": float(item["fy"]),
    }
    if item.get("cg_x") is not None and item.get("cg_y") is not None:
        step["cg_x"] = float(item["cg_x"])
        step["cg_y"] = float(item["cg_y"])
    if isinstance(item.get("outer"), dict):
        step["outer"] = dict(item["outer"])
    info = window_info()
    m = current_metrics(info=info) or (metrics_for_click(info) if info else None)
    mode = "fxfy"
    if m:
        mode = coordlib.resolve_mode(step, m)
        sx, sy = coordlib.resolve_screen(step, m)
        fx, fy = coordlib.screen_to_outer(sx, sy, m)
    else:
        fx, fy = step["fx"], step["fy"]
    log("INFO", "手校回放 key=%s orient=%s mode=%s outer=%.3f,%.3f" % (
        key, orient, mode, fx, fy,
    ))
    return fx, fy, step


def moyu_points_summary():
    store = load_moyu_points()
    out = []
    orient = current_orientation()
    for it in store["items"]:
        item = it.get(orient) or {}
        out.append({
            "key": it["key"],
            "label": it.get("label") or it["key"],
            "scope": it.get("scope") or "shared",
            "fx": item.get("fx") if isinstance(item, dict) else None,
            "fy": item.get("fy") if isinstance(item, dict) else None,
            "has_anchor": bool(
                isinstance(item, dict)
                and item.get("cg_x") is not None
                and isinstance(item.get("outer"), dict)
            ),
            "orient": orient,
            "ok": isinstance(item, dict) and item.get("fx") is not None,
        })
    return out


def moyu_point_label(key):
    key = (key or "").strip()
    for it in load_moyu_points()["items"]:
        if it["key"] == key:
            return it.get("label") or key
    if key == "back_button":
        return "关公告返回键"
    return dict(MOYU_POINT_KEYS).get(key) or key


def add_moyu_point(label, scope="shared"):
    label = (label or "").strip()
    if not label:
        return None, "请填写名称"
    store = load_moyu_points()
    existing = {it["key"] for it in store["items"]}
    for it in store["items"]:
        if (it.get("label") or "") == label:
            return it, ""
    key = _slug_key(label, existing)
    item = {
        "key": key, "label": label, "scope": (scope or "shared").strip() or "shared",
        "portrait": None, "landscape": None,
    }
    store["items"].append(item)
    write_moyu_store(store)
    log("INFO", "手校新增「%s」(%s)" % (label, key))
    return item, ""


def rename_moyu_point(key, label):
    key = (key or "").strip()
    label = (label or "").strip()
    if not key:
        return False, "缺少 key"
    if not label:
        return False, "名称不能为空"
    store = load_moyu_points()
    for it in store["items"]:
        if it["key"] == key:
            it["label"] = label
            write_moyu_store(store)
            return True, ""
    return False, "找不到该点位"


def delete_moyu_point(key):
    key = (key or "").strip()
    if not key:
        return False, "缺少 key"
    store = load_moyu_points()
    before = len(store["items"])
    store["items"] = [it for it in store["items"] if it["key"] != key]
    if len(store["items"]) == before:
        return False, "找不到该点位"
    write_moyu_store(store)
    log("INFO", "手校已删除：%s" % key)
    return True, ""


def clear_moyu_point_coords(key, orient=None):
    """只清坐标，保留条目，方便重校。"""
    key = (key or "").strip()
    if not key:
        return False, "缺少 key"
    if orient is None:
        orient = current_orientation()
    store = load_moyu_points()
    for it in store["items"]:
        if it["key"] == key:
            it[orient] = None
            write_moyu_store(store)
            return True, ""
    return False, "找不到该点位"


def move_moyu_point(key, direction):
    """direction: -1 上移 / 1 下移"""
    key = (key or "").strip()
    direction = int(direction or 0)
    if not key or direction == 0:
        return False, "参数无效"
    store = load_moyu_points()
    items = store["items"]
    idx = next((i for i, it in enumerate(items) if it["key"] == key), -1)
    if idx < 0:
        return False, "找不到该点位"
    j = idx + (1 if direction > 0 else -1)
    if j < 0 or j >= len(items):
        return True, ""
    items[idx], items[j] = items[j], items[idx]
    write_moyu_store(store)
    return True, ""


def reorder_moyu_points(keys):
    """按 keys 顺序重排；未出现的追加在后。"""
    if not isinstance(keys, list):
        return False, "order 必须是列表"
    store = load_moyu_points()
    by_key = {it["key"]: it for it in store["items"]}
    ordered = []
    seen = set()
    for k in keys:
        k = (k or "").strip()
        if k in by_key and k not in seen:
            ordered.append(by_key[k])
            seen.add(k)
    for it in store["items"]:
        if it["key"] not in seen:
            ordered.append(it)
    store["items"] = ordered
    write_moyu_store(store)
    return True, ""


def load_back_calibrate():
    if not os.path.isfile(BACK_CALIB_FILE):
        return {}
    try:
        with open(BACK_CALIB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_back_calibrate(fx, fy, orient=None, cg=None, outer=None):
    """兼容旧调用：写入统一点位表 key=back_button。"""
    return save_moyu_point("back_button", fx, fy, orient=orient, cg=cg, outer=outer)


def calibrated_back_button():
    """读关公告返回坐标；明显离谱的校准会忽略。"""
    pt = get_moyu_point("back_button")
    if not pt:
        data = load_back_calibrate()
        key = current_orientation()
        item = data.get(key)
        if not item:
            return None
        try:
            pt = float(item["fx"]), float(item["fy"])
        except Exception:
            return None
    fx, fy = pt
    near_corner = (
        (fx >= 0.70 or fx <= 0.30) and (fy <= 0.30 or fy >= 0.70)
    )
    if not near_corner:
        log("DEBUG", "忽略离谱校准返回 %.3f,%.3f（不像四角关闭键）" % (fx, fy))
        return None
    return fx, fy


def fallback_back_button():
    """按当前窗口方向选返回坐标：校准值 > 内置兜底。"""
    calib = calibrated_back_button()
    if calib:
        return calib
    if is_portrait_window():
        return BACK_BUTTON_PORT
    return BACK_BUTTON_LAND


def find_back_button(min_score=None):
    cfg = match_defaults()
    # 黑底浅色关闭键：阈值略放宽
    score = float(min_score if min_score is not None else min(0.60, cfg["back_min_score"]))
    templates = back_templates()
    if not templates:
        return None
    return find_icon(templates[0], score, extra_templates=templates[1:])


def find_continue_icon(min_score=0.62):
    templates = continue_templates()
    if not templates:
        return None
    return find_icon(templates[0], float(min_score), extra_templates=templates[1:])


def continue_fallback_point():
    if is_portrait_window():
        return CONTINUE_POINT_PORT
    return CONTINUE_POINT_LAND


def back_button_pos():
    # 用户校准优先于图标识别
    calib = calibrated_back_button()
    if calib:
        return calib
    hit = find_back_button()
    if hit:
        return hit[0], hit[1]
    cfg = match_defaults()
    if not cfg["allow_fallback"]:
        return None
    return fallback_back_button()


def unique_points(points):
    seen = set()
    out = []
    for item in points:
        if not item or len(item) < 2:
            continue
        fx, fy = float(item[0]), float(item[1])
        key = (round(fx, 3), round(fy, 3))
        if key in seen:
            continue
        if not in_window_safe(fx, fy):
            continue
        seen.add(key)
        out.append((fx, fy))
    return out


def find_back_by_ocr(items):
    """图标失败时用 OCR 找「返回」。"""
    words = ["返回", "关闭", "Back"]
    hit = match_app_item(items, words)
    if not hit:
        return None
    fx = float(hit.get("x") or 0) + float(hit.get("w") or 0) / 2.0
    fy = float(hit.get("y") or 0) + float(hit.get("h") or 0) / 2.0
    if not in_window_safe(fx, fy):
        return None
    log("INFO", "OCR 找到「%s」→ %.3f, %.3f" % (hit.get("text"), fx, fy))
    return fx, fy, hit


def right_back_points(items, allow_fallback=True):
    # 校准坐标放第一个，关公告优先点
    calib = calibrated_back_button() or (fallback_back_button() if allow_fallback else None)
    points = []
    if calib:
        fx, fy = calib
        points.extend([
            (fx, fy),
            (fx - 0.01, fy),
            (fx + 0.01, fy),
            (fx, fy - 0.01),
            (fx, fy + 0.01),
        ])
    hit = find_back_button()
    if hit:
        fx, fy, score = hit
        points.extend([
            (fx, fy),
            (fx - 0.01, fy),
            (fx + 0.01, fy),
        ])
    ocr = find_back_by_ocr(items)
    if ocr:
        fx, fy, _ = ocr
        points.extend([(fx, fy), (fx - 0.015, fy), (fx + 0.015, fy)])
    out = unique_points(points)
    if out:
        return out
    if not allow_fallback:
        log("WARN", "返回图标与 OCR 都失败，不使用兜底坐标")
        return []
    fx, fy = fallback_back_button()
    orient = "竖屏" if is_portrait_window() else "横屏"
    log("WARN", "没识别到返回，用%s兜底 %.4f, %.4f" % (orient, fx, fy))
    return unique_points([
        (fx, fy),
        (fx - 0.02, fy),
        (fx + 0.02, fy),
        (fx, fy - 0.03),
        (fx, fy + 0.03),
    ])


def raw_click_screen(x, y, tag=""):
    """遍历点击：先置前镜像，再用 soft HID；避免点到脚本合集。"""
    if not ensure_click_bin():
        return False
    pid = get_mirror_pid()
    if not pid:
        return False
    ensure_mirror_front(force=True)
    time.sleep(0.06)
    log("INFO", "遍历点击 screen=%.1f,%.1f%s" % (float(x), float(y), (" " + tag) if tag else ""))
    code, out, err = run_cmd([CLICK_BIN, "--hid-nowarp", str(x), str(y)], timeout=8)
    if code != 0:
        code, out, err = run_cmd([CLICK_BIN, str(pid), str(x), str(y)], timeout=8)
    if code != 0:
        log("WARN", "遍历点击失败: %s" % (err or out))
        return False
    return True


def _grid_points(x0, y0, x1, y1, cols, rows):
    pts = []
    cols = max(1, int(cols))
    rows = max(1, int(rows))
    for r in range(rows):
        for c in range(cols):
            if cols == 1:
                fx = (x0 + x1) / 2.0
            else:
                fx = x0 + (x1 - x0) * c / float(cols - 1)
            if rows == 1:
                fy = (y0 + y1) / 2.0
            else:
                fy = y0 + (y1 - y0) * r / float(rows - 1)
            pts.append((fx, fy))
    return pts


def sweep_clicks(step):
    """全屏网格遍历：红点可见地从左→右、从上→下移动，再点击。
    每点更新界面红点 + 屏幕悬浮红点，便于确认是否在扫。
    """
    stop_when = [k for k in (step.get("stop_when") or ["继续游戏", "选择角色"]) if k]
    still_when = [k for k in (step.get("when") or [
        "更新公告", "版本更新", "十六巷", "白露沾衣", "在线修复", "芳草意",
    ]) if k]
    interval = float(step.get("interval") if step.get("interval") is not None else 0.45)
    show_ms = float(step.get("show_ms") if step.get("show_ms") is not None else 0.35)
    # 默认很少 OCR，避免 screencapture 反复弹「屏幕录制」
    ocr_every = int(step.get("ocr_every") if step.get("ocr_every") is not None else 8)
    show_dot = bool(step.get("show_dot", True))
    cols = int(step.get("cols") if step.get("cols") is not None else 6)
    rows = int(step.get("rows") if step.get("rows") is not None else 8)
    # 默认：整窗从左到右、从上到下（略缩边，避免标题栏）
    regions = step.get("regions") or [
        {
            "name": "全屏左到右上到下",
            "x0": 0.08, "y0": 0.06, "x1": 0.92, "y1": 0.92,
            "cols": cols, "rows": rows,
        },
        {
            "name": "右上关闭区加扫",
            "x0": 0.72, "y0": 0.05, "x1": 0.94, "y1": 0.28,
            "cols": 5, "rows": 4,
        },
    ]
    set_phase("game_announcement")
    set_overlay_unlocked_for_clicks()
    ensure_mirror_front(force=True)
    log("INFO", "开始全屏遍历：红点左→右/上→下（少截图，避免弹权限）")
    if show_dot:
        show_screen_dot(100, 100)

    # 开头识图一次即可，不在每点都截
    items0 = ocr_items(accurate=True)
    if match_app_item(items0, stop_when) and not match_app_item(items0, still_when):
        log("INFO", "遍历前已是继续游戏画面，跳过")
        hide_screen_dot()
        set_phase("game_playing")
        return True

    n = 0
    try:
        for reg in regions:
            if should_stop():
                return False
            name = reg.get("name") or "区域"
            pts = _grid_points(
                float(reg.get("x0") or 0.1), float(reg.get("y0") or 0.1),
                float(reg.get("x1") or 0.9), float(reg.get("y1") or 0.9),
                reg.get("cols") or cols, reg.get("rows") or rows,
            )
            log("INFO", "遍历「%s」共 %s 点（左→右，上→下）" % (name, len(pts)))
            for fx, fy in pts:
                if not wait_if_paused():
                    return False
                n += 1
                info = window_info()
                if not info:
                    log("WARN", "无窗口，遍历中止")
                    return False
                m = metrics_for_click(info) or current_metrics(info=info)
                if m:
                    sx, sy = coordlib.outer_to_screen(fx, fy, m)
                    spx, spy = coordlib.screen_to_shot(sx, sy, m)
                else:
                    pt = point_in_window(fx, fy)
                    if not pt:
                        continue
                    sx, sy = pt
                    spx = spy = 0
                # 先亮红点，让你看清位置，再点
                if show_dot:
                    show_screen_dot(sx, sy)
                set_last_click(fx, fy, sx, sy, spx, spy, source="sweep")
                log("INFO", "红点 #%s/%s → 左到右上到下 outer=%.3f,%.3f screen=%.0f,%.0f" % (
                    n, len(pts), fx, fy, sx, sy))
                if not sleep_wait(show_ms):
                    return False
                raw_click_screen(sx, sy, tag="#%s" % n)
                if not sleep_wait(interval):
                    return False
                if ocr_every > 0 and (n % ocr_every == 0):
                    items = ocr_items(accurate=True)
                    names = [i.get("text") for i in items if i.get("text")]
                    if names:
                        log("INFO", "遍历后识图: %s" % "、".join(names[:10]))
                    if match_app_item(items, stop_when) and not match_app_item(items, still_when):
                        save_shot("sweep_done", click=(fx, fy))
                        log("INFO", "遍历命中：已看到继续游戏（第 %s 次）" % n)
                        set_phase("game_playing")
                        return True
        save_shot("sweep_timeout")
        log("WARN", "全屏遍历结束仍未确认关掉公告（共点 %s 次）" % n)
        items = ocr_items(accurate=True)
        if match_app_item(items, stop_when):
            set_phase("game_playing")
            return True
        return not step.get("required", True)
    finally:
        hide_screen_dot()


def close_popups(step):
    timeout = float(step.get("timeout") or 50)
    interval = float(step.get("interval") if step.get("interval") is not None else 1.0)
    max_fail = int(step.get("max_retry") or match_defaults()["max_fail"])
    allow_fallback = bool(step.get("allow_fallback", match_defaults()["allow_fallback"]))
    icon_first = bool(step.get("icon_first", True))
    when = [k for k in (step.get("when") or [
        "更新公告", "版本更新", "玩法内容", "白露沾衣",
        "不删档", "游侠请", "十六巷", "在线修复", "芳草意",
    ]) if k]
    stop_when = [k for k in (step.get("stop_when") or ["继续游戏", "选择角色"]) if k]
    close_words = [k for k in (step.get("close_words") or ["关闭", "我知道了", "知道了"]) if k]
    extra_points = step.get("points") or []
    clk = click_defaults()
    auto_tries = int(step.get("auto_tries") if step.get("auto_tries") is not None else clk["auto_tries"])
    manual_timeout = float(step.get("manual_timeout") if step.get("manual_timeout") is not None else clk["manual_timeout"])
    log("INFO", "关闭弹窗：识图点关闭图标（间隔 %.1fs，不再遍历）" % interval)
    set_overlay_unlocked_for_clicks()
    ensure_mirror_large()
    set_phase("game_announcement")
    end = time.time() + timeout
    n = 0
    fail_n = 0
    saw_page = False
    last_blob = ""
    assisted = False

    def announcement_cleared():
        items2 = ocr_items(accurate=True)
        ready2 = bool(match_app_item(items2, stop_when))
        still = bool(match_app_item(items2, when))
        return ready2 and not still

    # 先进图标：不等 OCR，反应约 1 秒
    if icon_first and not capture_denied():
        if capture_window(force=False):
            icon0 = find_back_button(min_score=0.58)
            if icon0:
                fx, fy, score = icon0
                save_shot("close_icon_first", click=(fx, fy))
                log("INFO", "先点公告关闭图标 %.3f,%.3f（相似度 %.2f）" % (fx, fy, score))
                tap_point(fx, fy)
                if not sleep_wait(interval):
                    return False
                items0 = ocr_items(accurate=True, recapture=True)
                if match_app_item(items0, stop_when) and not match_app_item(items0, when):
                    save_shot("close_done")
                    log("INFO", "已关掉公告，画面上有「继续游戏」")
                    set_phase("game_playing")
                    return True

    while time.time() < end:
        if not wait_if_paused():
            return False
        if wrong_app_cooling():
            time.sleep(0.5)
            continue
        if capture_denied():
            log("WARN", "关公告：截图权限冷却中，跳过识图，先按图标/兜底点关闭")
            # 不 OCR，只试图标（复用旧图）或兜底坐标，避免再弹权限
            icon = find_back_button(min_score=0.68) if screenshot_fresh(30) else None
            if icon:
                fx, fy, score = icon
                log("INFO", "权限冷却中仍点关闭图标 %.3f,%.3f" % (fx, fy))
                tap_point(fx, fy)
            else:
                fx, fy = fallback_back_button()
                log("INFO", "权限冷却中点兜底关闭 %.3f,%.3f" % (fx, fy))
                tap_point(fx, fy)
            time.sleep(interval)
            fail_n += 1
            if fail_n >= 3:
                log("WARN", "截图权限未就绪，关公告提前结束（请勾选屏幕录制后重跑）")
                return not step.get("required", True)
            continue
        # 一轮只截一次：OCR + 图标共用
        if not capture_window(force=False):
            time.sleep(interval)
            continue
        items = ocr_items(accurate=True, recapture=False)
        names = [i.get("text") for i in items if i.get("text")]
        blob = "、".join(names[:16])
        if blob and blob != last_blob:
            log("INFO", "识图: %s" % blob)
            last_blob = blob
        on_announcement = bool(match_app_item(items, when))
        ready = bool(match_app_item(items, stop_when))
        splash = match_app_item(items, [
            "光敏", "癫痫", "详细阅读", "抵制不良游戏", "适度游戏", "健康上网",
        ])
        if splash and not ready and not on_announcement:
            save_shot("close_splash")
            log("INFO", "点掉开屏提示：「%s」" % (splash.get("text") or "健康提示"))
            tap_point(0.50, 0.82)
            time.sleep(interval)
            continue
        if ready and not on_announcement:
            save_shot("close_done")
            log("INFO", "已关掉公告，画面上有「继续游戏」")
            set_phase("game_playing")
            return True
        if not on_announcement and not ready:
            wrong = is_wrong_app(items)
            if wrong == "connecting":
                wait_until_connected(12)
                continue
            if wrong:
                note_wrong_app(wrong)
                save_shot("close_wrong_app")
                go_home()
                record_error("关公告时进错 App", wrong)
                return False
            if not saw_page:
                save_shot("close_waiting")
            time.sleep(interval)
            continue
        saw_page = True

        # 自动点几次仍无效 → 人机接力（官方镜像最稳的做法）
        if clk["mode"] == "assist" and fail_n >= auto_tries and not assisted:
            assisted = True
            icon = find_back_button(min_score=0.70)
            where = ""
            if icon:
                where = "（红点大约在 %.0f%% , %.0f%%）" % (icon[0] * 100, icon[1] * 100)
            ok = wait_manual_action(
                "请用鼠标点镜像里公告右上角关闭「«」%s" % where,
                announcement_cleared,
                timeout=manual_timeout,
                interval=interval,
            )
            if ok:
                save_shot("close_manual_ok")
                set_phase("game_playing")
                return True
            save_shot("close_manual_timeout")
            record_error("关闭弹窗：等待手动点击超时")
            return not step.get("required", True)

        calib = calibrated_back_button()
        builtin = fallback_back_button()
        icon = find_back_button(min_score=0.68)
        hit = match_app_item(items, close_words)
        ocr_back = find_back_by_ocr(items) if not icon else None
        acted = False
        if icon:
            fx, fy, score = icon
            save_shot("close_icon", click=(fx, fy))
            log("INFO", "点公告关闭图标 %.3f, %.3f（相似度 %.2f）" % (fx, fy, score))
            acted = tap_point(fx, fy)
            if acted and fail_n >= 1:
                time.sleep(0.35)
                for dx, dy in ((-0.02, 0), (0.02, 0), (0, -0.02), (0, 0.02)):
                    if should_stop():
                        break
                    tap_point(max(0.02, min(0.98, fx + dx)), max(0.02, min(0.98, fy + dy)))
                    time.sleep(0.2)
        elif calib and fail_n < 2:
            fx, fy = calib
            save_shot("close_calib", click=(fx, fy))
            log("INFO", "点校准返回按钮 %.4f, %.4f" % (fx, fy))
            acted = tap_point(fx, fy)
        elif ocr_back:
            fx, fy, raw = ocr_back
            save_shot("close_ocr_back", click=(fx, fy))
            log("INFO", "点 OCR「%s」%.3f, %.3f" % (raw.get("text"), fx, fy))
            acted = tap_point(fx, fy)
        elif hit:
            save_shot("close_word", click=(
                hit.get("x", 0) + hit.get("w", 0) / 2.0,
                hit.get("y", 0) + hit.get("h", 0) / 2.0,
            ))
            log("INFO", "点选「%s」" % (hit.get("text") or "关闭"))
            acted = tap_ocr_item(hit, 0)
        else:
            fx, fy = builtin
            save_shot("close_before", click=(fx, fy))
            log("INFO", "点返回兜底 %.4f, %.4f" % (fx, fy))
            acted = tap_point(fx, fy)
            n += 1
        if not acted:
            fail_n += 1
        time.sleep(interval)
        # 点后再识一次（复用冷却策略）
        if not capture_denied():
            capture_window(force=False)
            after = ocr_items(accurate=True, recapture=False)
            save_shot("close_after")
            if match_app_item(after, stop_when) and not match_app_item(after, when):
                log("INFO", "点击后已看到继续游戏")
                set_phase("game_playing")
                return True
        fail_n += 1
        if fail_n >= max_fail and clk["mode"] != "assist":
            save_shot("close_retry_exhausted")
            record_error("关闭弹窗重试耗尽", "失败 %s 次" % fail_n)
            return not step.get("required", True)
    save_shot("close_timeout")
    log("WARN", "关闭弹窗超时，公告还在")
    return not step.get("required", True)


def silent_click_center():
    if not ensure_click_bin():
        return False
    pid = get_mirror_pid()
    pt = outer_to_screen(0.5, 0.55)
    if not pid or not pt:
        return False
    log_window_geom("click_center")
    return silent_click_screen(pt[0], pt[1], tag="center")


def silent_type_pin():
    if not ensure_click_bin():
        return False
    pid = get_mirror_pid()
    if not pid:
        return False
    code, out, err = run_cmd([CLICK_BIN, "--type-pin", str(pid)], timeout=15)
    if code != 0:
        record_error("自动输入锁屏密码失败", err or out)
        return False
    return True


def try_unlock():
    pin = get_passcode()
    if not pin:
        record_error("钥匙串里没有锁屏密码", "请运行: python3 mirror_keeper.py --set-passcode")
        return False
    if not silent_click_center():
        log("WARN", "锁屏点击未成功，仍尝试输入密码")
    time.sleep(0.4)
    if not silent_type_pin():
        return False
    log("INFO", "已向镜像窗口模拟发送锁屏密码（不移动你的鼠标）")
    time.sleep(1.2)
    return True


def load_config_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        data["_path"] = path
        return data
    except Exception as e:
        log("WARN", "读取配置失败 %s: %s" % (path, e))
        return None


def _iter_config_json_paths():
    """根目录 + configs/燕云|星穹铁道 子目录里的脚本。"""
    if not os.path.isdir(CONFIG_DIR):
        return
    skip = ("common.json", "catalog.json", "keep_alive.json")
    for name in sorted(os.listdir(CONFIG_DIR)):
        path = os.path.join(CONFIG_DIR, name)
        if name.endswith(".json"):
            if name in skip or name.startswith("_"):
                continue
            yield path
            continue
        if not os.path.isdir(path) or name.startswith(".") or name == "icons":
            continue
        for sub in sorted(os.listdir(path)):
            if not sub.endswith(".json") or sub.startswith("_"):
                continue
            yield os.path.join(path, sub)


def list_configs():
    items = []
    for path in _iter_config_json_paths():
        data = load_config_file(path)
        if data:
            items.append(data)
    return items


def group_display_name(group_id):
    mapping = {
        "yanyun": "燕云十六声",
        "starrail": "星穹铁道",
        "record": "手点录制",
    }
    return mapping.get(group_id) or group_id


def clear_all_hand_recordings():
    """清空未整理/已录制的手点数据目录。"""
    n = 0
    if not os.path.isdir(RECORD_DIR):
        return 0
    for name in list(os.listdir(RECORD_DIR)):
        path = os.path.join(RECORD_DIR, name)
        if not os.path.isdir(path):
            continue
        try:
            shutil.rmtree(path)
            n += 1
        except Exception as e:
            log("WARN", "删除录制目录失败 %s: %s" % (name, e))
    return n


def _is_recorded_script(cfg):
    """手点录制保存的脚本（可删除）。"""
    if not cfg:
        return False
    sid = str(cfg.get("id") or "")
    if sid.startswith("rec_"):
        return True
    for step in (cfg.get("steps") or []):
        if (step or {}).get("type") == "replay_recording":
            return True
    return False


def delete_script(script_id):
    """删除手动录制脚本：配置 + 录制数据。内置脚本不可删。"""
    sid = (script_id or "").strip()
    if not sid:
        return False, "缺少脚本 id"
    cfg = None
    for item in list_configs():
        if item.get("id") == sid:
            cfg = item
            break
    if not cfg:
        return False, "找不到脚本"
    if not _is_recorded_script(cfg):
        return False, "只能删除手动录制的脚本"
    # 录制数据目录
    rid = sid
    for step in (cfg.get("steps") or []):
        if step.get("recording_id"):
            rid = step.get("recording_id")
            break
    folder = os.path.join(RECORD_DIR, rid)
    path = cfg.get("_path") or ""
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except Exception as e:
            return False, "删除配置失败：%s" % e
    else:
        for group in ("yanyun", "starrail"):
            p = os.path.join(CONFIG_DIR, group, sid + ".json")
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception as e:
                    return False, "删除配置失败：%s" % e
    if os.path.isdir(folder):
        try:
            shutil.rmtree(folder)
        except Exception as e:
            log("WARN", "录制数据删除失败：%s" % e)
    log("INFO", "已删除手点脚本：%s" % sid)
    return True, ""


def list_groups():
    groups = [
        { "id": "yanyun", "name": "燕云十六声", "scripts": [] },
        { "id": "starrail", "name": "星穹铁道", "scripts": [] },
    ]
    path = os.path.join(CONFIG_DIR, "catalog.json")
    data = load_config_file(path)
    if data and data.get("groups"):
        groups = []
        for item in data.get("groups") or []:
            groups.append({
                "id": item.get("id"),
                "name": item.get("name") or item.get("id"),
                "scripts": [],
            })
    by_id = {}
    for g in groups:
        by_id[g["id"]] = g
    for cfg in list_configs():
        gid = cfg.get("group") or "other"
        if gid not in by_id:
            by_id[gid] = { "id": gid, "name": cfg.get("group_name") or gid, "scripts": [] }
            groups.append(by_id[gid])
        by_id[gid]["scripts"].append({
            "id": cfg.get("id"),
            "name": cfg.get("name") or cfg.get("id"),
            "description": cfg.get("description") or "",
            "order": int(cfg.get("order") or 99),
            "deletable": _is_recorded_script(cfg),
            "recorded": _is_recorded_script(cfg),
        })
    for g in groups:
        g["scripts"].sort(key=lambda s: (s.get("order") if isinstance(s.get("order"), int) else 99, s.get("name") or ""))
    return groups


def load_common():
    path = os.path.join(CONFIG_DIR, "common.json")
    data = load_config_file(path)
    if data:
        return data
    return {
        "steps": [
            { "type": "ensure_mirror" },
            { "type": "unlock_if_needed" },
            { "type": "go_home", "hotkey": "cmd-1", "click_bar": True },
            { "type": "open_search" },
        ]
    }


def ocr_items(accurate=False, recapture=True):
    if not ensure_ocr_bin():
        return []
    if capture_denied():
        return []
    if recapture:
        if not capture_window(force=False):
            return []
    elif not (os.path.isfile(SCREENSHOT) and os.path.getsize(SCREENSHOT) > 1000):
        if not capture_window(force=False):
            return []
    args = [OCR_BIN, "--boxes"]
    if accurate:
        args.append("--accurate")
    args.append(SCREENSHOT)
    code, out, err = run_cmd(args, timeout=20 if accurate else 12)
    if code != 0:
        log("WARN", "OCR 识别失败: %s" % (err or out))
        return []
    items = []
    for line in (out or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        try:
            items.append({
                "text": parts[0].strip(),
                "x": float(parts[1]),
                "y": float(parts[2]),
                "w": float(parts[3]),
                "h": float(parts[4]),
            })
        except Exception:
            continue
    return items


def silent_click_at(x, y):
    """与 silent_click_screen 同一条注入路径（登录 OCR 以前走这里）。"""
    return silent_click_screen(x, y, tag="(at)")


def silent_drag(x1, y1, x2, y2):
    if not ensure_click_bin():
        return False
    pid = get_mirror_pid()
    if not pid:
        return False
    code, out, err = run_cmd([
        CLICK_BIN, "--drag", str(pid),
        str(x1), str(y1), str(x2), str(y2),
    ], timeout=8)
    if code != 0:
        log("WARN", "模拟滑动失败: %s" % (err or out))
        return False
    return True


def silent_swipe_scroll(x, y, dx):
    if not ensure_click_bin():
        return False
    code, out, err = run_cmd([
        CLICK_BIN, "--swipe", str(x), str(y), str(dx),
    ], timeout=8)
    if code != 0:
        log("WARN", "模拟翻页失败: %s" % (err or out))
        return False
    return True


def send_hotkey(name, focus=False):
    if not ensure_click_bin():
        return False
    pid = get_mirror_pid()
    if not pid:
        return False
    if focus:
        bring_front()
        time.sleep(0.12)
    code, out, err = run_cmd([CLICK_BIN, "--hotkey", str(pid), name], timeout=8)
    if code != 0:
        log("WARN", "快捷键失败: %s" % (err or out))
        return False
    return True


# 镜像窗口太小 OCR/图标容易糊；目标高度约一掌机大小
MIRROR_MIN_H = 620
MIRROR_MIN_W = 280


def ensure_mirror_large(min_h=None, min_w=None, max_zoom=6, to_max=False):
    """窗口偏小时用「显示 → 放大」(⌘+)；to_max=True 时一直放到不再变大。"""
    info = window_info()
    if not info:
        return False
    ow, oh = float(info["outer"][2]), float(info["outer"][3])
    landscape = ow >= oh
    # 横屏本身就矮，不能用竖屏高度阈值
    if min_h is None:
        min_h = 480 if landscape else MIRROR_MIN_H
    if min_w is None:
        min_w = 900 if landscape else MIRROR_MIN_W
    min_h = int(min_h)
    min_w = int(min_w)
    if (not to_max) and oh >= min_h and ow >= min_w:
        log("INFO", "镜像窗口尺寸 OK：%sx%s" % (int(ow), int(oh)))
        return True
    if to_max:
        log("INFO", "镜像窗口放大到最大（当前 %sx%s）…" % (int(ow), int(oh)))
    else:
        log("INFO", "镜像窗口偏小 %sx%s，正在放大以便识图…" % (int(ow), int(oh)))
    last = (int(ow), int(oh))
    stable = 0
    start_area = ow * oh
    rounds = 16 if to_max else max_zoom
    for i in range(rounds):
        text = osascript("larger")
        if text.startswith("ERR"):
            if not send_hotkey("cmd-+", focus=True):
                break
        time.sleep(0.4)
        info = window_info()
        if not info:
            break
        ow, oh = float(info["outer"][2]), float(info["outer"][3])
        cur = (int(ow), int(oh))
        log("INFO", "放大 %s/%s → %sx%s" % (i + 1, rounds, cur[0], cur[1]))
        # 放大过头偶发变成断线竖屏小窗，立刻停
        if ow * oh < start_area * 0.55:
            log("WARN", "放大后窗口异常缩小，停止放大")
            break
        if to_max:
            if cur == last:
                stable += 1
                if stable >= 2:
                    log("INFO", "镜像已到最大：%sx%s" % cur)
                    return True
            else:
                stable = 0
                last = cur
            continue
        if oh >= min_h and ow >= min_w:
            log("INFO", "镜像窗口已放大到 %sx%s" % (int(ow), int(oh)))
            return True
    log("WARN", "镜像仍偏小 %sx%s，可手动：镜像菜单「显示 → 放大」" % (int(ow), int(oh)))
    return False


def ensure_mirror_max():
    """尽量放大镜像窗口。"""
    ensure_mirror_front(force=True)
    return ensure_mirror_large(to_max=True)


def send_text(text, focus=False):
    if not text:
        return True
    if not ensure_click_bin():
        return False
    pid = get_mirror_pid()
    if not pid:
        return False
    if focus:
        bring_front()
        time.sleep(0.2)
    code, out, err = run_cmd([CLICK_BIN, "--type-text", str(pid), text], timeout=20)
    if code != 0:
        log("WARN", "模拟输入失败: %s" % (err or out))
        return False
    return True


def window_rect():
    """外层窗口（含标题栏），与截图、遮罩、点击同一套。"""
    info = window_info()
    if not info:
        return None
    return info["outer"]


def point_in_window(fx, fy):
    """整窗归一化坐标 → 屏幕绝对坐标。"""
    return outer_to_screen(fx, fy)


def ensure_mirror_ready():
    if not process_running():
        open_mirror()
        if not wait_window():
            log("WARN", "镜像窗口还没出来")
            return False
    elif not has_window():
        open_mirror()
        if not wait_window():
            log("WARN", "镜像窗口还没出来")
            return False
    if not wait_until_connected(20):
        return False
    return True


def unlock_if_needed():
    text = ocr_text()
    state = screen_state(text)
    log("INFO", "画面状态: %s" % state)
    if state == "connecting":
        if not wait_until_connected(25):
            return False
        text = ocr_text()
        state = screen_state(text)
    if state == "lock":
        return try_unlock()
    return True


SEARCH_SCREEN_WORDS = ["搜索", "Search", "Siri建议", "Siri 建议"]
HOME_SCREEN_WORDS = [
    "天气", "日历", "照片", "相机", "设置", "时钟", "地图",
    "电话", "信息", "资料库", "备忘录", "文件", "提醒事项",
    "钱包", "家庭", "App Store",
]
IN_APP_WORDS = ["继续游戏", "更新公告", "进入江湖", "选择角色", "版本更新", "玩法内容"]


def joined_ocr(items):
    return "".join((i.get("text") or "") for i in (items or [])).replace(" ", "")


def phone_screen_kind():
    land = is_landscape()
    items = ocr_items()
    blob = joined_ocr(items)
    names = [i.get("text") or "" for i in items]
    text = " ".join(names)
    if contains_any(text, LOCK_WORDS):
        return "lock"
    search_ok = ("搜索" in blob) or ("Search" in blob)
    if search_ok and (("取消" in blob) or ("Siri" in blob) or ("建议" in blob) or ("键盘" in blob)):
        return "search"
    if search_ok and not land:
        return "search"
    if contains_any(text, IN_APP_WORDS):
        return "app"
    if land:
        return "app"
    if not names:
        return "home"
    home_hits = 0
    for word in HOME_SCREEN_WORDS:
        if word.replace(" ", "") in blob:
            home_hits += 1
    if home_hits >= 1:
        return "home"
    short = [n for n in names if 1 <= len((n or "").replace(" ", "")) <= 6]
    if len(short) >= 6:
        return "home"
    return "app"


def swipe_up_home():
    start = point_in_window(0.5, 0.99)
    end = point_in_window(0.5, 0.38)
    if not start or not end:
        return False
    log("INFO", "从底部上滑，回到主屏幕")
    return silent_drag(start[0], start[1], end[0], end[1])


def swipe_down_search():
    start = point_in_window(0.5, 0.18)
    end = point_in_window(0.5, 0.68)
    if not start or not end:
        return False
    log("INFO", "在主屏幕下拉打开搜索")
    return silent_drag(start[0], start[1], end[0], end[1])


def go_home(step=None):
    step = step or {}
    log("INFO", "回到主屏幕")
    hotkey = step.get("hotkey") or "cmd-1"
    for i in range(4):
        if should_stop():
            log("WARN", "已终止，中断回主屏幕")
            return False
        send_hotkey(hotkey, focus=True)
        time.sleep(0.4)
        swipe_up_home()
        time.sleep(0.4)
        send_hotkey(hotkey, focus=True)
        time.sleep(0.35)
        if step.get("click_bar", True):
            pt = point_in_window(0.5, 0.96)
            if pt:
                # 必须 postToPid：HID 点屏幕底部容易点到「脚本合集」的终止按钮
                ensure_mirror_front(force=True)
                silent_click_at(pt[0], pt[1])
        time.sleep(0.8)
        kind = phone_screen_kind()
        log("INFO", "回主屏幕后画面：%s" % kind)
        if kind == "search":
            send_hotkey(hotkey, focus=True)
            time.sleep(0.5)
            kind = phone_screen_kind()
        if kind == "home":
            save_shot("at_home")
            return True
        log("INFO", "还在别的 App 里，再回一次主屏幕")
    save_shot("home_fail")
    log("WARN", "没确认回到主屏幕")
    return True


def open_search(step=None):
    log("INFO", "进入搜索页")
    bring_front()
    time.sleep(0.25)
    send_hotkey("cmd-3", focus=True)
    time.sleep(1.3)
    return True


def match_app_item(items, keywords):
    kws = [k for k in (keywords or []) if k and str(k).strip()]
    kws.sort(key=lambda s: len(str(s).replace(" ", "")), reverse=True)
    for kw in kws:
        kw2 = str(kw).replace(" ", "")
        for item in items:
            text = (item.get("text") or "").replace(" ", "")
            if not kw2 or kw2 not in text:
                continue
            if kw2 in ("同意", "同意并继续") and "不同意" in text:
                continue
            return item
    return None


def _item_center(item):
    return (
        float(item.get("x") or 0) + float(item.get("w") or 0) / 2.0,
        float(item.get("y") or 0) + float(item.get("h") or 0) / 2.0,
    )


def match_vertical_phrase(items, phrase="继续游戏", max_span=0.35):
    """竖排字常被拆成单字；按顺序拼回并取包围盒中心。"""
    phrase = (phrase or "").replace(" ", "")
    if not phrase or len(phrase) < 2:
        return None
    # 先整词命中
    hit = match_app_item(items, [phrase])
    if hit:
        return hit
    chars = list(phrase)
    bags = []
    for ch in chars:
        found = []
        for item in items:
            text = (item.get("text") or "").replace(" ", "")
            if ch in text and len(text) <= 3:
                found.append(item)
        if not found:
            return None
        bags.append(found)
    # 贪心：每个字选离上一个最近的
    best = None
    for first in bags[0]:
        chain = [first]
        cx, cy = _item_center(first)
        ok = True
        for bag in bags[1:]:
            nxt = None
            nd = 1e9
            for cand in bag:
                if cand in chain:
                    continue
                x, y = _item_center(cand)
                d = (x - cx) ** 2 + (y - cy) ** 2
                if d < nd:
                    nd = d
                    nxt = cand
            if not nxt:
                ok = False
                break
            nx, ny = _item_center(nxt)
            if abs(nx - cx) > max_span or abs(ny - cy) > max_span:
                # 允许沿竖列（x 接近）或横排（y 接近）延伸
                if not (abs(nx - cx) <= 0.12 or abs(ny - cy) <= 0.12):
                    ok = False
                    break
            chain.append(nxt)
            cx, cy = nx, ny
        if not ok or len(chain) < len(chars):
            continue
        xs = [float(i.get("x") or 0) for i in chain]
        ys = [float(i.get("y") or 0) for i in chain]
        x2 = [float(i.get("x") or 0) + float(i.get("w") or 0) for i in chain]
        y2 = [float(i.get("y") or 0) + float(i.get("h") or 0) for i in chain]
        box = {
            "text": phrase,
            "x": min(xs),
            "y": min(ys),
            "w": max(x2) - min(xs),
            "h": max(y2) - min(ys),
        }
        # 竖列优先：高度大于宽度
        score = box["h"] + box["w"]
        if best is None or score < best[0]:
            best = (score, box)
    return best[1] if best else None


def find_continue_target(items=None):
    """定位「继续游戏」：OCR整词/竖排单字 → 模板 → 横竖屏兜底点。"""
    if items is None:
        items = ocr_items(accurate=True) if not capture_denied() else []
    hit = match_vertical_phrase(items, "继续游戏")
    if hit:
        fx = float(hit["x"]) + float(hit["w"]) / 2.0
        fy = float(hit["y"]) + float(hit["h"]) / 2.0
        if in_window_safe(fx, fy):
            log("INFO", "OCR 定位继续游戏 %.3f,%.3f（%s）" % (
                fx, fy, "竖排拼字" if hit.get("w", 1) < hit.get("h", 0) else "整词"))
            return fx, fy, "ocr"
    if not capture_denied():
        icon = find_continue_icon(0.58)
        if icon:
            fx, fy, score = icon
            log("INFO", "模板定位继续游戏 %.3f,%.3f score=%.2f" % (fx, fy, score))
            return fx, fy, "icon"
    fx, fy = continue_fallback_point()
    orient = "竖屏" if is_portrait_window() else "横屏"
    log("INFO", "继续游戏用%s兜底 %.3f,%.3f" % (orient, fx, fy))
    return fx, fy, "fallback"


def wait_if_paused():
    while run_mode == "paused":
        if should_stop():
            return False
        time.sleep(0.2)
    return not should_stop()


def tap_ocr_item(hit, tap_above):
    """OCR 框是截图归一化坐标，必须经 metrics 换算到屏幕，不能直接乘 outer。"""
    fx = float(hit.get("x") or 0) + float(hit.get("w") or 0) / 2.0
    fy = float(hit.get("y") or 0) + float(hit.get("h") or 0) / 2.0
    fy = fy - float(tap_above or 0)
    m = current_metrics() or refresh_metrics()
    if m:
        sx, sy = coordlib.shot_norm_to_screen(fx, fy, m)
        log("INFO", "OCR点击 screen=%.0f,%.0f（截图归一化 %.3f,%.3f）" % (sx, sy, fx, fy))
        return silent_click_at(sx, sy)
    # 兜底：无 metrics 时按整窗外框估
    rect = window_rect()
    if not rect:
        return False
    x, y, w, h = rect
    cx = x + w * fx
    cy = y + h * fy
    log("INFO", "OCR点击 screen=%.0f,%.0f（整窗兜底）" % (cx, cy))
    return silent_click_at(cx, cy)


def swipe_page(direction, inset=0.18):
    info = window_info()
    if not info:
        return False
    x, y, w, h = info["outer"]
    mid_y = y + h * 0.52
    left = x + w * inset
    right = x + w * (1.0 - inset)
    if direction == "right":
        x1, x2 = left, right
        dx = 900
    else:
        x1, x2 = right, left
        dx = -900
    log("INFO", "向%s翻页" % ("右" if direction == "right" else "左"))
    # 先点屏幕中下部，让镜像窗口吃到手势，再 Shift+滚轮横滑，最后 HID 拖一下
    focus = point_in_window(0.5, 0.82)
    if focus:
        silent_click_at(focus[0], focus[1])
        time.sleep(0.2)
    silent_swipe_scroll(x + w * 0.5, mid_y, dx)
    time.sleep(0.15)
    return silent_drag(x1, mid_y, x2, mid_y)


def type_search_and_open(config):
    keywords = config.get("keywords") or []
    name = (config.get("search") or "").strip()
    if not name and keywords:
        name = keywords[0]
    if not name:
        return True
    log("INFO", "搜索并打开：%s" % name)
    if not send_text(name, focus=True):
        return False
    time.sleep(1.2)
    hit = match_app_item(ocr_items(), keywords or [name])
    if hit:
        log("INFO", "搜索结果里找到 %s，点开" % hit.get("text"))
        tap_ocr_item(hit, float(config.get("tap_above") or 0.02))
        time.sleep(1.6)
        return True
    send_hotkey("return")
    time.sleep(1.6)
    return True


def is_landscape():
    return current_orientation() == "landscape"


def is_portrait_window():
    return current_orientation() == "portrait"


def current_orientation(info=None):
    """当前镜像窗口方向：outer.w > outer.h → landscape，否则 portrait。"""
    info = info or window_info()
    if not info:
        return "portrait"
    try:
        _ox, _oy, ow, oh = info["outer"]
        orient = "landscape" if float(ow) > float(oh) else "portrait"
    except Exception:
        orient = "portrait" if info.get("portrait") else ("landscape" if info.get("landscape") else "portrait")
    return orient


def resolve_kill_mirror(val):
    if val is False or val == 0 or val == "never" or val == "false":
        return "never"
    if val is True or val == 1 or val == "always" or val == "true":
        return "always"
    return "auto"


def in_game_now(config=None):
    words = list(IN_GAME_WORDS)
    if config:
        for k in (config.get("keywords") or []):
            if k and k not in words:
                words.append(k)
        for k in (config.get("search") or "").split():
            if k and k not in words:
                words.append(k)
    items = ocr_items(accurate=True)
    names = [i.get("text") for i in items if i.get("text")]
    if names:
        log("INFO", "识图: %s" % "、".join(names[:16]))
    hit = bool(match_app_item(items, words))
    return hit, items


def looks_like_game(items, config=None):
    """比 in_game_now 更宽：竖屏旋转后 OCR 乱也能抓住游戏痕迹。"""
    words = list(IN_GAME_WORDS)
    if config:
        for k in (config.get("keywords") or []):
            if k and k not in words:
                words.append(k)
    if match_app_item(items, words):
        return True
    blob = joined_ocr(items)
    soft = ["燕云", "公告", "继续", "角色", "江湖", "适龄", "实名", "防沉迷", "网易"]
    hits = sum(1 for w in soft if w in blob)
    return hits >= 2


def wait_landscape(timeout=22):
    end = time.time() + timeout
    while time.time() < end:
        if not wait_if_paused():
            return False
        if is_landscape():
            save_shot("landscape_ok")
            log("INFO", "已是横屏 %s" % (window_bounds() or ""))
            return True
        time.sleep(1.0)
    save_shot("landscape_timeout")
    log("WARN", "还没等到横屏 %s" % (window_bounds() or ""))
    return False


def recover_landscape(config=None, rounds=2):
    """竖屏进游戏：彻底杀掉镜像再连，争取第一次恢复横屏。不接受继续竖屏。"""
    config = config or {}
    for round_i in range(1, int(rounds) + 1):
        log("INFO", "竖屏恢复 %s/%s：强制杀掉镜像进程，重连后等横屏" % (round_i, rounds))
        save_shot("portrait_before_kill_%s" % round_i)
        if not restart_mirror():
            return False
        if not wait_mirror_ready(35):
            return False
        if not unlock_if_needed():
            return False
        time.sleep(1.6)
        if wait_landscape(26):
            in_game, items = in_game_now(config)
            if in_game or looks_like_game(items, config):
                log("INFO", "重连后游戏已在横屏")
                set_phase("game_playing")
                save_shot("landscape_recovered")
                return True
            wrong = is_wrong_app(items)
            if wrong and wrong != "connecting":
                log("WARN", "重连后横屏但不是游戏（%s），回主屏幕再打开一次" % wrong)
                go_home()
                open_search()
                if not type_search_and_open(config):
                    continue
                time.sleep(2.2)
                if wait_landscape(18) and (in_game_now(config)[0] or looks_like_game(ocr_items(accurate=True), config)):
                    set_phase("game_playing")
                    return True
                continue
            log("INFO", "已横屏且未见错 App，继续")
            set_phase("game_playing")
            return True
        # 仍竖屏：若已在游戏里，再杀一轮；不要当成功
        in_game, items = in_game_now(config)
        if in_game or looks_like_game(items, config):
            log("WARN", "重连后游戏仍在竖屏，再强杀一轮")
            continue
        wrong = is_wrong_app(items)
        if wrong and wrong != "connecting":
            log("WARN", "重连后不是游戏（%s），回主屏幕再开" % wrong)
            go_home()
        else:
            log("INFO", "重连后不在游戏里，打开一次后再判断")
            go_home()
        open_search()
        if not type_search_and_open(config):
            continue
        time.sleep(2.2)
        if is_landscape() and (in_game_now(config)[0] or looks_like_game(ocr_items(accurate=True), config)):
            set_phase("game_playing")
            return True
        if not is_landscape() and (in_game_now(config)[0] or looks_like_game(ocr_items(accurate=True), config)):
            log("WARN", "又开成竖屏，准备下一轮强杀")
            continue
    save_shot("landscape_recover_fail")
    log("WARN", "多次强杀镜像后仍未横屏进游戏")
    return False


def open_game_once(config, options=None):
    options = options or {}
    # 横竖屏都兼容：进了游戏就成功，不再为竖屏强杀镜像
    force_land = bool(config.get("require_landscape") or options.get("require_landscape"))
    log("INFO", "进入游戏（横竖屏兼容%s）" % ("；仅当显式要求才强杀横屏" if force_land else ""))
    log_window_geom("open_game")
    if not ensure_mirror_ready():
        return False
    if not wait_mirror_ready(35):
        return False
    ensure_mirror_large()
    if not unlock_if_needed():
        return False
    time.sleep(0.8)
    in_game, items = in_game_now(config)
    if in_game or looks_like_game(items, config):
        save_shot("already_in_game")
        orient = "横屏" if is_landscape() else "竖屏"
        log("INFO", "已经在游戏里（%s），直接继续" % orient)
        if force_land and not is_landscape():
            return recover_landscape(config)
        set_phase("game_playing")
        return True
    wrong = is_wrong_app(items)
    if wrong == "connecting":
        if not wait_until_connected(20):
            return False
        in_game, items = in_game_now(config)
        if in_game or looks_like_game(items, config):
            if force_land and not is_landscape():
                return recover_landscape(config)
            set_phase("game_playing")
            return True
    if wrong and wrong != "connecting":
        note_wrong_app(wrong)
        log("INFO", "当前是其他 App（%s），先回主屏幕" % wrong)
        save_shot("wrong_before_open")
    set_phase("home")
    go_home()
    set_phase("spotlight_search")
    open_search()
    if not type_search_and_open(config):
        return False
    time.sleep(1.0)
    tries = 0
    while tries < 2:
        in_game, items = in_game_now(config)
        if in_game or looks_like_game(items, config):
            break
        wrong = is_wrong_app(items)
        if wrong == "connecting":
            log("INFO", "打开后镜像又在连接，先等")
            if not wait_mirror_ready(20):
                return False
            tries += 1
            continue
        if wrong:
            if looks_like_game(items, config):
                log("INFO", "虽判为 %s，但画面像游戏，按进游戏处理" % wrong)
                break
            log("WARN", "打开后不是游戏，是 %s，回主屏幕再搜一次" % wrong)
            save_shot("opened_wrong_app")
            go_home()
            open_search()
            if not type_search_and_open(config):
                return False
            time.sleep(1.0)
            tries += 1
            continue
        time.sleep(1.0)
        tries += 1
    in_game, items = in_game_now(config)
    like = in_game or looks_like_game(items, config)
    if not like:
        save_shot("not_game")
        log("WARN", "没有进到游戏，回主屏幕")
        go_home()
        return False
    orient = "横屏" if is_landscape() else "竖屏"
    save_shot("opened_%s" % ("landscape" if is_landscape() else "portrait"))
    log("INFO", "已进入游戏（%s），横竖屏都继续跑" % orient)
    if force_land and not is_landscape():
        return recover_landscape(config)
    set_phase("game_playing")
    return True


def expand_step(step, config):
    data = json.loads(json.dumps(step, ensure_ascii=False))
    acc = (config.get("switch_account") or "").strip()
    raw = json.dumps(data, ensure_ascii=False).replace("$switch_account", acc)
    data = json.loads(raw)
    if data.get("need_account") and not acc:
        data["_skip"] = True
    return data


def content_rect_norm():
    # 内容区内再缩一圈黑边，避免点到边框
    if is_portrait_window():
        return 0.07, 0.11, 0.86, 0.76
    return 0.04, 0.08, 0.92, 0.84


def game_to_window(gx, gy):
    """游戏横屏坐标 -> 镜像窗口坐标。竖屏窗口里横屏游戏是顺时针转了 90°。"""
    cx, cy, cw, ch = content_rect_norm()
    gx = max(0.0, min(1.0, float(gx)))
    gy = max(0.0, min(1.0, float(gy)))
    if is_portrait_window():
        lx = 1.0 - gy
        ly = gx
        return cx + cw * lx, cy + ch * ly
    return cx + cw * gx, cy + ch * gy


def wait_screen(step):
    timeout = float(step.get("timeout") or 40)
    interval = float(step.get("interval") or 1.4)
    max_retry = int(step.get("max_retry") or 40)
    keywords = [k for k in (step.get("keywords") or []) if k]
    # 默认不强制横屏；只有 step.landscape=true 且 require_kill=true 才强杀
    need_land = bool(step.get("landscape")) and bool(step.get("require_kill", False))
    end = time.time() + timeout
    log("INFO", "等待游戏画面%s%s" % (
        "（要求横屏并强杀）" if need_land else "（横竖屏均可）",
        "，看到：%s" % " / ".join(keywords[:4]) if keywords else "",
    ))
    last_names = ""
    tries = 0
    recovered = False
    while time.time() < end:
        if not wait_if_paused():
            return False
        if wrong_app_cooling():
            time.sleep(0.5)
            continue
        tries += 1
        if tries > max_retry:
            save_shot("wait_max_retry")
            record_error("等待画面重试耗尽", "已试 %s 次" % tries)
            return not step.get("required", False)
        land_ok = (not need_land) or is_landscape()
        items = ocr_items(accurate=True)
        names = [i.get("text") for i in items if i.get("text")]
        blob = "、".join(names[:16])
        if blob and blob != last_names:
            log("INFO", "识图: %s" % blob)
            last_names = blob
        hit = match_app_item(items, keywords) if keywords else None
        like = bool(hit) or looks_like_game(items)
        if like and need_land and not is_landscape():
            if not recovered:
                log("INFO", "步骤要求横屏且当前竖屏 → 强杀镜像")
                save_shot("wait_portrait_game")
                if recover_landscape():
                    recovered = True
                    continue
                recovered = True
            time.sleep(interval)
            continue
        if land_ok and (not keywords or hit or like):
            save_shot("wait_ok")
            orient = "横屏" if is_landscape() else "竖屏"
            log("INFO", "游戏画面已就绪（%s）" % orient)
            return True
        wrong = is_wrong_app(items)
        if wrong == "connecting":
            wait_until_connected(10)
            continue
        if wrong and not like:
            note_wrong_app(wrong)
            log("WARN", "等游戏时看到的是其他界面（%s），回主屏幕，不再继续识图" % wrong)
            save_shot("wait_wrong_app")
            go_home()
            return False
        time.sleep(interval)
    save_shot("wait_timeout")
    log("WARN", "等待游戏画面超时")
    return not step.get("required", False)


def metrics_for_click(info):
    """只用窗口几何建 Metrics，不截图（避免弹录屏权限打断点击）。"""
    if not info:
        return None
    outer = info.get("outer_dict") or {
        "x": info["outer"][0], "y": info["outer"][1],
        "w": info["outer"][2], "h": info["outer"][3],
    }
    content = info.get("content_dict") or {
        "x": info["content"][0], "y": info["content"][1],
        "w": info["content"][2], "h": info["content"][3],
    }
    prev = _last_metrics
    if prev and prev.shot_w > 0 and prev.shot_h > 0:
        sw, sh = prev.shot_w, prev.shot_h
        sx, sy = prev.shot_scale_x, prev.shot_scale_y
        space = prev.shot_space
    else:
        sw, sh = int(outer["w"]), int(outer["h"])
        sx = sy = 1.0
        space = "outer"
    return coordlib.Metrics(
        outer=coordlib.rect_from(outer),
        content=coordlib.rect_from(content),
        shot_w=sw,
        shot_h=sh,
        shot_origin_x=float(outer["x"]),
        shot_origin_y=float(outer["y"]),
        shot_scale_x=sx,
        shot_scale_y=sy,
        shot_space=space,
    )


def tap_point(fx, fy, cg=None, step=None, source="tap"):
    """点击：最终必须是屏幕绝对点 → postToPid / HID。

    若传入 step（含 cg_x + outer 锚点），优先绝对 CG + 窗口位移。
    回放路径禁止截图，否则会弹「脚本合集」录屏权限框把点击打断。
    回放/校准复点强制 HID：镜像对 postToPid 常隔离，预览对了也不进游戏。
    """
    need_hid = (source or "") in (
        "replay", "calibrate", "record_verify", "resolve", "icon", "tap_text",
    )
    info = log_window_geom("tap")
    if step:
        m = metrics_for_click(info)
        if not m:
            log("WARN", "无窗口信息，无法回放点击")
            return False
        sx, sy = coordlib.resolve_screen(step, m)
        fx2, fy2 = coordlib.screen_to_outer(sx, sy, m)
        spx, spy = coordlib.screen_to_shot(sx, sy, m)
        if not in_window_safe(fx2, fy2):
            log("WARN", "点击坐标过靠边，丢弃 %.3f, %.3f" % (fx2, fy2))
            return False
        mode = coordlib.resolve_mode(step, m) + "+hid-nowarp"
        log_click(source or "replay", fx2, fy2, sx, sy, spx, spy, mode=mode)
        return silent_click_screen(sx, sy, tag="(resolve)", force_hid=True)

    # 普通脚本点击：有旧 metrics 就不强行截图
    m = current_metrics(info=info)
    if not m and info:
        m = metrics_for_click(info)
    fx = float(fx)
    fy = float(fy)
    if not in_window_safe(fx, fy):
        log("WARN", "点击坐标过靠边，丢弃 %.3f, %.3f" % (fx, fy))
        return False
    if m:
        if cg and len(cg) >= 2:
            sx, sy = float(cg[0]), float(cg[1])
        else:
            sx, sy = coordlib.outer_to_screen(fx, fy, m)
        spx, spy = coordlib.screen_to_shot(sx, sy, m)
        log_click(source or "tap", fx, fy, sx, sy, spx, spy)
        return silent_click_screen(sx, sy, force_hid=need_hid)
    pt = point_in_window(fx, fy)
    if not pt:
        return False
    if cg and len(cg) >= 2:
        sx, sy = float(cg[0]), float(cg[1])
    else:
        sx, sy = pt
    log("INFO", "按整窗点击 fx=%.4f fy=%.4f → screen=%.1f,%.1f（无 metrics）" % (fx, fy, sx, sy))
    return silent_click_screen(sx, sy, force_hid=need_hid)


def active_recording_info():
    rec = _active_recording
    if not rec:
        return None
    return {
        "id": rec.get("id"),
        "name": rec.get("name"),
        "count": len(rec.get("steps") or []),
    }


def start_hand_recording(name=None):
    global _active_recording
    if _active_recording:
        return None, "已经在录制中"
    ensure_dirs()
    rid = "rec_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(RECORD_DIR, rid)
    shots = os.path.join(folder, "shots")
    os.makedirs(shots, exist_ok=True)
    display = (name or "").strip() or ("手点录制 " + datetime.datetime.now().strftime("%m-%d %H:%M"))
    _active_recording = {
        "id": rid,
        "name": display,
        "folder": folder,
        "shots": shots,
        "steps": [],
        "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    log("INFO", "开始手点录制：%s（无遮罩，直接点镜像窗口）" % display)
    return _active_recording, ""


def append_hand_click(fx=None, fy=None, cg=None, verify=False, outer=None, content=None):
    """记一步：保存绝对 CG + 窗口锚点 + 截图像素。截图失败仍保存坐标。"""
    rec = _active_recording
    if not rec:
        return None, "当前没有在录制"
    # 尽量截图；失败不挡录制（预览可后补）
    got_shot = capture_window(force=False)
    if not got_shot:
        log("WARN", "录制本步截图失败，仍保存坐标（回放不依赖截图）")
    info = window_info()
    m = current_metrics(info=info) or refresh_metrics(info=info)
    if not m and info:
        m = metrics_for_click(info)
    if not m:
        return None, "无法建立坐标 metrics"
    if cg and len(cg) >= 2:
        sx, sy = float(cg[0]), float(cg[1])
    elif fx is not None and fy is not None:
        sx, sy = coordlib.outer_to_screen(float(fx), float(fy), m)
    else:
        return None, "缺少点击坐标"
    fx2, fy2 = coordlib.screen_to_outer(sx, sy, m)
    spx, spy = coordlib.screen_to_shot(sx, sy, m)
    set_last_click(fx2, fy2, sx, sy, spx, spy, source="record")
    idx = len(rec["steps"]) + 1
    shot_name = "%03d.png" % idx
    shot_path = os.path.join(rec["shots"], shot_name)
    if got_shot and os.path.isfile(SCREENSHOT):
        try:
            shutil.copy2(SCREENSHOT, shot_path)
            shutil.copy2(SCREENSHOT, LAST_SHOT)
        except Exception as e:
            log("WARN", "保存录制截图失败：%s" % e)
            got_shot = False
    outer_d = outer or (info["outer_dict"] if info else m.outer.as_dict())
    content_d = content or (info["content_dict"] if info else m.content.as_dict())
    if isinstance(outer_d, (list, tuple)):
        outer_d = {"x": outer_d[0], "y": outer_d[1], "w": outer_d[2], "h": outer_d[3]}
    if isinstance(content_d, (list, tuple)):
        content_d = {"x": content_d[0], "y": content_d[1], "w": content_d[2], "h": content_d[3]}
    step = {
        "type": "tap_point",
        "i": idx,
        "fx": round(fx2, 4),
        "fy": round(fy2, 4),
        "space": "outer",
        "cg_x": round(sx, 1),
        "cg_y": round(sy, 1),
        "outer": outer_d,
        "content": content_d,
        "shot": {
            "file": shot_name if got_shot else "",
            "w": m.shot_w,
            "h": m.shot_h,
            "scale_x": round(m.shot_scale_x, 4),
            "scale_y": round(m.shot_scale_y, 4),
            "origin_x": m.shot_origin_x,
            "origin_y": m.shot_origin_y,
            "space": m.shot_space,
        },
        "shot_px": round(spx, 1),
        "shot_py": round(spy, 1),
        "wait": 1.0,
        "orient": "landscape" if is_landscape() else "portrait",
    }
    step["shot_file"] = shot_name if got_shot else ""
    rec["steps"].append(step)
    with open(os.path.join(rec["folder"], "steps.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": rec["steps"]}, f, ensure_ascii=False, indent=2)
    log_click("record", fx2, fy2, sx, sy, spx, spy)
    log("INFO", "录制第 %s 步 outer=%.4f,%.4f（%s，锚点已存）" % (
        idx, fx2, fy2, step["orient"],
    ))
    if verify:
        time.sleep(0.35)
        ok = tap_point(fx2, fy2, step=step, source="record_verify")
        step["verified"] = bool(ok)
        with open(os.path.join(rec["folder"], "steps.json"), "w", encoding="utf-8") as f:
            json.dump({"steps": rec["steps"]}, f, ensure_ascii=False, indent=2)
    return step, ""


def finish_hand_recording():
    """结束录制，只落盘草稿，等用户选燕云/星穹铁道再正式保存。"""
    global _active_recording
    rec = _active_recording
    if not rec:
        return None, "当前没有在录制"
    steps = rec.get("steps") or []
    if not steps:
        _active_recording = None
        try:
            shutil.rmtree(rec["folder"])
        except Exception:
            pass
        return None, "一步都没点，已取消录制"
    with open(os.path.join(rec["folder"], "steps.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "name": rec["name"]}, f, ensure_ascii=False, indent=2)
    draft = {
        "id": rec["id"],
        "name": rec["name"],
        "steps": len(steps),
        "folder": rec["folder"],
        "pending": True,
    }
    with open(os.path.join(rec["folder"], "draft.json"), "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    _active_recording = None
    log("INFO", "录制草稿已就绪：%s，共 %s 步，请选择保存到燕云/星穹铁道" % (rec["name"], len(steps)))
    return draft, ""


def save_hand_recording(recording_id, name=None, group="yanyun"):
    """把草稿正式保存到 configs/yanyun 或 configs/starrail。"""
    rid = (recording_id or "").strip()
    if not rid:
        return None, "缺少录制 id"
    folder = os.path.join(RECORD_DIR, rid)
    if not os.path.isdir(folder):
        return None, "找不到这次录制的数据"
    steps, _ = load_recording_steps(rid)
    if not steps:
        return None, "这次录制没有步骤"
    group = (group or "yanyun").strip()
    if group not in ("yanyun", "starrail"):
        return None, "只能保存到燕云(yanyun)或星穹铁道(starrail)"
    gname = group_display_name(group)
    display = (name or "").strip() or ("手点 " + datetime.datetime.now().strftime("%m-%d %H:%M"))
    cfg = {
        "id": rid,
        "group": group,
        "group_name": gname,
        "name": display,
        "order": 50,
        "description": "共 %s 步手点回放（只点坐标）" % len(steps),
        "use_common": False,
        "keep_alive": False,
        "steps": [
            {
                "type": "replay_recording",
                "name": "回放手点",
                "recording_id": rid,
                "wait": 1.0,
                "verify": False,
                "required": True,
            }
        ],
    }
    out_dir = os.path.join(CONFIG_DIR, group)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, rid + ".json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    with open(os.path.join(folder, "steps.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "name": display}, f, ensure_ascii=False, indent=2)
    draft_path = os.path.join(folder, "draft.json")
    if os.path.isfile(draft_path):
        try:
            os.remove(draft_path)
        except Exception:
            pass
    rel = "configs/%s/%s.json" % (group, rid)
    log("INFO", "已保存手点脚本 → %s（%s · %s，%s 步）" % (rel, gname, display, len(steps)))
    return {"cfg": cfg, "path": out_path, "rel": rel, "group_name": gname}, ""


def discard_hand_recording(recording_id):
    rid = (recording_id or "").strip()
    if not rid:
        return False, "缺少录制 id"
    folder = os.path.join(RECORD_DIR, rid)
    if not os.path.isdir(folder):
        return False, "找不到这次录制"
    # 若已正式保存过配置，一并删掉
    for group in ("yanyun", "starrail"):
        path = os.path.join(CONFIG_DIR, group, rid + ".json")
        if os.path.isfile(path):
            try:
                os.remove(path)
            except Exception:
                pass
    try:
        shutil.rmtree(folder)
    except Exception as e:
        return False, "删除失败：%s" % e
    log("INFO", "已丢弃手点录制：%s" % rid)
    return True, ""


def cancel_hand_recording():
    global _active_recording
    rec = _active_recording
    if not rec:
        return False, "当前没有在录制"
    _active_recording = None
    try:
        shutil.rmtree(rec["folder"])
    except Exception:
        pass
    log("INFO", "已取消手点录制")
    return True, ""


def load_recording_steps(recording_id):
    folder = os.path.join(RECORD_DIR, recording_id)
    path = os.path.join(folder, "steps.json")
    if not os.path.isfile(path):
        return None, folder
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("steps") or [], folder
    except Exception as e:
        log("WARN", "读取录制失败：%s" % e)
        return None, folder


def image_similarity(path_a, path_b):
    try:
        from PIL import Image
        import math
    except Exception:
        return 0.0
    if not (os.path.isfile(path_a) and os.path.isfile(path_b)):
        return 0.0
    try:
        a = Image.open(path_a).convert("L")
        b = Image.open(path_b).convert("L")
        size = (96, 170)
        a = a.resize(size, Image.BILINEAR)
        b = b.resize(size, Image.BILINEAR)
        pa = list(a.getdata())
        pb = list(b.getdata())
        n = len(pa)
        if n == 0:
            return 0.0
        ma = sum(pa) / float(n)
        mb = sum(pb) / float(n)
        num = 0.0
        da = 0.0
        db = 0.0
        for i in range(n):
            xa = pa[i] - ma
            xb = pb[i] - mb
            num += xa * xb
            da += xa * xa
            db += xb * xb
        if da <= 1e-6 or db <= 1e-6:
            return 0.0
        return max(0.0, min(1.0, num / math.sqrt(da * db)))
    except Exception as e:
        log("WARN", "截图比对失败：%s" % e)
        return 0.0


def verify_recording_shot(expected_path, min_score=0.68, timeout=12, interval=0.6):
    deadline = time.time() + float(timeout)
    best = 0.0
    while time.time() < deadline:
        if should_stop():
            return False, best
        if not capture_window():
            time.sleep(interval)
            continue
        score = image_similarity(SCREENSHOT, expected_path)
        if score > best:
            best = score
        log("INFO", "画面校验分 %.3f（需 ≥ %.2f）" % (score, float(min_score)))
        if score >= float(min_score):
            return True, score
        # 超时短时少刷日志：分数变化不大就安静等
        time.sleep(interval)
    return False, best


def replay_recording(step):
    rid = step.get("recording_id") or ""
    steps, folder = load_recording_steps(rid)
    if not steps:
        log("WARN", "找不到录制内容：%s" % rid)
        return False
    wait = float(step.get("wait") if step.get("wait") is not None else 1.0)
    total = len(steps)
    log("INFO", "回放手点共 %s 步（优先 CG+位移；先置前镜像）" % total)
    try:
        ctrl = os.path.join(DATA_DIR, "overlay.lock")
        with open(ctrl, "w") as f:
            f.write("0")
    except Exception:
        pass
    ensure_mirror_front(force=True)
    ensure_mirror_large()
    for item in steps:
        if should_stop():
            return False
        while run_mode == "paused":
            if should_stop():
                return False
            time.sleep(0.2)
        idx = item.get("i") or 0
        fx = float(item.get("fx") or 0.5)
        fy = float(item.get("fy") or 0.5)
        step_wait = float(item.get("wait") if item.get("wait") is not None else wait)
        log("INFO", "回放 %s/%s：等 %.1fs 后点 outer=%.4f, %.4f" % (idx, total, step_wait, fx, fy))
        if not sleep_wait(step_wait):
            return False
        # 兼容旧录制：shot 可能是字符串文件名
        if isinstance(item.get("shot"), str):
            item = dict(item)
            item["shot_file"] = item.get("shot")
        if not tap_point(fx, fy, step=item, source="replay"):
            log("WARN", "第 %s 步点击失败" % idx)
            return False
        time.sleep(0.45)
    log("INFO", "手点回放完成，共 %s 步" % total)
    return True



def crop_account_image(box):
    if not box or not os.path.isfile(SCREENSHOT) or not ensure_ocr_bin():
        return False
    pad = 0.03
    x = max(0.0, float(box.get("x") or 0) - pad)
    y = max(0.0, float(box.get("y") or 0) - pad)
    w = min(1.0 - x, float(box.get("w") or 0.12) + pad * 2)
    h = min(1.0 - y, float(box.get("h") or 0.06) + pad * 2)
    code, out, err = run_cmd([
        OCR_BIN, "--crop", SCREENSHOT, ACCOUNT_IMG,
        str(x), str(y), str(w), str(h),
    ], timeout=8)
    return code == 0 and os.path.isfile(ACCOUNT_IMG)


def set_current_account(name, box=None):
    global current_account
    current_account = (name or "").strip()
    if box:
        crop_account_image(box)
    if current_account:
        log("INFO", "当前账号：%s" % current_account)


def username_near(items, anchor="继续游戏"):
    hit = match_app_item(items, [anchor])
    skip = ("继续游戏", "选择角色", "燕云十六声", "燕云", "适龄提示", "16+", "网易")
    best = None
    best_d = 9e9
    ax = ay = 0.5
    if hit:
        ax = hit["x"] + hit["w"] / 2.0
        ay = hit["y"] + hit["h"] / 2.0
    for it in items:
        text = (it.get("text") or "").strip()
        if not text or text in skip:
            continue
        if anchor and anchor in text:
            continue
        if len(text) < 2 or len(text) > 16:
            continue
        if any(word in text for word in ("版本", "公告", "更新", "公司", "适龄")):
            continue
        cx = it["x"] + it["w"] / 2.0
        cy = it["y"] + it["h"] / 2.0
        dist = (cx - ax) ** 2 + (cy - ay) ** 2
        if dist < best_d:
            best_d = dist
            best = it
    if not best or best_d > 0.12:
        return None, None
    return best.get("text"), best


def read_account(step):
    anchor = step.get("anchor") or "继续游戏"
    timeout = float(step.get("timeout") or 30)
    interval = float(step.get("interval") or 1.3)
    log("INFO", "识别当前账号")
    end = time.time() + timeout
    while time.time() < end:
        if not wait_if_paused():
            return False
        items = ocr_items(accurate=True)
        names = [i.get("text") for i in items if i.get("text")]
        if names:
            log("INFO", "识图: %s" % "、".join(names[:18]))
        if not match_app_item(items, [anchor, "选择角色"]):
            time.sleep(interval)
            continue
        name, box = username_near(items, anchor)
        if name:
            set_current_account(name, box)
            return True
        time.sleep(interval)
    log("WARN", "没有识别到账号名")
    return True


def find_icon_click(step):
    """按模板找图标并点击；有手校点位则优先用手点坐标。"""
    timeout = float(step.get("timeout") or 18)
    interval = float(step.get("interval") if step.get("interval") is not None else 1.0)
    min_score = float(step.get("min_score") if step.get("min_score") is not None else 0.55)
    clicks = int(step.get("clicks") or 1)
    wait_after = float(step.get("wait") if step.get("wait") is not None else 1.0)
    name = step.get("name") or "图标"
    calib_key = (step.get("calib_key") or "").strip()
    # 手校点位优先：描述定步骤 + 你点一下定位置
    if calib_key:
        resolved = resolve_moyu_tap(calib_key)
        if resolved:
            fx, fy, step_hit = resolved
            log("INFO", "「%s」用手校点位 %.3f,%.3f" % (name, fx, fy))
            set_overlay_unlocked_for_clicks()
            save_shot("calib_" + name, click=(fx, fy))
            for i in range(max(1, clicks)):
                tap_point(fx, fy, step=step_hit, source="icon")
                if i + 1 < clicks:
                    time.sleep(0.35)
            if not sleep_wait(wait_after):
                return False
            return True
    paths = []
    for p in (step.get("templates") or []):
        if not p:
            continue
        full = p if os.path.isabs(p) else os.path.join(ROOT, p)
        if os.path.isfile(full):
            paths.append(full)
    # 快捷字段
    for key in ("template", "icon"):
        p = step.get(key)
        if p:
            full = p if os.path.isabs(p) else os.path.join(ROOT, p)
            if os.path.isfile(full) and full not in paths:
                paths.append(full)
    if not paths:
        log("WARN", "%s：没有可用模板" % name)
        return not step.get("required", True)
    log("INFO", "寻找并点击「%s」" % name)
    set_overlay_unlocked_for_clicks()
    end = time.time() + timeout
    while time.time() < end:
        if not wait_if_paused():
            return False
        if capture_denied():
            time.sleep(interval)
            continue
        hit = find_icon(paths[0], min_score, extra_templates=paths[1:])
        if hit:
            fx, fy, score = hit
            # 分太低容易点偏到邻钮，丢掉再找
            if score < min_score:
                time.sleep(interval)
                continue
            save_shot("icon_" + name, click=(fx, fy))
            log("INFO", "命中「%s」%.3f,%.3f score=%.2f，点 %s 次" % (name, fx, fy, score, clicks))
            for i in range(max(1, clicks)):
                tap_point(fx, fy, source="icon")
                if i + 1 < clicks:
                    time.sleep(0.35)
            if not sleep_wait(wait_after):
                return False
            return True
        # 兜底坐标（横竖屏）
        point = step.get("point")
        if is_portrait_window() and step.get("point_port"):
            point = step.get("point_port")
        elif (not is_portrait_window()) and step.get("point_land"):
            point = step.get("point_land")
        if point and len(point) >= 2 and (time.time() + interval >= end - 0.01):
            # 只在最后一轮兜底，避免过早乱点
            pass
        time.sleep(interval)
    # 超时兜底
    point = step.get("point_port") if is_portrait_window() else step.get("point_land")
    point = point or step.get("point")
    if point and len(point) >= 2:
        log("WARN", "「%s」模板未命中，用兜底坐标 %.3f,%.3f" % (name, point[0], point[1]))
        for i in range(max(1, clicks)):
            tap_point(point[0], point[1], source="icon")
            time.sleep(0.35)
        time.sleep(wait_after)
        return True
    log("WARN", "超时未找到「%s」" % name)
    return not step.get("required", True)


def read_role_name(step):
    """菜单页：在「角色编号」上方识别角色名，写入当前账号。"""
    timeout = float(step.get("timeout") or 16)
    interval = float(step.get("interval") if step.get("interval") is not None else 1.0)
    anchor = step.get("anchor") or "角色编号"
    log("INFO", "识别角色名（%s 上方）" % anchor)
    end = time.time() + timeout
    while time.time() < end:
        if not wait_if_paused():
            return False
        items = ocr_items(accurate=True)
        names = [i.get("text") for i in items if i.get("text")]
        if names:
            log("INFO", "识图: %s" % "、".join(names[:18]))
        id_hit = match_app_item(items, [anchor, "角色编号"])
        if not id_hit:
            # 有时 OCR 成「角色编」等
            for it in items:
                t = (it.get("text") or "").replace(" ", "")
                if "角色" in t and ("编号" in t or "编" in t):
                    id_hit = it
                    break
        if id_hit:
            ix = float(id_hit.get("x") or 0) + float(id_hit.get("w") or 0) / 2.0
            iy = float(id_hit.get("y") or 0)
            best = None
            best_score = 9e9
            skip = ("角色编号", "角色", "编号", "燕云", "同游", "家业", "商店", "活动", "设置")
            for it in items:
                text = (it.get("text") or "").strip()
                if not text or text in skip:
                    continue
                if anchor in text or "编号" in text:
                    continue
                if len(text) < 2 or len(text) > 18:
                    continue
                if any(ch.isdigit() for ch in text) and sum(c.isdigit() for c in text) >= 6:
                    continue  # 跳过纯编号
                cx = float(it.get("x") or 0) + float(it.get("w") or 0) / 2.0
                cy = float(it.get("y") or 0) + float(it.get("h") or 0) / 2.0
                # 名称应在编号上方，且横向接近
                if cy >= iy - 0.005:
                    continue
                dist = abs(cx - ix) * 1.5 + (iy - cy)
                if dist < best_score:
                    best_score = dist
                    best = it
            if best:
                set_current_account(best.get("text"), best)
                save_shot("role_name")
                return True
        time.sleep(interval)
    log("WARN", "未识别到角色名")
    return not step.get("required", False)


def match_app_item_precise(items, keywords):
    """优先整词相等、框更小的命中，减少点到旁边按钮。"""
    kws = [k for k in (keywords or []) if k and str(k).strip()]
    if not kws:
        return None
    best = None
    best_rank = None
    for kw in kws:
        kw2 = str(kw).replace(" ", "")
        if not kw2:
            continue
        for item in items:
            text = (item.get("text") or "").replace(" ", "")
            if not text or kw2 not in text:
                continue
            if kw2 in ("同意", "同意并继续") and "不同意" in text:
                continue
            exact = 1 if text == kw2 else 0
            # 框太大容易点偏；优先小框
            area = max(1e-6, float(item.get("w") or 0) * float(item.get("h") or 0))
            # 完全相等最好；其次短文本；再小框
            rank = (exact, -abs(len(text) - len(kw2)), -area)
            if best is None or rank > best_rank:
                best = item
                best_rank = rank
    return best


def ocr_hit_to_outer(hit, bias=None):
    """OCR 框是截图归一化 → outer；可加 bias 微调（点图标不点旁字）。"""
    fx = float(hit.get("x") or 0) + float(hit.get("w") or 0) / 2.0
    fy = float(hit.get("y") or 0) + float(hit.get("h") or 0) / 2.0
    # 竖排字：框又高又窄时，中心仍用框心；横向偏大时略收一点
    w = float(hit.get("w") or 0)
    h = float(hit.get("h") or 0)
    if h > w * 1.6:
        # 竖排标签：略向框内收，避免点到相邻列
        fx = float(hit.get("x") or 0) + w * 0.50
        fy = float(hit.get("y") or 0) + h * 0.45
    if bias and len(bias) >= 2:
        fx += float(bias[0])
        fy += float(bias[1])
    fx = max(0.02, min(0.98, fx))
    fy = max(0.04, min(0.98, fy))
    m = current_metrics() or refresh_metrics()
    if not m:
        return fx, fy
    # 截图归一化 → 屏幕 → outer，与图标匹配同一套
    sx, sy = coordlib.shot_norm_to_screen(fx, fy, m)
    return coordlib.screen_to_outer(sx, sy, m)


def tap_text(step):
    """优先模板点按钮本体；OCR 作辅。避免点到旁边的字/邻钮。"""
    timeout = float(step.get("timeout") or 20)
    interval = float(step.get("interval") if step.get("interval") is not None else 1.0)
    wait_after = float(step.get("wait") if step.get("wait") is not None else 1.0)
    clicks = int(step.get("clicks") or 1)
    kws = [k for k in (step.get("keywords") or []) if k]
    name = step.get("name") or (kws[0] if kws else "文字")
    min_score = float(step.get("min_score") if step.get("min_score") is not None else 0.62)
    prefer_icon = bool(step.get("prefer_icon", True))
    bias = step.get("bias")
    calib_key = (step.get("calib_key") or "").strip()
    templates = []
    for p in (step.get("templates") or []):
        full = p if os.path.isabs(p) else os.path.join(ROOT, p)
        if os.path.isfile(full):
            templates.append(full)
    stop_when = [k for k in (step.get("stop_when") or []) if k]
    log("INFO", "寻找并点击「%s」×%s（手校→图标→文字）" % (name, clicks))
    set_overlay_unlocked_for_clicks()

    # 手校点位优先
    if calib_key:
        resolved = resolve_moyu_tap(calib_key)
        if resolved:
            fx, fy, step_hit = resolved
            log("INFO", "「%s」用手校点位 %.3f,%.3f" % (name, fx, fy))
            save_shot("calib_" + name, click=(fx, fy))
            for i in range(max(1, clicks)):
                tap_point(fx, fy, step=step_hit, source="tap_text")
                if i + 1 < clicks:
                    time.sleep(0.45)
            if not sleep_wait(wait_after):
                return False
            return True

    end = time.time() + timeout
    while time.time() < end:
        if not wait_if_paused():
            return False
        # 先截一张，图标和 OCR 共用
        if capture_denied():
            time.sleep(interval)
            continue
        if not capture_window(force=False):
            time.sleep(interval)
            continue
        items = ocr_items(accurate=True, recapture=False)
        if stop_when and match_app_item(items, stop_when):
            log("INFO", "已在目标界面，跳过「%s」" % name)
            return True

        fx = fy = None
        how = ""

        # 1) 模板优先：点按钮图中心，比 OCR 字旁更准
        if prefer_icon and templates:
            icon = find_icon(templates[0], min_score, extra_templates=templates[1:])
            if icon:
                fx, fy, score = icon
                how = "icon:%.2f" % score

        # 2) OCR：整词优先、小框优先
        if fx is None and kws:
            hit = match_app_item_precise(items, kws)
            if not hit and len(kws[0]) >= 2:
                hit = match_vertical_phrase(items, kws[0])
            if hit:
                fx, fy = ocr_hit_to_outer(hit, bias=bias)
                how = "ocr:%s" % (hit.get("text") or "")

        # 3) 模板放宽再试一次
        if fx is None and templates:
            icon = find_icon(templates[0], max(0.48, min_score - 0.12), extra_templates=templates[1:])
            if icon:
                fx, fy, score = icon
                how = "icon_loose:%.2f" % score

        if fx is not None:
            if bias and how.startswith("icon") and len(bias) >= 2:
                fx = max(0.02, min(0.98, fx + float(bias[0])))
                fy = max(0.04, min(0.98, fy + float(bias[1])))
            save_shot("tap_" + name, click=(fx, fy))
            log("INFO", "点「%s」%.3f,%.3f ×%s（%s）" % (name, fx, fy, clicks, how))
            for i in range(max(1, clicks)):
                tap_point(fx, fy, source="tap_text")
                if i + 1 < clicks:
                    time.sleep(0.45)
            if not sleep_wait(wait_after):
                return False
            return True
        time.sleep(interval)
    point = step.get("point")
    if is_portrait_window() and step.get("point_port"):
        point = step.get("point_port")
    elif (not is_portrait_window()) and step.get("point_land"):
        point = step.get("point_land")
    if point and len(point) >= 2:
        log("WARN", "「%s」未识到，用兜底坐标" % name)
        for _ in range(max(1, clicks)):
            tap_point(point[0], point[1], source="tap_text")
            time.sleep(0.35)
        time.sleep(wait_after)
        return True
    log("WARN", "超时未点到「%s」" % name)
    return not step.get("required", True)


def wait_match_and_kill(step):
    """点开始匹配后：等到出现「退出匹配」/开始匹配消失，再杀游戏后台。"""
    timeout = float(step.get("timeout") or 25)
    interval = float(step.get("interval") if step.get("interval") is not None else 1.0)
    ready = [k for k in (step.get("ready_when") or ["退出匹配"]) if k]
    gone = [k for k in (step.get("gone_when") or ["开始匹配"]) if k]
    log("INFO", "等待匹配态（看到「退出匹配」或「开始匹配」消失）后杀后台")
    end = time.time() + timeout
    ok = False
    while time.time() < end:
        if not wait_if_paused():
            return False
        items = ocr_items(accurate=True)
        names = [i.get("text") for i in items if i.get("text")]
        if names:
            log("INFO", "识图: %s" % "、".join(names[:14]))
        if match_app_item(items, ready):
            ok = True
            break
        if gone and not match_app_item(items, gone) and match_app_item(items, ["匹配", "排队", "退出"]):
            ok = True
            break
        time.sleep(interval)
    if not ok:
        log("WARN", "未确认进入匹配，仍尝试杀后台")
    return kill_game_background(step)


def kill_game_background(step=None):
    """回主屏 → 上滑进多任务 → 上滑关掉卡片（杀游戏后台）。"""
    step = step or {}
    log("INFO", "杀掉游戏后台")
    set_overlay_unlocked_for_clicks()
    go_home()
    if not sleep_wait(1.0):
        return False
    # 底部上滑打开多任务
    info = window_info()
    if not info:
        log("WARN", "无窗口，无法杀后台")
        return not (step.get("required", True) if step else True)
    m = metrics_for_click(info) or current_metrics(info=info)
    def drag_outer(x0, y0, x1, y1):
        if m:
            s0 = coordlib.outer_to_screen(x0, y0, m)
            s1 = coordlib.outer_to_screen(x1, y1, m)
        else:
            ox, oy, ow, oh = info["outer"]
            s0 = (ox + ow * x0, oy + oh * y0)
            s1 = (ox + ow * x1, oy + oh * y1)
        return silent_drag(s0[0], s0[1], s1[0], s1[1])

    ensure_mirror_front(force=True)
    log("INFO", "上滑打开多任务")
    drag_outer(0.50, 0.96, 0.50, 0.42)
    time.sleep(1.0)
    # 上滑关掉中间/偏左卡片（镜像里常见）
    for fx in (0.50, 0.28, 0.72):
        if should_stop():
            break
        log("INFO", "上滑关掉后台卡片 %.2f" % fx)
        drag_outer(fx, 0.55, fx, 0.08)
        time.sleep(0.55)
    time.sleep(0.6)
    go_home()
    save_shot("killed_background")
    log("INFO", "已尝试杀掉游戏后台")
    return True


def ocr_flow(step):
    timeout = float(step.get("timeout") or 70)
    interval = float(step.get("interval") or 1.5)
    taps = step.get("taps") or []
    stop_when = [k for k in (step.get("stop_when") or []) if k]
    tap_above = float(step.get("tap_above") or 0)
    name = step.get("name") or "识图"
    log("INFO", "开始识图流程：%s" % name)
    used = {}
    end = time.time() + timeout
    while time.time() < end:
        if not wait_if_paused():
            return False
        items = ocr_items(accurate=True)
        names = [i.get("text") for i in items if i.get("text")]
        if names:
            log("INFO", "识图: %s" % "、".join(names[:18]))
        if stop_when and match_app_item(items, stop_when):
            save_shot("flow_done_" + name)
            log("INFO", "识图完成：%s" % name)
            return True
        acted = False
        for i, rule in enumerate(taps):
            max_use = int(rule.get("max") or 1)
            if used.get(i, 0) >= max_use:
                continue
            kws = [k for k in (rule.get("keywords") or []) if k]
            when = [k for k in (rule.get("when") or []) if k]
            blockers = [k for k in (rule.get("when_not") or []) if k]
            if blockers and match_app_item(items, blockers):
                continue
            if when and not match_app_item(items, when):
                continue
            hit = match_app_item(items, kws) if kws else None
            if rule.get("back_button") and (when or hit or not kws):
                if when or not kws or hit:
                    fx, fy = back_button_pos()
                    save_shot("flow_back", click=(fx, fy))
                    log("INFO", "点右侧返回 %.2f, %.2f" % (fx, fy))
                    tap_point(fx, fy)
                    used[i] = used.get(i, 0) + 1
                    acted = True
                    time.sleep(float(rule.get("wait") or 1.2))
                    break
            if hit and not rule.get("back_button") and not rule.get("point"):
                # 「继续游戏」用专用定位（竖排拼字/模板/横竖兜底）
                kws_join = "".join(kws)
                if "继续游戏" in kws_join or "继续游戏" in (hit.get("text") or ""):
                    fx, fy, how = find_continue_target(items)
                    save_shot("flow_continue_" + how, click=(fx, fy))
                    log("INFO", "点继续游戏（%s）%.3f, %.3f" % (how, fx, fy))
                    tap_point(fx, fy)
                else:
                    save_shot("flow_tap_" + name)
                    log("INFO", "点选「%s」" % (hit.get("text") or ""))
                    tap_ocr_item(hit, float(rule.get("tap_above") or tap_above))
                used[i] = used.get(i, 0) + 1
                acted = True
                time.sleep(float(rule.get("wait") or 1.2))
                break
            point = rule.get("point")
            if point and len(point) >= 2 and not hit:
                if kws and not when:
                    continue
                # 继续游戏坐标也按横竖屏切换
                if rule.get("continue") or (kws and "继续游戏" in "".join(kws)):
                    fx, fy, how = find_continue_target(items)
                    tap_point(fx, fy)
                    log("INFO", "点继续游戏坐标兜底（%s）" % how)
                else:
                    tap_point(point[0], point[1])
                used[i] = used.get(i, 0) + 1
                acted = True
                time.sleep(float(rule.get("wait") or 1.0))
                break
            # 关键词是继续游戏但 OCR 没整词：仅模板/拼字命中才点，避免公告页乱点兜底
            if (not hit) and kws and "继续游戏" in "".join(kws) and not rule.get("point"):
                fx, fy, how = find_continue_target(items)
                if how in ("ocr", "icon"):
                    save_shot("flow_continue_" + how, click=(fx, fy))
                    log("INFO", "未见整词，仍点继续游戏（%s）%.3f,%.3f" % (how, fx, fy))
                    tap_point(fx, fy)
                    used[i] = used.get(i, 0) + 1
                    acted = True
                    time.sleep(float(rule.get("wait") or 1.2))
                    break
        if not acted:
            time.sleep(interval)
    if stop_when:
        save_shot("flow_timeout_" + name)
        log("WARN", "识图流程超时：%s" % name)
        return not step.get("required", False)
    log("INFO", "识图流程结束：%s" % name)
    return True


def spotlight_open(keywords):
    if not open_search():
        return False
    return type_search_and_open({"keywords": keywords})


def find_in_folder(keywords, max_pages, swipe, tap_above):
    log("INFO", "已打开盒子，开始在里面找应用")
    for page in range(max_pages):
        if not wait_if_paused():
            return False
        items = ocr_items()
        names = [i.get("text") for i in items if i.get("text")]
        if names:
            log("INFO", "盒子第 %s 页看到: %s" % (page + 1, "、".join(names[:12])))
        hit = match_app_item(items, keywords)
        if hit:
            log("INFO", "盒子里找到 %s，准备点开" % hit["text"])
            tap_ocr_item(hit, tap_above)
            time.sleep(1.5)
            return True
        if page < max_pages - 1:
            swipe_page(swipe, inset=0.28)
            time.sleep(1.0)
    record_error("盒子里没有找到目标 App", "、".join(keywords))
    return False


def find_and_open_app(step):
    keywords = step.get("keywords") or []
    folder_keywords = list(step.get("folder_keywords") or [])
    folder = (step.get("folder") or "").strip()
    if folder and folder not in folder_keywords:
        folder_keywords = [folder] + folder_keywords
    max_pages = int(step.get("max_pages") or 8)
    max_folder_pages = int(step.get("max_folder_pages") or 6)
    swipe = step.get("swipe") or "left"
    tap_above = float(step.get("tap_above") or 0.07)
    search_first = step.get("search_first", True)

    if search_first:
        items = ocr_items()
        hit = match_app_item(items, keywords)
        if hit:
            log("INFO", "当前屏幕已有 %s，直接点开" % hit["text"])
            tap_ocr_item(hit, tap_above)
            time.sleep(1.5)
            return True
        if spotlight_open(keywords):
            return True
        log("WARN", "搜索打开不成功，改成翻页查找")

    if folder_keywords:
        log("INFO", "先找文件夹：%s，再找应用：%s" % (" / ".join(folder_keywords), " / ".join(keywords)))
    else:
        log("INFO", "开始翻页查找：%s" % " / ".join(keywords))

    for page in range(max_pages):
        if not wait_if_paused():
            return False
        items = ocr_items()
        names = [i.get("text") for i in items if i.get("text")]
        if names:
            log("INFO", "主屏幕第 %s 页看到: %s" % (page + 1, "、".join(names[:12])))

        hit = match_app_item(items, keywords)
        if hit:
            log("INFO", "找到 %s，准备点开" % hit["text"])
            tap_ocr_item(hit, tap_above)
            time.sleep(1.5)
            return True

        if folder_keywords:
            folder_hit = match_app_item(items, folder_keywords)
            if folder_hit:
                log("INFO", "找到文件夹 %s，点开后在里面找" % folder_hit["text"])
                tap_ocr_item(folder_hit, tap_above)
                time.sleep(1.2)
                if find_in_folder(keywords, max_folder_pages, swipe, tap_above):
                    return True
                return False

        if page < max_pages - 1:
            swipe_page(swipe)
            time.sleep(1.1)

    if step.get("fallback_spotlight") and not search_first:
        return spotlight_open(keywords)
    record_error("没有找到目标 App", "、".join(keywords))
    return False


def run_step(step):
    kind = step.get("type") or ""
    if kind == "ensure_mirror":
        return ensure_mirror_ready()
    if kind == "restart_mirror":
        return restart_mirror()
    if kind == "unlock_if_needed":
        return unlock_if_needed()
    if kind == "go_home":
        return go_home(step)
    if kind == "open_search":
        return open_search(step)
    if kind == "find_and_open_app":
        return find_and_open_app(step)
    if kind == "wait_screen":
        return wait_screen(step)
    if kind == "ocr_flow":
        return ocr_flow(step)
    if kind == "close_popups":
        return close_popups(step)
    if kind == "sweep_clicks":
        return sweep_clicks(step)
    if kind == "read_account":
        return read_account(step)
    if kind == "read_role_name":
        return read_role_name(step)
    if kind == "find_icon_click":
        return find_icon_click(step)
    if kind == "tap_text":
        return tap_text(step)
    if kind == "wait_match_and_kill":
        return wait_match_and_kill(step)
    if kind == "kill_game_background":
        return kill_game_background(step)
    if kind == "tap_point":
        # 普通给坐标：与登录 close_popups 同路，不传整份 step
        # 只有带 outer 锚点的录制回放才走 resolve
        if step.get("outer"):
            return tap_point(
                step.get("fx") or 0.5, step.get("fy") or 0.5,
                step=step, source="step",
            )
        return tap_point(
            step.get("fx") or 0.5, step.get("fy") or 0.5,
            source="step",
        )
    if kind == "replay_recording":
        return replay_recording(step)
    log("WARN", "未知步骤: %s" % kind)
    return False


def start_shot_run():
    global _shot_seq, _shot_run, _last_saved_shot
    _shot_run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    _shot_seq = 0
    _last_saved_shot = None
    folder = os.path.join(SHOT_DIR, _shot_run)
    os.makedirs(folder, exist_ok=True)
    log("INFO", "本轮校验截图：logs/shots/%s" % _shot_run)
    return folder


def save_shot(tag, click=None):
    global _shot_seq, _last_saved_shot
    if capture_denied() and not screenshot_fresh(60):
        return ""
    if not os.path.isfile(SCREENSHOT) or os.path.getsize(SCREENSHOT) < 1000:
        if not capture_window(force=False):
            return ""
    m = current_metrics() or refresh_metrics()
    if click and m:
        fx, fy = float(click[0]), float(click[1])
        sx, sy = coordlib.outer_to_screen(fx, fy, m)
        spx, spy = coordlib.screen_to_shot(sx, sy, m)
        set_last_click(fx, fy, sx, sy, spx, spy, source="save_shot")
    _shot_seq += 1
    run_id = _shot_run or "misc"
    folder = os.path.join(SHOT_DIR, run_id)
    os.makedirs(folder, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (tag or "shot"))[:40]
    name = "%03d_%s.png" % (_shot_seq, safe)
    dest = os.path.join(folder, name)
    try:
        shutil.copy2(SCREENSHOT, dest)
        shutil.copy2(SCREENSHOT, LAST_SHOT)
        _last_saved_shot = {"run": run_id, "name": name, "path": dest}
    except Exception as e:
        log("WARN", "保存截图失败: %s" % e)
        return ""
    extra = " bounds=%s" % (window_bounds() or "")
    if click:
        extra += " click=%.2f,%.2f" % (float(click[0]), float(click[1]))
        try:
            with open(dest.replace(".png", ".txt"), "w", encoding="utf-8") as f:
                f.write("tag=%s\n" % tag)
                f.write("click=%.3f,%.3f\n" % (float(click[0]), float(click[1])))
                f.write("bounds=%s\n" % (window_bounds() or ""))
        except Exception:
            pass
    log("INFO", "已保存校验截图 %s%s" % (name, extra))
    return dest


def resolve_shot_file(run_id, name):
    """只允许读 logs/shots 下的 png，防路径穿越。"""
    run_id = (run_id or "").strip()
    name = (name or "").strip()
    if not run_id or not name:
        return ""
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        return ""
    if "/" in name or "\\" in name or ".." in name:
        return ""
    if not name.lower().endswith(".png"):
        return ""
    path = os.path.realpath(os.path.join(SHOT_DIR, run_id, name))
    root = os.path.realpath(SHOT_DIR)
    if not path.startswith(root + os.sep):
        return ""
    if not os.path.isfile(path):
        return ""
    return path


def list_shot_thumbs(limit=12):
    """最近一轮校验截图缩略列表（供界面预览）。"""
    run_id = _shot_run or ""
    if not run_id:
        # 取最新一轮目录
        if not os.path.isdir(SHOT_DIR):
            return []
        runs = sorted(
            [d for d in os.listdir(SHOT_DIR) if os.path.isdir(os.path.join(SHOT_DIR, d))],
            reverse=True,
        )
        run_id = runs[0] if runs else ""
    if not run_id:
        return []
    folder = os.path.join(SHOT_DIR, run_id)
    if not os.path.isdir(folder):
        return []
    names = sorted([n for n in os.listdir(folder) if n.lower().endswith(".png")])
    if limit > 0:
        names = names[-limit:]
    out = []
    for name in names:
        path = os.path.join(folder, name)
        try:
            mtime = int(os.path.getmtime(path))
        except Exception:
            mtime = 0
        out.append({"run": run_id, "name": name, "ts": mtime})
    return out


def start_run_session():
    import threading
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, stop_handler)
        signal.signal(signal.SIGTERM, stop_handler)
    ensure_dirs()
    write_pid()
    start_shot_run()
    start_f12_guardian()


def watch_loop(config=None):
    config = config or {}
    reconnect = bool(config.get("reconnect", False))
    watch_only = bool(config.get("watch_only", True))
    lost_need = int(config.get("lost_confirm") or 2)
    max_fail = int(config.get("max_fail") or 2)
    max_unlock = int(config.get("max_unlock") or UNLOCK_MAX_TRIES)

    unlock_tries = 0
    fail_count = 0
    lost_hits = 0
    saw_window = has_window()
    if process_running():
        log("INFO", "检测到 iPhone 镜像已在运行")
    if saw_window:
        log("INFO", "检测到镜像窗口: %s" % window_bounds())
    if watch_only:
        log("INFO", "进入看守：窗口在就等着，窗口没了就停，不再重连、不再乱点")

    while not should_stop():
        if run_mode == "paused":
            time.sleep(0.2)
            continue

        running = process_running()
        window = has_window()
        if not running or not window:
            lost_hits += 1
            if saw_window:
                log("WARN", "镜像窗口不在了（确认 %s/%s）" % (lost_hits, lost_need))
                if lost_hits >= lost_need:
                    if reconnect:
                        log("INFO", "窗口丢失，按配置尝试重连")
                        lost_hits = 0
                        saw_window = False
                        open_mirror()
                        wait_window()
                        continue
                    log("INFO", "确认窗口已关闭，刹车停止")
                    break
                if not sleep_wait(2):
                    break
                continue
            if reconnect:
                log("INFO", "没有窗口，按配置去打开镜像")
                open_mirror()
                if not wait_window():
                    log("WARN", "打开后还是没有窗口")
                    if not sleep_wait(CHECK_INTERVAL):
                        break
                continue
            log("INFO", "一直没有镜像窗口，刹车停止")
            break

        lost_hits = 0
        saw_window = True

        if watch_only:
            if not sleep_wait(CHECK_INTERVAL):
                break
            continue

        text = ocr_text()
        if should_stop():
            break
        state = screen_state(text)
        log("INFO", "画面状态: %s" % state)
        if state == "lock":
            unlock_tries += 1
            if unlock_tries > max_unlock:
                record_error("锁屏解锁连续失败", "已刹车停止，避免一直乱输密码")
                break
            log("INFO", "识别到锁屏，尝试解锁 (%s/%s)" % (unlock_tries, max_unlock))
            try_unlock()
        elif state == "fail":
            fail_count += 1
            record_error("镜像显示连接失败", (text or "")[:200])
            if fail_count >= max_fail:
                log("INFO", "连接失败次数过多，刹车停止")
                break
            if reconnect:
                time.sleep(2)
                open_mirror()
            else:
                log("INFO", "连接失败且不重连，刹车停止")
                break
        elif state == "connecting":
            log("INFO", "镜像正在连接，继续等待")
        elif state == "connected":
            unlock_tries = 0
            fail_count = 0
        else:
            log("INFO", "窗口在，但画面文字不足以判断状态")

        if not sleep_wait(CHECK_INTERVAL):
            break


def run_steps(steps, config=None):
    config = config or {}
    for raw in steps or []:
        if should_stop():
            return False
        while run_mode == "paused":
            if should_stop():
                return False
            time.sleep(0.2)
        step = expand_step(raw, config)
        if step.get("_skip"):
            log("INFO", "跳过步骤：%s（未填写切号账号）" % (step.get("name") or step.get("type")))
            continue
        kind = step.get("type") or ""
        log("INFO", "执行步骤：%s" % (step.get("name") or kind))
        if not run_step(step):
            if step.get("required", True):
                record_error("步骤失败：%s" % (step.get("name") or kind))
                return False
    return True


def run_task(config, options=None, manage_session=True):
    options = options or {}
    if manage_session:
        start_run_session()
    name = config.get("name") or config.get("id") or "未命名配置"
    log("INFO", "使用配置：%s" % name)
    ok = True
    use_common = config.get("use_common", True)
    kill_mode = resolve_kill_mirror(options.get("kill_mirror", "auto"))
    if kill_mode == "always" and not options.get("mirror_ready"):
        ok = restart_mirror()
        if ok:
            options["mirror_ready"] = True
            options["kill_mirror"] = False
    if ok and use_common:
        search_name = (config.get("search") or "").strip()
        keywords = config.get("keywords") or []
        if search_name or keywords:
            ok = open_game_once(config, options)
            if not ok:
                record_error("打开游戏失败", search_name or "、".join(keywords))
        else:
            common = load_common()
            log("INFO", "先走通用前置：打开镜像并进入搜索页")
            ok = run_steps(common.get("steps") or [])
    if ok and not should_stop():
        extra = config.get("steps") or []
        if extra:
            log("INFO", "执行该脚本自己的步骤")
            ok = run_steps(extra, config)
    elif should_stop():
        log("WARN", "已终止，跳过关公告/遍历等后续步骤（若误触终止，请再点开始）")
        ok = False
    if ok and config.get("keep_alive") and not should_stop():
        log("INFO", "任务步骤完成，进入看守")
        watch_loop(config)
    if manage_session:
        remove_pid()
        log("INFO", "任务结束")
    return ok


def run_queue(configs, options=None):
    options = options or {}
    start_run_session()
    global current_account
    current_account = ""
    opts = dict(options)
    ok = True
    kill_mode = resolve_kill_mirror(opts.get("kill_mirror", "auto"))
    if kill_mode == "always":
        log("INFO", "横屏策略：强制重启镜像")
        ok = restart_mirror()
        opts["kill_mirror"] = False
        opts["mirror_ready"] = True
    elif kill_mode == "auto":
        log("INFO", "横屏策略：auto（已在横屏游戏则不杀镜像；竖屏才 recover）")
        opts["kill_mirror"] = False
        opts["mirror_ready"] = True
    else:
        log("INFO", "横屏策略：不杀镜像")
        opts["kill_mirror"] = False
        opts["mirror_ready"] = True
    log_window_geom("queue_start")
    items = list(configs or [])
    total = len(items)
    for i, cfg in enumerate(items):
        if should_stop() or not ok:
            break
        cfg = dict(cfg)
        log("INFO", "队列 %s/%s：%s" % (i + 1, total, cfg.get("name") or cfg.get("id")))
        is_last = (i == total - 1)
        if not is_last:
            cfg["keep_alive"] = False
        else:
            if opts.get("reconnect"):
                cfg["keep_alive"] = True
                cfg["watch_only"] = False
                cfg["reconnect"] = True
            elif opts.get("watch_lost"):
                cfg["keep_alive"] = True
                cfg["watch_only"] = True
                cfg["reconnect"] = False
            else:
                cfg["keep_alive"] = False
        task_opts = dict(opts)
        task_opts["kill_mirror"] = False
        ok = run_task(cfg, task_opts, manage_session=False)
        if not ok:
            record_error("队列在此停止", cfg.get("name") or "")
            break
    remove_pid()
    log("INFO", "队列结束")
    return ok


def keep_alive():
    start_run_session()
    log("INFO", "保活开始")
    if not get_passcode():
        record_error("钥匙串里没有锁屏密码", "请运行: python3 mirror_keeper.py --set-passcode")
    watch_loop({"reconnect": True, "watch_only": False})
    remove_pid()
    log("INFO", "保活已停止")


def write_pid():
    ensure_dirs()
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def remove_pid():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pid():
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def show_status():
    pid = read_pid()
    if pid and pid_alive(pid):
        print("保活脚本: 运行中 (pid %s)" % pid)
    else:
        print("保活脚本: 未运行")
    print("镜像进程: %s" % ("在" if process_running() else "不在"))
    print("镜像窗口: %s" % ("有" if has_window() else "无"))
    data = load_errors()
    items = data.get("items") or []
    print("未清除错误: %d 条" % len(items))
    if data.get("cleared_at"):
        print("上次清空: %s" % data["cleared_at"])
    if items:
        last = items[-1]
        print("最近错误: %s [%s] x%s" % (last.get("message"), last.get("time"), last.get("count") or 1))
    log_path = os.path.join(LOG_DIR, datetime.datetime.now().strftime("%Y-%m-%d") + ".log")
    if os.path.exists(log_path):
        print("今日日志: %s" % log_path)


def stop_handler(signum, frame):
    log("INFO", "收到停止信号，退出")
    emergency_stop("信号")
    remove_pid()
    stop_f12_guardian()
    sys.exit(0)


def running_process_label():
    try:
        import psutil  # noqa: may not exist
    except Exception:
        pass
    # 不引入新依赖：用父进程链粗判
    try:
        ppid = os.getppid()
        code, out, err = run_cmd(["ps", "-p", str(ppid), "-o", "comm="], timeout=3)
        parent = (out or "").strip() or "unknown"
    except Exception:
        parent = "unknown"
    me = sys.executable or "python3"
    if "脚本合集" in me or "ScriptBox" in me:
        return "脚本合集.app"
    if "Terminal" in parent or "terminal" in parent.lower():
        return "终端 (Terminal)"
    if "iTerm" in parent:
        return "iTerm"
    if "Cursor" in parent or "Code" in parent:
        return "Cursor / 编辑器内 Python"
    return "Python (%s)" % os.path.basename(me)


def check_accessibility():
    """用 AXIsProcessTrusted 探测辅助功能。"""
    check_src = os.path.join(ROOT, "scripts", "axcheck.swift")
    check_bin = os.path.join(ROOT, "scripts", "axcheck")
    if not os.path.isfile(check_src):
        try:
            with open(check_src, "w", encoding="utf-8") as f:
                f.write(
                    "import ApplicationServices\n"
                    "print(AXIsProcessTrusted() ? \"yes\" : \"no\")\n"
                )
        except Exception:
            return None
    if (not os.path.isfile(check_bin)) or (
        os.path.getmtime(check_bin) < os.path.getmtime(check_src)
    ):
        code = subprocess.call(
            ["swiftc", "-O", "-o", check_bin, check_src],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if code != 0:
            return None
    code, out, err = run_cmd([check_bin], timeout=5)
    text = (out or "").strip().lower()
    if text == "yes":
        return True
    if text == "no":
        return False
    return None


_scr_probe_cache = None
_scr_probe_at = 0


def check_screen_recording(force=False):
    """永不主动 screencapture 探针（会弹权限并卡住）。"""
    global _scr_probe_cache, _scr_probe_at
    if _scr_probe_cache is not None and time.time() - _scr_probe_at < 3600:
        return _scr_probe_cache
    if os.path.isfile(SCREENSHOT) and os.path.getsize(SCREENSHOT) > 2000:
        _scr_probe_cache = True
        _scr_probe_at = time.time()
        return True
    # force 也不探针
    return None


def permission_report(probe_screen=False):
    """权限摘要。永远不主动截图像素探针。"""
    global _perm_hint
    who = running_process_label()
    ax = check_accessibility()
    lines = ["当前进程：%s" % who]
    if ax is True:
        lines.append("辅助功能：已授权")
    elif ax is False:
        lines.append("辅助功能：未授权 → 系统设置 → 隐私与安全性 → 辅助功能，勾选「%s」" % who)
    else:
        lines.append("辅助功能：无法检测")
    lines.append("屏幕录制：不探测（避免弹窗）；若截图失败请到系统设置勾选「%s」" % who)
    lines.append("提示：不要重编译/重签名工具，否则权限会再弹")
    _perm_hint = " | ".join(lines)
    return {
        "who": who,
        "accessibility": ax,
        "screen_recording": None,
        "hint": _perm_hint,
        "lines": lines,
    }


def self_test():
    ensure_dirs()
    log("INFO", "开始自检")
    ok = True

    log("INFO", "检查日志写入")
    if not os.path.isdir(LOG_DIR):
        print("失败: 日志目录不存在")
        ok = False

    record_error("自检临时错误", "可忽略，随后会清空")
    data = load_errors()
    found = any(item.get("message") == "自检临时错误" for item in (data.get("items") or []))
    if not found:
        print("失败: 错误记录写入失败")
        ok = False
    else:
        log("INFO", "错误暂存写入正常")

    clear_errors()
    data = load_errors()
    if data.get("items"):
        print("失败: 清空错误记录失败")
        ok = False
    else:
        log("INFO", "错误记录清空正常")

    if ensure_ocr_bin():
        log("INFO", "OCR 工具可用")
    else:
        print("警告: OCR 未编译成功，锁屏自动解锁可能不可用")
        ok = False

    if ensure_wininfo_bin():
        log("INFO", "窗口检测工具可用")
        info = window_info()
        if info:
            print("窗口几何样例: %s" % info.get("raw"))
    else:
        print("警告: 窗口检测工具未编译成功")
        ok = False

    if ensure_click_bin():
        log("INFO", "模拟点击工具可用")
    else:
        print("警告: 模拟点击工具未编译成功")
        ok = False

    pin = get_passcode()
    if pin:
        log("INFO", "钥匙串密码已就绪")
    else:
        print("警告: 钥匙串还没有锁屏密码，请运行 python3 mirror_keeper.py --set-passcode")

    text = osascript("running")
    if text in ("yes", "no"):
        log("INFO", "AppleScript 进程检测正常: %s" % text)
    else:
        print("警告: AppleScript 可能缺辅助功能权限: %s" % text)

    perm = permission_report()
    for line in perm.get("lines") or []:
        print(line)
        log("INFO", line)
    if perm.get("accessibility") is False or not perm.get("screen_recording"):
        ok = False

    print("镜像进程: %s" % ("在" if process_running() else "不在"))
    print("镜像窗口: %s" % ("有" if has_window() else "无"))
    cfgs = list_configs()
    print("配置文件: %d 个" % len(cfgs))
    for item in cfgs:
        print("  - %s (%s)" % (item.get("name"), os.path.basename(item.get("_path") or "")))
    if not cfgs:
        print("警告: configs 目录没有配置")
        ok = False
    if ok:
        log("INFO", "自检完成")
        print("自检通过")
        return 0
    log("WARN", "自检完成，但有问题")
    print("自检未完全通过，请看上面的警告")
    return 1


def print_help():
    print("用法:")
    print("  python3 mirror_keeper.py")
    print("  python3 mirror_keeper.py --gui")
    print("  python3 gui.py")
    print("  python3 mirror_keeper.py --status")
    print("  python3 mirror_keeper.py --clear-errors")
    print("  python3 mirror_keeper.py --set-passcode")
    print("  python3 mirror_keeper.py --run yanyun")
    print("  python3 mirror_keeper.py --self-test")


def read_passcode_arg(argv):
    if len(argv) >= 3 and argv[2]:
        return argv[2]
    env_pin = os.environ.get("IPHONE_PASSCODE", "").strip()
    if env_pin:
        return env_pin
    try:
        return input("请输入 iPhone 锁屏密码: ").strip()
    except EOFError:
        return ""


def resolve_config(name):
    if not name:
        return None
    if os.path.isfile(name):
        return load_config_file(name)
    path = os.path.join(CONFIG_DIR, name)
    if not path.endswith(".json"):
        path += ".json"
    if os.path.isfile(path):
        return load_config_file(path)
    # 子目录：yanyun / starrail
    base = name if name.endswith(".json") else (name + ".json")
    for group in ("yanyun", "starrail"):
        path = os.path.join(CONFIG_DIR, group, base)
        if os.path.isfile(path):
            return load_config_file(path)
    # 按 id 扫一遍
    for cfg in list_configs():
        if cfg.get("id") == name or cfg.get("id") == name.replace(".json", ""):
            return cfg
    return None


def main():
    global run_mode
    argv = sys.argv
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd in ("-h", "--help"):
        print_help()
        return 0
    if cmd == "--clear-errors":
        clear_errors()
        return 0
    if cmd == "--status":
        show_status()
        return 0
    if cmd == "--set-passcode":
        pin = read_passcode_arg(argv)
        return 0 if set_passcode(pin) else 1
    if cmd == "--self-test":
        return self_test()
    if cmd == "--gui":
        from gui import run_gui
        run_gui()
        return 0
    if cmd == "--run":
        name = argv[2] if len(argv) >= 3 else "yanyun"
        cfg = resolve_config(name)
        if not cfg:
            print("找不到配置: %s" % name)
            return 1
        run_mode = "running"
        return 0 if run_task(cfg) else 1
    if cmd:
        print("未知参数: %s" % cmd)
        print_help()
        return 1
    keep_alive()
    return 0


if __name__ == "__main__":
    sys.exit(main())

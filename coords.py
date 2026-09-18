# -*- coding: utf-8 -*-
"""统一坐标换算：outer / content / shot / screen。

所有 UI、录制、回放、匹配禁止手写 fx * width，一律走本模块。

谁在什么场景用哪个函数
--------------------------------
mirror_keeper.py
  - outer_to_screen / screen_to_outer：脚本点击、手校落盘
  - screen_to_shot：预览红点、校验截图标点
  - resolve_screen：回放 / 手校回放（优先 cg+outer 位移，尺寸变了退 fx/fy）
  - build_metrics / refresh：每次 screencapture -x -o -l 后重建 Metrics
  - click_log_lines：统一点击日志

gui.py
  - screen_to_outer：遮罩回调绝对 CG → outer 归一化
  - screen_to_shot：校准预览红点
  - resolve 间接经 mirror_keeper.tap_point(step=...)

clickwatch / overlay（Swift）
  - 只回报屏幕绝对点 + outer 锚点；归一化由 Python 用本模块完成

match.py
  - 模板命中是截图归一化坐标；经 shot_norm_to_screen / outer 再点

截图约定：screencapture -x -o -l <windowId>（-o 去阴影，否则 shot↔screen 会偏）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def as_dict(self):
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass
class Metrics:
    outer: Rect
    content: Rect
    shot_w: int
    shot_h: int
    shot_origin_x: float
    shot_origin_y: float
    shot_scale_x: float
    shot_scale_y: float
    shot_space: str = "outer"  # outer | content | unknown

    def as_dict(self):
        return {
            "outer": self.outer.as_dict(),
            "content": self.content.as_dict(),
            "shot_w": self.shot_w,
            "shot_h": self.shot_h,
            "shot_origin_x": self.shot_origin_x,
            "shot_origin_y": self.shot_origin_y,
            "shot_scale_x": self.shot_scale_x,
            "shot_scale_y": self.shot_scale_y,
            "shot_space": self.shot_space,
        }


def rect_from(obj):
    if isinstance(obj, Rect):
        return obj
    if isinstance(obj, (list, tuple)) and len(obj) >= 4:
        return Rect(float(obj[0]), float(obj[1]), float(obj[2]), float(obj[3]))
    if isinstance(obj, dict):
        return Rect(
            float(obj.get("x") if obj.get("x") is not None else obj.get("ox") or 0),
            float(obj.get("y") if obj.get("y") is not None else obj.get("oy") or 0),
            float(obj.get("w") if obj.get("w") is not None else obj.get("ow") or 1),
            float(obj.get("h") if obj.get("h") is not None else obj.get("oh") or 1),
        )
    raise TypeError("无法解析 Rect: %s" % type(obj))


def outer_to_screen(fx, fy, m):
    return m.outer.x + float(fx) * m.outer.w, m.outer.y + float(fy) * m.outer.h


def screen_to_outer(sx, sy, m):
    return (float(sx) - m.outer.x) / max(m.outer.w, 1e-6), (float(sy) - m.outer.y) / max(m.outer.h, 1e-6)


def content_to_screen(fx, fy, m):
    return m.content.x + float(fx) * m.content.w, m.content.y + float(fy) * m.content.h


def screen_to_content(sx, sy, m):
    return (
        (float(sx) - m.content.x) / max(m.content.w, 1e-6),
        (float(sy) - m.content.y) / max(m.content.h, 1e-6),
    )


def shot_to_screen(px, py, m):
    return (
        m.shot_origin_x + float(px) / max(m.shot_scale_x, 1e-6),
        m.shot_origin_y + float(py) / max(m.shot_scale_y, 1e-6),
    )


def screen_to_shot(sx, sy, m):
    return (
        (float(sx) - m.shot_origin_x) * m.shot_scale_x,
        (float(sy) - m.shot_origin_y) * m.shot_scale_y,
    )


def shot_norm_to_screen(fx_img, fy_img, m):
    """截图归一化坐标 → 屏幕绝对点。"""
    return shot_to_screen(float(fx_img) * m.shot_w, float(fy_img) * m.shot_h, m)


def build_metrics(wininfo, shot_w, shot_h, strict=False):
    """根据窗口与截图像素建立 Metrics。

    优先判断截图是否等比于 outer；否则试 content；再否则 strict 抛错或 best-effort。
    """
    if isinstance(wininfo, dict) and "outer" in wininfo:
        outer = rect_from(wininfo["outer"])
        content = rect_from(wininfo.get("content") or wininfo["outer"])
    else:
        # window_info() 风格：outer/content 为 tuple
        outer = rect_from(wininfo["outer"] if isinstance(wininfo, dict) else wininfo)
        content = rect_from(
            wininfo["content"] if isinstance(wininfo, dict) and wininfo.get("content") else outer
        )

    shot_w = int(shot_w)
    shot_h = int(shot_h)
    if shot_w <= 0 or shot_h <= 0:
        raise RuntimeError("截图尺寸无效: %sx%s" % (shot_w, shot_h))

    outer_sx = shot_w / max(outer.w, 1e-6)
    outer_sy = shot_h / max(outer.h, 1e-6)
    content_sx = shot_w / max(content.w, 1e-6)
    content_sy = shot_h / max(content.h, 1e-6)

    if abs(outer_sx - outer_sy) < 0.02:
        return Metrics(
            outer=outer,
            content=content,
            shot_w=shot_w,
            shot_h=shot_h,
            shot_origin_x=outer.x,
            shot_origin_y=outer.y,
            shot_scale_x=outer_sx,
            shot_scale_y=outer_sy,
            shot_space="outer",
        )

    if abs(content_sx - content_sy) < 0.02:
        return Metrics(
            outer=outer,
            content=content,
            shot_w=shot_w,
            shot_h=shot_h,
            shot_origin_x=content.x,
            shot_origin_y=content.y,
            shot_scale_x=content_sx,
            shot_scale_y=content_sy,
            shot_space="content",
        )

    msg = (
        "截图与 outer/content 都不等比: shot=%sx%s outer=%.0fx%.0f(sx=%.3f,sy=%.3f) "
        "content=%.0fx%.0f(sx=%.3f,sy=%.3f)"
        % (
            shot_w, shot_h, outer.w, outer.h, outer_sx, outer_sy,
            content.w, content.h, content_sx, content_sy,
        )
    )
    if strict:
        raise RuntimeError(msg)
    # best-effort：按 outer
    return Metrics(
        outer=outer,
        content=content,
        shot_w=shot_w,
        shot_h=shot_h,
        shot_origin_x=outer.x,
        shot_origin_y=outer.y,
        shot_scale_x=outer_sx,
        shot_scale_y=outer_sy,
        shot_space="unknown",
    )


def resolve_screen(step, m):
    """回放：优先绝对 CG + 窗口位移；尺寸变了退回 outer 相对坐标。"""
    old_outer = step.get("outer")
    cur = m.outer
    cg_x = step.get("cg_x")
    cg_y = step.get("cg_y")
    if cg_x is not None and cg_y is not None and old_outer:
        old = rect_from(old_outer)
        same_size = abs(cur.w - old.w) <= 2 and abs(cur.h - old.h) <= 2
        if same_size:
            return (
                float(cg_x) + (cur.x - old.x),
                float(cg_y) + (cur.y - old.y),
            )
    fx = float(step.get("fx") if step.get("fx") is not None else 0.5)
    fy = float(step.get("fy") if step.get("fy") is not None else 0.5)
    return outer_to_screen(fx, fy, m)


def resolve_mode(step, m):
    """返回 resolve_screen 实际走的路径：cg+delta | fxfy。"""
    old_outer = step.get("outer")
    cg_x = step.get("cg_x")
    cg_y = step.get("cg_y")
    if cg_x is not None and cg_y is not None and old_outer:
        old = rect_from(old_outer)
        cur = m.outer
        if abs(cur.w - old.w) <= 2 and abs(cur.h - old.h) <= 2:
            return "cg+delta"
    return "fxfy"


def metrics_log_line(m):
    return (
        "metrics outer=(%.0f,%.0f,%.0f,%.0f) content=(%.0f,%.0f,%.0f,%.0f) "
        "shot=(%s,%s) scale=(%.3f,%.3f) origin=(%.0f,%.0f) space=%s"
        % (
            m.outer.x, m.outer.y, m.outer.w, m.outer.h,
            m.content.x, m.content.y, m.content.w, m.content.h,
            m.shot_w, m.shot_h, m.shot_scale_x, m.shot_scale_y,
            m.shot_origin_x, m.shot_origin_y, m.shot_space,
        )
    )


def click_log_lines(source, fx, fy, sx, sy, shot_px, shot_py, orient="", mode="", key=""):
    head = "click source=%s" % source
    if key:
        head += " key=%s" % key
    if orient:
        head += " orient=%s" % orient
    if mode:
        head += " mode=%s" % mode
    return [
        head,
        "  outer=(%.4f,%.4f)" % (float(fx), float(fy)),
        "  screen=(%.1f,%.1f)" % (float(sx), float(sy)),
        "  shot=(%.1f,%.1f)" % (float(shot_px), float(shot_py)),
    ]


def save_metrics_config(path, m):
    data = {
        "shot_space": m.shot_space,
        "shot_scale_x": round(m.shot_scale_x, 4),
        "shot_scale_y": round(m.shot_scale_y, 4),
        "shot_origin_x": m.shot_origin_x,
        "shot_origin_y": m.shot_origin_y,
        "shot_w": m.shot_w,
        "shot_h": m.shot_h,
        "outer": m.outer.as_dict(),
        "content": m.content.as_dict(),
    }
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_metrics_config(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

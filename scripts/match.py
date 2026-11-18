#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在截图里找返回图标。支持多模板、横竖屏 ROI。

输出: fx fy score scale template
fx/fy 相对**截图像素归一化**（screencapture -o 去阴影后）。
调用方必须经 coords.shot_norm_to_screen → screen_to_outer 再点。
ROI 仍按截图比例，与 outer 对齐时即 outer ROI。
"""

import math
import os
import sys

from PIL import Image


def prepare(im, thr=75):
    w, h = im.size
    px = im.load()
    idxs = []
    vals = []
    for y in range(h):
        for x in range(w):
            v = px[x, y]
            if v >= thr:
                idxs.append((x, y))
                vals.append(float(v))
    # 黑底浅色图标：亮点太少时降低阈值再试
    if len(idxs) < 14 and thr > 35:
        return prepare(im, thr=35)
    if len(idxs) < 10:
        return None
    n = float(len(vals))
    mean = sum(vals) / n
    std = math.sqrt(max(1e-2, sum((v - mean) ** 2 for v in vals) / n))
    return idxs, vals, mean, std, w, h


def ncc_at(hay_px, prep, ox, oy):
    idxs, vals, tmean, tstd, _, _ = prep
    n = float(len(idxs))
    samples = [float(hay_px[ox + x, oy + y]) for x, y in idxs]
    pmean = sum(samples) / n
    pvar = sum((v - pmean) ** 2 for v in samples) / n
    cov = sum((samples[i] - pmean) * (vals[i] - tmean) for i in range(len(vals))) / n
    return max(-1.0, min(1.0, cov / (math.sqrt(max(1e-2, pvar)) * tstd)))


def search(hay, prep, roi, step=2, floor=0.55):
    hw, hh = hay.size
    hay_px = hay.load()
    _, _, _, _, nw, nh = prep
    x0 = int(hw * roi[0])
    y0 = int(hh * roi[1])
    x1 = min(hw - nw, int(hw * (roi[0] + roi[2])) - nw)
    y1 = min(hh - nh, int(hh * (roi[1] + roi[3])) - nh)
    if x0 > x1 or y0 > y1:
        return None
    cands = []
    y = y0
    while y <= y1:
        x = x0
        while x <= x1:
            s = ncc_at(hay_px, prep, x, y)
            if s >= floor:
                cands.append((s, x, y))
            x += step
        y += step
    if not cands:
        return None
    cands.sort(reverse=True)
    best = None
    for s0, bx, by in cands[:8]:
        local = (s0, bx, by)
        for yy in range(max(y0, by - step), min(y1, by + step) + 1):
            for xx in range(max(x0, bx - step), min(x1, bx + step) + 1):
                s = ncc_at(hay_px, prep, xx, yy)
                if s > local[0]:
                    local = (s, xx, yy)
        if best is None or local[0] > best[0]:
            best = local
            if best[0] >= 0.97:
                return best
    return best


def land_rois():
    # 横屏：公告关闭多在右上；偶发左上/右下（镜像旋转）
    return [
        (0.82, 0.00, 0.18, 0.22),
        (0.72, 0.00, 0.28, 0.30),
        (0.00, 0.00, 0.22, 0.22),
        (0.78, 0.70, 0.22, 0.30),
    ]


def port_rois():
    # 竖屏窗：游戏横屏时关闭键常落在底右/底左；竖屏公告则在顶右
    return [
        (0.55, 0.70, 0.42, 0.28),
        (0.40, 0.72, 0.55, 0.26),
        (0.72, 0.00, 0.28, 0.22),
        (0.00, 0.70, 0.35, 0.28),
        (0.00, 0.00, 0.28, 0.22),
    ]


def announce_rois(portrait):
    # 少 ROI、先扫常见角，加快速度（避免点完又卡好几秒）
    if portrait:
        return [
            (0.70, 0.00, 0.28, 0.22),
            (0.55, 0.72, 0.42, 0.26),
            (0.00, 0.72, 0.35, 0.26),
            (0.00, 0.00, 0.28, 0.22),
        ]
    return [
        (0.78, 0.00, 0.22, 0.22),
        (0.00, 0.00, 0.22, 0.22),
        (0.78, 0.75, 0.22, 0.25),
        (0.00, 0.75, 0.22, 0.25),
    ]


def continue_rois(portrait):
    # 「继续游戏」：竖屏偏中下；横屏/竖排字偏右侧
    if portrait:
        return [
            (0.20, 0.55, 0.60, 0.40),
            (0.55, 0.35, 0.40, 0.50),
            (0.10, 0.40, 0.40, 0.50),
        ]
    return [
        (0.55, 0.20, 0.42, 0.60),
        (0.20, 0.55, 0.60, 0.40),
        (0.05, 0.20, 0.40, 0.60),
    ]


def _jz_card(base):
    """止戈 / 觉障林 / 开始匹配 / 退出匹配：按当前画面原尺寸找，不再半分辨率多尺度。"""
    name = os.path.basename(base).lower()
    return any(k in name for k in (
        "jz_zhige", "jz_juezhanglin", "jz_start_match", "jz_exit_match",
    ))


def _scaled_jobs(im, path, rois, scales, tag=""):
    out = []
    for sc in scales:
        tw = max(8, int(im.size[0] * sc))
        th = max(8, int(im.size[1] * sc))
        name = path if not tag else (path + tag)
        out.append((im.resize((tw, th), Image.BILINEAR), sc, rois, name))
    return out


def collect_templates(paths, portrait):
    """按方向选模板；公告关闭会四向旋转。"""
    jobs = []
    seen = set()
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        key = os.path.abspath(path)
        if key in seen:
            continue
        seen.add(key)
        base = os.path.basename(path).lower()
        try:
            im = Image.open(path).convert("L")
        except Exception:
            continue

        # 右上角返回标：只扫这一角，不旋转
        if "back_chevron" in base:
            rois = [(0.84, 0.02, 0.16, 0.18)]
            scales = (1.0,)
            jobs.extend(_scaled_jobs(im, path, rois, scales))
            continue

        # 「继续游戏」四个字：横屏在右侧中部，不旋转
        if "continue_label" in base:
            rois = [(0.70, 0.42, 0.26, 0.24)]
            scales = (1.0,)
            jobs.extend(_scaled_jobs(im, path, rois, scales))
            continue

        # 左下角四格菜单：游戏主界面，不旋转
        if "hud_menu" in base:
            rois = [(0.02, 0.76, 0.18, 0.20)]
            scales = (1.0,)
            jobs.extend(_scaled_jobs(im, path, rois, scales))
            continue

        # 「仗剑长啸」开屏标语：底部居中，不旋转
        if "splash_slogan" in base:
            rois = [(0.30, 0.78, 0.45, 0.18)]
            scales = (1.0,)
            jobs.extend(_scaled_jobs(im, path, rois, scales))
            continue

        if base.startswith("jz_"):
            rois = [(0.0, 0.0, 1.0, 1.0)]
            scales = (1.0,) if _jz_card(base) else (0.75, 1.0, 1.25)
            jobs.extend(_scaled_jobs(im, path, rois, scales))
            continue

        # 公告关闭（黑底浅色）：优先用二值模板；尺度/旋转收紧，避免卡顿
        if "announce_close" in base:
            rois = announce_rois(portrait)
            scales = (0.75, 1.0, 1.35, 1.8)
            # 已是旋转文件则不再现场旋转；原图才补四向
            if any(x in base for x in ("_90", "_180", "_270")):
                jobs.extend(_scaled_jobs(im, path, rois, scales))
            else:
                for vim, tag in (
                    (im, ""),
                    (im.transpose(Image.ROTATE_90), "#r90"),
                    (im.transpose(Image.ROTATE_180), "#r180"),
                    (im.transpose(Image.ROTATE_270), "#r270"),
                ):
                    jobs.extend(_scaled_jobs(vim, path, rois, scales, tag))
            continue

        # 刷么鱼菜单/玩法图标：多尺度 + 四向（竖屏窗）
        if base.startswith("moyu_"):
            if "menu" in base:
                rois = announce_rois(portrait)
            else:
                rois = continue_rois(portrait) if not portrait else [
                    (0.05, 0.15, 0.55, 0.70),
                    (0.35, 0.20, 0.55, 0.65),
                    (0.10, 0.50, 0.70, 0.45),
                ]
            scales = (0.55, 0.75, 1.0, 1.3, 1.7)
            jobs.extend(_scaled_jobs(im, path, rois, scales))
            if portrait or "menu" in base:
                for vim, tag in (
                    (im.transpose(Image.ROTATE_90), "#r90"),
                    (im.transpose(Image.ROTATE_270), "#r270"),
                ):
                    jobs.extend(_scaled_jobs(vim, path, rois, scales, tag))
            continue

        # 「继续游戏」按钮/竖排字模板
        if "continue_game" in base:
            if portrait and "land" in base and "port" not in base:
                continue
            if (not portrait) and "port" in base:
                continue
            rois = continue_rois(portrait)
            scales = (0.45, 0.6, 0.8, 1.0, 1.2)
            jobs.extend(_scaled_jobs(im, path, rois, scales))
            if portrait and "port" in base:
                jobs.extend(_scaled_jobs(
                    im.transpose(Image.ROTATE_90), path, rois, scales, "#r90"))
                jobs.extend(_scaled_jobs(
                    im.transpose(Image.ROTATE_270), path, rois, scales, "#r270"))
            continue

        if portrait:
            if "land" in base and "port" not in base:
                continue
            rois = port_rois()
            if "port" in base or "alt" in base or base in ("back.png", "back_user.png", "back_live.png"):
                jobs.append((im, 1.0, rois, path))
            elif "popup_close" in base or base.startswith("back_popup"):
                jobs.extend(_scaled_jobs(im, path, rois, (0.7, 0.85, 1.0, 1.2, 1.5, 2.0)))
                jobs.extend(_scaled_jobs(
                    im.transpose(Image.ROTATE_90), path, rois, (0.85, 1.0, 1.3), "#r90"))
                jobs.extend(_scaled_jobs(
                    im.transpose(Image.ROTATE_270), path, rois, (0.85, 1.0, 1.3), "#r270"))
        else:
            if "port" in base:
                continue
            rois = land_rois()
            if "popup_close" in base or base.startswith("back_popup"):
                jobs.extend(_scaled_jobs(im, path, rois, (0.7, 0.85, 1.0, 1.2, 1.5, 2.0)))
            else:
                jobs.append((im, 1.0, rois, path))
    if jobs:
        return jobs
    # 兜底：只有一张图时，竖屏才旋转一次
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            im = Image.open(path).convert("L")
        except Exception:
            continue
        if portrait:
            jobs.append((im.transpose(Image.ROTATE_270), 1.0, port_rois(), path + "#rot270"))
            jobs.append((im.transpose(Image.ROTATE_90), 1.0, port_rois(), path + "#rot90"))
        else:
            jobs.append((im, 1.0, land_rois(), path))
        break
    return jobs


def main():
    args = sys.argv[1:]
    roi_arg = None
    templates = []
    if "--roi" in args:
        i = args.index("--roi")
        roi_arg = tuple(float(args[i + k]) for k in range(1, 5))
        args = args[:i] + args[i + 5:]
    while "--template" in args:
        i = args.index("--template")
        if i + 1 < len(args):
            templates.append(args[i + 1])
            args = args[:i] + args[i + 2:]
        else:
            break
    if len(args) < 2 and not templates:
        print("usage: match.py hay.png needle.png [minScore] [--template more.png ...]", file=sys.stderr)
        return 1
    hay_path = args[0]
    if not templates:
        templates = [args[1]]
        min_score = float(args[2]) if len(args) >= 3 else 0.85
    else:
        if len(args) >= 2 and not args[1].replace(".", "", 1).isdigit():
            templates.insert(0, args[1])
            min_score = float(args[2]) if len(args) >= 3 else 0.85
        else:
            min_score = float(args[1]) if len(args) >= 2 else 0.85

    hay = Image.open(hay_path).convert("L")
    portrait = hay.size[1] > hay.size[0] * 1.08
    jobs = collect_templates(templates, portrait)
    if roi_arg:
        jobs = [(im, scale, [roi_arg], name) for im, scale, _, name in jobs]

    best = None
    weak = -1.0
    weak_name = ""
    for im, scale, rois, name in jobs:
        base = os.path.basename(name).lower()
        hay_use = hay
        prep_im = im
        # 「继续游戏」、菜单、小图标先半分辨率扫。大卡片按原图找，半分辨率会把细字分数打下去。
        if (
            "hud_menu" in base or "splash_slogan" in base
            or (base.startswith("jz_") and not _jz_card(base))
        ):
            hay_use = hay.resize((max(8, hay.size[0] // 2), max(8, hay.size[1] // 2)), Image.BOX)
            prep_im = im.resize((max(8, im.size[0] // 2), max(8, im.size[1] // 2)), Image.BOX)
        prep = prepare(prep_im)
        if not prep:
            continue
        step = 2 if _jz_card(base) else 1 if (
            "back_chevron" in base or "continue_label" in base
            or "hud_menu" in base or "splash_slogan" in base or base.startswith("jz_")
        ) else (
            2 if max(prep[4], prep[5]) > 40 else 1
        )
        for roi in rois:
            # 细字模板差一个像素分数就掉下去，粗扫先放低，再在附近找最高点
            floor = 0.45 if _jz_card(base) else 0.55
            hit = search(hay_use, prep, roi, step=step, floor=floor)
            if not hit:
                continue
            if hit[0] > weak:
                weak = hit[0]
                weak_name = name
            if hit[0] < min_score:
                continue
            fx = (hit[1] + prep[4] / 2.0) / hay_use.size[0]
            fy = (hit[2] + prep[5] / 2.0) / hay_use.size[1]
            cand = (hit[0], fx, fy, scale, name)
            if best is None or cand[0] > best[0]:
                best = cand
            if best[0] >= 0.90:
                print("%.4f\t%.4f\t%.3f\t%.2f\t%s" % (best[1], best[2], best[0], best[3], os.path.basename(best[4])))
                return 0
    if not best:
        print("none\t%.3f\t%s" % (weak, os.path.basename(weak_name) if weak_name else ""))
        return 0
    print("%.4f\t%.4f\t%.3f\t%.2f\t%s" % (best[1], best[2], best[0], best[3], os.path.basename(best[4])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

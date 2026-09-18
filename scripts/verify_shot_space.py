#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 0 步：对比 screencapture -l 与 -o -l，写入 data/coord_config.json。"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import coords as coordlib
import mirror_keeper as mk


def main():
    info = mk.window_info()
    if not info:
        print("没有 iPhone 镜像窗口，请先打开镜像后再跑：")
        print("  python3 scripts/verify_shot_space.py")
        return 1
    wid = info["window_id"]
    outer = info["outer_dict"]
    content = info["content_dict"]
    print("windowId", wid)
    print("outer", outer)
    print("content", content)

    paths = {
        "with_shadow": "/tmp/gp_with_shadow.png",
        "no_shadow": "/tmp/gp_no_shadow.png",
    }
    subprocess.run(["screencapture", "-x", "-l", str(wid), paths["with_shadow"]], check=False)
    subprocess.run(["screencapture", "-x", "-o", "-l", str(wid), paths["no_shadow"]], check=False)

    from PIL import Image
    for name, p in paths.items():
        if not os.path.isfile(p) or os.path.getsize(p) < 100:
            print(name, "截图失败")
            continue
        im = Image.open(p)
        w, h = im.size
        print("%s size=%sx%s" % (name, w, h))
        try:
            m = coordlib.build_metrics(
                {"outer": outer, "content": content}, w, h, strict=False
            )
            print("  → space=%s scale=(%.3f,%.3f) origin=(%.0f,%.0f)" % (
                m.shot_space, m.shot_scale_x, m.shot_scale_y, m.shot_origin_x, m.shot_origin_y,
            ))
            if name == "no_shadow":
                out = coordlib.save_metrics_config(
                    os.path.join(ROOT, "data", "coord_config.json"), m
                )
                print("已写入 data/coord_config.json:")
                print(json.dumps(out, ensure_ascii=False, indent=2))
        except Exception as e:
            print("  →", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""素材处理脚本：把 assets/raw/sprite_sheet.png (3列x2行) 切成 6 张姿势图，
品红色 (#FF00FF) 背景转透明，去除边缘紫边，统一画布尺寸（底部居中对齐），
并生成托盘图标 icon.ico。

用法:  python tools/process_assets.py
"""
import os
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "assets", "raw", "sprite_sheet.png")
OUT = os.path.join(ROOT, "assets")

# 网格中 6 个姿势的名称（行优先）
NAMES = ["idle", "blink", "shy", "panic", "sleep", "tea"]
COLS, ROWS = 3, 2
INSET = 10           # 每个格子向内收缩，避免切到分隔线
MAGENTA_THRESH = 96  # 与品红色的距离阈值


def key_out_magenta(img):
    """品红背景 -> 透明，并柔化边缘、去除紫红色描边残留。"""
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            d = (255 - r) + g + (255 - b)  # 与 #FF00FF 的曼哈顿距离
            if d < MAGENTA_THRESH:
                px[x, y] = (0, 0, 0, 0)
            elif d < MAGENTA_THRESH * 2:
                # 过渡带：去掉品红偏色并做半透明
                m = max(0, min(255, (r + b) // 2 - g))
                nr = max(0, r - m // 2)
                nb = max(0, b - m // 2)
                alpha = int(255 * (d - MAGENTA_THRESH) / MAGENTA_THRESH)
                px[x, y] = (nr, g, nb, min(a, alpha))
    r_, g_, b_, a_ = img.split()
    a_ = a_.filter(ImageFilter.GaussianBlur(0.6))
    img.putalpha(a_)
    return img

def main():
    sheet = Image.open(RAW).convert("RGBA")
    W, H = sheet.size
    cw, ch = W // COLS, H // ROWS

    trimmed = {}
    for i, name in enumerate(NAMES):
        c, r = i % COLS, i // COLS
        box = (c * cw + INSET, r * ch + INSET,
               (c + 1) * cw - INSET, (r + 1) * ch - INSET)
        cell = key_out_magenta(sheet.crop(box))
        bbox = cell.getbbox()
        trimmed[name] = cell.crop(bbox) if bbox else cell

    # 统一画布：底部居中对齐，动画帧之间不跳动
    cw_max = max(im.width for im in trimmed.values())
    ch_max = max(im.height for im in trimmed.values())
    for name, im in trimmed.items():
        canvas = Image.new("RGBA", (cw_max, ch_max), (0, 0, 0, 0))
        canvas.paste(im, ((cw_max - im.width) // 2, ch_max - im.height), im)
        canvas.save(os.path.join(OUT, name + ".png"))
        print("saved assets/%s.png (%dx%d)" % (name, cw_max, ch_max))

    # 托盘图标：取 idle 姿势头部区域，做成正方形 ico
    idle = trimmed["idle"]
    head = idle.crop((0, 0, idle.width, idle.width))
    side = max(head.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(head, ((side - head.width) // 2, (side - head.height) // 2), head)
    sq.save(os.path.join(OUT, "icon.png"))
    sq.resize((256, 256), Image.LANCZOS).save(
        os.path.join(OUT, "icon.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("saved assets/icon.png, assets/icon.ico")


if __name__ == "__main__":
    main()

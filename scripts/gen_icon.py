"""用 PySide6 生成 MouthWrite 应用图标（.ico），无需 Pillow。"""

import struct
import sys
import io
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QPen
from PySide6.QtCore import Qt, QRect, QBuffer, QIODevice


def render_icon(size: int) -> QPixmap:
    """绘制一个尺寸为 size x size 的图标 pixmap。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 背景渐变（深蓝 → 紫蓝）
    margin = int(size * 0.06)
    rect = QRect(margin, margin, size - margin * 2, size - margin * 2)
    radius = size * 0.22

    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#4a6cf7"))
    grad.setColorAt(1.0, QColor("#7c3aed"))
    p.setBrush(grad)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(rect, radius, radius)

    # 绘制 "M" 字母
    p.setPen(QColor(255, 255, 255))
    p.setBrush(Qt.BrushStyle.NoBrush)
    font = QFont("Segoe UI", int(size * 0.38), QFont.Weight.Bold)
    p.setFont(font)
    text_rect = QRect(int(-size * 0.06), 0, size, size)
    p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "M")

    # 右侧声波弧线
    wave_pen = QPen(QColor(255, 255, 255, 200))
    wave_pen.setWidth(max(1, int(size * 0.035)))
    wave_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(wave_pen)

    cx = int(size * 0.76)
    cy = int(size * 0.46)
    for i, r in enumerate([size * 0.08, size * 0.15, size * 0.22]):
        alpha = 220 - i * 50
        wave_pen.setColor(QColor(255, 255, 255, alpha))
        p.setPen(wave_pen)
        arc_rect = QRect(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
        p.drawArc(arc_rect, -35 * 16, 70 * 16)  # 弧度单位是 1/16 度

    p.end()
    return pixmap


def pixmap_to_png_bytes(pixmap: QPixmap) -> bytes:
    """将 QPixmap 转为 PNG 字节。"""
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buf, "PNG")
    return bytes(buf.data())


def build_ico(png_data_list: list[tuple[int, bytes]]) -> bytes:
    """从多个 (size, png_bytes) 构建 .ico 文件。"""
    count = len(png_data_list)

    # ICO 头部：6 字节
    header = struct.pack("<HHH", 0, 1, count)

    # 计算每个图像条目的偏移
    entries_size = 16 * count
    offset = 6 + entries_size

    entries = b""
    image_data = b""

    for size, png_bytes in png_data_list:
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        entry = struct.pack(
            "<BBBBHHII",
            w,            # width (0 = 256)
            h,            # height (0 = 256)
            0,            # color palette
            0,            # reserved
            1,            # color planes
            32,           # bits per pixel
            len(png_bytes),  # image size
            offset,       # offset
        )
        entries += entry
        image_data += png_bytes
        offset += len(png_bytes)

    return header + entries + image_data


def main():
    app = QApplication(sys.argv)

    sizes = [256, 128, 64, 48, 32, 16]
    png_list = []
    for s in sizes:
        pm = render_icon(s)
        png_list.append((s, pixmap_to_png_bytes(pm)))

    ico_bytes = build_ico(png_list)

    out = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(ico_bytes)
    print(f"图标已生成: {out}  ({len(ico_bytes)} bytes, {len(sizes)} 个尺寸)")

    # 同时保存一份 256x256 PNG 预览
    preview = out.parent / "icon_preview.png"
    render_icon(256).save(str(preview), "PNG")
    print(f"预览已保存: {preview}")


if __name__ == "__main__":
    main()

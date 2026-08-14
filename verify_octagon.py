# -*- coding: utf-8 -*-
"""验证: 1) 信号名不越过八边形边(实际文字盒采样) 2) 注释框不重叠(实际渲染包围盒)"""
import json
import sys
import math

sys.path.insert(0, '.')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from parse import (get_signals, _split_byte_segments, _octagon_geometry,
                   _octagon_edge_point, _octagon_outward, _measure_text,
                   _layout_octagon_annotations, ldfparser)


def point_in_poly(px, py, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def text_box_corners(anchor, theta_deg, length, height, ha):
    """实际文字盒的角点与边中点(旋转后)，ha='left' 向前延伸, 'right' 向后延伸"""
    th = math.radians(theta_deg)
    c, s = math.cos(th), math.sin(th)
    pts = []
    sgn = -1.0 if ha == 'right' else 1.0
    for x, y in [(0.0, -height / 2), (0.0, height / 2),
                 (sgn * length, -height / 2), (sgn * length, height / 2)]:
        pts.append((anchor[0] + x * c - y * s, anchor[1] + x * s + y * c))
    mids = []
    for i in range(4):
        j = (i + 1) % 4
        mids.append(((pts[i][0] + pts[j][0]) / 2, (pts[i][1] + pts[j][1]) / 2))
    return pts + mids


def main():
    ldf = ldfparser.parse_ldf(path='LDF_EESystem25_23KW51_V36_M_LIN_4_V297.ldf', encoding='latin-1')
    ann = json.load(open('annotations.json', encoding='utf-8'))
    all_ok = True
    for frame_name, items in ann.items():
        frame = ldf.get_unconditional_frame(frame_name)
        signals = get_signals(frame)
        verts, byte_edges = _octagon_geometry()
        OFF, W = 0.07, 0.16
        ann_items = []
        for sig in signals:
            text = (items.get(sig['name']) or '').strip()
            if text:
                ann_items.append((sig, text))

        fig, ax = plt.subplots(figsize=(9, 9))
        ax.set_aspect('equal')
        ax.set_title('t', pad=12)
        plt.tight_layout()
        lim = 1.5 + 0.30 * max(len(ann_items), 1)
        ann_layout = []
        for _ in range(6):
            ax.set_xlim(-lim, lim)
            ax.set_ylim(-lim, lim)
            ann_layout, max_ext = _layout_octagon_annotations(ax, ann_items, verts, byte_edges, OFF, W, lim)
            new_lim = max(lim, max_ext + 0.35)
            if new_lim <= lim * 1.005:
                lim = new_lim
                break
            lim = new_lim
        else:
            lim = max(lim, max_ext + 0.35)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        fig.canvas.draw()

        # ---- 1) 信号名实际文字盒是否越过八边形边 ----
        poly = verts
        crossing = []
        for sig in signals:
            segs = _split_byte_segments(sig)
            b, j0, j1 = segs[0]
            cmid = (j0 / 8 + (j1 + 1) / 8) / 2
            mx, my = _octagon_edge_point(verts, byte_edges, b, cmid)
            nx, ny = _octagon_outward(verts, byte_edges, b)
            rad_ang = math.degrees(math.atan2(ny, nx))
            if rad_ang > 90 or rad_ang < -90:
                rad_ang += 180
            ha = 'right' if nx < 0 else 'left'
            ln = len(sig['name'])
            fs = 6.5 if ln <= 12 else 5.8 if ln <= 20 else 5.0 if ln <= 28 else 4.2
            name_w, name_h = _measure_text(ax, sig['name'], fs)
            anchor = (mx + nx * OFF, my + ny * OFF)
            for px, py in text_box_corners(anchor, rad_ang, name_w, name_h, ha):
                if point_in_poly(px, py, poly):
                    crossing.append(sig['name'])
                    break

        # ---- 2) 注释文本框实际渲染是否重叠 ----
        overlaps = []
        rects = []
        for sig, wrapped, cx, cy in ann_layout:
            t = ax.text(cx, cy, wrapped, ha='center', va='center', fontsize=7,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='#fff8e1',
                                  edgecolor='#c0392b', lw=0.8))
            fig.canvas.draw()
            bb = t.get_window_extent(renderer=fig.canvas.get_renderer())
            inv = ax.transData.inverted()
            x0, y0 = inv.transform((bb.x0, bb.y0))
            x1, y1 = inv.transform((bb.x1, bb.y1))
            rects.append((sig['name'], x0, y0, x1, y1))
            t.remove()
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                n1, a0, b0, a1, b1 = rects[i]
                n2, c0, d0, c1, d1 = rects[j]
                if a0 < c1 and a1 > c0 and b0 < d1 and b1 > d0:
                    overlaps.append((n1, n2))
        plt.close(fig)

        print('[%s] 名称越过八边形边的信号: %s' % (frame_name, crossing if crossing else '无'))
        print('[%s] 注释框渲染重叠: %s' % (frame_name, overlaps if overlaps else '无'))
        if crossing or overlaps:
            all_ok = False
    print('== 全部通过 ==' if all_ok else '== 存在问题 ==')


if __name__ == '__main__':
    main()
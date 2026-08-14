# -*- coding: utf-8 -*-
"""压力测试: 全部信号加长注释, 验证名称越界 + 注释重叠"""
import sys
import math

sys.path.insert(0, '.')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from parse import (get_signals, _split_byte_segments, _octagon_geometry,
                   _octagon_edge_point, _octagon_outward, _measure_text,
                   _layout_octagon_annotations, ldfparser, plot_single_frame_octagon)


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


ldf = ldfparser.parse_ldf(path='LDF_EESystem25_23KW51_V36_M_LIN_4_V297.ldf', encoding='latin-1')
frame = ldf.get_unconditional_frame('ST_FAN_1_LIN')
signals = get_signals(frame)
verts, byte_edges = _octagon_geometry()
OFF, W = 0.07, 0.16

items = {sig['name']: ('注释%d: 该信号表示发动机风扇转速上报值，转化公式 raw*0.4 单位 rpm' % i)
         for i, sig in enumerate(signals)}
ann_items = [(sig, items[sig['name']]) for sig in signals]

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
print('converged lim = %.2f' % lim)

# 名称越界检查(实际文字盒)
poly = verts
cross = []
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
            cross.append(sig['name'])
            break

# 注释重叠检查(实际渲染包围盒)
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
over = []
for i in range(len(rects)):
    for j in range(i + 1, len(rects)):
        n1, a0, b0, a1, b1 = rects[i]
        n2, c0, d0, c1, d1 = rects[j]
        if a0 < c1 and a1 > c0 and b0 < d1 and b1 > d0:
            over.append((n1, n2))
plt.close(fig)

print('名称越过八边形边的信号(%d): %s' % (len(cross), cross if cross else '无'))
print('注释框重叠(%d对): %s' % (len(over), over[:8] if over else '无'))

# 生成压力测试图
plot_single_frame_octagon(ldf, 'ST_FAN_1_LIN', output_dir='output', annotations=items)
print('压力测试图: output/ST_FAN_1_LIN_signal_mapping_octagon.png')
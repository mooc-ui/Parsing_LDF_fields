
#!/usr/bin/env python3
"""
LIN LDF Signal Mapping Visualizer
解析 LDF 文件并生成类似 CANoe/Vector 风格的 Signal Mapping 图
支持: CLI 直接运行 (python parse.py) 或作为模块被 gui.py 调用
"""

import ldfparser
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, PathPatch, Circle
from matplotlib.path import Path
from matplotlib.colors import LinearSegmentedColormap
import os
import math
import textwrap

# ==================== 中文字体配置 ====================
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "Noto Sans SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# ==================== 配置 ====================
LDF_PATH = "./LDF_EESystem25_23KW51_V36_M_LIN_4_V297.ldf"
OUTPUT_DIR = "./output"
DEFAULT_FRAMES = [
    "ST_FAN_1_LIN",
    "CTR_FAN_LIN",
    "StatusThreeWayValveBatt48LIN",
    "ControlThreeWayValveBatt48LIN",
]


# ==================== 工具函数 ====================
def get_signals(frame):
    """获取帧内信号列表（按起始位排序）"""
    signals = []
    for start_bit, sig in sorted(frame.signal_map, key=lambda x: x[0]):
        signals.append({
            "name": sig.name,
            "start": start_bit,
            "size": sig.width,
            "end": start_bit + sig.width - 1
        })
    return signals


def draw_signal_label(ax, sig, y, base_fs=6.5, min_fs=3.0):
    """绘制信号完整标识符（不简写），窄字段或长名称时自动旋转/缩字体"""
    name = sig["name"]
    rot = 90 if sig["size"] < 8 else 0
    width_lim = base_fs * sig["size"] / 10.0 if rot == 0 else base_fs * sig["size"] / max(len(name), 4)
    len_lim = base_fs * 10.0 / max(len(name), 10) + 0.5
    fs = max(min_fs, min(base_fs, width_lim, len_lim))
    ax.text(sig["start"] + sig["size"] / 2, y, name, ha="center", va="center",
            rotation=rot, fontsize=fs, fontweight="normal", color="#111", zorder=5)


def plot_single_frame(ldf, frame_name, output_dir=OUTPUT_DIR, save_png=True, save_svg=True, dpi=300,
                      annotations=None):
    """绘制单帧 Signal Mapping 图，返回生成的文件路径列表

    annotations: dict {信号名: 注释文本}，注释会以引线+文本框绘制在信号块下方
    """
    frame = ldf.get_unconditional_frame(frame_name)
    signals = get_signals(frame)
    total_bits = frame.length * 8

    # 收集该帧的注释（按信号顺序，与信号块保持对应）
    ann_items = []
    if annotations:
        for sig in signals:
            text = (annotations.get(sig["name"]) or "").strip()
            if text:
                ann_items.append((sig, text))

    # 注释区高度：每个注释一行(0.32)，多行注释按行数扩展
    ann_rows = 0
    for _, text in ann_items:
        n_lines = len(textwrap.wrap(text, 28)) if any('\u4e00' <= ch <= '\u9fff' for ch in text) \
            else len(textwrap.wrap(text, 50))
        ann_rows += n_lines
    ann_height = 0.32 * max(ann_rows, len(ann_items))

    # 颜色渐变（黄绿 → 青绿 → 深蓝）
    colors = ["#f0e68c", "#c5e1a5", "#81c784", "#4db6ac", "#26a69a",
              "#00897b", "#00695c", "#004d40", "#1a237e", "#0d47a1", "#ffcc80"]
    cmap = LinearSegmentedColormap.from_list("custom", colors, N=len(signals))

    fig_h = 5 + ann_height
    fig, ax = plt.subplots(figsize=(max(8, frame.length * 2.25), fig_h))
    ax.set_facecolor("#fafafa")

    # 垂直网格线
    for i in range(total_bits + 1):
        lw = 1.2 if i % 8 == 0 else 0.4
        color = "#333" if i % 8 == 0 else "#ccc"
        ax.axvline(i, color=color, linewidth=lw, ymin=0.15, ymax=0.85, zorder=1)

    # 绘制信号块
    for i, sig in enumerate(signals):
        color = cmap(i / max(len(signals) - 1, 1))
        rect = Rectangle((sig["start"], 0.35), sig["size"], 0.3,
                         facecolor=color, edgecolor="#222", linewidth=0.6, alpha=0.9, zorder=2)
        ax.add_patch(rect)

        # 信号完整标识符（不简写）
        draw_signal_label(ax, sig, 0.72)

    # 中间高亮斜线（仅 ST_FAN_1_LIN 原图风格，对应 AVL_U 区域）
    if frame.name == "ST_FAN_1_LIN":
        hatch_rect = Rectangle((24, 0.35), 8, 0.3, facecolor="none", edgecolor="#555",
                               linewidth=0.8, hatch="///", alpha=0.6, zorder=3)
        ax.add_patch(hatch_rect)

    # 底部箭头
    for i in range(0, total_bits, 2):
        ax.annotate("", xy=(i + 1.5, 0.28), xytext=(i + 0.5, 0.28),
                    arrowprops=dict(arrowstyle="->", color="black", lw=0.8), zorder=4)

    # 顶部字节号
    for i in range(frame.length):
        ax.text(i * 8 + 4, 0.95, str(i), ha="center", va="center", fontsize=11, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.8))

    # 底部 bit 编号
    for i in range(0, total_bits, 8):
        ax.text(i, 0.08, str(i), ha="center", va="top", fontsize=8, color="#333")
    for i in range(7, total_bits, 8):
        ax.text(i, 0.08, str(i), ha="center", va="top", fontsize=7, color="#666")

    ax.set_title(f"Signal Mapping — {frame.name}  (Frame ID: {frame.frame_id}, Length: {frame.length} bytes)",
                 fontsize=13, fontweight="bold", pad=10)
    ax.set_xlim(-0.5, total_bits + 0.5)
    ax.set_ylim(-ann_height - 0.12 if ann_items else 0, 1.1)
    ax.set_yticks([])
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # ===== 绘制注释（引线 + 文本框，位于信号块下方） =====
    y_cursor = -0.08
    for sig, text in ann_items:
        cx = sig["start"] + sig["size"] / 2
        # 引线：从信号块下边缘到注释框上边缘
        ax.plot([cx, cx], [0.35, y_cursor + 0.20], color="#c0392b", lw=0.9, zorder=4)

        # 注释文本框
        wrap_w = 28 if any('\u4e00' <= ch <= '\u9fff' for ch in text) else 50
        wrapped = "\n".join(textwrap.wrap(text, wrap_w)) or text
        ax.text(cx, y_cursor + 0.16, wrapped, ha="center", va="center", fontsize=8,
                color="#222", zorder=5,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="#fff8e1",
                          edgecolor="#c0392b", lw=0.8))
        n_lines = len(wrapped.split("\n"))
        y_cursor -= 0.22 * n_lines + 0.10

    plt.tight_layout()

    saved = []
    if save_png:
        png_path = f"{output_dir}/{frame_name}_signal_mapping.png"
        plt.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        saved.append(png_path)
    if save_svg:
        svg_path = f"{output_dir}/{frame_name}_signal_mapping.svg"
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
        saved.append(svg_path)
    plt.close()
    return saved


# ==================== 八边形布局 ====================
def _octagon_geometry():
    """正八边形几何：顶点(8个)与字节边定义(byte b -> (起点顶点, 终点顶点))
    顶点 k 角度 = 67.5° + 45°*k；byte0=顶边(左→右)，顺时针排列"""
    R = 1.0
    verts = []
    for k in range(8):
        ang = math.radians(67.5 + 45 * k)
        verts.append((R * math.cos(ang), R * math.sin(ang)))
    byte_edges = [(1, 0), (0, 7), (7, 6), (6, 5), (5, 4), (4, 3), (3, 2), (2, 1)]
    return verts, byte_edges


def _octagon_edge_point(verts, byte_edges, b, t):
    """字节边 b 上参数 t (0~1) 处的坐标（t=0 起点顶点, t=1 终点顶点）"""
    ks, ke = byte_edges[b]
    x0, y0 = verts[ks]
    x1, y1 = verts[ke]
    return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)


def _octagon_outward(verts, byte_edges, b):
    """字节边 b 的外法向（单位向量），正八边形边中点径向即外法向"""
    mx, my = _octagon_edge_point(verts, byte_edges, b, 0.5)
    L = math.hypot(mx, my)
    return (mx / L, my / L)


def _octagon_block_quad(verts, byte_edges, b, t0, t1, off, width):
    """信号块四边形：字节边 b 上 [t0,t1] 段，沿外法向偏移 off~off+width"""
    p0 = _octagon_edge_point(verts, byte_edges, b, t0)
    p1 = _octagon_edge_point(verts, byte_edges, b, t1)
    nx, ny = _octagon_outward(verts, byte_edges, b)
    return [(p0[0] + nx * off, p0[1] + ny * off),
            (p1[0] + nx * off, p1[1] + ny * off),
            (p1[0] + nx * (off + width), p1[1] + ny * (off + width)),
            (p0[0] + nx * (off + width), p0[1] + ny * (off + width))]


def _split_byte_segments(sig):
    """把信号拆成按字节分段的 [(byte, j0, j1)]，j0/j1 为该字节内 bit 序号(含两端)"""
    segs = []
    s, e = sig["start"], sig["end"]
    for b in range(s // 8, e // 8 + 1):
        j0 = s if b == s // 8 else b * 8
        j1 = e if b == e // 8 else b * 8 + 7
        segs.append((b, j0 - b * 8, j1 - b * 8))
    return segs


def _rect_overlap(rect, placed):
    """判断轴对齐矩形 rect 是否与已放置矩形列表 placed 中任意一个重叠"""
    ax0, ay0, ax1, ay1 = rect
    for bx0, by0, bx1, by1 in placed:
        if ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0:
            return True
    return False


def _measure_text(ax, text, fs):
    """测量文本（含 bbox 边框）在数据坐标系中的实际渲染尺寸 (w, h)。

    依赖当前 axes 的变换（xlim/ylim/tight_layout 已就位），用于防重叠布局。
    """
    fig = ax.figure
    inv = ax.transData.inverted()
    t = ax.text(0, 0, text, ha="center", va="center", fontsize=fs,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff8e1",
                          edgecolor="#c0392b", lw=0.8))
    fig.canvas.draw()
    bb = t.get_window_extent(renderer=fig.canvas.get_renderer())
    x0, y0 = inv.transform((bb.x0, bb.y0))
    x1, y1 = inv.transform((bb.x1, bb.y1))
    t.remove()
    return x1 - x0, y1 - y0


def _layout_octagon_annotations(ax, ann_items, verts, byte_edges, OFF, W, lim):
    """八边形注释防重叠布局（基于实际渲染尺寸测量）

    沿各信号径向放置注释框，用碰撞检测（半径递增 × 切向偏移）搜索无重叠位置；
    同时避开该信号自身的名称文字（名称沿径向从块内边缘向外延伸）。
    返回 ([(sig, wrapped, cx, cy)], 最大外接半径)。
    """
    placed = []          # 已放置文本框矩形
    out = []
    base_r, r_step = 0.5, 0.14
    max_r = lim * 0.90
    t_offs = (0.0, 0.18, -0.18, 0.36, -0.36, 0.54, -0.54, 0.72, -0.72,
              0.90, -0.90, 1.08, -1.08, 1.44, -1.44, 1.80, -1.80)
    max_ext = 0.0

    for sig, text in ann_items:
        segs = _split_byte_segments(sig)
        b, j0, j1 = segs[0]
        t0, t1 = j0 / 8, (j1 + 1) / 8
        cmid = (t0 + t1) / 2
        mx, my = _octagon_edge_point(verts, byte_edges, b, cmid)
        nx, ny = _octagon_outward(verts, byte_edges, b)
        anchor = (mx + nx * (OFF + W), my + ny * (OFF + W))
        L = math.hypot(anchor[0], anchor[1])
        ux, uy = anchor[0] / L, anchor[1] / L
        # 切向单位向量（沿字节边方向，用于切向错开）
        ks, ke = byte_edges[b]
        tx, ty = verts[ke][0] - verts[ks][0], verts[ke][1] - verts[ks][1]
        tl = math.hypot(tx, ty)
        tx /= tl
        ty /= tl

        # 文本换行
        wrap_w = 22 if any('\u4e00' <= ch <= '\u9fff' for ch in text) else 40
        wrapped = "\n".join(textwrap.wrap(text, wrap_w)) or text
        # 实际渲染尺寸（数据单位，含边框）
        w, h = _measure_text(ax, wrapped, 7.0)

        # 自身信号名占用的径向外端（名称锚定块内边缘、沿径向向外延伸）
        ln = len(sig["name"])
        if ln <= 12:
            nfs = 6.5
        elif ln <= 20:
            nfs = 5.8
        elif ln <= 28:
            nfs = 5.0
        else:
            nfs = 4.2
        name_len, _ = _measure_text(ax, sig["name"], nfs)
        name_outer = (mx + nx * (OFF + name_len), my + ny * (OFF + name_len))
        name_outer_dist = math.hypot(name_outer[0], name_outer[1])
        min_r = name_outer_dist + 0.12 + h / 2 - L

        # 搜索无重叠位置：半径递增 × 切向偏移
        pos = None
        for i in range(40):
            r = base_r + i * r_step
            if r > max_r:
                break
            if r < min_r:
                continue
            for t_off in t_offs:
                cx = anchor[0] + ux * r + tx * t_off
                cy = anchor[1] + uy * r + ty * t_off
                rect = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
                if not _rect_overlap(rect, placed):
                    pos = (cx, cy, rect)
                    break
            if pos is not None:
                break
        if pos is None:   # 兜底：放在基础位置
            cx = anchor[0] + ux * base_r
            cy = anchor[1] + uy * base_r
            pos = (cx, cy, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
        placed.append(pos[2])
        max_ext = max(max_ext, abs(pos[0]) + w / 2, abs(pos[1]) + h / 2)
        out.append((sig, wrapped, pos[0], pos[1]))
    return out, max_ext


def plot_single_frame_octagon(ldf, frame_name, output_dir=OUTPUT_DIR, save_png=True, save_svg=True,
                              dpi=300, annotations=None):
    """绘制八边形布局单帧图（8条边=8字节，每条边8 bit，中心区帧信息）

    规则：
    - 字节按顺时针排列，byte0 顶边左→右，bit0 为该边最左端
    - 帧长 < 8 字节时，空余边以虚线 + "Reserved" 标记
    - 跨字节信号拆分为多段分别绘于各字节边，段间用弧线连接
    - 注释以引线+文本框绘制在八边形外侧（沿信号径向）
    """
    from matplotlib.patches import FancyArrowPatch

    frame = ldf.get_unconditional_frame(frame_name)
    signals = get_signals(frame)
    total_bits = frame.length * 8
    n_bytes = frame.length

    verts, byte_edges = _octagon_geometry()

    # 颜色渐变（与线性布局一致）
    colors = ["#f0e68c", "#c5e1a5", "#81c784", "#4db6ac", "#26a69a",
              "#00897b", "#00695c", "#004d40", "#1a237e", "#0d47a1", "#ffcc80"]
    cmap = LinearSegmentedColormap.from_list("custom", colors, N=len(signals))

    # 收集注释
    ann_items = []
    if annotations:
        for sig in signals:
            text = (annotations.get(sig["name"]) or "").strip()
            if text:
                ann_items.append((sig, text))

    # 区块偏移参数（半径单位）
    OFF, W = 0.07, 0.16   # 信号块外偏移与宽度
    LABEL_R = OFF + W + 0.10   # Reserved 标签半径（外侧）
    BYTE_LABEL_R = 0.20        # 字节标签内偏移（向中心，避开径向信号名文字）

    fig, ax = plt.subplots(figsize=(9, 9))
    ax.set_facecolor("#fafafa")
    ax.set_aspect("equal")

    # 八边形外轮廓（浅灰填充）
    poly = Polygon(verts, closed=True, facecolor="#f2f4f7", edgecolor="#555",
                   linewidth=1.2, zorder=1)
    ax.add_patch(poly)

    # 每条边的 bit 刻度（1~7 分隔线）与字节标签
    for b in range(8):
        nx, ny = _octagon_outward(verts, byte_edges, b)
        if b >= n_bytes:
            # Reserved 边：虚线 + 标签
            p0 = _octagon_edge_point(verts, byte_edges, b, 0.0)
            p1 = _octagon_edge_point(verts, byte_edges, b, 1.0)
            ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color="#bbb", lw=1.0,
                    linestyle=(0, (4, 3)), zorder=2)
            mx, my = _octagon_edge_point(verts, byte_edges, b, 0.5)
            ax.text(mx + nx * LABEL_R, my + ny * LABEL_R, "Reserved",
                    ha="center", va="center", fontsize=6.5, color="#999",
                    fontstyle="italic", zorder=6)
            continue
        for j in range(1, 8):
            px, py = _octagon_edge_point(verts, byte_edges, b, j / 8)
            ax.plot([px + nx * (OFF - 0.02), px + nx * (OFF + W + 0.02)],
                    [py + ny * (OFF - 0.02), py + ny * (OFF + W + 0.02)],
                    color="#666", lw=0.6, zorder=3)
        # 字节标签（放内侧靠近中心圆，避开径向信号名文字）
        mx, my = _octagon_edge_point(verts, byte_edges, b, 0.5)
        ks, ke = byte_edges[b]
        dx = verts[ke][0] - verts[ks][0]
        dy = verts[ke][1] - verts[ks][1]
        ang = math.degrees(math.atan2(dy, dx))
        if ang > 90 or ang < -90:
            ang += 180
        ax.text(mx - nx * BYTE_LABEL_R, my - ny * BYTE_LABEL_R,
                f"B{b} [{b * 8}-{b * 8 + 7}]", ha="center", va="center",
                rotation=ang, fontsize=6.5, fontweight="bold", color="#333",
                zorder=6, bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                                    edgecolor="#aaa", lw=0.5))

    # 绘制信号块（按字节分段）
    drawn = {}   # byte -> list[(t0, t1, color)] 用于跨字节连接
    for i, sig in enumerate(signals):
        color = cmap(i / max(len(signals) - 1, 1))
        segs = _split_byte_segments(sig)
        for idx, (b, j0, j1) in enumerate(segs):
            t0, t1 = j0 / 8, (j1 + 1) / 8
            quad = _octagon_block_quad(verts, byte_edges, b, t0, t1, OFF, W)
            ax.add_patch(Polygon(quad, closed=True, facecolor=color,
                                 edgecolor="#222", linewidth=0.6, alpha=0.92, zorder=4))
            drawn.setdefault(b, []).append((t0, t1, color))
            # 段内 bit 分隔
            for j in range(j0 + 1, j1 + 1):
                px, py = _octagon_edge_point(verts, byte_edges, b, j / 8)
                nx, ny = _octagon_outward(verts, byte_edges, b)
                ax.plot([px + nx * OFF, px + nx * (OFF + W)],
                        [py + ny * OFF, py + ny * (OFF + W)],
                        color="#222", lw=0.3, alpha=0.55, zorder=5)
            # 信号名（沿外法向[径向]书写，完整名称不缩写；
            # 锚定在信号块内边缘并只向外延伸，保证不越过八边形边、不遮挡内部）
            if idx == 0:
                cmid = (t0 + t1) / 2
                mx, my = _octagon_edge_point(verts, byte_edges, b, cmid)
                nx, ny = _octagon_outward(verts, byte_edges, b)
                # 文字长轴沿外法向（径向），规范化到 [-90,90] 保证不颠倒
                rad_ang = math.degrees(math.atan2(ny, nx))
                if rad_ang > 90 or rad_ang < -90:
                    rad_ang += 180
                # 外法向朝左(x<0)的边：文字由内端向左(外)延伸 → ha=right；其余 ha=left
                ha = "right" if nx < 0 else "left"
                # 字号按名称长度分档：径向文字沿垂直边书写（长轴=径向），
                # 不受沿边 seg_len 限制，始终显示完整名称、足够大
                ln = len(sig["name"])
                if ln <= 12:
                    fs = 6.5
                elif ln <= 20:
                    fs = 5.8
                elif ln <= 28:
                    fs = 5.0
                else:
                    fs = 4.2
                # 锚点 = 信号块内边缘(径向 OFF)；rotation_mode="anchor" 使文字
                # 从锚点起只沿阅读方向延伸(ha=left 向前 / ha=right 向后=外法向)，
                # 保证信号名只位于八边形外侧、绝不越过八边形边
                ax.text(mx + nx * OFF, my + ny * OFF,
                        sig["name"], ha=ha, va="center", rotation=rad_ang,
                        rotation_mode="anchor",
                        fontsize=fs, fontweight="bold", color="#111", zorder=6)

    # 跨字节信号：段间弧线连接（在共享顶点外侧弯出）
    for i, sig in enumerate(signals):
        segs = _split_byte_segments(sig)
        if len(segs) < 2:
            continue
        color = cmap(i / max(len(signals) - 1, 1))
        for idx in range(len(segs) - 1):
            b1, j1a, j1b = segs[idx]
            b2, j2a, j2b = segs[idx + 1]
            p1 = _octagon_edge_point(verts, byte_edges, b1, (j1b + 1) / 8)
            p2 = _octagon_edge_point(verts, byte_edges, b2, j2a / 8)
            nx1, ny1 = _octagon_outward(verts, byte_edges, b1)
            nx2, ny2 = _octagon_outward(verts, byte_edges, b2)
            A = (p1[0] + nx1 * OFF, p1[1] + ny1 * OFF)
            B = (p2[0] + nx2 * OFF, p2[1] + ny2 * OFF)
            arc = FancyArrowPatch(A, B, arrowstyle="-", color=color, lw=1.8,
                                  connectionstyle="arc3,rad=-0.45",
                                  shrinkA=0, shrinkB=0, zorder=5)
            ax.add_patch(arc)

    # 中心区帧信息
    center = Circle((0, 0), 0.52, facecolor="white", edgecolor="#555",
                    linewidth=1.0, zorder=7)
    ax.add_patch(center)
    ax.text(0, 0.16, frame.name, ha="center", va="center", fontsize=10,
            fontweight="bold", color="#111", zorder=8)
    ax.text(0, -0.02, f"ID: {frame.frame_id}", ha="center", va="center",
            fontsize=7.5, color="#333", zorder=8)
    ax.text(0, -0.18, f"{n_bytes} B / {total_bits} bit", ha="center", va="center",
            fontsize=7.5, color="#555", zorder=8)

    # ===== 注释布局：引线 + 外圈文本框（碰撞检测防重叠） =====
    # 先固定标题与画布布局，使文本测量的坐标变换稳定；
    # 画幅 lim 与文本框尺寸互相依赖，迭代收敛
    ax.set_title(f"Signal Mapping (Octagon) — {frame.name}  "
                 f"(Frame ID: {frame.frame_id}, Length: {frame.length} bytes)",
                 fontsize=13, fontweight="bold", pad=12)
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

    for sig, wrapped, cx, cy in ann_layout:
        segs = _split_byte_segments(sig)
        b, j0, j1 = segs[0]
        t0, t1 = j0 / 8, (j1 + 1) / 8
        cmid = (t0 + t1) / 2
        mx, my = _octagon_edge_point(verts, byte_edges, b, cmid)
        nx, ny = _octagon_outward(verts, byte_edges, b)
        anchor = (mx + nx * (OFF + W), my + ny * (OFF + W))
        # 引线：从信号块外边缘到注释框中心
        ax.plot([anchor[0], cx], [anchor[1], cy], color="#c0392b", lw=0.9, zorder=6)
        ax.text(cx, cy, wrapped, ha="center", va="center", fontsize=7, color="#222",
                zorder=7, bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff8e1",
                                    edgecolor="#c0392b", lw=0.8))

    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    saved = []
    if save_png:
        png_path = f"{output_dir}/{frame_name}_signal_mapping_octagon.png"
        plt.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        saved.append(png_path)
    if save_svg:
        svg_path = f"{output_dir}/{frame_name}_signal_mapping_octagon.svg"
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
        saved.append(svg_path)
    plt.close()
    return saved


def plot_all_frames(ldf, frames_to_plot, output_dir=OUTPUT_DIR, save_png=True, save_svg=True, dpi=300):
    """绘制多帧总览图，返回生成的文件路径列表"""
    colors_list = ["#f0e68c", "#c5e1a5", "#81c784", "#4db6ac", "#26a69a", "#00897b",
                   "#00695c", "#004d40", "#1a237e", "#0d47a1", "#ffcc80", "#ffab91",
                   "#ce93d8", "#90caf9", "#a5d6a7"]

    fig, axes = plt.subplots(len(frames_to_plot), 1, figsize=(16, 3.5 * len(frames_to_plot)))
    if len(frames_to_plot) == 1:
        axes = [axes]

    for ax_idx, fname in enumerate(frames_to_plot):
        frame = ldf.get_unconditional_frame(fname)
        ax = axes[ax_idx]
        signals = get_signals(frame)
        total_bits = frame.length * 8

        # 网格
        for i in range(total_bits + 1):
            lw = 1.0 if i % 8 == 0 else 0.3
            color = "#222" if i % 8 == 0 else "#ddd"
            ax.axvline(i, color=color, linewidth=lw, ymin=0.2, ymax=0.8)

        # 信号块
        for i, sig in enumerate(signals):
            color = colors_list[i % len(colors_list)]
            rect = Rectangle((sig["start"], 0.3), sig["size"], 0.4,
                             facecolor=color, edgecolor="black", linewidth=0.7, alpha=0.85)
            ax.add_patch(rect)

            # 信号完整标识符（不简写）
            draw_signal_label(ax, sig, 0.5)

        # 字节号
        for i in range(frame.length):
            ax.text(i * 8 + 4, 0.92, str(i), ha="center", va="center", fontsize=9, fontweight="bold")

        # bit 号
        for i in range(0, total_bits, 8):
            ax.text(i, 0.12, str(i), ha="center", va="top", fontsize=7)
        ax.text(total_bits, 0.12, str(total_bits - 1), ha="center", va="top", fontsize=7)

        ax.set_title(f"{fname}  (ID={frame.frame_id}, {frame.length} bytes) — Publisher: {frame.publisher.name}",
                     fontsize=11, fontweight="bold", loc="left")
        ax.set_xlim(-0.5, total_bits + 0.5)
        ax.set_ylim(0, 1.05)
        ax.set_yticks([])
        ax.set_xticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    plt.suptitle("LIN Signal Mapping Visualization (from LDF)", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()

    saved = []
    if save_png:
        png_path = f"{output_dir}/LIN_Signal_Mappings_All_Frames.png"
        plt.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        saved.append(png_path)
    if save_svg:
        svg_path = f"{output_dir}/LIN_Signal_Mappings_All_Frames.svg"
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
        saved.append(svg_path)
    plt.close()
    return saved


def export_excel(ldf, frames_to_plot, output_dir=OUTPUT_DIR):
    """生成 Excel 汇总（仅包含指定帧），返回文件路径

    布局目标：适配 A4 页面（纸张/边距/缩放设置），拷贝到 Word 后不超宽
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.page import PageMargins

    excel_path = f"{output_dir}/LIN_Signal_Mapping.xlsx"
    wb = Workbook()

    # 样式
    header_font = Font(name="Arial", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    body_font = Font(name="Arial", size=10)
    thin_border = Border(*[Side(style="thin", color="B0B0B0")] * 4)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # A4 纵向可打印宽约 82 个字符单位，Word 默认正文宽度相当；留余量取 80
    A4_WIDTH_UNITS = 80
    MIN_COL_WIDTH = 6

    def style_header(ws, ncols):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=1, column=c)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = thin_border
        ws.freeze_panes = "A2"
        ws.row_dimensions[1].height = 22

    def style_body(ws, nrows, ncols):
        for r in range(2, nrows + 1):
            for c in range(1, ncols + 1):
                cell = ws.cell(row=r, column=c)
                cell.font = body_font
                cell.border = thin_border
                cell.alignment = left if c in (1, 2, 3) else center

    def auto_width(ws, ncols):
        """按内容计算列宽：总宽固定为 A4_WIDTH_UNITS，按内容长度比例分配
        （短列保底 MIN_COL_WIDTH，长文本靠 wrap_text 换行显示完整内容）"""
        raw = []
        for c in range(1, ncols + 1):
            max_len = 0
            for r in range(1, ws.max_row + 1):
                v = ws.cell(row=r, column=c).value
                if v is not None:
                    # 中文/全角字符按 2 个单位估算
                    length = sum(2 if ord(ch) > 0xFF else 1 for ch in str(v))
                    max_len = max(max_len, length)
            raw.append(max(max_len + 3, MIN_COL_WIDTH))

        # 比例分配：每列先保底 MIN_COL_WIDTH，剩余宽度按 (raw - MIN) 占比分配
        min_total = MIN_COL_WIDTH * ncols
        extra_budget = max(A4_WIDTH_UNITS - min_total, 0)
        extra_weights = [max(r - MIN_COL_WIDTH, 0) for r in raw]
        weight_sum = sum(extra_weights)

        widths = []
        for i, w in enumerate(raw):
            if weight_sum and extra_budget:
                extra = extra_weights[i] / weight_sum * extra_budget
            else:
                extra = 0
            widths.append(MIN_COL_WIDTH + extra)

        # 由于四舍五入可能差 1-2 个单位，补偿到内容最多的列
        deficit = A4_WIDTH_UNITS - sum(widths)
        if deficit != 0:
            top = max(range(ncols), key=lambda i: extra_weights[i])
            widths[top] = max(widths[top] + deficit, MIN_COL_WIDTH)

        for c, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(c)].width = round(w, 1)

    def setup_a4(ws):
        """A4 页面设置：纸张、边距、缩放适配一页宽、打印重复表头"""
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.orientation = "portrait"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.6, bottom=0.6,
                                      header=0.3, footer=0.3)
        ws.print_title_rows = "1:1"
        ws.print_area = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"

    # ---- Sheet 1: Frames 概览 ----
    ws_frames = wb.active
    ws_frames.title = "Frames"
    frames_headers = ["Frame Name", "Frame ID", "Length (bytes)", "Length (bits)", "Publisher", "Signal Count"]
    ws_frames.append(frames_headers)
    for frame in ldf.get_unconditional_frames():
        if frame.name in frames_to_plot:
            ws_frames.append([frame.name, frame.frame_id, frame.length, frame.length * 8,
                              frame.publisher.name, len(frame.signal_map)])
    style_header(ws_frames, len(frames_headers))
    style_body(ws_frames, ws_frames.max_row, len(frames_headers))
    auto_width(ws_frames, len(frames_headers))
    setup_a4(ws_frames)

    # ---- Sheet 2: Signals 明细 ----
    ws_sig = wb.create_sheet("Signals")
    sig_headers = ["Frame Name", "Frame ID", "Signal Name", "Start Bit", "Size (bits)", "End Bit",
                   "Init Value", "Encoding Type", "Publisher", "Subscribers"]
    ws_sig.append(sig_headers)
    for frame in ldf.get_unconditional_frames():
        if frame.name not in frames_to_plot:
            continue
        for sig in get_signals(frame):
            lin_sig = next(s for s in frame.signal_map if s[0] == sig["start"])[1]
            ws_sig.append([
                frame.name,
                frame.frame_id,
                sig["name"],
                sig["start"],
                sig["size"],
                sig["end"],
                lin_sig.init_value,
                lin_sig.encoding_type.name if lin_sig.encoding_type else "",
                lin_sig.publisher.name if lin_sig.publisher else "",
                ", ".join(s.name for s in lin_sig.subscribers) if lin_sig.subscribers else "",
            ])
    style_header(ws_sig, len(sig_headers))
    style_body(ws_sig, ws_sig.max_row, len(sig_headers))
    auto_width(ws_sig, len(sig_headers))
    setup_a4(ws_sig)

    wb.save(excel_path)
    return excel_path


def main():
    """CLI 入口：解析默认 LDF 并生成全部默认帧"""
    ldf = ldfparser.parse_ldf(path=LDF_PATH, encoding="latin-1")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Baudrate: {ldf.get_baudrate()} bps")
    print("Unconditional Frames:")
    for frame in ldf.get_unconditional_frames():
        print(f"  {frame.name} (ID={frame.frame_id}, {frame.length} bytes, Publisher={frame.publisher.name})")

    # 1. 单帧高清图
    for fname in DEFAULT_FRAMES:
        saved = plot_single_frame(ldf, fname, OUTPUT_DIR)
        for s in saved:
            print(f"Saved: {s}")

    # 1b. 单帧八边形布局图（8边=8字节）
    for fname in DEFAULT_FRAMES:
        saved = plot_single_frame_octagon(ldf, fname, OUTPUT_DIR)
        for s in saved:
            print(f"Saved: {s}")

    # 2. 多帧总览图
    saved = plot_all_frames(ldf, DEFAULT_FRAMES, OUTPUT_DIR)
    for s in saved:
        print(f"Saved: {s}")

    # 3. Excel
    try:
        path = export_excel(ldf, DEFAULT_FRAMES, OUTPUT_DIR)
        print(f"Saved: {path}")
    except PermissionError:
        print("错误: LIN_Signal_Mapping.xlsx 被占用（可能在 Excel 中打开），请关闭后重试")

    print("\nDone!")


if __name__ == "__main__":
    main()

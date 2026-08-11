
#!/usr/bin/env python3
"""
LIN LDF Signal Mapping Visualizer
解析 LDF 文件并生成类似 CANoe/Vector 风格的 Signal Mapping 图
支持: CLI 直接运行 (python parse.py) 或作为模块被 gui.py 调用
"""

import ldfparser
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.colors import LinearSegmentedColormap
import os
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

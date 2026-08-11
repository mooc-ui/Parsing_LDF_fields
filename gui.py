#!/usr/bin/env python3
"""
LIN LDF Signal Mapping Visualizer - GUI
加载 LDF 文件 → 勾选要生成的帧 → 给信号添加注释 → 生成图片(PNG/SVG) + Excel
未勾选的帧不生成任何输出
"""

import json
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import parse

APP_TITLE = "LIN Signal Mapping Generator"
BG = "#f5f6f8"
ACCENT = "#1f4e79"
ANN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "annotations.json")


class LDFGui:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("920x720")
        self.root.configure(bg=BG)

        self.ldf = None          # 已加载的 LDF 对象
        self.frame_vars = {}     # frame name -> tk.BooleanVar
        self.signal_meta = {}    # iid -> (frame_name, signal_name)
        self.annotations = {}    # {frame_name: {signal_name: comment}}
        self.msg_queue = queue.Queue()

        self._load_annotations()
        self._build_ui()

        # 启动消息轮询（后台线程 → UI 线程）
        self.root.after(100, self._poll_queue)

        # 若默认 LDF 存在则自动加载
        if os.path.exists(parse.LDF_PATH):
            self._load_ldf(parse.LDF_PATH)

    # ==================== UI 构建 ====================
    def _build_ui(self):
        # --- 顶部: LDF 文件选择 ---
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=12, pady=(12, 6))

        tk.Label(top, text="LDF 文件:", font=("Microsoft YaHei", 10), bg=BG).pack(side="left")
        self.ldf_path_var = tk.StringVar(value=parse.LDF_PATH)
        self.ldf_entry = tk.Entry(top, textvariable=self.ldf_path_var, width=55,
                                  font=("Consolas", 9))
        self.ldf_entry.pack(side="left", padx=6)
        tk.Button(top, text="浏览...", command=self._browse_ldf,
                  font=("Microsoft YaHei", 9), bg=ACCENT, fg="white",
                  activebackground="#2f6fb5", activeforeground="white").pack(side="left")

        # LDF 信息栏
        self.info_var = tk.StringVar(value="未加载 LDF 文件")
        tk.Label(self.root, textvariable=self.info_var, font=("Microsoft YaHei", 9),
                 bg=BG, fg="#555").pack(fill="x", padx=12, pady=(0, 6))

        # --- Notebook: 帧选择 / 信号注释 ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=6)

        # ===== Tab 1: 帧选择 =====
        tab_frames = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab_frames, text="  帧选择  ")

        sel_bar = tk.Frame(tab_frames, bg=BG)
        sel_bar.pack(fill="x", pady=(4, 4))
        tk.Label(sel_bar, text="勾选要生成的帧（勾选才会生成图片和 Excel）:",
                 font=("Microsoft YaHei", 9), bg=BG).pack(side="left")
        tk.Button(sel_bar, text="全选", command=self._select_all,
                  font=("Microsoft YaHei", 9)).pack(side="right", padx=(4, 0))
        tk.Button(sel_bar, text="全不选", command=self._select_none,
                  font=("Microsoft YaHei", 9)).pack(side="right")

        self.list_canvas = tk.Canvas(tab_frames, bg="white", highlightthickness=1,
                                     highlightbackground="#ccc")
        self.list_scroll = ttk.Scrollbar(tab_frames, orient="vertical",
                                         command=self.list_canvas.yview)
        self.frames_frame = tk.Frame(self.list_canvas, bg="white")
        self.frames_frame.bind("<Configure>",
                               lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.create_window((0, 0), window=self.frames_frame, anchor="nw")
        self.list_canvas.configure(yscrollcommand=self.list_scroll.set)
        self.list_canvas.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=(0, 4))
        self.list_scroll.pack(side="right", fill="y", pady=(0, 4))

        # ===== Tab 2: 信号注释 =====
        tab_ann = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab_ann, text="  信号注释  ")

        # 提示
        tk.Label(tab_ann, text="选中一个信号，在下方输入注释后点击“保存注释”（可填中文）；"
                               "生成图片时注释会以引线标注在对应信号下方。",
                 font=("Microsoft YaHei", 9), bg=BG, fg="#555", justify="left").pack(
            fill="x", pady=(6, 4))

        # Treeview: 帧 -> 信号
        tree_frame = tk.Frame(tab_ann, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=(0, 4))

        self.tree = ttk.Treeview(tree_frame, columns=("signal", "start", "size", "comment"),
                                 show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="帧 / 信号")
        self.tree.heading("signal", text="信号")
        self.tree.heading("start", text="起始位")
        self.tree.heading("size", text="位宽")
        self.tree.heading("comment", text="注释")
        self.tree.column("#0", width=170, anchor="w")
        self.tree.column("signal", width=180, anchor="w")
        self.tree.column("start", width=60, anchor="center")
        self.tree.column("size", width=55, anchor="center")
        self.tree.column("comment", width=280, anchor="w")

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # 注释编辑区
        edit_frame = tk.Frame(tab_ann, bg=BG)
        edit_frame.pack(fill="x", pady=6)

        self.ann_target_var = tk.StringVar(value="未选择信号")
        tk.Label(edit_frame, textvariable=self.ann_target_var, font=("Microsoft YaHei", 9, "bold"),
                 bg=BG, fg=ACCENT).pack(fill="x", pady=(0, 2))

        self.ann_text = tk.Text(edit_frame, height=3, font=("Microsoft YaHei", 10), wrap="word")
        self.ann_text.pack(fill="x", pady=(0, 4))

        btn_row = tk.Frame(edit_frame, bg=BG)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="保存注释", command=self._save_annotation,
                  font=("Microsoft YaHei", 9), bg="#2e7d32", fg="white",
                  activebackground="#43a047", activeforeground="white").pack(side="left", padx=(0, 6))
        tk.Button(btn_row, text="删除注释", command=self._delete_annotation,
                  font=("Microsoft YaHei", 9)).pack(side="left")

        # --- 底部: 输出选项 ---
        bottom = tk.LabelFrame(self.root, text=" 输出选项 ", font=("Microsoft YaHei", 10),
                               bg=BG, padx=8, pady=6)
        bottom.pack(fill="x", padx=12, pady=6)

        opt_row1 = tk.Frame(bottom, bg=BG)
        opt_row1.pack(fill="x", pady=2)
        tk.Label(opt_row1, text="输出目录:", font=("Microsoft YaHei", 9), bg=BG).pack(side="left")
        self.outdir_var = tk.StringVar(value=parse.OUTPUT_DIR)
        tk.Entry(opt_row1, textvariable=self.outdir_var, width=50,
                 font=("Consolas", 9)).pack(side="left", padx=6)
        tk.Button(opt_row1, text="浏览...", command=self._browse_outdir,
                  font=("Microsoft YaHei", 9)).pack(side="left")

        opt_row2 = tk.Frame(bottom, bg=BG)
        opt_row2.pack(fill="x", pady=4)
        self.var_png = tk.BooleanVar(value=True)
        self.var_svg = tk.BooleanVar(value=True)
        self.var_excel = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_row2, text="生成 PNG 图片", variable=self.var_png,
                       font=("Microsoft YaHei", 9), bg=BG).pack(side="left", padx=(0, 12))
        tk.Checkbutton(opt_row2, text="生成 SVG 图片", variable=self.var_svg,
                       font=("Microsoft YaHei", 9), bg=BG).pack(side="left", padx=(0, 12))
        tk.Checkbutton(opt_row2, text="生成 Excel", variable=self.var_excel,
                       font=("Microsoft YaHei", 9), bg=BG).pack(side="left", padx=(0, 12))

        # 生成按钮
        self.btn_generate = tk.Button(self.root, text="生成", command=self._generate,
                                      font=("Microsoft YaHei", 12, "bold"), bg="#2e7d32",
                                      fg="white", padx=30, pady=6,
                                      activebackground="#43a047", activeforeground="white")
        self.btn_generate.pack(pady=6)

        # 状态输出
        self.status_text = tk.Text(self.root, height=9, font=("Consolas", 9),
                                   bg="#1e1e1e", fg="#d4d4d4", state="disabled",
                                   wrap="word")
        self.status_text.pack(fill="both", expand=False, padx=12, pady=(0, 12))

    # ==================== 注释持久化 ====================
    def _load_annotations(self):
        try:
            if os.path.exists(ANN_FILE):
                with open(ANN_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.annotations = data if isinstance(data, dict) else {}
        except Exception:
            self.annotations = {}

    def _save_annotations(self):
        try:
            with open(ANN_FILE, "w", encoding="utf-8") as f:
                json.dump(self.annotations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"注释保存失败: {e}\n")

    # ==================== 功能 ====================
    def _browse_ldf(self):
        path = filedialog.askopenfilename(
            title="选择 LDF 文件",
            filetypes=[("LDF 文件", "*.ldf"), ("所有文件", "*.*")])
        if path:
            self.ldf_path_var.set(path)
            self._load_ldf(path)

    def _load_ldf(self, path):
        try:
            self.ldf = parse.ldfparser.parse_ldf(path=path, encoding="latin-1")
        except Exception as e:
            self.ldf = None
            self._log(f"加载失败: {e}\n")
            messagebox.showerror("加载失败", f"无法解析 LDF 文件:\n{e}")
            return

        baud = self.ldf.get_baudrate()
        frames = self.ldf.get_unconditional_frames()
        self.info_var.set(f"已加载: {os.path.basename(path)}  |  Baudrate: {baud} bps  |  帧数: {len(frames)}")

        # 重建帧勾选框
        for w in self.frames_frame.winfo_children():
            w.destroy()
        self.frame_vars = {}
        for frame in frames:
            var = tk.BooleanVar(value=True)
            self.frame_vars[frame.name] = var
            cb = tk.Checkbutton(
                self.frames_frame, text=f"{frame.name}   (ID={frame.frame_id}, "
                                        f"{frame.length} bytes, Publisher={frame.publisher.name})",
                variable=var, bg="white", anchor="w",
                font=("Microsoft YaHei", 9))
            cb.pack(fill="x", padx=6, pady=1)

        # 重建信号树
        self._rebuild_tree(frames)

        self._log(f"已加载 {len(frames)} 帧: {', '.join(f.name for f in frames)}\n")

    def _rebuild_tree(self, frames):
        self.tree.delete(*self.tree.get_children())
        self.signal_meta = {}
        frame_ann = self.annotations
        for frame in frames:
            parent = self.tree.insert("", "end", text=f"{frame.name}  (ID={frame.frame_id}, {frame.length}B)",
                                      open=True)
            frame_comments = frame_ann.get(frame.name, {})
            for sig in parse.get_signals(frame):
                comment = frame_comments.get(sig["name"], "")
                iid = self.tree.insert(parent, "end", text="",
                                       values=(sig["name"], sig["start"], sig["size"], comment))
                self.signal_meta[iid] = (frame.name, sig["name"])

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid not in self.signal_meta:
            return  # 选中的是帧节点
        frame_name, sig_name = self.signal_meta[iid]
        self.ann_target_var.set(f"{frame_name} / {sig_name}")
        comment = self.annotations.get(frame_name, {}).get(sig_name, "")
        self.ann_text.delete("1.0", "end")
        self.ann_text.insert("1.0", comment)

    def _selected_signal(self):
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        return self.signal_meta.get(iid)

    def _save_annotation(self):
        target = self._selected_signal()
        if target is None:
            messagebox.showwarning("未选择信号", "请先在列表中选择一个信号")
            return
        frame_name, sig_name = target
        comment = self.ann_text.get("1.0", "end").strip()
        if not comment:
            messagebox.showwarning("空注释", "请输入注释内容")
            return
        self.annotations.setdefault(frame_name, {})[sig_name] = comment
        # 更新树中显示
        for iid, (fn, sn) in self.signal_meta.items():
            if fn == frame_name and sn == sig_name:
                self.tree.set(iid, "comment", comment)
                break
        self._save_annotations()
        self._log(f"已保存注释: {frame_name} / {sig_name} -> {comment}\n")

    def _delete_annotation(self):
        target = self._selected_signal()
        if target is None:
            messagebox.showwarning("未选择信号", "请先在列表中选择一个信号")
            return
        frame_name, sig_name = target
        if frame_name in self.annotations and sig_name in self.annotations[frame_name]:
            del self.annotations[frame_name][sig_name]
            if not self.annotations[frame_name]:
                del self.annotations[frame_name]
        for iid, (fn, sn) in self.signal_meta.items():
            if fn == frame_name and sn == sig_name:
                self.tree.set(iid, "comment", "")
                break
        self.ann_text.delete("1.0", "end")
        self._save_annotations()
        self._log(f"已删除注释: {frame_name} / {sig_name}\n")

    def _select_all(self):
        for var in self.frame_vars.values():
            var.set(True)

    def _select_none(self):
        for var in self.frame_vars.values():
            var.set(False)

    def _browse_outdir(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.outdir_var.set(path)

    def _selected_frames(self):
        return [name for name, var in self.frame_vars.items() if var.get()]

    def _generate(self):
        if self.ldf is None:
            messagebox.showwarning("未加载 LDF", "请先加载 LDF 文件")
            return

        frames = self._selected_frames()
        if not frames:
            messagebox.showwarning("未选择帧", "请至少勾选一帧")
            return

        outdir = self.outdir_var.get().strip() or parse.OUTPUT_DIR
        try:
            os.makedirs(outdir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("目录错误", f"无法创建输出目录:\n{e}")
            return

        if not (self.var_png.get() or self.var_svg.get() or self.var_excel.get()):
            messagebox.showwarning("无输出类型", "请至少勾选一种输出类型（PNG / SVG / Excel）")
            return

        # 禁用按钮，后台线程执行
        self.btn_generate.config(state="disabled")
        worker = threading.Thread(target=self._generate_worker,
                                  args=(frames, outdir), daemon=True)
        worker.start()

    def _generate_worker(self, frames, outdir):
        try:
            self._log("=" * 50)
            self._log(f"开始生成 {len(frames)} 帧: {', '.join(frames)}\n")

            # 1. 每帧单独高清图（带注释）
            if self.var_png.get() or self.var_svg.get():
                for fname in frames:
                    ann = self.annotations.get(fname, {})
                    if ann:
                        self._log(f"  帧 {fname} 注释 {len(ann)} 条\n")
                    saved = parse.plot_single_frame(
                        self.ldf, fname, outdir,
                        save_png=self.var_png.get(), save_svg=self.var_svg.get(),
                        annotations=ann or None)
                    for s in saved:
                        self._log(f"Saved: {s}")

                # 2. 多帧总览图（仅勾选帧）
                saved = parse.plot_all_frames(
                    self.ldf, frames, outdir,
                    save_png=self.var_png.get(), save_svg=self.var_svg.get())
                for s in saved:
                    self._log(f"Saved: {s}")

            # 3. Excel（仅勾选帧）
            if self.var_excel.get():
                try:
                    path = parse.export_excel(self.ldf, frames, outdir)
                    self._log(f"Saved: {path}")
                except PermissionError:
                    self._log("错误: LIN_Signal_Mapping.xlsx 被占用（可能在 Excel 中打开），请关闭后重试\n")

            self._log("完成!\n")
        except Exception as e:
            import traceback
            self._log(f"生成失败: {e}\n{traceback.format_exc()}\n")
        finally:
            self.msg_queue.put(("done", None))

    # ==================== 消息/日志 ====================
    def _log(self, text):
        self.msg_queue.put(("log", text))

    def _poll_queue(self):
        try:
            while True:
                kind, data = self.msg_queue.get_nowait()
                if kind == "log":
                    self.status_text.config(state="normal")
                    self.status_text.insert("end", data)
                    self.status_text.see("end")
                    self.status_text.config(state="disabled")
                elif kind == "done":
                    self.btn_generate.config(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)


def main():
    root = tk.Tk()
    LDFGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""PSD/PSB -> PNG 변환기

- 파일(들)을 선택해 PNG로 내보낸다.
- 내보내기 방식은 두 가지 중 선택:
    1) 레이어별로 내보내기: 파일명_레이어이름.png (레이어마다 개별 PNG)
    2) 합쳐서 내보내기: 파일명.png (모든 레이어를 합친 한 장의 PNG)

필요 패키지: psd-tools, Pillow
    pip install psd-tools Pillow
"""

import os
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image
from psd_tools import PSDImage

INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')


def sanitize(name: str) -> str:
    name = INVALID_CHARS.sub("_", name).strip()
    return name or "layer"


def unique_path(directory: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    candidate = filename
    i = 2
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{base}_{i}{ext}"
        i += 1
    return os.path.join(directory, candidate)


def layer_path_name(layer) -> str:
    parts = [layer.name]
    parent = layer.parent
    while parent is not None and not isinstance(parent, PSDImage):
        parts.append(parent.name)
        parent = parent.parent
    return "_".join(sanitize(p) for p in reversed(parts))


class App:
    def __init__(self, root):
        self.root = root
        root.title("PSD/PSB → PNG 변환기")
        root.geometry("640x560")
        root.minsize(560, 480)

        self.files = []
        self.output_dir = tk.StringVar()
        self.mode = tk.StringVar(value="layer")
        self.include_hidden = tk.BooleanVar(value=False)
        self.cancel_flag = threading.Event()
        self.running = False

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        file_frame = ttk.LabelFrame(self.root, text="파일 선택")
        file_frame.pack(fill="x", **pad)

        self.file_listbox = tk.Listbox(file_frame, height=6, selectmode=tk.EXTENDED)
        self.file_listbox.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        list_scroll = ttk.Scrollbar(file_frame, orient="vertical", command=self.file_listbox.yview)
        list_scroll.pack(side="left", fill="y", pady=8)
        self.file_listbox.config(yscrollcommand=list_scroll.set)

        btn_col = ttk.Frame(file_frame)
        btn_col.pack(side="left", fill="y", padx=8, pady=8)
        ttk.Button(btn_col, text="파일 추가", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(btn_col, text="선택 삭제", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(btn_col, text="목록 초기화", command=self.clear_files).pack(fill="x", pady=2)

        option_frame = ttk.LabelFrame(self.root, text="내보내기 옵션")
        option_frame.pack(fill="x", **pad)

        ttk.Radiobutton(
            option_frame, text="레이어별로 내보내기  (파일명_레이어이름.png)",
            variable=self.mode, value="layer",
        ).pack(anchor="w", padx=8, pady=(6, 0))
        ttk.Radiobutton(
            option_frame, text="합쳐서 내보내기  (파일명.png)",
            variable=self.mode, value="merged",
        ).pack(anchor="w", padx=8, pady=(0, 6))
        ttk.Checkbutton(
            option_frame, text="숨겨진 레이어도 포함 (레이어별 내보내기 시)",
            variable=self.include_hidden,
        ).pack(anchor="w", padx=8, pady=(0, 6))

        out_frame = ttk.LabelFrame(self.root, text="출력 폴더 (비워두면 각 파일이 있는 폴더에 저장)")
        out_frame.pack(fill="x", **pad)
        out_row = ttk.Frame(out_frame)
        out_row.pack(fill="x", padx=8, pady=8)
        ttk.Entry(out_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(out_row, text="찾아보기", command=self.choose_output_dir).pack(side="left", padx=(6, 0))

        run_frame = ttk.Frame(self.root)
        run_frame.pack(fill="x", **pad)
        self.start_btn = ttk.Button(run_frame, text="변환 시작", command=self.start_conversion)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(run_frame, text="취소", command=self.cancel_conversion, state="disabled")
        self.cancel_btn.pack(side="left", padx=(6, 0))

        self.progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", **pad)

        log_frame = ttk.LabelFrame(self.root, text="진행 로그")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.pack(side="left", fill="y", pady=8)
        self.log_text.config(yscrollcommand=log_scroll.set)

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="PSD/PSB 파일 선택",
            filetypes=[("Photoshop 파일", "*.psd *.psb"), ("모든 파일", "*.*")],
        )
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.file_listbox.insert(tk.END, p)

    def remove_selected(self):
        for idx in reversed(self.file_listbox.curselection()):
            del self.files[idx]
            self.file_listbox.delete(idx)

    def clear_files(self):
        self.files.clear()
        self.file_listbox.delete(0, tk.END)

    def choose_output_dir(self):
        d = filedialog.askdirectory(title="출력 폴더 선택")
        if d:
            self.output_dir.set(d)

    def log(self, msg: str):
        self.root.after(0, self._append_log, msg)

    def _append_log(self, msg: str):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def start_conversion(self):
        if self.running:
            return
        if not self.files:
            messagebox.showwarning("알림", "변환할 파일을 먼저 선택하세요.")
            return

        self.running = True
        self.cancel_flag.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress.config(value=0, maximum=len(self.files))

        files = list(self.files)
        mode = self.mode.get()
        include_hidden = self.include_hidden.get()
        out_dir = self.output_dir.get().strip()

        threading.Thread(
            target=self._run_conversion, args=(files, mode, include_hidden, out_dir), daemon=True
        ).start()

    def cancel_conversion(self):
        self.cancel_flag.set()
        self.log("취소를 요청했습니다...")

    def _finish(self):
        self.running = False
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")

    def _run_conversion(self, files, mode, include_hidden, out_dir):
        for i, path in enumerate(files, start=1):
            if self.cancel_flag.is_set():
                self.log("변환이 취소되었습니다.")
                break

            self.log(f"[{i}/{len(files)}] 열기: {os.path.basename(path)}")
            target_dir = out_dir or os.path.dirname(path)
            try:
                os.makedirs(target_dir, exist_ok=True)
                psd = PSDImage.open(path)
                if mode == "merged":
                    self._export_merged(psd, path, target_dir)
                else:
                    self._export_layers(psd, path, target_dir, include_hidden)
            except Exception as e:
                self.log(f"  오류: {e}")

            self.root.after(0, self.progress.config, {"value": i})

        self.log("완료." if not self.cancel_flag.is_set() else "")
        self.root.after(0, self._finish)

    def _export_merged(self, psd, source_path, target_dir):
        base = os.path.splitext(os.path.basename(source_path))[0]
        image = psd.composite()
        if image is None:
            self.log("  건너뜀: 합성 이미지를 만들 수 없습니다.")
            return
        out_path = os.path.join(target_dir, sanitize(base) + ".png")
        image.save(out_path)
        self.log(f"  저장: {out_path}")

    def _export_layers(self, psd, source_path, target_dir, include_hidden):
        base = sanitize(os.path.splitext(os.path.basename(source_path))[0])
        canvas_size = psd.size
        count = 0
        for layer in psd.descendants():
            if self.cancel_flag.is_set():
                return
            if layer.is_group():
                continue
            if not include_hidden and not layer.is_visible():
                continue
            if layer.bbox is None or layer.width == 0 or layer.height == 0:
                continue

            try:
                piece = layer.composite()
            except Exception as e:
                self.log(f"  레이어 '{layer.name}' 건너뜀: {e}")
                continue
            if piece is None:
                continue

            canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
            canvas.paste(piece, layer.offset)

            filename = f"{base}_{layer_path_name(layer)}.png"
            out_path = unique_path(target_dir, filename)
            canvas.save(out_path)
            count += 1
            self.log(f"  저장: {out_path}")

        self.log(f"  레이어 {count}개 내보냄.")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

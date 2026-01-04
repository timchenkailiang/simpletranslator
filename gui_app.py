# gui_app.py
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

# 你现有后端
from pdf_to_excel_auto import run

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF → Excel 自动解析/匹配")
        self.geometry("640x260")
        self.resizable(False, False)

        self.pdf_path = tk.StringVar()
        self.master_path = tk.StringVar()
        self.out_path = tk.StringVar(value="matched_output.xlsx")

        tk.Label(self, text="PDF（必选）").pack(anchor="w", padx=12, pady=(12, 0))
        row1 = tk.Frame(self); row1.pack(fill="x", padx=12)
        tk.Entry(row1, textvariable=self.pdf_path).pack(side="left", fill="x", expand=True)
        tk.Button(row1, text="选择 PDF", command=self.pick_pdf).pack(side="left", padx=(8, 0))

        tk.Label(self, text="Master Excel（可选，仅 .xlsx）").pack(anchor="w", padx=12, pady=(12, 0))
        row2 = tk.Frame(self); row2.pack(fill="x", padx=12)
        tk.Entry(row2, textvariable=self.master_path).pack(side="left", fill="x", expand=True)
        tk.Button(row2, text="选择 xlsx", command=self.pick_master).pack(side="left", padx=(8, 0))
        tk.Button(row2, text="清空", command=lambda: self.master_path.set("")).pack(side="left", padx=(8, 0))

        tk.Label(self, text="输出文件（.xlsx）").pack(anchor="w", padx=12, pady=(12, 0))
        row3 = tk.Frame(self); row3.pack(fill="x", padx=12)
        tk.Entry(row3, textvariable=self.out_path).pack(side="left", fill="x", expand=True)
        tk.Button(row3, text="选择保存位置", command=self.pick_out).pack(side="left", padx=(8, 0))

        row4 = tk.Frame(self); row4.pack(fill="x", padx=12, pady=14)
        tk.Button(row4, text="Run", command=self.run_job, height=2).pack(side="left", fill="x", expand=True)

        tk.Label(
            self,
            text="说明：只选 PDF = 只解析；选 PDF + xlsx = 自动匹配。\n（为避免 xls 依赖问题，本工具仅支持 xlsx）",
            fg="#555"
        ).pack(padx=12, pady=(0, 10), anchor="w")

    def pick_pdf(self):
        p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if p:
            self.pdf_path.set(p)

    def pick_master(self):
        p = filedialog.askopenfilename(filetypes=[("Excel (.xlsx)", "*.xlsx")])
        if p:
            self.master_path.set(p)

    def pick_out(self):
        p = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel (.xlsx)", "*.xlsx")])
        if p:
            self.out_path.set(p)

    def run_job(self):
        pdf = self.pdf_path.get().strip()
        master = self.master_path.get().strip()
        out = self.out_path.get().strip()

        if not pdf:
            messagebox.showerror("错误", "请先选择 PDF")
            return
        if master and (not master.lower().endswith(".xlsx")):
            messagebox.showerror("错误", "Master 仅支持 .xlsx，请另存为 .xlsx 后选择")
            return
        if out and (not out.lower().endswith(".xlsx")):
            out += ".xlsx"
            self.out_path.set(out)

        try:
            # ✅ 推荐你把 pdf_to_excel_auto.py 的 run 改成：run(pdf_path, out_path, master_path=None)
            # 如果你还没改，先用旧签名（run(pdf, master, out)）那就把下面两行换一下即可。
            run(Path(pdf), Path(out), master_path=Path(master) if master else None)

            messagebox.showinfo("完成", f"已生成：\n{out}")
        except Exception as e:
            messagebox.showerror("失败", str(e))

if __name__ == "__main__":
    App().mainloop()

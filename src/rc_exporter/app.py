"""Tkinter GUI. Run with `pixi run app`."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from rc_exporter import api


class App(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root, padding=12)
        self.root = root
        self.project = None
        self.info: api.ProjectInfo | None = None
        self.results: queue.Queue = queue.Queue()

        root.title("REDCap Report Exporter")
        root.minsize(520, 0)
        self.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        # --- connection ---
        conn = ttk.LabelFrame(self, text="Connection", padding=8)
        conn.grid(row=0, column=0, columnspan=2, sticky="ew")
        conn.columnconfigure(1, weight=1)

        self.url = tk.StringVar(value=api.DEFAULT_API_URL)
        self.pid = tk.StringVar()
        self.token = tk.StringVar()
        self.show_token = tk.BooleanVar(value=False)

        ttk.Label(conn, text="API URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(conn, textvariable=self.url).grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)
        ttk.Label(conn, text="Project ID").grid(row=1, column=0, sticky="w")
        ttk.Entry(conn, textvariable=self.pid, width=12).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(conn, text="API token").grid(row=2, column=0, sticky="w")
        self.token_entry = ttk.Entry(conn, textvariable=self.token, show="•")
        self.token_entry.grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Checkbutton(conn, text="Show", variable=self.show_token, command=self._toggle_token).grid(
            row=2, column=2, padx=(6, 0)
        )
        self.connect_btn = ttk.Button(conn, text="Connect", command=self.on_connect)
        self.connect_btn.grid(row=3, column=1, sticky="w", pady=(6, 0))
        self.project_label = ttk.Label(conn, text="Not connected", foreground="gray")
        self.project_label.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # --- export ---
        exp = ttk.LabelFrame(self, text="Export", padding=8)
        exp.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        exp.columnconfigure(2, weight=1)

        self.mode = tk.StringVar(value="report")
        self.report_id = tk.StringVar()
        self.labels = tk.StringVar(value="raw")
        self.fmt = tk.StringVar(value="csv")

        ttk.Radiobutton(exp, text="Report ID", variable=self.mode, value="report", command=self._mode_changed).grid(
            row=0, column=0, sticky="w"
        )
        self.report_entry = ttk.Entry(exp, textvariable=self.report_id, width=12)
        self.report_entry.grid(row=0, column=1, sticky="w")
        ttk.Label(exp, text="(shown on the project's Reports page)", foreground="gray").grid(
            row=0, column=2, sticky="w", padx=(6, 0)
        )
        ttk.Radiobutton(
            exp, text="All records (full dataset)", variable=self.mode, value="all", command=self._mode_changed
        ).grid(row=1, column=0, columnspan=3, sticky="w")

        ttk.Label(exp, text="Values").grid(row=2, column=0, sticky="w", pady=(8, 0))
        vals = ttk.Frame(exp)
        vals.grid(row=2, column=1, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Radiobutton(vals, text="Raw codes", variable=self.labels, value="raw").pack(side="left")
        ttk.Radiobutton(vals, text="Labels", variable=self.labels, value="label").pack(side="left", padx=8)

        ttk.Label(exp, text="Format").grid(row=3, column=0, sticky="w")
        fmts = ttk.Frame(exp)
        fmts.grid(row=3, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(fmts, text="CSV", variable=self.fmt, value="csv").pack(side="left")
        ttk.Radiobutton(fmts, text="Excel (.xlsx)", variable=self.fmt, value="xlsx").pack(side="left", padx=8)

        self.export_btn = ttk.Button(exp, text="Download…", command=self.on_export, state="disabled")
        self.export_btn.grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        # --- status ---
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.status = ttk.Label(self, text="Enter your project ID and API token, then Connect.", wraplength=500)
        self.status.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        root.bind("<Return>", lambda _e: self.on_connect() if self.project is None else self.on_export())
        self.after(100, self._poll)

    # --- helpers ---
    def _toggle_token(self):
        self.token_entry.configure(show="" if self.show_token.get() else "•")

    def _mode_changed(self):
        self.report_entry.configure(state="normal" if self.mode.get() == "report" else "disabled")

    def _busy(self, busy: bool, msg: str = ""):
        state = "disabled" if busy else "normal"
        self.connect_btn.configure(state=state)
        self.export_btn.configure(state="disabled" if busy or self.project is None else "normal")
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
        if msg:
            self.status.configure(text=msg)

    def _run(self, kind: str, fn, *args):
        """Run fn in a worker thread so the window stays responsive; results go through a queue."""

        def worker():
            try:
                self.results.put((kind, True, fn(*args)))
            except Exception as e:  # noqa: BLE001 - any failure must reach the UI
                self.results.put((kind, False, e))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, ok, value = self.results.get_nowait()
                getattr(self, f"_done_{kind}")(ok, value)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # --- connect ---
    def on_connect(self):
        pid_text = self.pid.get().strip()
        if not pid_text.isdigit():
            messagebox.showerror("Project ID", "Project ID must be a number.")
            return
        self.project = None
        self._busy(True, "Connecting…")
        self._run("connect", api.connect, self.url.get(), self.token.get(), int(pid_text))

    def _done_connect(self, ok, value):
        if ok:
            self.project, self.info = value
            stage = "production" if self.info.in_production else "development"
            self.project_label.configure(
                text=f"✓ {self.info.project_id}: {self.info.title}  ({stage}, REDCap {self.info.redcap_version})",
                foreground="green",
            )
            self._busy(False, "Connected. Choose what to export.")
        else:
            self.project_label.configure(text="Not connected", foreground="gray")
            self._busy(False, "Connection failed.")
            messagebox.showerror("Connection failed", str(value))

    # --- export ---
    def on_export(self):
        if self.project is None:
            return
        report_id = None
        if self.mode.get() == "report":
            rid = self.report_id.get().strip()
            if not rid.isdigit():
                messagebox.showerror("Report ID", "Report ID must be a number.")
                return
            report_id = int(rid)

        ext = self.fmt.get()
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        what = f"report{report_id}" if report_id else "all_records"
        path = filedialog.asksaveasfilename(
            title="Save export as",
            initialfile=f"redcap_{self.info.project_id}_{what}_{stamp}.{ext}",
            defaultextension=f".{ext}",
            filetypes=[("CSV", "*.csv")] if ext == "csv" else [("Excel", "*.xlsx")],
        )
        if not path:
            return
        self._busy(True, f"Downloading {what.replace('_', ' ')}…")
        self._run("export", self._export, report_id, self.labels.get() == "label", Path(path))

    def _export(self, report_id, labels, path):
        text = api.fetch_csv(self.project, report_id, labels)
        return path, api.save(text, path)

    def _done_export(self, ok, value):
        if ok:
            path, rows = value
            self._busy(False, f"Saved {rows} rows to {path}")
        else:
            self._busy(False, "Export failed.")
            messagebox.showerror("Export failed", str(value))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

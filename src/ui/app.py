"""Main GUI application — PDF to Excel Data Merger."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import logging
import os
import sys
import threading
import shutil

from ui.widgets import SearchableDropdown
from converters import load_converter_module
from engine.insert import NoMatchesFoundError
from engine.pipeline import run_full_pipeline, run_extract_only
from utils import (
    get_install_dir, get_user_data_dir, get_resource_path,
    ensure_config_exists,
)
from i18n import t, set_language, get_language, LANGUAGES, save_language

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
#  Main application
# ══════════════════════════════════════════════════════════════════════

class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title(t("app.title"))
        self.root.geometry("600x750")

        # Data
        self.tools = []
        self.profiles = []

        # Tk variables
        self.selected_file = tk.StringVar()
        self.status_var = tk.StringVar(value=t("app.ready"))
        self.merge_progress_var = tk.DoubleVar(value=0.0)
        self.merge_progress_label_var = tk.StringVar(value="0%")
        self.profile_var = tk.StringVar()
        self.tool_var = tk.StringVar()
        self.excel_file = tk.StringVar()
        self.pdf_cols_var = tk.StringVar()
        self.excel_cols_var = tk.StringVar()
        self.qty_increase_var = tk.StringVar(value="5%")
        self.qty_decrease_var = tk.StringVar(value="5%")

        # Config paths (config/ subdirectory)
        self.tools_path = ensure_config_exists(
            os.path.join("config", "tools.json"))
        self.profiles_path = ensure_config_exists(
            os.path.join("config", "merge_profiles.json"))

        self.load_tools()
        self.load_profiles()

        self.create_menu()
        self.create_widgets()

    # ── Language switching ─────────────────────────────────────────────

    def _switch_language(self, lang_code):
        """Switch UI language and rebuild all widgets."""
        save_language(lang_code)
        # Rebuild the entire UI
        self.root.title(t("app.title"))
        self.status_var.set(t("app.ready"))
        # Destroy existing widgets and rebuild
        for widget in self.root.winfo_children():
            widget.destroy()
        self.create_menu()
        self.create_widgets()

    # ── Data persistence ──────────────────────────────────────────────

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=t("menu.file"), menu=file_menu)
        file_menu.add_command(label=t("menu.exit"), command=self.root.quit)

        # Language menu
        lang_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=t("menu.language"), menu=lang_menu)
        for code, name in LANGUAGES.items():
            lang_menu.add_command(
                label=name,
                command=lambda c=code: self._switch_language(c),
            )

    def load_tools(self):
        try:
            with open(self.tools_path, "r") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError(t("error.tools_json_array"))
            self.tools = [
                t for t in data
                if isinstance(t, dict) and "name" in t and "script" in t
            ]
        except Exception as e:
            logger.warning("Could not load tools.json: %s", e)
            self.tools = []

    def load_profiles(self):
        try:
            with open(self.profiles_path, "r") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError(t("error.profiles_json_array"))
            self.profiles = [
                p for p in data
                if isinstance(p, dict) and "name" in p
            ]
        except Exception as e:
            logger.warning("Could not load profiles: %s", e)
            self.profiles = []

    def save_profiles_to_disk(self):
        try:
            with open(self.profiles_path, "w") as f:
                json.dump(self.profiles, f, indent=4)
        except Exception as e:
            messagebox.showerror(t("error"), t("error.save_profiles", e=e))

    def _save_tools_to_disk(self):
        """Persist the tools list to config/tools.json."""
        try:
            with open(self.tools_path, "w") as f:
                json.dump(self.tools, f, indent=4)
        except Exception as e:
            messagebox.showerror(t("error"), t("error.save_tools", e=e))

    def _get_intermediate_dir(self):
        """Return a writable folder for transient CSV files."""
        inter_dir = os.path.join(get_user_data_dir(), "intermediate")
        os.makedirs(inter_dir, exist_ok=True)
        return inter_dir

    def _prepare_intermediate_csv_path(self, pdf_path, tool_name):
        """
        Keep only the latest intermediate CSV and return its target path.

        Behavior:
        - Deletes previous CSVs in the intermediate folder.
        - Deletes previous CSVs from legacy OS temp intermediate folder.
        - Removes old legacy CSV next to the source PDF (if present).
        - Returns a safe CSV path under repo intermediate/.
        """
        inter_dir = self._get_intermediate_dir()

        # Keep only latest intermediate CSV (remove older files first)
        for fname in os.listdir(inter_dir):
            if fname.lower().endswith(".csv"):
                try:
                    os.remove(os.path.join(inter_dir, fname))
                except OSError:
                    pass

        # Clean legacy temp intermediate folder from previous behavior
        # Use TMPDIR-based path from previous behavior
        env_tmp = os.environ.get("TMPDIR")
        if env_tmp:
            old_inter_dir = os.path.join(env_tmp, "simpletranslator", "intermediate")
            if os.path.isdir(old_inter_dir):
                for fname in os.listdir(old_inter_dir):
                    if fname.lower().endswith(".csv"):
                        try:
                            os.remove(os.path.join(old_inter_dir, fname))
                        except OSError:
                            pass

        # Remove legacy behavior artifact (CSV beside source PDF)
        legacy_csv = os.path.splitext(pdf_path)[0] + ".csv"
        if os.path.exists(legacy_csv):
            try:
                os.remove(legacy_csv)
            except OSError:
                pass

        def _safe(s):
            cleaned = "".join(ch if ch.isalnum() else "_" for ch in s)
            cleaned = cleaned.strip("_")
            return cleaned or "file"

        safe_tool = _safe(tool_name)
        safe_pdf = _safe(os.path.splitext(os.path.basename(pdf_path))[0])
        return os.path.join(inter_dir, f"{safe_tool}__{safe_pdf}.csv")

    # ── Thread-safe UI helper ───────────────────────────────────────

    def _ui(self, func, *args, **kwargs):
        """Schedule *func(*args, **kwargs)* on the main Tk thread."""
        self.root.after(0, lambda: func(*args, **kwargs))

    # ── Portable path helpers ───────────────────────────────────────

    def _resolve_profile_path(self, path):
        """Resolve a profile path (absolute or relative) to an existing file."""
        if not path:
            return None
        if os.path.isabs(path) and os.path.exists(path):
            return path
        full = os.path.join(get_install_dir(), path)
        if os.path.exists(full):
            return full
        full = os.path.join(get_user_data_dir(), path)
        if os.path.exists(full):
            return full
        return None

    @staticmethod
    def _make_portable_path(path):
        """Convert an absolute path to relative if inside the install dir."""
        if not path:
            return path
        try:
            install = get_install_dir()
            abs_path = os.path.abspath(path)
            if os.path.commonpath([abs_path, install]) == install:
                return os.path.relpath(abs_path, install)
        except ValueError:
            pass
        return path

    # ── UI layout ─────────────────────────────────────────────────────

    def create_widgets(self):
        padding = {"padx": 15, "pady": 5}

        # Title
        self.lbl_heading = ttk.Label(
            self.root, text=t("app.heading"),
            font=("Helvetica", 16, "bold"),
        )
        self.lbl_heading.pack(pady=15)

        # ── 1. Profile Loader ─────────────────────────────────────────
        self.frame_profile = ttk.LabelFrame(
            self.root, text=t("section.profile"))
        self.frame_profile.pack(fill="x", **padding)

        h_frame = ttk.Frame(self.frame_profile)
        h_frame.pack(fill="x", padx=10, pady=5)

        profile_names = [p["name"] for p in self.profiles]
        self.profile_dropdown = SearchableDropdown(
            h_frame, textvariable=self.profile_var,
            items=profile_names, command=self.on_profile_select,
        )
        self.profile_dropdown.pack(side="left", fill="x", expand=True)

        self.btn_delete_profile = ttk.Button(
            h_frame, text=t("btn.delete_profile"),
            command=self.delete_profile,
        )
        self.btn_delete_profile.pack(side="right", padx=(5, 0))

        # ── 2. PDF Input ──────────────────────────────────────────────
        self.frame_input = ttk.LabelFrame(self.root, text=t("section.pdf_input"))
        self.frame_input.pack(fill="x", **padding)

        inp_layout = ttk.Frame(self.frame_input)
        inp_layout.pack(fill="x", padx=10, pady=5)

        ttk.Entry(inp_layout, textvariable=self.selected_file).pack(
            side="left", fill="x", expand=True)
        self.btn_browse_pdf = ttk.Button(
            inp_layout, text=t("btn.browse_dots"), command=self.browse_file,
        )
        self.btn_browse_pdf.pack(side="right", padx=(5, 0))

        # ── 3. Configuration ──────────────────────────────────────────
        self.frame_config = ttk.LabelFrame(
            self.root, text=t("section.config"))
        self.frame_config.pack(fill="x", **padding)

        # Converter selector
        c_frame = ttk.Frame(self.frame_config)
        c_frame.pack(fill="x", padx=10, pady=5)
        self.lbl_converter = ttk.Label(c_frame, text=t("label.converter"), width=15)
        self.lbl_converter.pack(side="left")

        self.tool_dropdown = SearchableDropdown(
            c_frame, textvariable=self.tool_var,
            items=[], command=self.on_tool_change,
        )
        self.tool_dropdown.pack(side="left", fill="x", expand=True)

        ttk.Button(
            c_frame, text="+", width=3, command=self.open_add_tool_window,
        ).pack(side="right", padx=1)
        self.btn_edit_tool = ttk.Button(
            c_frame, text=t("btn.edit"), width=4, command=self.open_edit_tool_window,
        )
        self.btn_edit_tool.pack(side="right", padx=1)

        # Excel template
        e_frame = ttk.Frame(self.frame_config)
        e_frame.pack(fill="x", padx=10, pady=5)
        self.lbl_excel_template = ttk.Label(e_frame, text=t("label.excel_template"), width=15)
        self.lbl_excel_template.pack(side="left")
        ttk.Entry(e_frame, textvariable=self.excel_file).pack(
            side="left", fill="x", expand=True)
        self.btn_browse_excel = ttk.Button(
            e_frame, text=t("btn.browse"), command=self.browse_excel,
        )
        self.btn_browse_excel.pack(side="right")

        # Column mappings
        col_frame = ttk.Frame(self.frame_config)
        col_frame.pack(fill="x", padx=10, pady=5)

        p_col_f = ttk.Frame(col_frame)
        p_col_f.pack(fill="x", pady=2)
        self.lbl_pdf_cols = ttk.Label(p_col_f, text=t("label.pdf_columns"), width=15)
        self.lbl_pdf_cols.pack(side="left")
        ttk.Entry(p_col_f, textvariable=self.pdf_cols_var).pack(
            side="left", fill="x", expand=True)
        self.lbl_pdf_hint = ttk.Label(p_col_f, text=t("hint.comma_separated"))
        self.lbl_pdf_hint.pack(
            side="right", padx=5)

        e_col_f = ttk.Frame(col_frame)
        e_col_f.pack(fill="x", pady=2)
        self.lbl_excel_cols = ttk.Label(e_col_f, text=t("label.excel_columns"), width=15)
        self.lbl_excel_cols.pack(side="left")
        ttk.Entry(e_col_f, textvariable=self.excel_cols_var).pack(
            side="left", fill="x", expand=True)
        self.lbl_excel_hint = ttk.Label(e_col_f, text=t("hint.comma_separated"))
        self.lbl_excel_hint.pack(
            side="right", padx=5)

        # Quantity tolerance
        tol_frame = ttk.Frame(self.frame_config)
        tol_frame.pack(fill="x", padx=10, pady=5)
        self.lbl_qty = ttk.Label(tol_frame, text=t("label.qty_tolerance"), width=15)
        self.lbl_qty.pack(side="left")
        ttk.Label(tol_frame, text="+").pack(side="left")
        ttk.Entry(tol_frame, textvariable=self.qty_increase_var,
                  width=8).pack(side="left", padx=(0, 5))
        ttk.Label(tol_frame, text="−").pack(side="left")
        ttk.Entry(tol_frame, textvariable=self.qty_decrease_var,
                  width=8).pack(side="left", padx=(0, 5))
        self.lbl_tol_hint = ttk.Label(tol_frame, text=t("hint.tolerance_format"))
        self.lbl_tol_hint.pack(
            side="right", padx=5)

        self.btn_save_profile = ttk.Button(
            self.frame_config, text=t("btn.save_profile"),
            command=self.save_new_profile,
        )
        self.btn_save_profile.pack(anchor="e", padx=10, pady=10)

        self.refresh_combo_list()

        # ── 4. Action ─────────────────────────────────────────────────
        frame_run = ttk.Frame(self.root)
        frame_run.pack(fill="x", padx=padding["padx"], pady=15)

        self.btn_run = ttk.Button(
            frame_run, text=t("btn.run_merge"),
            command=self.run_merge_thread,
        )
        self.btn_run.pack(fill="x", ipady=12)

        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill="x", padx=padding["padx"], pady=(0, 8))

        self.merge_progressbar = ttk.Progressbar(
            progress_frame,
            variable=self.merge_progress_var,
            maximum=100,
            mode="determinate",
        )
        self.merge_progressbar.pack(side="left", fill="x", expand=True)

        ttk.Label(
            progress_frame,
            textvariable=self.merge_progress_label_var,
            width=5,
            anchor="e",
        ).pack(side="right", padx=(8, 0))

        # Utilities
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", pady=5)
        debug_frame = ttk.Frame(self.root)
        debug_frame.pack(fill="x", pady=5)
        self.btn_convert_only = ttk.Button(
            debug_frame,
            text=t("btn.convert_only"),
            command=self.run_conversion_thread,
        )
        self.btn_convert_only.pack()

        # Status bar
        self.lbl_status = ttk.Label(
            self.root, textvariable=self.status_var,
            relief="sunken", anchor="w",
        )
        self.lbl_status.pack(side="bottom", fill="x", ipady=5)

    # ── Combo / dropdown helpers ──────────────────────────────────────

    def refresh_combo_list(self):
        self.tools.sort(key=lambda x: x["name"])
        self.tool_dropdown.update_items([t["name"] for t in self.tools])

    def on_tool_change(self, event):
        pass

    # ── Profile management ────────────────────────────────────────────

    def on_profile_select(self, event):
        name = self.profile_var.get()
        if not name:
            return
        profile = next(
            (p for p in self.profiles if p["name"] == name), None)
        if profile:
            self.tool_var.set(profile.get("converter", ""))

            # Resolve the excel template path (may be relative or stale)
            excel_path = profile.get("excel_template", "")
            if excel_path:
                resolved = self._resolve_profile_path(excel_path)
                if resolved:
                    self.excel_file.set(resolved)
                else:
                    messagebox.showwarning(
                        t("warning.file_not_found_title"),
                        t("warning.template_not_found", path=excel_path))
                    self.excel_file.set("")
            else:
                self.excel_file.set("")

            self.pdf_cols_var.set(profile.get("pdf_cols", ""))
            self.excel_cols_var.set(profile.get("excel_cols", ""))
            self.qty_increase_var.set(profile.get("qty_increase", "5%"))
            self.qty_decrease_var.set(profile.get("qty_decrease", "5%"))
            self.on_tool_change(None)
            self.status_var.set(t("info.loaded_profile", name=name))

    def save_new_profile(self):
        current_data = {
            "converter": self.tool_var.get(),
            "excel_template": self._make_portable_path(self.excel_file.get()),
            "pdf_cols": self.pdf_cols_var.get(),
            "excel_cols": self.excel_cols_var.get(),
            "qty_increase": self.qty_increase_var.get(),
            "qty_decrease": self.qty_decrease_var.get(),
        }
        if not current_data["converter"] or not current_data["excel_template"]:
            messagebox.showwarning(
                t("warning.incomplete"),
                t("warning.fill_fields"),
            )
            return

        ask_win = tk.Toplevel(self.root)
        ask_win.title(t("dialog.save_profile"))
        ask_win.geometry("300x150")

        ttk.Label(ask_win, text=t("label.profile_name")).pack(pady=10)
        name_var = tk.StringVar(value=self.profile_var.get())
        ttk.Entry(ask_win, textvariable=name_var).pack(
            pady=5, padx=20, fill="x")

        def do_save():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror(t("error"), t("error.name_required"))
                return
            existing = next(
                (p for p in self.profiles if p["name"] == name), None)
            if existing:
                if not messagebox.askyesno(
                        t("confirm.overwrite"), t("confirm.overwrite_profile", name=name)):
                    return
                existing.update(current_data)
            else:
                new_p = {"name": name}
                new_p.update(current_data)
                self.profiles.append(new_p)

            self.save_profiles_to_disk()
            self.profile_dropdown.update_items(
                [p["name"] for p in self.profiles])
            self.profile_var.set(name)
            messagebox.showinfo(t("info.saved"), t("info.profile_saved", name=name))
            ask_win.destroy()

        ttk.Button(ask_win, text=t("btn.save"), command=do_save).pack(pady=10)

    def delete_profile(self):
        name = self.profile_var.get()
        if not name:
            return
        if messagebox.askyesno(t("confirm.delete"), t("confirm.delete_profile", name=name)):
            self.profiles = [
                p for p in self.profiles if p["name"] != name]
            self.save_profiles_to_disk()
            self.profile_dropdown.update_items(
                [p["name"] for p in self.profiles])
            self.profile_var.set("")
            messagebox.showinfo(t("info.deleted"), t("info.profile_deleted"))

    # ── Tool management dialogs ───────────────────────────────────────

    def open_add_tool_window(self):
        self._open_tool_dialog(title=t("dialog.add_converter"), mode="add")

    def open_edit_tool_window(self):
        current_name = self.tool_var.get()
        if not current_name:
            return
        tool = next(
            (tl for tl in self.tools if tl["name"] == current_name), None)
        if tool:
            self._open_tool_dialog(
                title=t("dialog.edit_converter", name=current_name), mode="edit", tool_data=tool)

    def _open_tool_dialog(self, title, mode, tool_data=None):
        top = tk.Toplevel(self.root)
        top.title(title)
        top.geometry("450x350")

        pad = {"padx": 10, "pady": 5}

        # Name
        ttk.Label(top, text=t("label.converter_name")).pack(anchor="w", **pad)
        entry_name = ttk.Entry(top)
        entry_name.pack(fill="x", **pad)
        if tool_data:
            entry_name.insert(0, tool_data["name"])

        # Category
        ttk.Label(top, text=t("label.category")).pack(anchor="w", **pad)
        entry_cat = ttk.Entry(top)
        entry_cat.pack(fill="x", **pad)
        if tool_data and "category" in tool_data:
            entry_cat.insert(0, tool_data["category"])

        # Description
        ttk.Label(top, text=t("label.description")).pack(anchor="w", **pad)
        entry_desc = ttk.Entry(top)
        entry_desc.pack(fill="x", **pad)
        if tool_data:
            entry_desc.insert(0, tool_data.get("description", ""))

        # Script
        ttk.Label(top, text=t("label.script_file")).pack(anchor="w", **pad)
        frame_script = ttk.Frame(top)
        frame_script.pack(fill="x", **pad)
        entry_script = ttk.Entry(frame_script)
        entry_script.pack(side="left", fill="x", expand=True)
        if tool_data:
            entry_script.insert(0, tool_data["script"])

        def browse_script():
            f = filedialog.askopenfilename(
                filetypes=[("Python Files", "*.py")])
            if f:
                entry_script.delete(0, tk.END)
                entry_script.insert(0, f)

        ttk.Button(
            frame_script, text=t("btn.browse"), command=browse_script,
        ).pack(side="right", padx=(5, 0))

        # ── Save logic ────────────────────────────────────────────────
        def save_tool():
            name = entry_name.get().strip()
            category = entry_cat.get().strip()
            source_script = entry_script.get().strip()
            desc = entry_desc.get().strip()

            if not name or not source_script:
                messagebox.showerror(
                    t("error"), t("error.name_script_required"))
                return

            # Resolve script path — copy into converters/ if external
            script_filename = os.path.basename(source_script)
            converters_dir = os.path.join(get_user_data_dir(), "converters")
            os.makedirs(converters_dir, exist_ok=True)
            target_script = os.path.join(converters_dir, script_filename)
            script_rel_path = os.path.join("converters", script_filename)

            try:
                if (os.path.exists(source_script) and
                        os.path.abspath(source_script) !=
                        os.path.abspath(target_script)):
                    shutil.copy2(source_script, target_script)
                elif (not os.path.exists(target_script) and
                      not os.path.exists(source_script)):
                    # Might already be a relative path in tools.json
                    full = get_resource_path(source_script)
                    if not os.path.exists(full):
                        messagebox.showerror(
                            t("error"),
                            t("error.script_not_found", path=source_script))
                        return
                    script_rel_path = source_script

                new_entry = {
                    "name": name,
                    "category": category,
                    "script": script_rel_path,
                    "description": desc,
                }

                if mode == "add":
                    self.tools.append(new_entry)
                else:
                    for i, tl in enumerate(self.tools):
                        if tl["name"] == tool_data["name"]:
                            self.tools[i] = new_entry
                            break

                self._save_tools_to_disk()
                self.refresh_combo_list()
                self.tool_var.set(name)
                self.on_tool_change(None)

                messagebox.showinfo(t("success"), t("info.tool_saved", name=name))
                top.destroy()
            except Exception as e:
                messagebox.showerror(t("error"), t("error.save_tool_failed", e=e))

        # Buttons
        if mode == "edit":
            def delete_tool():
                if messagebox.askyesno(
                        t("confirm"), t("confirm.delete_tool", name=tool_data['name'])):
                    self.tools = [
                        tl for tl in self.tools
                        if tl["name"] != tool_data["name"]
                    ]
                    self._save_tools_to_disk()
                    self.refresh_combo_list()
                    top.destroy()

            btn_frame = ttk.Frame(top)
            btn_frame.pack(pady=20, fill="x")
            ttk.Button(
                btn_frame, text=t("btn.delete_tool"), command=delete_tool,
            ).pack(side="left", padx=10)
            ttk.Button(
                btn_frame, text=t("btn.save_changes"), command=save_tool,
            ).pack(side="right", padx=10)
        else:
            ttk.Button(
                top, text=t("btn.add_converter"), command=save_tool,
            ).pack(pady=20)

    # ── File browsing ─────────────────────────────────────────────────

    def browse_file(self):
        f = filedialog.askopenfilename(
            title=t("dialog.open_pdf"), initialdir="source",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if f:
            self.selected_file.set(f)

    def browse_excel(self):
        f = filedialog.askopenfilename(
            title=t("dialog.open_excel"), initialdir="source",
            filetypes=[("Excel files", "*.xlsx *.xls"),
                       ("All files", "*.*")])
        if f:
            self.excel_file.set(f)

    # ── Merge workflow (Layer 1 → Layer 2) ────────────────────────────

    def _set_merge_progress(self, percent, status_text=None):
        """Update merge progress widgets and optional status text."""
        safe_percent = max(0, min(100, int(percent)))
        self.merge_progress_var.set(safe_percent)
        self.merge_progress_label_var.set(f"{safe_percent}%")
        if status_text:
            self.status_var.set(status_text)

    def run_merge_thread(self):
        # ── Validate inputs on the main (UI) thread ──────────────────
        self._set_merge_progress(0, t("pipeline.validating_inputs"))
        pdf_path = self.selected_file.get()
        excel_path = self.excel_file.get()
        tool_name = self.tool_var.get()
        pdf_cols_str = self.pdf_cols_var.get().strip()
        excel_cols_str = self.excel_cols_var.get().strip()

        if not pdf_path or not excel_path:
            messagebox.showwarning(
                t("warning.missing_files"),
                t("warning.select_both"))
            return

        if not pdf_cols_str or not excel_cols_str:
            messagebox.showwarning(
                t("warning.missing_columns"),
                t("warning.specify_columns"))
            return

        tool_config = next(
            (t for t in self.tools if t["name"] == tool_name), None)
        if not tool_config:
            messagebox.showerror(t("error"), t("error.tool_not_found"))
            return

        pdf_cols = [c.strip() for c in pdf_cols_str.split(",")]
        excel_cols = [c.strip() for c in excel_cols_str.split(",")]

        if len(pdf_cols) != len(excel_cols):
            messagebox.showerror(
                t("error"),
                t("error.column_mismatch", pdf=len(pdf_cols), excel=len(excel_cols)))
            return

        default_name = os.path.basename(
            excel_path).replace(".xlsx", "_merged.xlsx")
        output_path = filedialog.asksaveasfilename(
            title=t("dialog.save_merged"),
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not output_path:
            self._set_merge_progress(0, t("app.ready"))
            return

        self.btn_run.config(state="disabled")
        self._set_merge_progress(10, t("pipeline.preparing"))
        threading.Thread(
            target=self._run_merge_worker,
            args=(output_path, pdf_path, excel_path,
                  tool_config, pdf_cols, excel_cols),
            daemon=True,
        ).start()

    def _run_merge_worker(self, output_path, pdf_path, excel_path,
                          tool_config, pdf_cols, excel_cols):
        """Heavy merge work — runs on a background thread."""
        try:
            logger.info("Merge requested — tool=%s  pdf=%s  excel=%s  output=%s",
                        tool_config["name"], pdf_path, excel_path, output_path)
            self._ui(self._set_merge_progress, 20, t("pipeline.loading_converter"))
            script_path = get_resource_path(tool_config["script"])
            converter = load_converter_module(script_path)
            csv_path = self._prepare_intermediate_csv_path(
                pdf_path, tool_config["name"])

            def on_progress(pct, msg):
                self._ui(self._set_merge_progress, pct, msg)

            result = run_full_pipeline(
                pdf_path, csv_path, excel_path,
                converter, pdf_cols, excel_cols,
                output_path=output_path,
                on_progress=on_progress,
                qty_increase_ratio=self.qty_increase_var.get(),
                qty_decrease_ratio=self.qty_decrease_var.get(),
            )

            removed = result.get('rows_removed', 0)
            report = (
                t("report.rows_extracted", n=result['rows_extracted']) + "\n"
            )
            if removed:
                report += t("report.rows_removed", n=removed) + "\n"
            report += (
                t("report.validation_flags", n=result['cells_flagged']) + "\n"
                + t("report.rows_matched", matched=result['rows_matched'], total=result['total_csv_rows']) + "\n"
                + t("report.rows_not_found", n=result['rows_not_found']) + "\n"
            )
            if result.get("missing_columns"):
                report += t("report.missing_columns", cols=', '.join(result['missing_columns'])) + "\n"
            if result.get("qty_recalc_disabled"):
                report += t("report.qty_disabled") + "\n"
            report += (
                f"{'─' * 35}\n"
                + t("report.output", path=result['output_path'])
            )
            self._ui(self._set_merge_progress, 100,
                     t("report.success_saved", path=result['output_path']))
            self._ui(messagebox.showinfo, t("report.merge_complete"), report)

        except NoMatchesFoundError as e:
            stats = e.stats
            removed = stats.get('rows_removed', 0)
            report = (
                t("report.rows_extracted", n=stats.get('rows_extracted', '?')) + "\n"
            )
            if removed:
                report += t("report.rows_removed", n=removed) + "\n"
            report += (
                t("report.validation_flags", n=stats.get('cells_flagged', '?')) + "\n"
                + t("report.rows_matched", matched=0, total=stats.get('total_csv_rows', '?')) + "\n"
                + f"{'─' * 35}\n"
                + t("report.no_matches_body")
            )
            logger.warning("Merge finished with no matches — file not generated.")
            self._ui(self._set_merge_progress, 0,
                     t("report.no_matches_status"))
            self._ui(messagebox.showwarning, t("report.no_matches_title"), report)
        except Exception as e:
            logger.exception("Merge failed")
            self._ui(self._set_merge_progress, 0, t("report.error_during_merge"))
            self._ui(self.status_var.set, t("report.error_during_merge"))
            self._ui(messagebox.showerror, t("error"),
                     t("error.merge_error", e=e))
        finally:
            self._ui(self.btn_run.config, state="normal")

    # ── Convert-only workflow (Layer 1 only) ──────────────────────────

    def run_conversion_thread(self):
        input_path = self.selected_file.get()
        tool_name = self.tool_var.get()

        if not input_path:
            messagebox.showwarning(t("warning"), t("warning.select_file_first"))
            return
        if not os.path.exists(input_path):
            messagebox.showerror(t("error"), t("error.file_not_found"))
            return

        tool_config = next(
            (t_item for t_item in self.tools if t_item["name"] == tool_name), None)
        if not tool_config:
            messagebox.showerror(t("error"), t("error.tool_not_found"))
            return

        default_name = os.path.splitext(
            os.path.basename(input_path))[0] + ".csv"
        csv_output_path = filedialog.asksaveasfilename(
            title=t("dialog.save_csv"),
            initialfile=default_name,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not csv_output_path:
            return

        self.btn_run.config(state="disabled")
        self.status_var.set(t("convert.running", name=tool_name))

        threading.Thread(
            target=self._run_conversion_worker,
            args=(input_path, tool_config, csv_output_path),
            daemon=True,
        ).start()

    def _run_conversion_worker(self, input_path, tool_config, csv_output_path):
        """Heavy conversion work — runs on a background thread."""
        try:
            logger.info("Convert-only requested — tool=%s  pdf=%s  output=%s",
                        tool_config["name"], input_path, csv_output_path)
            script_path = get_resource_path(tool_config["script"])
            converter = load_converter_module(script_path)
            output_path = csv_output_path

            def on_progress(pct, msg):
                self._ui(self.status_var.set, msg)

            csv_path, flagged_cells = run_extract_only(
                input_path, output_path, converter,
                on_progress=on_progress,
            )

            flag_msg = ""
            if flagged_cells:
                flag_msg = "\n\n" + t("convert.flagged", n=len(flagged_cells))

            logger.info("Convert-only finished — %s  (%d flagged)",
                        csv_path, len(flagged_cells))
            self._ui(
                self.status_var.set,
                t("convert.done", name=os.path.basename(csv_path)))
            self._ui(
                messagebox.showinfo, t("success"),
                t("convert.success_msg", path=csv_path, flag_msg=flag_msg))

        except Exception as e:
            logger.exception("Conversion failed")
            self._ui(self.status_var.set, t("report.error_occurred"))
            self._ui(messagebox.showerror, t("error"), str(e))
        finally:
            self._ui(self.btn_run.config, state="normal")


# Allow running directly:  python ui/app.py
if __name__ == "__main__":
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()

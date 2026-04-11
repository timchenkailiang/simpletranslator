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
from engine.merge import process_merge as merge_csv_to_excel
from engine.merge import NoMatchesFoundError
from engine.validate import validate_csv
from utils import (
    get_install_dir, get_user_data_dir, get_resource_path,
    ensure_config_exists,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
#  Main application
# ══════════════════════════════════════════════════════════════════════

class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF to Excel Merger Application")
        self.root.geometry("600x750")

        # Data
        self.tools = []
        self.profiles = []

        # Tk variables
        self.selected_file = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.profile_var = tk.StringVar()
        self.tool_var = tk.StringVar()
        self.excel_file = tk.StringVar()
        self.pdf_cols_var = tk.StringVar()
        self.excel_cols_var = tk.StringVar()

        # Config paths (config/ subdirectory)
        self.tools_path = ensure_config_exists(
            os.path.join("config", "tools.json"))
        self.profiles_path = ensure_config_exists(
            os.path.join("config", "merge_profiles.json"))

        self.load_tools()
        self.load_profiles()

        self.create_menu()
        self.create_widgets()

    # ── Data persistence ──────────────────────────────────────────────

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.root.quit)

    def load_tools(self):
        try:
            with open(self.tools_path, "r") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("tools.json must be a JSON array")
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
                raise ValueError("merge_profiles.json must be a JSON array")
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
            messagebox.showerror("Error", f"Could not save profiles: {e}")

    def _save_tools_to_disk(self):
        """Persist the tools list to config/tools.json."""
        try:
            with open(self.tools_path, "w") as f:
                json.dump(self.tools, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save tools: {e}")

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
        ttk.Label(
            self.root, text="PDF to Excel Data Merger",
            font=("Helvetica", 16, "bold"),
        ).pack(pady=15)

        # ── 1. Profile Loader ─────────────────────────────────────────
        frame_profile = ttk.LabelFrame(
            self.root, text="1. Load Saved Configuration")
        frame_profile.pack(fill="x", **padding)

        h_frame = ttk.Frame(frame_profile)
        h_frame.pack(fill="x", padx=10, pady=5)

        profile_names = [p["name"] for p in self.profiles]
        self.profile_dropdown = SearchableDropdown(
            h_frame, textvariable=self.profile_var,
            items=profile_names, command=self.on_profile_select,
        )
        self.profile_dropdown.pack(side="left", fill="x", expand=True)

        ttk.Button(
            h_frame, text="Delete Profile",
            command=self.delete_profile,
        ).pack(side="right", padx=(5, 0))

        # ── 2. PDF Input ──────────────────────────────────────────────
        frame_input = ttk.LabelFrame(self.root, text="2. Input PDF File")
        frame_input.pack(fill="x", **padding)

        inp_layout = ttk.Frame(frame_input)
        inp_layout.pack(fill="x", padx=10, pady=5)

        ttk.Entry(inp_layout, textvariable=self.selected_file).pack(
            side="left", fill="x", expand=True)
        ttk.Button(
            inp_layout, text="Browse...", command=self.browse_file,
        ).pack(side="right", padx=(5, 0))

        # ── 3. Configuration ──────────────────────────────────────────
        frame_config = ttk.LabelFrame(
            self.root, text="3. Configuration Settings")
        frame_config.pack(fill="x", **padding)

        # Converter selector
        c_frame = ttk.Frame(frame_config)
        c_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(c_frame, text="Converter Model:", width=15).pack(side="left")

        self.tool_dropdown = SearchableDropdown(
            c_frame, textvariable=self.tool_var,
            items=[], command=self.on_tool_change,
        )
        self.tool_dropdown.pack(side="left", fill="x", expand=True)

        ttk.Button(
            c_frame, text="+", width=3, command=self.open_add_tool_window,
        ).pack(side="right", padx=1)
        ttk.Button(
            c_frame, text="Edit", width=4, command=self.open_edit_tool_window,
        ).pack(side="right", padx=1)

        # Description label
        self.desc_label = ttk.Label(
            frame_config, text="Select a converter...",
            font=("Helvetica", 9, "italic"), wraplength=550,
        )
        self.desc_label.pack(padx=10, pady=(0, 5), fill="x")

        # Excel template
        e_frame = ttk.Frame(frame_config)
        e_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(e_frame, text="Excel Template:", width=15).pack(side="left")
        ttk.Entry(e_frame, textvariable=self.excel_file).pack(
            side="left", fill="x", expand=True)
        ttk.Button(
            e_frame, text="Browse", command=self.browse_excel,
        ).pack(side="right")

        # Column mappings
        col_frame = ttk.Frame(frame_config)
        col_frame.pack(fill="x", padx=10, pady=5)

        p_col_f = ttk.Frame(col_frame)
        p_col_f.pack(fill="x", pady=2)
        ttk.Label(p_col_f, text="PDF Columns:", width=15).pack(side="left")
        ttk.Entry(p_col_f, textvariable=self.pdf_cols_var).pack(
            side="left", fill="x", expand=True)
        ttk.Label(p_col_f, text="(comma separated)").pack(
            side="right", padx=5)

        e_col_f = ttk.Frame(col_frame)
        e_col_f.pack(fill="x", pady=2)
        ttk.Label(e_col_f, text="Excel Columns:", width=15).pack(side="left")
        ttk.Entry(e_col_f, textvariable=self.excel_cols_var).pack(
            side="left", fill="x", expand=True)
        ttk.Label(e_col_f, text="(comma separated)").pack(
            side="right", padx=5)

        ttk.Button(
            frame_config, text="💾 Save Current Settings as Profile",
            command=self.save_new_profile,
        ).pack(anchor="e", padx=10, pady=10)

        self.refresh_combo_list()

        # ── 4. Action ─────────────────────────────────────────────────
        frame_run = ttk.Frame(self.root)
        frame_run.pack(fill="x", padx=padding["padx"], pady=15)

        self.btn_run = ttk.Button(
            frame_run, text="RUN MERGE PROCESS",
            command=self.run_merge_thread,
        )
        self.btn_run.pack(fill="x", ipady=12)

        # Utilities
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", pady=5)
        debug_frame = ttk.Frame(self.root)
        debug_frame.pack(fill="x", pady=5)
        ttk.Button(
            debug_frame,
            text="Tools: Convert PDF to CSV Only (No Merge)",
            command=self.run_conversion_thread,
        ).pack()

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
        self.update_description()

    def on_tool_change(self, event):
        self.update_description()

    def update_description(self):
        name = self.tool_var.get()
        for t in self.tools:
            if t["name"] == name:
                self.desc_label.config(text=t.get("description", ""))
                break

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
                        "File Not Found",
                        f"Template not found:\n{excel_path}\n\n"
                        "Please select a new file.")
                    self.excel_file.set("")
            else:
                self.excel_file.set("")

            self.pdf_cols_var.set(profile.get("pdf_cols", ""))
            self.excel_cols_var.set(profile.get("excel_cols", ""))
            self.on_tool_change(None)
            self.status_var.set(f"Loaded profile: {name}")

    def save_new_profile(self):
        current_data = {
            "converter": self.tool_var.get(),
            "excel_template": self._make_portable_path(self.excel_file.get()),
            "pdf_cols": self.pdf_cols_var.get(),
            "excel_cols": self.excel_cols_var.get(),
        }
        if not current_data["converter"] or not current_data["excel_template"]:
            messagebox.showwarning(
                "Incomplete",
                "Please fill in Converter, Excel Template, "
                "and Columns before saving.",
            )
            return

        ask_win = tk.Toplevel(self.root)
        ask_win.title("Save Profile")
        ask_win.geometry("300x150")

        ttk.Label(ask_win, text="Profile Name:").pack(pady=10)
        name_var = tk.StringVar(value=self.profile_var.get())
        ttk.Entry(ask_win, textvariable=name_var).pack(
            pady=5, padx=20, fill="x")

        def do_save():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "Name required")
                return
            existing = next(
                (p for p in self.profiles if p["name"] == name), None)
            if existing:
                if not messagebox.askyesno(
                        "Overwrite", f"Profile '{name}' exists. Overwrite?"):
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
            messagebox.showinfo("Saved", f"Profile '{name}' saved.")
            ask_win.destroy()

        ttk.Button(ask_win, text="Save", command=do_save).pack(pady=10)

    def delete_profile(self):
        name = self.profile_var.get()
        if not name:
            return
        if messagebox.askyesno("Delete", f"Delete profile '{name}'?"):
            self.profiles = [
                p for p in self.profiles if p["name"] != name]
            self.save_profiles_to_disk()
            self.profile_dropdown.update_items(
                [p["name"] for p in self.profiles])
            self.profile_var.set("")
            messagebox.showinfo("Deleted", "Profile deleted.")

    # ── Tool management dialogs ───────────────────────────────────────

    def open_add_tool_window(self):
        self._open_tool_dialog(title="Add New Converter", mode="add")

    def open_edit_tool_window(self):
        current_name = self.tool_var.get()
        if not current_name:
            return
        tool = next(
            (t for t in self.tools if t["name"] == current_name), None)
        if tool:
            self._open_tool_dialog(
                title=f"Edit {current_name}", mode="edit", tool_data=tool)

    def _open_tool_dialog(self, title, mode, tool_data=None):
        top = tk.Toplevel(self.root)
        top.title(title)
        top.geometry("450x350")

        pad = {"padx": 10, "pady": 5}

        # Name
        ttk.Label(top, text="Converter Name:").pack(anchor="w", **pad)
        entry_name = ttk.Entry(top)
        entry_name.pack(fill="x", **pad)
        if tool_data:
            entry_name.insert(0, tool_data["name"])

        # Category
        ttk.Label(top, text="Category (optional):").pack(anchor="w", **pad)
        entry_cat = ttk.Entry(top)
        entry_cat.pack(fill="x", **pad)
        if tool_data and "category" in tool_data:
            entry_cat.insert(0, tool_data["category"])

        # Description
        ttk.Label(top, text="Description:").pack(anchor="w", **pad)
        entry_desc = ttk.Entry(top)
        entry_desc.pack(fill="x", **pad)
        if tool_data:
            entry_desc.insert(0, tool_data.get("description", ""))

        # Script
        ttk.Label(top, text="Python Script (.py):").pack(anchor="w", **pad)
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
            frame_script, text="Browse", command=browse_script,
        ).pack(side="right", padx=(5, 0))

        # ── Save logic ────────────────────────────────────────────────
        def save_tool():
            name = entry_name.get().strip()
            category = entry_cat.get().strip()
            source_script = entry_script.get().strip()
            desc = entry_desc.get().strip()

            if not name or not source_script:
                messagebox.showerror(
                    "Error", "Name and Script File are required.")
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
                            "Error",
                            f"Script file not found: {source_script}")
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
                    for i, t in enumerate(self.tools):
                        if t["name"] == tool_data["name"]:
                            self.tools[i] = new_entry
                            break

                self._save_tools_to_disk()
                self.refresh_combo_list()
                self.tool_var.set(name)
                self.on_tool_change(None)

                messagebox.showinfo("Success", f"Tool '{name}' saved!")
                top.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save tool: {e}")

        # Buttons
        if mode == "edit":
            def delete_tool():
                if messagebox.askyesno(
                        "Confirm", f"Delete '{tool_data['name']}'?"):
                    self.tools = [
                        t for t in self.tools
                        if t["name"] != tool_data["name"]
                    ]
                    self._save_tools_to_disk()
                    self.refresh_combo_list()
                    top.destroy()

            btn_frame = ttk.Frame(top)
            btn_frame.pack(pady=20, fill="x")
            ttk.Button(
                btn_frame, text="Delete Tool", command=delete_tool,
            ).pack(side="left", padx=10)
            ttk.Button(
                btn_frame, text="Save Changes", command=save_tool,
            ).pack(side="right", padx=10)
        else:
            ttk.Button(
                top, text="Add Converter", command=save_tool,
            ).pack(pady=20)

    # ── File browsing ─────────────────────────────────────────────────

    def browse_file(self):
        f = filedialog.askopenfilename(
            title="Open PDF File", initialdir="source",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if f:
            self.selected_file.set(f)

    def browse_excel(self):
        f = filedialog.askopenfilename(
            title="Open Excel Template", initialdir="source",
            filetypes=[("Excel files", "*.xlsx *.xls"),
                       ("All files", "*.*")])
        if f:
            self.excel_file.set(f)

    # ── Merge workflow (Layer 1 → Layer 2) ────────────────────────────

    def run_merge_thread(self):
        # ── Validate inputs on the main (UI) thread ──────────────────
        pdf_path = self.selected_file.get()
        excel_path = self.excel_file.get()
        tool_name = self.tool_var.get()
        pdf_cols_str = self.pdf_cols_var.get().strip()
        excel_cols_str = self.excel_cols_var.get().strip()

        if not pdf_path or not excel_path:
            messagebox.showwarning(
                "Missing Files",
                "Select both a PDF input and an Excel template.")
            return

        if not pdf_cols_str or not excel_cols_str:
            messagebox.showwarning(
                "Missing Columns",
                "Specify columns for both PDF and Excel.")
            return

        tool_config = next(
            (t for t in self.tools if t["name"] == tool_name), None)
        if not tool_config:
            messagebox.showerror("Error", "Tool configuration not found.")
            return

        pdf_cols = [c.strip() for c in pdf_cols_str.split(",")]
        excel_cols = [c.strip() for c in excel_cols_str.split(",")]

        if len(pdf_cols) != len(excel_cols):
            messagebox.showerror(
                "Error",
                f"Column count mismatch!\n"
                f"PDF: {len(pdf_cols)}, Excel: {len(excel_cols)}")
            return

        default_name = os.path.basename(
            excel_path).replace(".xlsx", "_merged.xlsx")
        output_path = filedialog.asksaveasfilename(
            title="Save Merged Excel As",
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not output_path:
            return

        self.status_var.set("Merging data...")
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
            script_path = get_resource_path(tool_config["script"])
            converter = load_converter_module(script_path)
            csv_path = self._prepare_intermediate_csv_path(
                pdf_path, tool_config["name"])
            success = converter.process_file(pdf_path, csv_path)

            if not success:
                if (os.path.exists(csv_path) and
                        os.path.getsize(csv_path) > 0):
                    logger.warning(
                        "Converter returned False but CSV exists.")
                else:
                    raise Exception("PDF to CSV conversion failed.")

            final_output = merge_csv_to_excel(
                csv_path, excel_path, pdf_cols, excel_cols,
                output_path=output_path,
            )

            self._ui(self.status_var.set,
                     f"Success! Saved to {final_output}")
            self._ui(messagebox.showinfo, "Success",
                     f"Merge complete!\nSaved to:\n{final_output}")

        except NoMatchesFoundError:
            self._ui(self.status_var.set,
                     "No matches. File not generated.")
            self._ui(messagebox.showwarning, "No Matches",
                     "No matches found. A new file was not generated.")
        except Exception as e:
            logger.exception("Merge failed")
            self._ui(self.status_var.set, "Error during merge.")
            self._ui(messagebox.showerror, "Error",
                     f"An error occurred:\n{e}")

    # ── Convert-only workflow (Layer 1 only) ──────────────────────────

    def run_conversion_thread(self):
        input_path = self.selected_file.get()
        tool_name = self.tool_var.get()

        if not input_path:
            messagebox.showwarning("Warning", "Please select a file first.")
            return
        if not os.path.exists(input_path):
            messagebox.showerror("Error", "File not found.")
            return

        tool_config = next(
            (t for t in self.tools if t["name"] == tool_name), None)
        if not tool_config:
            messagebox.showerror("Error", "Tool configuration not found.")
            return

        self.btn_run.config(state="disabled")
        self.status_var.set(f"Running {tool_name}...")

        threading.Thread(
            target=self._run_conversion_worker,
            args=(input_path, tool_config),
            daemon=True,
        ).start()

    def _run_conversion_worker(self, input_path, tool_config):
        """Heavy conversion work — runs on a background thread."""
        try:
            # ── Layer 1: Convert ──────────────────────────────────────
            script_path = get_resource_path(tool_config["script"])
            module = load_converter_module(script_path)

            output_path = self._prepare_intermediate_csv_path(
                input_path, tool_config["name"])
            success = module.process_file(input_path, output_path)

            if success:
                self._ui(self.status_var.set,
                         "Conversion successful. Validating...")

                # Use converter metadata for validation when available
                fmt = getattr(module, "FORMAT_NAME", None)
                rules = getattr(module, "VALIDATION_RULES", None)

                try:
                    validate_csv(
                        output_path,
                        format_name=fmt,
                        validation_rules=rules,
                    )
                    self._ui(
                        self.status_var.set,
                        f"Done! Saved to {os.path.basename(output_path)}")
                    self._ui(
                        messagebox.showinfo, "Success",
                        f"Converted & validated!\n\n"
                        f"Saved to: {output_path}\n\n"
                        f"(Check log for details)")
                except Exception as ve:
                    logger.exception("Validation failed")
                    self._ui(self.status_var.set,
                             "Conversion OK, Validation Failed")
                    self._ui(
                        messagebox.showwarning, "Warning",
                        f"Conversion succeeded but validation crashed:\n{ve}")
            else:
                self._ui(self.status_var.set,
                         "Conversion failed (no data).")
                self._ui(messagebox.showerror, "Error",
                         "Conversion returned no data.")

        except Exception as e:
            logger.exception("Conversion failed")
            self._ui(self.status_var.set, "Error Occurred")
            self._ui(messagebox.showerror, "Error", str(e))
        finally:
            self._ui(self.btn_run.config, state="normal")


# Allow running directly:  python ui/app.py
if __name__ == "__main__":
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()

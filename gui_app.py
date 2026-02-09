import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import importlib.util
import sys
import threading
import shutil


def _get_app_dir() -> str:
    """Return the directory the app should treat as its home.

    - If frozen (PyInstaller), use the executable directory.
    - Otherwise, use the directory containing this script.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

# NEW: Custom Widget for "Web-Style" Searchable Dropdown
class SearchableDropdown(ttk.Frame):
    def __init__(self, master, textvariable, items, command=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.textvariable = textvariable
        self.items = items
        self.command = command  # Function to call on selection (e.g. self.on_tool_change)
        self.filtered_items = items
        
        # UI Components
        self.entry = ttk.Entry(self, textvariable=self.textvariable)
        self.entry.pack(side="left", fill="x", expand=True)
        
        # Button to toggle full list
        self.btn = ttk.Button(self, text="▼", width=3, command=self.toggle_full_list, takefocus=False)
        self.btn.pack(side="right")
        
        # Events
        self.entry.bind("<KeyRelease>", self.on_key_release)
        self.entry.bind("<FocusOut>", self.on_focus_out)
        self.entry.bind("<Down>", self.move_selection)
        self.entry.bind("<Up>", self.move_selection)
        self.entry.bind("<Return>", self.on_selection_confirm)
        self.entry.bind("<Button-1>", self.on_click_entry)
        
        # Floating Listbox (Popup)
        self.popup = None
        self.listbox = None
        
        # Bind events to reference window to close popup on external interaction
        self.after(100, self._bind_toplevel)

    def _bind_toplevel(self):
        try:
            top = self.winfo_toplevel()
            top.bind("<Button-1>", self.on_toplevel_click, add="+")
            top.bind("<Configure>", self.on_window_move, add="+")
        except:
            pass
            
    def on_toplevel_click(self, event):
        if not self.popup:
            return
        
        # Check if click is inside the dropdown or its popup
        clicked_widget = event.widget
        try:
            # If clicked widget is child of self (entry, btn) or popup
            if str(clicked_widget).startswith(str(self)) or str(clicked_widget).startswith(str(self.popup)):
                return
        except:
            pass
            
        self.destroy_popup()

    def on_window_move(self, event):
        # Pass if it's the popup moving (unlikely) or some child widget resizing
        if self.popup and event.widget == self.winfo_toplevel():
            self.destroy_popup()

    def update_items(self, new_items):
        self.items = new_items
        self.filtered_items = new_items

        # If popup is open, refresh visible list immediately
        if self.popup and self.listbox:
            self.listbox.delete(0, tk.END)
            for item in self.filtered_items:
                self.listbox.insert(tk.END, item)

    def toggle_full_list(self):
        if self.popup:
            self.destroy_popup()
        else:
            self.filtered_items = self.items # Reset filter
            self.show_popup()

    def on_click_entry(self, event):
        self.filter_items()
        self.show_popup()

    def on_key_release(self, event):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape'):
            return
            
        self.filter_items() 
        self.show_popup() # Show (or refresh) popup with filtered items
        
    def filter_items(self):
        typed = self.textvariable.get()
        if typed == '':
            self.filtered_items = self.items
        else:
            self.filtered_items = [item for item in self.items if typed.lower() in item.lower()]

    def show_popup(self):
        # Create popup if not exists
        if not self.popup:
            self.popup = tk.Toplevel(self)
            try:
                self.popup.transient(self.winfo_toplevel())
            except:
                pass
            self.popup.wm_overrideredirect(True) # Remove window borders
            
            # Position it directly below the entry
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height()
            w = self.entry.winfo_width() + self.btn.winfo_width()
            self.popup.geometry(f"{w}x150+{x}+{y}")

            # On Windows, focus can briefly shift when the Toplevel opens;
            # lifting helps ensure the popup is visible.
            try:
                self.popup.lift()
            except Exception:
                pass
            
            # Listbox inside
            frame = ttk.Frame(self.popup, relief="solid", borderwidth=1)
            frame.pack(fill="both", expand=True)
            
            self.listbox = tk.Listbox(frame, height=5, selectmode="single", highlightthickness=0, borderwidth=0)
            self.listbox.pack(side="left", fill="both", expand=True)
            
            scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
            scrollbar.pack(side="right", fill="y")
            self.listbox.config(yscrollcommand=scrollbar.set)
            
            self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)
        
        # Update Content
        self.listbox.delete(0, tk.END)
        for item in self.filtered_items:
            self.listbox.insert(tk.END, item)

    def destroy_popup(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None
            self.listbox = None

    def on_focus_out(self, event):
        # Delay destruction to allow listbox click to register
        self.after(200, self.check_focus)

    def check_focus(self):
        if self.popup:
            # If mouse is currently over the dropdown or popup, don't close.
            try:
                px, py = self.winfo_pointerxy()
                hover_widget = self.winfo_containing(px, py)
                if hover_widget:
                    hover_name = str(hover_widget)
                    if hover_name.startswith(str(self)) or hover_name.startswith(str(self.popup)):
                        return
            except Exception:
                pass

            focused = self.winfo_toplevel().focus_get()
            
            # Keep open if focus is on entry, button/arrow, or listbox
            if focused in [self.entry, self.btn, self.listbox]:
                return

            # Keep open if focus is inside popup (e.g. scrollbar)
            if focused and str(focused).startswith(str(self.popup)):
                return
                
            self.destroy_popup()

    def move_selection(self, event):
        if not self.popup:
            self.show_popup()
            return

        cur_sel = self.listbox.curselection()
        next_idx = 0
        if cur_sel:
            if event.keysym == 'Up':
                next_idx = max(0, cur_sel[0] - 1)
            else:
                next_idx = min(self.listbox.size() - 1, cur_sel[0] + 1)
        else:
            if event.keysym == 'Down': next_idx = 0
        
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(next_idx)
        self.listbox.see(next_idx)

    def on_selection_confirm(self, event):
        if self.popup:
            cur_sel = self.listbox.curselection()
            if cur_sel:
                self.set_selection(self.listbox.get(cur_sel))

    def on_listbox_select(self, event):
        if not self.listbox:
            return
        cur_sel = self.listbox.curselection()
        if cur_sel:
            self.set_selection(self.listbox.get(cur_sel))

    def set_selection(self, value):
        self.textvariable.set(value)
        self.destroy_popup()
        self.entry.icursor(tk.END) # Move cursor to end
        if self.command:
            self.command(None)  # Trigger callback

class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF to Excel Merger Application")
        self.root.geometry("600x750") # Increased height for new layout
        
        # Data
        self.tools = []
        self.profiles = [] # Saved configurations
        
        # Variables
        self.selected_file = tk.StringVar() # PDF Input
        self.status_var = tk.StringVar(value="Ready")

        # App paths
        self.app_dir = _get_app_dir()
        self.tools_path = os.path.join(self.app_dir, 'tools.json')
        self.profiles_path = os.path.join(self.app_dir, 'merge_profiles.json')
        
        # Configuration Variables
        self.profile_var = tk.StringVar()
        self.tool_var = tk.StringVar()
        self.excel_file = tk.StringVar()
        self.pdf_cols_var = tk.StringVar()
        self.excel_cols_var = tk.StringVar()
        
        # Load Data
        self.load_tools()
        self.load_profiles()
        
        # UI Setup
        self.create_menu()
        self.create_widgets()

        # Startup status (helps confirm tools/profiles were loaded)
        self.status_var.set(f"Loaded {len(self.tools)} tools, {len(self.profiles)} profiles")
        
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.root.quit)

    def load_tools(self):
        try:
            path = self.tools_path
            if not os.path.exists(path) and os.path.exists('tools.json'):
                path = 'tools.json'
            with open(path, 'r', encoding='utf-8') as f:
                self.tools = json.load(f)
        except Exception as e:
            # First run might not have tools, don't popup error yet, just log
            print(f"Could not load tools.json: {e}")
            self.tools = []
            self.status_var.set("Could not load tools.json (check app folder)")

    def load_profiles(self):
        try:
            path = self.profiles_path
            if not os.path.exists(path) and os.path.exists('merge_profiles.json'):
                path = 'merge_profiles.json'
            with open(path, 'r', encoding='utf-8') as f:
                self.profiles = json.load(f)
        except Exception:
            self.profiles = []

    def save_profiles_to_disk(self):
        try:
            with open(self.profiles_path, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save profiles: {e}")

    def create_widgets(self):
        padding = {'padx': 15, 'pady': 5}
        
        # Title
        header = ttk.Label(self.root, text="PDF to Excel Data Merger", font=("Helvetica", 16, "bold"))
        header.pack(pady=15)
        
        # 1. Profile Loader
        frame_profile = ttk.LabelFrame(self.root, text="1. Load Saved Configuration")
        frame_profile.pack(fill="x", **padding)
        
        h_frame = ttk.Frame(frame_profile)
        h_frame.pack(fill="x", padx=10, pady=5)
        
        profile_names = [p['name'] for p in self.profiles]
        self.profile_dropdown = SearchableDropdown(h_frame, textvariable=self.profile_var, items=profile_names, command=self.on_profile_select)
        self.profile_dropdown.pack(side="left", fill="x", expand=True)
        
        ttk.Button(h_frame, text="Delete Profile", command=self.delete_profile).pack(side="right", padx=(5,0))


        # 2. PDF Input (The Variable Part)
        frame_input = ttk.LabelFrame(self.root, text="2. Input PDF File")
        frame_input.pack(fill="x", **padding)
        
        inp_layout = ttk.Frame(frame_input)
        inp_layout.pack(fill="x", padx=10, pady=5)
        
        ttk.Entry(inp_layout, textvariable=self.selected_file).pack(side="left", fill="x", expand=True)
        ttk.Button(inp_layout, text="Browse...", command=self.browse_file).pack(side="right", padx=(5,0))


        # 3. Configuration (The Saved Part)
        frame_config = ttk.LabelFrame(self.root, text="3. Configuration Settings")
        frame_config.pack(fill="x", **padding)
        
        # A. Converter Tool
        c_frame = ttk.Frame(frame_config)
        c_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(c_frame, text="Converter Model:", width=15).pack(side="left")
        
        self.tool_dropdown = SearchableDropdown(c_frame, textvariable=self.tool_var, items=[], command=self.on_tool_change)
        self.tool_dropdown.pack(side="left", fill="x", expand=True)
        
        # Tool Management Buttons
        ttk.Button(c_frame, text="+", width=3, command=self.open_add_tool_window).pack(side="right", padx=1)
        ttk.Button(c_frame, text="Edit", width=4, command=self.open_edit_tool_window).pack(side="right", padx=1)
        
        # Description Label
        self.desc_label = ttk.Label(frame_config, text="Select a converter...", font=("Helvetica", 9, "italic"), wraplength=550)
        self.desc_label.pack(padx=10, pady=(0, 5), fill="x")

        # B. Excel Template
        e_frame = ttk.Frame(frame_config)
        e_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(e_frame, text="Excel Template:", width=15).pack(side="left")
        ttk.Entry(e_frame, textvariable=self.excel_file).pack(side="left", fill="x", expand=True)
        ttk.Button(e_frame, text="Browse", command=self.browse_excel).pack(side="right")

        # C. Columns
        col_frame = ttk.Frame(frame_config)
        col_frame.pack(fill="x", padx=10, pady=5)
        
        # PDF Cols
        p_col_f = ttk.Frame(col_frame)
        p_col_f.pack(fill="x", pady=2)
        ttk.Label(p_col_f, text="PDF Columns:", width=15).pack(side="left")
        ttk.Entry(p_col_f, textvariable=self.pdf_cols_var).pack(side="left", fill="x", expand=True)
        ttk.Label(p_col_f, text="(comma separated)").pack(side="right", padx=5)

        # Excel Cols
        e_col_f = ttk.Frame(col_frame)
        e_col_f.pack(fill="x", pady=2)
        ttk.Label(e_col_f, text="Excel Columns:", width=15).pack(side="left")
        ttk.Entry(e_col_f, textvariable=self.excel_cols_var).pack(side="left", fill="x", expand=True)
        ttk.Label(e_col_f, text="(comma separated)").pack(side="right", padx=5)

        # Save Config Button
        ttk.Button(frame_config, text="💾 Save Current Settings as Profile", command=self.save_new_profile).pack(anchor="e", padx=10, pady=10)

        self.refresh_combo_list()

        # 4. Action
        frame_run = ttk.Frame(self.root)
        frame_run.pack(fill="x", padx=padding['padx'], pady=15)
        
        self.btn_run = ttk.Button(frame_run, text="RUN MERGE PROCESS", command=self.run_merge_thread)
        self.btn_run.pack(fill="x", ipady=12)
        
        # Utilities
        ttk.Separator(self.root, orient='horizontal').pack(fill='x', pady=5)
        debug_frame = ttk.Frame(self.root)
        debug_frame.pack(fill="x", pady=5)
        ttk.Button(debug_frame, text="Tools: Convert PDF to CSV Only (No Merge)", command=self.run_conversion_thread).pack()

        # Status Bar
        self.lbl_status = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        self.lbl_status.pack(side="bottom", fill="x", ipady=5)

    def refresh_combo_list(self):
        # Sort tools alphabetically for easier navigation
        self.tools.sort(key=lambda x: x['name'])
        tool_names = [t['name'] for t in self.tools]
        self.tool_dropdown.update_items(tool_names)
        self.update_description()

    def on_profile_select(self, event):
        name = self.profile_var.get()
        if not name: return

        profile = next((p for p in self.profiles if p['name'] == name), None)
        if profile:
            self.tool_var.set(profile.get('converter', ''))
            self.excel_file.set(profile.get('excel_template', ''))
            self.pdf_cols_var.set(profile.get('pdf_cols', ''))
            self.excel_cols_var.set(profile.get('excel_cols', ''))
            
            # Update desc
            self.on_tool_change(None)
            self.status_var.set(f"Loaded profile: {name}")

    def save_new_profile(self):
        # Prompt for name
        current_data = {
            "converter": self.tool_var.get(),
            "excel_template": self.excel_file.get(),
            "pdf_cols": self.pdf_cols_var.get(),
            "excel_cols": self.excel_cols_var.get()
        }
        
        if not current_data['converter'] or not current_data['excel_template']:
            messagebox.showwarning("Incomplete", "Please fill in Converter, Excel Template, and Columns before saving.")
            return

        # Simple input dialog
        ask_win = tk.Toplevel(self.root)
        ask_win.title("Save Profile")
        ask_win.geometry("300x150")
        
        ttk.Label(ask_win, text="Profile Name:").pack(pady=10)
        name_var = tk.StringVar(value=self.profile_var.get())
        ttk.Entry(ask_win, textvariable=name_var).pack(pady=5, padx=20, fill="x")
        
        def do_save():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "Name required")
                return
            
            # Check overwrite
            existing = next((p for p in self.profiles if p['name'] == name), None)
            if existing:
                if not messagebox.askyesno("Overwrite", f"Profile '{name}' exists. Overwrite?"):
                    return
                # Update existing
                existing.update(current_data)
            else:
                # Create new
                new_p = {"name": name}
                new_p.update(current_data)
                self.profiles.append(new_p)
            
            self.save_profiles_to_disk()
            
            # Update dropdown
            profile_names = [p['name'] for p in self.profiles]
            self.profile_dropdown.update_items(profile_names)
            
            self.profile_var.set(name)
            messagebox.showinfo("Saved", f"Profile '{name}' saved successfully.")
            ask_win.destroy()
            
        ttk.Button(ask_win, text="Save", command=do_save).pack(pady=10)

    def delete_profile(self):
        name = self.profile_var.get()
        if not name: return
        
        if messagebox.askyesno("Delete", f"Delete profile '{name}'?"):
            self.profiles = [p for p in self.profiles if p['name'] != name]
            self.save_profiles_to_disk()
            
            # Update dropdown
            profile_names = [p['name'] for p in self.profiles]
            self.profile_dropdown.update_items(profile_names)
            self.profile_var.set('')
            messagebox.showinfo("Deleted", "Profile deleted.")

    def open_add_tool_window(self):
        self.open_tool_window(title="Add New Converter", mode="add")

    def open_edit_tool_window(self):
        current_name = self.tool_var.get()
        if not current_name:
            return
            
        tool = next((t for t in self.tools if t['name'] == current_name), None)
        if tool:
            self.open_tool_window(title=f"Edit {current_name}", mode="edit", tool_data=tool)

    def open_tool_window(self, title, mode, tool_data=None):
        top = tk.Toplevel(self.root)
        top.title(title)
        top.geometry("450x400")
        
        padding = {'padx': 10, 'pady': 5}
        
        # Name
        ttk.Label(top, text="Converter Name:").pack(anchor="w", **padding)
        entry_name = ttk.Entry(top)
        entry_name.pack(fill="x", **padding)
        if tool_data: entry_name.insert(0, tool_data['name'])
        
        # Category (Folder-like structure) - New Feature
        ttk.Label(top, text="Category (Optional, e.g. 'US Vendors'):").pack(anchor="w", **padding)
        entry_cat = ttk.Entry(top)
        entry_cat.pack(fill="x", **padding)
        if tool_data and 'category' in tool_data: entry_cat.insert(0, tool_data['category'])
        
        # Description
        ttk.Label(top, text="Description:").pack(anchor="w", **padding)
        entry_desc = ttk.Entry(top)
        entry_desc.pack(fill="x", **padding)
        if tool_data: entry_desc.insert(0, tool_data.get('description', ''))
        
        # Script
        ttk.Label(top, text="Python Script (.py):").pack(anchor="w", **padding)
        frame_script = ttk.Frame(top)
        frame_script.pack(fill="x", **padding)
        entry_script = ttk.Entry(frame_script)
        entry_script.pack(side="left", fill="x", expand=True)
        if tool_data: entry_script.insert(0, tool_data['script'])
        
        def browse_script():
            f = filedialog.askopenfilename(filetypes=[("Python Files", "*.py")])
            if f:
                entry_script.delete(0, tk.END)
                entry_script.insert(0, f)
        
        ttk.Button(frame_script, text="Browse", command=browse_script).pack(side="right", padx=(5,0))
        
        # Validator
        ttk.Label(top, text="Validator Script (Optional):").pack(anchor="w", **padding)
        frame_valid = ttk.Frame(top)
        frame_valid.pack(fill="x", **padding)
        entry_valid = ttk.Entry(frame_valid)
        entry_valid.pack(side="left", fill="x", expand=True)
        if tool_data: 
            entry_valid.insert(0, tool_data.get('validator', 'validate_output.py'))
        else:
            entry_valid.insert(0, "validate_output.py")

        def browse_valid():
            f = filedialog.askopenfilename(filetypes=[("Python Files", "*.py")])
            if f:
                entry_valid.delete(0, tk.END)
                entry_valid.insert(0, f)
        
        ttk.Button(frame_valid, text="Browse", command=browse_valid).pack(side="right", padx=(5,0))

        def save_tool():
            name = entry_name.get().strip()
            category = entry_cat.get().strip()
            source_script = entry_script.get().strip()
            desc = entry_desc.get().strip()
            validator = entry_valid.get().strip()
            
            if not name or not source_script:
                messagebox.showerror("Error", "Name and Script File are required.")
                return
            
            # Logic to verify script exists or copy it
            script_filename = os.path.basename(source_script)
            target_script = os.path.join(self.app_dir, script_filename)
            
            try:
                # Only copy if it's a new path and file exists (if editing, might be same)
                if os.path.exists(source_script) and os.path.abspath(source_script) != os.path.abspath(target_script):
                    shutil.copy2(source_script, target_script)
                elif not os.path.exists(target_script) and not os.path.exists(source_script):
                    # If editing and file wasn't changed but exists locally
                    if not os.path.exists(os.path.join(self.app_dir, source_script)):
                        messagebox.showerror("Error", f"Script file not found: {source_script}")
                        return
                    script_filename = source_script # Keep existing name if relative

                # Handle validator copy
                if validator and validator != "validate_output.py":
                    val_filename = os.path.basename(validator)
                    target_val = os.path.join(self.app_dir, val_filename)
                    if os.path.exists(validator) and os.path.abspath(validator) != os.path.abspath(target_val):
                        shutil.copy2(validator, target_val)
                    validator = val_filename
                
                new_entry = {
                    "name": name,
                    "category": category,
                    "script": script_filename,
                    "validator": validator,
                    "description": desc
                }
                
                if mode == "add":
                    self.tools.append(new_entry)
                else:
                    # Update existing
                    # Find index of tool being edited (using original name passed in tool_data)
                    for i, t in enumerate(self.tools):
                        if t['name'] == tool_data['name']:
                            self.tools[i] = new_entry
                            break
                            
                with open(self.tools_path, 'w', encoding='utf-8') as f:
                    json.dump(self.tools, f, indent=4)
                
                self.refresh_combo_list()
                self.tool_var.set(name)
                self.on_tool_change(None)
                
                messagebox.showinfo("Success", f"Tool '{name}' saved!")
                top.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save tool: {e}")

        # Delete Button for Edit Mode
        if mode == "edit":
            def delete_tool():
                if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{tool_data['name']}'?"):
                    self.tools = [t for t in self.tools if t['name'] != tool_data['name']]
                    with open(self.tools_path, 'w', encoding='utf-8') as f:
                        json.dump(self.tools, f, indent=4)
                    self.refresh_combo_list()
                    top.destroy()
            
            btn_frame = ttk.Frame(top)
            btn_frame.pack(pady=20, fill="x")
            ttk.Button(btn_frame, text="Delete Tool", command=delete_tool).pack(side="left", padx=10)
            ttk.Button(btn_frame, text="Save Changes", command=save_tool).pack(side="right", padx=10)
        else:
            ttk.Button(top, text="Add Converter", command=save_tool).pack(pady=20)

    def on_tool_change(self, event):
        self.update_description()

    def update_description(self):
        # Find selected tool
        name = self.tool_var.get()
        for t in self.tools:
            if t['name'] == name:
                self.desc_label.config(text=t.get('description', ''))
                break

    def browse_file(self):
        filetypes = (("PDF files", "*.pdf"), ("All files", "*.*"))
        initialdir = os.path.join(self.app_dir, "source")
        if not os.path.isdir(initialdir):
            initialdir = self.app_dir
        filename = filedialog.askopenfilename(title="Open PDF File", initialdir=initialdir, filetypes=filetypes)
        if filename:
            self.selected_file.set(filename)

    def browse_excel(self):
        filetypes = (("Excel files", "*.xlsx *.xls"), ("All files", "*.*"))
        initialdir = os.path.join(self.app_dir, "source")
        if not os.path.isdir(initialdir):
            initialdir = self.app_dir
        filename = filedialog.askopenfilename(title="Open Excel Template", initialdir=initialdir, filetypes=filetypes)
        if filename:
            self.excel_file.set(filename)

    def run_merge_thread(self):
        # Ask for save location first
        default_name = os.path.basename(self.excel_file.get()).replace(".xlsx", "_merged.xlsx")
        output_path = filedialog.asksaveasfilename(
            title="Save Merged Excel As",
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        
        if not output_path:
            return # User cancelled

        t = threading.Thread(target=self.run_merge, args=(output_path,))
        t.start()

    def run_merge(self, output_path):
        pdf_path = self.selected_file.get()
        excel_path = self.excel_file.get()
        tool_name = self.tool_var.get()
        
        pdf_cols_str = self.pdf_cols_var.get().strip()
        excel_cols_str = self.excel_cols_var.get().strip()
        
        if not pdf_path or not excel_path:
            messagebox.showwarning("Missing Files", "Please select both a PDF input and an Excel template.")
            return

        if not pdf_cols_str or not excel_cols_str:
            messagebox.showwarning("Missing Columns", "Please specify columns to map for both PDF and Excel.")
            return

        tool_config = next((t for t in self.tools if t['name'] == tool_name), None)
        if not tool_config:
            messagebox.showerror("Error", "Tool configuration not found.")
            return

        self.status_var.set("Merging data...")
        
        try:
            # Parse user input columns
            pdf_cols = [c.strip() for c in pdf_cols_str.split(',')]
            excel_cols = [c.strip() for c in excel_cols_str.split(',')]

            if len(pdf_cols) != len(excel_cols):
                messagebox.showerror("Error", f"Column count mismatch!\nPDF has {len(pdf_cols)} columns.\nExcel has {len(excel_cols)} columns.\nThey must match.")
                return

            import merge_to_excel
            importlib.reload(merge_to_excel) # Ensure fresh load

            script_path = tool_config['script']
            if script_path and not os.path.isabs(script_path):
                script_path = os.path.join(self.app_dir, script_path)
            
            final_output = merge_to_excel.process_merge(
                pdf_path, 
                script_path, 
                excel_path, 
                pdf_cols, 
                excel_cols,
                output_path=output_path
            )
            
            self.status_var.set(f"Success! Saved to {final_output}")
            messagebox.showinfo("Success", f"Merge complete!\nFile saved to:\n{final_output}")
            
        except Exception as e:
            self.status_var.set("Error during merge.")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

    def run_conversion_thread(self):
        # Run in separate thread to keep UI responsive
        t = threading.Thread(target=self.run_conversion)
        t.start()
        
    def run_conversion(self):
        input_path = self.selected_file.get()
        tool_name = self.tool_var.get()
        
        if not input_path:
            messagebox.showwarning("Warning", "Please select a file first.")
            return

        if not os.path.exists(input_path):
             messagebox.showerror("Error", "File not found.")
             return
             
        # Find tool config
        tool_config = next((t for t in self.tools if t['name'] == tool_name), None)
        if not tool_config:
            messagebox.showerror("Error", "Tool configuration not found.")
            return

        self.btn_run.config(state="disabled")
        self.status_var.set(f"Running {tool_name}...")
        
        try:
            # Dynamic Import of the Script
            script_file = tool_config['script']
            if script_file and not os.path.isabs(script_file):
                script_file = os.path.join(self.app_dir, script_file)
            
            # Load the module dynamically
            if not os.path.exists(script_file):
                 raise FileNotFoundError(f"Script {script_file} not found.")
                 
            spec = importlib.util.spec_from_file_location("dynamic_tool", script_file)
            module = importlib.util.module_from_spec(spec)
            sys.modules["dynamic_tool"] = module
            spec.loader.exec_module(module)
            
            # Check for standard interface
            if not hasattr(module, 'process_file'):
                raise AttributeError(f"Script {script_file} does not have a 'process_file(input_path, output_path)' function.")
            
            # Execute
            output_path = input_path.replace(".pdf", ".csv")
            success = module.process_file(input_path, output_path)
            
            if success:
                self.status_var.set("Conversion successful. Validating...")
                
                # Validation Step
                validator_script = tool_config.get('validator')

                if validator_script and not os.path.isabs(validator_script):
                    validator_script = os.path.join(self.app_dir, validator_script)

                if validator_script and os.path.exists(validator_script):
                     try:
                         v_spec = importlib.util.spec_from_file_location("dynamic_validator", validator_script)
                         v_module = importlib.util.module_from_spec(v_spec)
                         v_spec.loader.exec_module(v_module)
                         
                         if hasattr(v_module, 'validate_file'):
                             v_module.validate_file(output_path)
                         elif hasattr(v_module, 'validate_csvs'):
                             v_module.validate_csvs(output_path)
                             
                         self.status_var.set(f"Done! Saved to {os.path.basename(output_path)}")
                         messagebox.showinfo("Success", f"File converted successfully!\n\nSaved to: {output_path}\n\n(Check console for validation details)")
                     except Exception as ve:
                         self.status_var.set("Conversion OK, Validation Failed")
                         messagebox.showwarning("Warning", f"Conversion successful, but validation script crashed:\n{ve}")
                else:
                    # No validator configured
                    self.status_var.set("Conversion successful. No validation performed.")
                    messagebox.showinfo("Success", f"File converted successfully!\n\nSaved to: {output_path}\n\n⚠️ Note: No validation script was configured for this tool.")
            else:
                self.status_var.set("Conversion failed (no data returned).")
                messagebox.showerror("Error", "Conversion returned no data.")

        except Exception as e:
            self.status_var.set("Error Occurred")
            messagebox.showerror("Error", str(e))
            print(e)
            
        finally:
            self.btn_run.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    # Set icon if available (platform dependent, skipped for simplicity)
    app = ConverterApp(root)
    root.mainloop()

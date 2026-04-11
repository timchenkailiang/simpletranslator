"""Reusable Tkinter widgets."""

import tkinter as tk
from tkinter import ttk


class SearchableDropdown(ttk.Frame):
    """A web-style dropdown with type-to-search filtering."""

    def __init__(self, master, textvariable, items, command=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.textvariable = textvariable
        self.items = items
        self.command = command
        self.filtered_items = items

        # UI Components
        self.entry = ttk.Entry(self, textvariable=self.textvariable)
        self.entry.pack(side="left", fill="x", expand=True)

        self.btn = ttk.Button(self, text="▼", width=3,
                              command=self.toggle_full_list, takefocus=False)
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

        self.after(100, self._bind_toplevel)

    # ── Top-level window bindings ─────────────────────────────────────

    def _bind_toplevel(self):
        try:
            top = self.winfo_toplevel()
            top.bind("<Button-1>", self.on_toplevel_click, add="+")
            top.bind("<Configure>", self.on_window_move, add="+")
        except Exception:
            pass

    def on_toplevel_click(self, event):
        if not self.popup:
            return
        clicked_widget = event.widget
        try:
            if (str(clicked_widget).startswith(str(self)) or
                    str(clicked_widget).startswith(str(self.popup))):
                return
        except Exception:
            pass
        self.destroy_popup()

    def on_window_move(self, event):
        if self.popup and event.widget == self.winfo_toplevel():
            self.destroy_popup()

    # ── Public API ────────────────────────────────────────────────────

    def update_items(self, new_items):
        self.items = new_items
        self.filtered_items = new_items

    # ── Popup management ──────────────────────────────────────────────

    def toggle_full_list(self):
        if self.popup:
            self.destroy_popup()
        else:
            self.filtered_items = self.items
            self.show_popup()

    def on_click_entry(self, event):
        self.filter_items()
        self.show_popup()

    def on_key_release(self, event):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape'):
            return
        self.filter_items()
        self.show_popup()

    def filter_items(self):
        typed = self.textvariable.get()
        if typed == '':
            self.filtered_items = self.items
        else:
            self.filtered_items = [
                item for item in self.items
                if typed.lower() in item.lower()
            ]

    def show_popup(self):
        if not self.popup:
            self.popup = tk.Toplevel(self)
            try:
                self.popup.transient(self.winfo_toplevel())
            except Exception:
                pass
            self.popup.wm_overrideredirect(True)

            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height()
            w = self.entry.winfo_width() + self.btn.winfo_width()
            self.popup.geometry(f"{w}x150+{x}+{y}")

            frame = ttk.Frame(self.popup, relief="solid", borderwidth=1)
            frame.pack(fill="both", expand=True)

            self.listbox = tk.Listbox(frame, height=5, selectmode="single",
                                      highlightthickness=0, borderwidth=0)
            self.listbox.pack(side="left", fill="both", expand=True)

            scrollbar = ttk.Scrollbar(frame, orient="vertical",
                                      command=self.listbox.yview)
            scrollbar.pack(side="right", fill="y")
            self.listbox.config(yscrollcommand=scrollbar.set)

            self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)

        # Refresh content
        self.listbox.delete(0, tk.END)
        for item in self.filtered_items:
            self.listbox.insert(tk.END, item)

    def destroy_popup(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None
            self.listbox = None

    # ── Focus / selection handling ────────────────────────────────────

    def on_focus_out(self, event):
        self.after(200, self.check_focus)

    def check_focus(self):
        if self.popup:
            focused = self.winfo_toplevel().focus_get()
            if focused in [self.entry, self.btn, self.listbox]:
                return
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
            if event.keysym == 'Down':
                next_idx = 0
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
        self.entry.icursor(tk.END)
        if self.command:
            self.command(None)

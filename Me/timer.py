#!/usr/bin/env python3

# ==============================================================================
# Description:
# This script quickly starts a timer when you need it :)
#
# Author: Pablo Sanchez
# Date: 2025-10-08
# ==============================================================================

import tkinter as tk
from tkinter import ttk, messagebox


class TimerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Full Screen Timer")

        # Timer state
        self.total_seconds = 0
        self.remaining_seconds = 0
        self.running = False
        self.fullscreen = False
        self.after_id = None

        # Layout
        self.create_widgets()
        self.apply_style()

        # Make window reasonably big by default
        self.root.geometry("800x400")

    def create_widgets(self):
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Top: duration input
        input_frame = ttk.Frame(main)
        input_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        ttk.Label(input_frame, text="Hours").grid(row=0, column=0, padx=5)
        ttk.Label(input_frame, text="Minutes").grid(row=0, column=2, padx=5)
        ttk.Label(input_frame, text="Seconds").grid(row=0, column=4, padx=5)

        self.hours_var = tk.StringVar(value="0")
        self.minutes_var = tk.StringVar(value="25")
        self.seconds_var = tk.StringVar(value="0")

        self.hours_entry = ttk.Entry(input_frame, width=5, textvariable=self.hours_var, justify="center")
        self.minutes_entry = ttk.Entry(input_frame, width=5, textvariable=self.minutes_var, justify="center")
        self.seconds_entry = ttk.Entry(input_frame, width=5, textvariable=self.seconds_var, justify="center")

        self.hours_entry.grid(row=0, column=1, padx=5)
        self.minutes_entry.grid(row=0, column=3, padx=5)
        self.seconds_entry.grid(row=0, column=5, padx=5)

        presets = ttk.Frame(main)
        presets.pack(side=tk.TOP, pady=(0, 10))

        ttk.Label(presets, text="Presets (minutes):").grid(row=0, column=0, padx=5)
        for idx, minutes in enumerate((5, 10, 15, 20), start=1):
            btn = ttk.Button(presets, text=str(minutes), command=lambda m=minutes: self.set_preset_minutes(m))
            btn.grid(row=0, column=idx, padx=3)

        # Center: big timer label
        self.timer_label = ttk.Label(main, text="00:25:00", anchor="center")
        self.timer_label.pack(fill=tk.BOTH, expand=True, pady=10)

        # Bottom: controls
        controls = ttk.Frame(main)
        controls.pack(side=tk.TOP, pady=(10, 0))

        self.start_button = ttk.Button(controls, text="Start", command=self.start_timer)
        self.pause_button = ttk.Button(controls, text="Pause", command=self.pause_timer)
        self.reset_button = ttk.Button(controls, text="Reset", command=self.reset_timer)
        self.fullscreen_button = ttk.Button(controls, text="Toggle Full Screen (F11)", command=self.toggle_fullscreen)

        self.start_button.grid(row=0, column=0, padx=5)
        self.pause_button.grid(row=0, column=1, padx=5)
        self.reset_button.grid(row=0, column=2, padx=5)
        self.fullscreen_button.grid(row=0, column=3, padx=5)

        # Appearance controls
        appearance = ttk.Frame(main)
        appearance.pack(side=tk.TOP, pady=(10, 0))

        ttk.Label(appearance, text="Theme:").grid(row=0, column=0, padx=5)
        self.theme_var = tk.StringVar(value="dark")
        theme_combo = ttk.Combobox(appearance, textvariable=self.theme_var, values=["dark", "light"], width=6, state="readonly")
        theme_combo.grid(row=0, column=1, padx=5)
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_style())

        ttk.Label(appearance, text="Font size:").grid(row=0, column=2, padx=5)
        self.font_size_var = tk.StringVar(value="400")
        font_entry = ttk.Entry(appearance, width=5, textvariable=self.font_size_var, justify="center")
        font_entry.grid(row=0, column=3, padx=5)
        apply_font_button = ttk.Button(appearance, text="Apply", command=self.apply_font_size)
        apply_font_button.grid(row=0, column=4, padx=5)

        # Store non-timer widgets for fullscreen hide/show behavior
        self.fullscreen_hidden_widgets = []
        self.fullscreen_hidden_widgets_pack = {}
        for child in main.winfo_children():
            if child is not self.timer_label:
                self.fullscreen_hidden_widgets.append(child)
                self.fullscreen_hidden_widgets_pack[child] = child.pack_info()

        # Key bindings
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.exit_fullscreen())

        # Initialize display
        self.update_display(25 * 60)

    def apply_style(self):
        theme = self.theme_var.get()

        if theme == "dark":
            bg = "#000000"
            fg = "#00FF7F"  # spring green
        else:
            bg = "#FFFFFF"
            fg = "#000000"

        style = ttk.Style(self.root)
        # Use a theme that allows background changes
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.configure(bg=bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", padding=6)

        self.timer_label.configure(background=bg, foreground=fg)

    def apply_font_size(self):
        try:
            size = int(self.font_size_var.get())
            if size <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid font size", "Font size must be a positive integer.")
            return

        self.timer_label.configure(font=("Helvetica", size, "bold"))

    def parse_duration(self):
        try:
            h = int(self.hours_var.get() or 0)
            m = int(self.minutes_var.get() or 0)
            s = int(self.seconds_var.get() or 0)
        except ValueError:
            messagebox.showerror("Invalid time", "Hours, minutes, and seconds must be integers.")
            return None

        if h < 0 or m < 0 or s < 0:
            messagebox.showerror("Invalid time", "Time values cannot be negative.")
            return None

        total = h * 3600 + m * 60 + s
        if total <= 0:
            messagebox.showerror("Invalid time", "Total time must be greater than zero.")
            return None

        return total

    def set_preset_minutes(self, minutes):
        self.pause_timer()
        self.hours_var.set("0")
        self.minutes_var.set(str(minutes))
        self.seconds_var.set("0")
        total = minutes * 60
        self.total_seconds = total
        self.remaining_seconds = total
        self.update_display(total)

    def start_timer(self):
        if not self.running:
            if self.remaining_seconds <= 0:
                total = self.parse_duration()
                if total is None:
                    return
                self.total_seconds = total
                self.remaining_seconds = total
            self.running = True
            self.tick()

    def pause_timer(self):
        if self.running:
            self.running = False
            if self.after_id is not None:
                self.root.after_cancel(self.after_id)
                self.after_id = None

    def reset_timer(self):
        self.pause_timer()
        total = self.parse_duration()
        if total is None:
            return
        self.total_seconds = total
        self.remaining_seconds = total
        self.update_display(self.remaining_seconds)

    def tick(self):
        if not self.running:
            return

        if self.remaining_seconds <= 0:
            self.update_display(0)
            self.running = False
            self.after_id = None
            self.on_timer_finished()
            return

        self.update_display(self.remaining_seconds)
        self.remaining_seconds -= 1
        self.after_id = self.root.after(1000, self.tick)

    def update_display(self, seconds):
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        self.timer_label.config(text=f"{h:02d}:{m:02d}:{s:02d}")

    def on_timer_finished(self):
        # Simple notification; you can swap this for a sound if desired.
        try:
            self.root.bell()
        except tk.TclError:
            pass
        messagebox.showinfo("Time's up", "The timer has finished.")

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

        if self.fullscreen:
            for widget in getattr(self, "fullscreen_hidden_widgets", []):
                widget.pack_forget()
        else:
            for widget in getattr(self, "fullscreen_hidden_widgets", []):
                pack_opts = self.fullscreen_hidden_widgets_pack.get(widget, {})
                if pack_opts:
                    widget.pack(**pack_opts)

    def exit_fullscreen(self):
        if self.fullscreen:
            # Reuse toggle_fullscreen so widgets are restored as well
            self.toggle_fullscreen()


def main():
    root = tk.Tk()
    app = TimerApp(root)
    app.apply_font_size()
    root.mainloop()


if __name__ == "__main__":
    main()

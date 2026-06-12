#!/usr/bin/env python3
"""Graphical interface for the Minecraft -> Scrap Mechanic converter.

Run:        python3 gui.py
Package:    ./build_linux.sh  or  build_windows.bat  (PyInstaller)
"""

from __future__ import annotations

import queue
import shutil
import sys
import threading
import traceback
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError:  # pragma: no cover
    print(
        "tkinter is not available. On Debian/Ubuntu install it with:\n"
        "    sudo apt install python3-tk",
        file=sys.stderr,
    )
    raise

from conversion_settings import (
    BIOME_PRESETS,
    COLOR_DETAIL_STEPS,
    CONNECTOR_MATERIALS,
    WATER_MODES,
    ConversionSettings,
)
from install_paths import default_challenge_dir, detect_challenge_dirs, find_existing_challenges

# Estimation constants (measured from real conversions)
_PARTS_PER_OPAQUE_CELL = 310   # per shell layer
_PARTS_PER_TRANSPARENT_CELL = 250
_BYTES_PER_PART = 163


class _QueueWriter:
    """Redirect stdout/stderr lines into the GUI log queue."""

    def __init__(self, q):
        self.q = q
        self._buffer = ""

    def write(self, text):
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self.q.put(("log", line))

    def flush(self):
        pass


class ConverterGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Minecraft \u2192 Scrap Mechanic Converter")
        root.minsize(720, 640)

        self.queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.schematic_info = None  # (opaque, transparent, entities, dims)

        self._build_widgets()
        self._populate_output_dirs()
        self.root.after(100, self._poll_queue)

    # ------------------------------------------------------------------ UI

    def _build_widgets(self):
        pad = {"padx": 6, "pady": 3}
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)
        row = 0

        # --- Schematic input
        ttk.Label(main, text="Schematic:").grid(row=row, column=0, sticky="w", **pad)
        self.schematic_var = tk.StringVar()
        entry = ttk.Entry(main, textvariable=self.schematic_var)
        entry.grid(row=row, column=1, sticky="ew", **pad)
        ttk.Button(main, text="Browse...", command=self._pick_schematic).grid(
            row=row, column=2, **pad
        )
        row += 1

        self.schematic_info_var = tk.StringVar(value="No schematic loaded.")
        ttk.Label(main, textvariable=self.schematic_info_var, foreground="#555").grid(
            row=row, column=0, columnspan=3, sticky="w", **pad
        )
        row += 1

        # --- Map name / description
        ttk.Label(main, text="Map name:").grid(row=row, column=0, sticky="w", **pad)
        self.name_var = tk.StringVar(value="My Map")
        ttk.Entry(main, textvariable=self.name_var).grid(row=row, column=1, columnspan=2, sticky="ew", **pad)
        row += 1

        ttk.Label(main, text="Description:").grid(row=row, column=0, sticky="w", **pad)
        self.description_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.description_var).grid(row=row, column=1, columnspan=2, sticky="ew", **pad)
        row += 1

        # --- Output dir
        ttk.Label(main, text="Challenges folder:").grid(row=row, column=0, sticky="w", **pad)
        self.output_var = tk.StringVar()
        self.output_combo = ttk.Combobox(main, textvariable=self.output_var)
        self.output_combo.grid(row=row, column=1, sticky="ew", **pad)
        ttk.Button(main, text="Browse...", command=self._pick_output_dir).grid(row=row, column=2, **pad)
        row += 1

        # --- Settings notebook-ish frame
        settings = ttk.LabelFrame(main, text="Settings", padding=6)
        settings.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)
        for c in (1, 3):
            settings.columnconfigure(c, weight=1)
        row += 1
        srow = 0

        ttk.Label(settings, text="Biome colors:").grid(row=srow, column=0, sticky="w", **pad)
        self.biome_var = tk.StringVar(value="Plains")
        ttk.Combobox(
            settings, textvariable=self.biome_var,
            values=list(BIOME_PRESETS.keys()), state="readonly", width=16,
        ).grid(row=srow, column=1, sticky="w", **pad)

        ttk.Label(settings, text="Water:").grid(row=srow, column=2, sticky="w", **pad)
        self.water_var = tk.StringVar(value="glass")
        ttk.Combobox(
            settings, textvariable=self.water_var,
            values=list(WATER_MODES), state="readonly", width=10,
        ).grid(row=srow, column=3, sticky="w", **pad)
        srow += 1

        ttk.Label(settings, text="Wall thickness:").grid(row=srow, column=0, sticky="w", **pad)
        self.thickness_var = tk.IntVar(value=2)
        spin = ttk.Spinbox(
            settings, from_=1, to=6, textvariable=self.thickness_var, width=6,
            command=self._update_estimate,
        )
        spin.grid(row=srow, column=1, sticky="w", **pad)

        ttk.Label(settings, text="Color detail:").grid(row=srow, column=2, sticky="w", **pad)
        self.detail_var = tk.StringVar(value="Normal")
        ttk.Combobox(
            settings, textvariable=self.detail_var,
            values=list(COLOR_DETAIL_STEPS.keys()), state="readonly", width=10,
        ).grid(row=srow, column=3, sticky="w", **pad)
        srow += 1

        ttk.Label(settings, text="Max parts:").grid(row=srow, column=0, sticky="w", **pad)
        self.max_parts_var = tk.IntVar(value=320000)
        ttk.Spinbox(
            settings, from_=10000, to=1000000, increment=10000,
            textvariable=self.max_parts_var, width=10, command=self._update_estimate,
        ).grid(row=srow, column=1, sticky="w", **pad)

        ttk.Label(settings, text="Connector glass:").grid(row=srow, column=2, sticky="w", **pad)
        self.connector_var = tk.StringVar(value="Indestructible glass")
        ttk.Combobox(
            settings, textvariable=self.connector_var,
            values=list(CONNECTOR_MATERIALS.keys()), state="readonly", width=18,
        ).grid(row=srow, column=3, sticky="w", **pad)
        srow += 1

        ttk.Label(settings, text="Anchor pole height:").grid(row=srow, column=0, sticky="w", **pad)
        self.pole_height_var = tk.IntVar(value=32)
        ttk.Spinbox(
            settings, from_=1, to=128, textvariable=self.pole_height_var, width=6,
        ).grid(row=srow, column=1, sticky="w", **pad)
        srow += 1

        self.hollow_var = tk.BooleanVar(value=True)
        self.merge_var = tk.BooleanVar(value=True)
        self.connect_var = tk.BooleanVar(value=True)
        self.prefabs_var = tk.BooleanVar(value=False)
        self.entities_var = tk.BooleanVar(value=True)
        self.pole_var = tk.BooleanVar(value=True)
        checks = (
            ("Hollow structure", self.hollow_var),
            ("Merge voxels (fewer parts)", self.merge_var),
            ("Glass-weld floating parts", self.connect_var),
            ("Anchor pole (32-voxel glass pole)", self.pole_var),
            ("Paintings / entities", self.entities_var),
            ("Builder palette (spawns loose blocks!)", self.prefabs_var),
        )
        for i, (label, var) in enumerate(checks):
            ttk.Checkbutton(settings, text=label, variable=var).grid(
                row=srow + i // 2, column=(i % 2) * 2, columnspan=2, sticky="w", **pad
            )
        srow += (len(checks) + 1) // 2

        # --- Lights
        lights = ttk.LabelFrame(main, text="Light emission (glowstone, torches, lanterns, ...)", padding=6)
        lights.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)
        lights.columnconfigure(3, weight=1)
        row += 1

        self.lights_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            lights, text="Place real lamps on all 6 faces, symmetric from the center",
            variable=self.lights_var,
        ).grid(row=0, column=0, columnspan=4, sticky="w", **pad)

        ttk.Label(lights, text="Placement:").grid(row=1, column=0, sticky="w", **pad)
        self.light_mode_var = tk.StringVar(value="embed")
        ttk.Combobox(
            lights, textvariable=self.light_mode_var,
            values=["embed", "replace"], state="readonly", width=10,
        ).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(
            lights, text="embed = hidden inside the voxel (glitchweld), replace = cutout",
            foreground="#555",
        ).grid(row=1, column=2, columnspan=2, sticky="w", **pad)

        ttk.Label(lights, text="Lamps per face:").grid(row=2, column=0, sticky="w", **pad)
        self.lamps_per_face_var = tk.IntVar(value=1)
        ttk.Spinbox(lights, from_=1, to=9, textvariable=self.lamps_per_face_var, width=6).grid(
            row=2, column=1, sticky="w", **pad
        )

        ttk.Label(lights, text="Light strength:").grid(row=2, column=2, sticky="w", **pad)
        self.luminance_var = tk.IntVar(value=50)
        ttk.Scale(
            lights, from_=1, to=100, orient="horizontal",
            variable=self.luminance_var,
        ).grid(row=2, column=3, sticky="ew", **pad)

        # --- Size estimate
        est = ttk.LabelFrame(main, text="Estimated output size", padding=6)
        est.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)
        est.columnconfigure(0, weight=1)
        row += 1
        self.estimate_bar = ttk.Progressbar(est, maximum=1.0, value=0.0)
        self.estimate_bar.grid(row=0, column=0, sticky="ew", **pad)
        self.estimate_label_var = tk.StringVar(value="Load a schematic to see the estimate.")
        ttk.Label(est, textvariable=self.estimate_label_var).grid(row=1, column=0, sticky="w", **pad)

        # --- Convert + progress
        self.convert_button = ttk.Button(main, text="Convert", command=self._start_conversion)
        self.convert_button.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)
        row += 1

        self.progress_bar = ttk.Progressbar(main, maximum=1.0, value=0.0)
        self.progress_bar.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)
        row += 1
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(main, textvariable=self.status_var).grid(row=row, column=0, columnspan=3, sticky="w", **pad)
        row += 1

        # --- Log
        log_frame = ttk.LabelFrame(main, text="Log", padding=4)
        log_frame.grid(row=row, column=0, columnspan=3, sticky="nsew", **pad)
        main.rowconfigure(row, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="none")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        # React to setting changes that affect the estimate
        for var in (self.thickness_var, self.max_parts_var):
            var.trace_add("write", lambda *_: self._update_estimate())

    # ------------------------------------------------------------- helpers

    def _populate_output_dirs(self):
        detected = [str(p) for p in detect_challenge_dirs()]
        self.output_combo["values"] = detected
        default = default_challenge_dir()
        if default:
            self.output_var.set(str(default))
        elif detected:
            self.output_var.set(detected[0])

    def _pick_schematic(self):
        path = filedialog.askopenfilename(
            title="Choose a schematic",
            filetypes=[
                ("Schematics", "*.schem *.schematic *.json"),
                ("All files", "*"),
            ],
        )
        if not path:
            return
        self.schematic_var.set(path)
        name = Path(path).stem
        if self.name_var.get() in ("", "My Map"):
            self.name_var.set(name.replace("_", " ").title())
        self._load_schematic_info(path)

    def _pick_output_dir(self):
        path = filedialog.askdirectory(title="Choose the Challenges folder")
        if path:
            self.output_var.set(path)

    def _load_schematic_info(self, path):
        self.schematic_info_var.set("Reading schematic...")

        def work():
            try:
                from schematic_parser import parse_schematic_file
                from transparent_blocks import is_transparent_block

                data = parse_schematic_file(path)
                opaque = sum(
                    1 for b in data["blocks"] if not is_transparent_block(b["name"])
                )
                transparent = len(data["blocks"]) - opaque
                entities = len(data.get("entities") or [])
                dims = f"{data['width']}x{data['height']}x{data['length']}"
                self.queue.put(("info", (opaque, transparent, entities, dims)))
            except Exception as e:
                self.queue.put(("info_error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _update_estimate(self):
        if not self.schematic_info:
            return
        opaque, transparent, entities, dims = self.schematic_info
        try:
            thickness = max(1, int(self.thickness_var.get()))
            max_parts = max(1, int(self.max_parts_var.get()))
        except (tk.TclError, ValueError):
            return
        parts = int(
            opaque * _PARTS_PER_OPAQUE_CELL * thickness
            + transparent * _PARTS_PER_TRANSPARENT_CELL
        )
        mb = parts * _BYTES_PER_PART / (1024 * 1024)
        fraction = min(1.0, parts / max_parts)
        self.estimate_bar.configure(value=fraction)
        over = "  \u26a0 over limit!" if parts > max_parts else ""
        self.estimate_label_var.set(
            f"~{parts:,} parts, ~{mb:.1f} MB  ({fraction * 100:.0f}% of {max_parts:,} part limit){over}"
        )

    def _collect_settings(self) -> ConversionSettings:
        return ConversionSettings(
            biome=self.biome_var.get(),
            color_detail=self.detail_var.get(),
            water_mode=self.water_var.get(),
            wall_thickness=max(1, int(self.thickness_var.get())),
            hollow=self.hollow_var.get(),
            merge=self.merge_var.get(),
            connect_islands=self.connect_var.get(),
            lights_enabled=self.lights_var.get(),
            light_mode=self.light_mode_var.get(),
            lamps_per_face=max(1, int(self.lamps_per_face_var.get())),
            lamp_luminance=int(float(self.luminance_var.get())),
            anchor_pole=self.pole_var.get(),
            anchor_pole_height=max(1, int(self.pole_height_var.get())),
            connector_material=self.connector_var.get(),
            include_entities=self.entities_var.get(),
            include_prefabs=self.prefabs_var.get(),
            max_parts=max(1, int(self.max_parts_var.get())),
        )

    # ---------------------------------------------------------- conversion

    def _start_conversion(self):
        if self.worker and self.worker.is_alive():
            return
        schematic = self.schematic_var.get().strip()
        name = self.name_var.get().strip()
        output_dir = self.output_var.get().strip()

        if not schematic or not Path(schematic).is_file():
            messagebox.showerror("Missing schematic", "Please choose a schematic file.")
            return
        if not name:
            messagebox.showerror("Missing name", "Please enter a map name.")
            return
        if not output_dir:
            messagebox.showerror("Missing folder", "Please choose the Challenges output folder.")
            return
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Overwrite popup
        exact_name = False
        existing = find_existing_challenges(Path(output_dir), name)
        if existing:
            listing = "\n".join(f"  \u2022 {n}" for _, n in existing[:6])
            choice = messagebox.askyesnocancel(
                "Map already exists",
                f"A challenge map with this name already exists:\n{listing}\n\n"
                "Yes = overwrite it\nNo = keep both (auto-number the new map)\nCancel = abort",
            )
            if choice is None:
                return
            if choice:  # overwrite
                for folder, _ in existing:
                    shutil.rmtree(folder, ignore_errors=True)
                exact_name = True

        settings = self._collect_settings()
        self.convert_button.configure(state="disabled")
        self.progress_bar.configure(value=0.0)
        self.status_var.set("Converting...")
        self._log_clear()

        def work():
            import progress as progress_reporter

            progress_reporter.set_callback(
                lambda frac, msg: self.queue.put(("progress", (frac, msg)))
            )
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = _QueueWriter(self.queue)
            try:
                from convert import convert_schematic

                result = convert_schematic(
                    schematic_path=Path(schematic),
                    name=name,
                    output_dir=Path(output_dir),
                    description=self.description_var.get(),
                    hollow=settings.hollow,
                    merge=settings.merge,
                    connect_islands=settings.connect_islands,
                    settings=settings,
                    exact_name=exact_name,
                )
                self.queue.put(("done", str(result) if result else "Dry run finished."))
            except Exception as e:
                traceback.print_exc()
                self.queue.put(("error", str(e)))
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr
                progress_reporter.set_callback(None)

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    # ------------------------------------------------------------ queueing

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._log_line(payload)
                elif kind == "progress":
                    frac, msg = payload
                    self.progress_bar.configure(value=frac)
                    if msg:
                        self.status_var.set(msg)
                elif kind == "info":
                    self.schematic_info = payload
                    opaque, transparent, entities, dims = payload
                    self.schematic_info_var.set(
                        f"{dims} | {opaque} solid blocks, {transparent} partial/transparent, "
                        f"{entities} entities"
                    )
                    self._update_estimate()
                elif kind == "info_error":
                    self.schematic_info = None
                    self.schematic_info_var.set(f"Could not read schematic: {payload}")
                elif kind == "done":
                    self.progress_bar.configure(value=1.0)
                    self.status_var.set("Finished!")
                    self.convert_button.configure(state="normal")
                    messagebox.showinfo("Conversion finished", f"Map exported:\n{payload}")
                elif kind == "error":
                    self.status_var.set(f"Failed: {payload}")
                    self.convert_button.configure(state="normal")
                    messagebox.showerror("Conversion failed", payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _log_line(self, line):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _log_clear(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    ConverterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

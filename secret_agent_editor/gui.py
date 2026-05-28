from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageTk

from .bundle import GameBundle, Episode, load_game
from .constants import LEVEL_BYTES, LEVEL_H, LEVEL_W, ROW_BYTES, TILE
from .crypto import encrypt_secret_agent
from .catalog import CATEGORY_HELP, build_code_entries, category_groups, code_title
from .mapping import BACKGROUND_MAP, DEFAULT_BG, TILE_MAP, WORLD_MAP, describe_code
from .render import SecretAgentRenderer


CODE_ENTRIES = build_code_entries()
PICKER_GROUPS = category_groups()




class SecretAgentEditor:
    def __init__(self, start_path: Optional[Path] = None):
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.root = tk.Tk()
        self.root.title("Secret Agent RE Level Editor")
        self.root.geometry("1400x900")
        self.bundle: Optional[GameBundle] = None
        self.current_ep = 1
        self.current_level = 0
        self.zoom = tk.IntVar(value=2)
        self.show_grid = tk.BooleanVar(value=True)
        self.show_codes = tk.BooleanVar(value=False)
        self.show_unknown = tk.BooleanVar(value=True)
        self.show_bg = tk.BooleanVar(value=True)
        self.show_fg = tk.BooleanVar(value=True)
        self.paint_code = tk.StringVar(value="20")
        self.paint_layer = tk.StringVar(value="bg")
        self.picker_group = tk.StringVar(value="Used in current level")
        self.image_tk = None
        self.atlas_tk = None
        self.picker_tk = None
        self.picker_items: list[tuple[int, int, int, int, int]] = []  # code, x0, y0, x1, y1 in picker canvas
        self.selected_code: Optional[int] = None
        self._current_picker_codes: list[int] = []
        self._picker_cols = 1
        self._picker_resize_after = None
        self._ghost_tk = None
        self._ghost_cell: Optional[tuple[int, int]] = None
        self._last_base_size = (LEVEL_W * TILE, LEVEL_H * TILE)
        self._build_ui()
        if start_path:
            try:
                self.open_path(start_path)
            except Exception as exc:
                messagebox.showerror("Load failed", str(exc))

    def _build_ui(self) -> None:
        tk, ttk = self.tk, self.ttk
        top = ttk.Frame(self.root)
        top.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        ttk.Button(top, text="Open game_data folder/ZIP", command=self.open_dialog).pack(side=tk.LEFT)
        ttk.Label(top, text="Episode").pack(side=tk.LEFT, padx=(10, 2))
        self.ep_combo = ttk.Combobox(top, width=5, state="readonly")
        self.ep_combo.pack(side=tk.LEFT)
        self.ep_combo.bind("<<ComboboxSelected>>", self._on_ep)
        ttk.Label(top, text="Level").pack(side=tk.LEFT, padx=(10, 2))
        self.level_combo = ttk.Combobox(top, width=6, state="readonly")
        self.level_combo.pack(side=tk.LEFT)
        self.level_combo.bind("<<ComboboxSelected>>", self._on_level)

        ttk.Label(top, text="Zoom").pack(side=tk.LEFT, padx=(10, 2))
        self.zoom_spin = ttk.Spinbox(top, from_=1, to=8, width=3, textvariable=self.zoom, command=self.refresh)
        self.zoom_spin.pack(side=tk.LEFT)
        self.zoom_spin.bind("<Return>", lambda _e: self.refresh())
        self.zoom_spin.bind("<FocusOut>", lambda _e: self.refresh())

        ttk.Checkbutton(top, text="BG", variable=self.show_bg, command=self.refresh).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Checkbutton(top, text="FG *", variable=self.show_fg, command=self.refresh).pack(side=tk.LEFT)
        ttk.Checkbutton(top, text="grid", variable=self.show_grid, command=self.refresh).pack(side=tk.LEFT)
        ttk.Checkbutton(top, text="codes", variable=self.show_codes, command=self.refresh).pack(side=tk.LEFT)
        ttk.Checkbutton(top, text="unknown", variable=self.show_unknown, command=self.refresh).pack(side=tk.LEFT)
        ttk.Label(top, text="paint hex").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Entry(top, width=4, textvariable=self.paint_code).pack(side=tk.LEFT)
        ttk.Radiobutton(top, text="BG", variable=self.paint_layer, value="bg").pack(side=tk.LEFT)
        ttk.Radiobutton(top, text="FG", variable=self.paint_layer, value="fg").pack(side=tk.LEFT)
        ttk.Button(top, text="Save SAM?03.GFX", command=self.save_levels).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(top, text="Export PNG", command=self.export_png).pack(side=tk.LEFT, padx=(6, 0))

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        level_tab = ttk.Frame(self.notebook)
        atlas_tab = ttk.Frame(self.notebook)
        self.notebook.add(level_tab, text="Level editor")
        self.notebook.add(atlas_tab, text="Raw tile atlas")

        paned = ttk.Panedwindow(level_tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(paned)
        right = ttk.Frame(paned, width=360)
        paned.add(left, weight=5)
        paned.add(right, weight=1)

        canvas_frame = ttk.Frame(left)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_frame, bg="black", width=LEVEL_W * TILE * 2, height=LEVEL_H * TILE * 2)
        yscroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        xscroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self._on_level_motion)
        self.canvas.bind("<Leave>", lambda _e: self._clear_ghost())
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_wheel)
        self.canvas.bind("<Control-Button-4>", lambda _e: self._zoom_delta(1))
        self.canvas.bind("<Control-Button-5>", lambda _e: self._zoom_delta(-1))
        self.status = ttk.Label(left, text="Open a Secret Agent game_data folder or ZIP.")
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_picker(right)
        self._build_atlas_tab(atlas_tab)

    def _build_picker(self, parent) -> None:
        tk, ttk = self.tk, self.ttk
        ttk.Label(parent, text="Code picker", font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, padx=6, pady=(6, 0))
        ttk.Label(
            parent,
            text="Pick map codes. Groups are source-derived from Camoto/SAMLEV mapping: specials, composites, world-map table and tileset banks.",
            wraplength=350,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=6, pady=(2, 6))

        group_row = ttk.Frame(parent)
        group_row.pack(fill=tk.X, padx=6)
        ttk.Label(group_row, text="Category").pack(side=tk.LEFT)
        self.picker_group_combo = ttk.Combobox(group_row, state="readonly", textvariable=self.picker_group, values=list(PICKER_GROUPS), width=30)
        self.picker_group_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        self.picker_group_combo.bind("<<ComboboxSelected>>", lambda _e: self._populate_picker())

        help_text = CATEGORY_HELP.get(self.picker_group.get(), "")
        self.picker_help = ttk.Label(parent, text=help_text, wraplength=350, justify=tk.LEFT)
        self.picker_help.pack(fill=tk.X, padx=6, pady=(4, 4))

        atlas_frame = ttk.Frame(parent)
        atlas_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.picker_canvas = tk.Canvas(atlas_frame, bg="#101010", width=350, height=460, highlightthickness=1, highlightbackground="#555")
        picker_y = ttk.Scrollbar(atlas_frame, orient=tk.VERTICAL, command=self.picker_canvas.yview)
        self.picker_canvas.configure(yscrollcommand=picker_y.set)
        self.picker_canvas.grid(row=0, column=0, sticky="nsew")
        picker_y.grid(row=0, column=1, sticky="ns")
        atlas_frame.rowconfigure(0, weight=1)
        atlas_frame.columnconfigure(0, weight=1)
        self.picker_canvas.bind("<Button-1>", self._on_picker_canvas_click)
        self.picker_canvas.bind("<Motion>", self._on_picker_motion)
        self.picker_canvas.bind("<Configure>", self._on_picker_configure)

        detail = ttk.LabelFrame(parent, text="Selected code details")
        detail.pack(fill=tk.X, padx=6, pady=(0, 6))
        self.picker_preview = tk.Canvas(detail, width=144, height=96, bg="black")
        self.picker_preview.pack(side=tk.LEFT, padx=6, pady=6)
        self.picker_info = ttk.Label(detail, text="No code selected.", wraplength=190, justify=tk.LEFT)
        self.picker_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6), pady=6)

    def _build_atlas_tab(self, parent) -> None:
        tk, ttk = self.tk, self.ttk
        row = ttk.Frame(parent)
        row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        ttk.Label(row, text="Raw SAM?01.GFX tile atlas. Use this for RE/inspection; level painting should normally use the picker tab.").pack(side=tk.LEFT)
        atlas_frame = ttk.Frame(parent)
        atlas_frame.pack(fill=tk.BOTH, expand=True)
        self.atlas_canvas = tk.Canvas(atlas_frame, bg="black", width=900, height=700)
        atlas_y = ttk.Scrollbar(atlas_frame, orient=tk.VERTICAL, command=self.atlas_canvas.yview)
        atlas_x = ttk.Scrollbar(atlas_frame, orient=tk.HORIZONTAL, command=self.atlas_canvas.xview)
        self.atlas_canvas.configure(yscrollcommand=atlas_y.set, xscrollcommand=atlas_x.set)
        self.atlas_canvas.grid(row=0, column=0, sticky="nsew")
        atlas_y.grid(row=0, column=1, sticky="ns")
        atlas_x.grid(row=1, column=0, sticky="ew")
        atlas_frame.rowconfigure(0, weight=1)
        atlas_frame.columnconfigure(0, weight=1)

    def open_dialog(self) -> None:
        p = self.filedialog.askopenfilename(title="Open game_data ZIP", filetypes=[("ZIP", "*.zip"), ("All files", "*.*")])
        if not p:
            p = self.filedialog.askdirectory(title="Open game_data folder")
        if p:
            self.open_path(Path(p))

    def open_path(self, path: Path) -> None:
        if self.bundle:
            self.bundle.cleanup()
        self.bundle = load_game(path)
        eps = sorted(self.bundle.episodes)
        self.current_ep = eps[0]
        self.ep_combo["values"] = [str(e) for e in eps]
        self.ep_combo.set(str(self.current_ep))
        self._populate_levels()
        self._refresh_picker_groups()
        self._populate_picker()
        self.refresh()

    def _populate_levels(self) -> None:
        ep = self._ep()
        self.level_combo["values"] = [str(i) for i in range(len(ep.levels))]
        self.current_level = 0
        self.level_combo.set("0")

    def _refresh_picker_groups(self) -> None:
        """Refresh category combo after a game is loaded.

        Static source-derived groups already omit empty banks in catalog.py.
        This method also keeps the current selection valid and adds the dynamic
        current-level group only while a bundle is open.
        """
        if not hasattr(self, "picker_group_combo"):
            return
        values = list(PICKER_GROUPS)
        self.picker_group_combo["values"] = values
        if self.picker_group.get() not in values:
            self.picker_group.set(values[0] if values else "")

    def _current_level_used_codes(self) -> list[int]:
        if not self.bundle:
            return []
        info = self._ep().levels[self.current_level]
        SecretAgentRenderer.build_layout(info)
        found: set[int] = set()
        for y in range(LEVEL_H):
            for rr in (info.bg_raw_for_y[y], info.fg_raw_for_y[y]):
                if rr is None:
                    continue
                row = info.raw[rr * ROW_BYTES:rr * ROW_BYTES + LEVEL_W]
                for code in row:
                    if code not in (0, 0x20):
                        found.add(code)
        return sorted(found)

    def _populate_picker(self) -> None:
        if not hasattr(self, "picker_canvas"):
            return
        group = self.picker_group.get()
        if group == "Used in current level":
            codes = self._current_level_used_codes()
        else:
            codes = PICKER_GROUPS.get(group, [])
        self.picker_help.config(text=CATEGORY_HELP.get(group, "Codes used by the currently selected level."))
        self._draw_picker_atlas(codes)
        if self.selected_code in codes:
            self._draw_picker_preview(self.selected_code)
        else:
            self.selected_code = None
            self.picker_preview.delete("all")
            self.picker_info.config(text="No code selected.")

    def _mapping_for_picker_group(self):
        return WORLD_MAP if self.picker_group.get() == "World map codes" else TILE_MAP

    def _make_code_preview_image(self, code: int, *, scale: int = 2, cell_px: int = 56, bg=(16, 16, 16, 255)) -> Image.Image:
        ep = self._ep()
        mapping = self._mapping_for_picker_group()
        refs = mapping.get(code, [])
        img = Image.new("RGBA", (cell_px, cell_px), bg)
        if not refs:
            draw = ImageDraw.Draw(img)
            draw.rectangle((1, 1, cell_px - 2, cell_px - 2), outline=(255, 0, 255, 255))
            draw.text((4, 4), f"{code:02X}", fill=(255, 255, 0, 255))
            return img
        min_rx = min(rx for rx, _ry, _b, _t in refs)
        max_rx = max(rx for rx, _ry, _b, _t in refs)
        min_ry = min(ry for _rx, ry, _b, _t in refs)
        max_ry = max(ry for _rx, ry, _b, _t in refs)
        w = (max_rx - min_rx + 1) * TILE
        h = (max_ry - min_ry + 1) * TILE
        sprite = Image.new("RGBA", (max(TILE, w), max(TILE, h)), (0, 0, 0, 0))
        for rx, ry, bank, tile_no in refs:
            tile = ep.tiles16.get(bank, tile_no)
            if tile:
                sprite.alpha_composite(tile, ((rx - min_rx) * TILE, (ry - min_ry) * TILE))
        # Fit with nearest-neighbour scaling so multi-tile structures still fit
        # into one picker cell while remaining recognizable.
        target = min(cell_px - 10, max(16, min(sprite.width * scale, sprite.height * scale)))
        factor = min((cell_px - 10) / max(1, sprite.width), (cell_px - 18) / max(1, sprite.height))
        factor = max(1, min(scale, int(factor))) if factor >= 1 else factor
        nw = max(1, int(sprite.width * factor))
        nh = max(1, int(sprite.height * factor))
        sprite = sprite.resize((nw, nh), Image.Resampling.NEAREST)
        img.alpha_composite(sprite, ((cell_px - nw) // 2, (cell_px - nh) // 2 - 2))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, cell_px - 1, cell_px - 1), outline=(70, 70, 70, 255))
        return img

    def _draw_picker_atlas(self, codes: list[int]) -> None:
        if not self.bundle:
            return
        self._current_picker_codes = list(codes)
        cell = 72
        thumb = 56
        canvas_w = max(1, self.picker_canvas.winfo_width() - 4)
        cols = max(1, canvas_w // cell)
        self._picker_cols = cols
        rows = max(1, (len(codes) + cols - 1) // cols)
        w = max(canvas_w, cols * cell)
        h = rows * cell
        atlas = Image.new("RGBA", (w, h), (16, 16, 16, 255))
        draw = ImageDraw.Draw(atlas)
        self.picker_items = []
        for i, code in enumerate(codes):
            col = i % cols
            row = i // cols
            x = col * cell
            y = row * cell
            preview = self._make_code_preview_image(code, cell_px=thumb)
            atlas.alpha_composite(preview, (x + 8, y + 4))
            label = f"{code:02X}"
            draw.rectangle((x + 8, y + 4, x + 8 + thumb - 1, y + 4 + thumb - 1), outline=(80, 80, 80, 255))
            if self.selected_code == code:
                draw.rectangle((x + 5, y + 1, x + 8 + thumb + 2, y + 4 + thumb + 2), outline=(255, 255, 0, 255), width=2)
            draw.text((x + 10, y + thumb + 5), label, fill=(230, 230, 230, 255))
            self.picker_items.append((code, x, y, x + cell, y + cell))
        if not codes:
            draw.text((8, 8), "No codes in this group.", fill=(220, 220, 220, 255))
        self.picker_tk = ImageTk.PhotoImage(atlas)
        self.picker_canvas.config(scrollregion=(0, 0, w, h))
        self.picker_canvas.delete("all")
        self.picker_canvas.create_image(0, 0, image=self.picker_tk, anchor="nw")

    def _on_picker_configure(self, _event=None) -> None:
        # Reflow the image atlas to the new panel width.  Debounce so dragging
        # the splitter/window does not redraw hundreds of times per second.
        if not hasattr(self, "picker_canvas"):
            return
        if self._picker_resize_after is not None:
            self.root.after_cancel(self._picker_resize_after)
        self._picker_resize_after = self.root.after(80, self._redraw_current_picker)

    def _redraw_current_picker(self) -> None:
        self._picker_resize_after = None
        if self.bundle:
            self._draw_picker_atlas(self._current_picker_codes)

    def _code_at_picker_pos(self, event) -> Optional[int]:
        cx = self.picker_canvas.canvasx(event.x)
        cy = self.picker_canvas.canvasy(event.y)
        for code, x0, y0, x1, y1 in self.picker_items:
            if x0 <= cx < x1 and y0 <= cy < y1:
                return code
        return None

    def _on_picker_canvas_click(self, event) -> None:
        code = self._code_at_picker_pos(event)
        if code is None:
            return
        self.selected_code = code
        self.paint_code.set(f"{code:02X}")
        self._draw_picker_preview(code)
        # Redraw just to move the yellow selection frame.
        if self.picker_group.get() == "Used in current level":
            codes = self._current_level_used_codes()
        else:
            codes = PICKER_GROUPS.get(self.picker_group.get(), [])
        self._draw_picker_atlas(codes)

    def _on_picker_motion(self, event) -> None:
        code = self._code_at_picker_pos(event)
        self.picker_canvas.configure(cursor="hand2" if code is not None else "")

    def _draw_picker_preview(self, code: int) -> None:
        if not self.bundle:
            return
        mapping = self._mapping_for_picker_group()
        refs = mapping.get(code, [])
        img = Image.new("RGBA", (144, 96), (0, 0, 0, 255))
        preview = self._make_code_preview_image(code, cell_px=88, bg=(0, 0, 0, 255))
        img.alpha_composite(preview, (28, 4))
        draw = ImageDraw.Draw(img)
        draw.rectangle((28, 4, 28 + 87, 4 + 87), outline=(255, 255, 0, 255))
        self.picker_preview_tk = ImageTk.PhotoImage(img)
        self.picker_preview.delete("all")
        self.picker_preview.create_image(0, 0, image=self.picker_preview_tk, anchor="nw")
        entry = CODE_ENTRIES.get(code)
        title = entry.title if entry else code_title(code)
        category = entry.category if entry else self.picker_group.get()
        ref_text = ", ".join(f"{rx:+d},{ry:+d}:B{b}:T{t}" for rx, ry, b, t in refs) or "unmapped"
        self.picker_info.config(
            text=(
                f"0x{code:02X} / {code}\n"
                f"{title}\n"
                f"Category: {category}\n"
                f"Basis: {getattr(entry, 'basis', '') if entry else 'current picker group'}\n"
                f"Refs: {ref_text}\n"
                f"Hold Shift to preview placement. Shift+click paints. Right-click deletes on active layer."
            )
        )

    def _on_ep(self, _event=None) -> None:
        self.current_ep = int(self.ep_combo.get())
        self._populate_levels()
        self._populate_picker()
        self.refresh()

    def _on_level(self, _event=None) -> None:
        self.current_level = int(self.level_combo.get())
        self._populate_picker()
        self.refresh()

    def _ep(self) -> Episode:
        assert self.bundle is not None
        return self.bundle.episodes[self.current_ep]

    def _safe_zoom(self) -> int:
        try:
            return max(1, min(8, int(self.zoom.get())))
        except Exception:
            self.zoom.set(1)
            return 1

    def refresh(self) -> None:
        if not self.bundle:
            return
        ep = self._ep()
        z = self._safe_zoom()
        renderer = SecretAgentRenderer(ep)
        # Render only the game pixels.  Editor overlays are drawn as Canvas items
        # afterwards so their line widths/text do not get scaled into chunky pixels.
        img = renderer.render(
            self.current_level,
            zoom=z,
            show_codes=False,
            show_unknown=False,
            show_bg=self.show_bg.get(),
            show_fg=self.show_fg.get(),
        )
        self._last_base_size = (img.width, img.height)
        self.image_tk = ImageTk.PhotoImage(img)
        self.canvas.config(scrollregion=(0, 0, img.width, img.height))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.image_tk, anchor="nw", tags=("level",))
        self._draw_level_overlays()
        info = ep.levels[self.current_level]
        tile_count = len(ep.tiles16.banks[0]) if ep.tiles16.banks else 0
        self.status.config(text=f"EP{ep.number} level {self.current_level}: bg={info.bg_code}, zoom={z}x, levels={len(ep.levels)}, banks={len(ep.tiles16.banks)}x{tile_count}")
        self._draw_atlas()
        if hasattr(self, "picker_group") and self.picker_group.get() == "Used in current level":
            self._populate_picker()

    def _draw_level_overlays(self) -> None:
        if not self.bundle:
            return
        ep = self._ep()
        info = ep.levels[self.current_level]
        SecretAgentRenderer.build_layout(info)
        z = self._safe_zoom()
        cell = TILE * z
        mapping = WORLD_MAP if self.current_level == 0 else TILE_MAP

        if self.show_grid.get():
            for x in range(LEVEL_W + 1):
                px = x * cell
                self.canvas.create_line(px, 0, px, LEVEL_H * cell, fill="#333333", width=1, tags=("overlay", "grid"))
            for y in range(LEVEL_H + 1):
                py = y * cell
                self.canvas.create_line(0, py, LEVEL_W * cell, py, fill="#333333", width=1, tags=("overlay", "grid"))

        if self.show_unknown.get() or self.show_codes.get():
            for y in range(LEVEL_H):
                # BG row overlays
                raw_row = info.bg_raw_for_y[y]
                if raw_row is not None:
                    row = info.raw[raw_row * ROW_BYTES:raw_row * ROW_BYTES + LEVEL_W]
                    for x, code in enumerate(row):
                        if code in (0, 0x20):
                            continue
                        if self.show_unknown.get() and code not in mapping and code not in (0x35, 0x36, 0x37):
                            self._draw_unknown_box(x, y, code, prefix="")
                        if self.show_codes.get():
                            self.canvas.create_text(x * cell + 2, y * cell + 2, text=f"{code:02X}", fill="white", anchor="nw", font=("TkFixedFont", 8), tags=("overlay", "codes"))
                # FG star row overlays
                fg_row = info.fg_raw_for_y[y]
                if fg_row is not None:
                    row = info.raw[fg_row * ROW_BYTES:fg_row * ROW_BYTES + LEVEL_W]
                    for x, code in enumerate(row):
                        if x == 0 or code in (0, 0x20):
                            continue
                        if self.show_unknown.get() and code not in mapping and code not in (0x35, 0x36, 0x37):
                            self._draw_unknown_box(x, y, code, prefix="*")
                        if self.show_codes.get():
                            self.canvas.create_text(x * cell + 2, y * cell + 11, text=f"*{code:02X}", fill="yellow", anchor="nw", font=("TkFixedFont", 8), tags=("overlay", "codes"))

    def _draw_unknown_box(self, x: int, y: int, code: int, *, prefix: str) -> None:
        z = self._safe_zoom()
        cell = TILE * z
        x0, y0 = x * cell, y * cell
        self.canvas.create_rectangle(x0 + 2, y0 + 2, x0 + cell - 3, y0 + cell - 3, outline="#ff00ff", width=2, tags=("overlay", "unknown"))
        self.canvas.create_text(x0 + 4, y0 + 4, text=f"{prefix}{code:02X}", fill="#ffff00", anchor="nw", font=("TkFixedFont", 8), tags=("overlay", "unknown"))

    def _draw_atlas(self) -> None:
        if not self.bundle:
            return
        ep = self._ep()
        cols = 10
        label_h = 12
        atlas_w = cols * TILE * 2
        rows = len(ep.tiles16.banks) * 5
        atlas = Image.new("RGBA", (atlas_w, rows * TILE * 2 + len(ep.tiles16.banks) * label_h), (0, 0, 0, 255))
        draw = ImageDraw.Draw(atlas)
        y_offset = 0
        for b, bank in enumerate(ep.tiles16.banks):
            draw.text((2, y_offset), f"Bank {b}", fill=(255, 255, 0, 255))
            y_offset += label_h
            for t, tile in enumerate(bank):
                x = (t % cols) * TILE * 2
                y = y_offset + (t // cols) * TILE * 2
                atlas.alpha_composite(tile.resize((TILE * 2, TILE * 2), Image.Resampling.NEAREST), (x, y))
                draw.text((x + 1, y + 1), str(t), fill=(255, 255, 255, 255))
            y_offset += 5 * TILE * 2
        self.atlas_tk = ImageTk.PhotoImage(atlas)
        self.atlas_canvas.config(scrollregion=(0, 0, atlas.width, atlas.height))
        self.atlas_canvas.delete("all")
        self.atlas_canvas.create_image(0, 0, image=self.atlas_tk, anchor="nw")

    def _event_to_cell(self, event) -> tuple[int, int]:
        z = self._safe_zoom()
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        return int(cx // (TILE * z)), int(cy // (TILE * z))

    def on_click(self, event) -> None:
        if not self.bundle:
            return
        x, y = self._event_to_cell(event)
        if not (0 <= x < LEVEL_W and 0 <= y < LEVEL_H):
            return
        ep = self._ep()
        info = ep.levels[self.current_level]
        SecretAgentRenderer.build_layout(info)
        bg_rr = info.bg_raw_for_y[y]
        fg_rr = info.fg_raw_for_y[y]
        mapping = WORLD_MAP if self.current_level == 0 else TILE_MAP
        parts = [f"cell {x},{y}"]
        if bg_rr is not None:
            code = info.raw[bg_rr * ROW_BYTES + x]
            parts.append(f"BG raw_row={bg_rr} code=0x{code:02X}/{code} -> {describe_code(code, mapping, info.bg_code)}")
        if fg_rr is not None:
            code = info.raw[fg_rr * ROW_BYTES + x]
            parts.append(f"FG raw_row={fg_rr} code=0x{code:02X}/{code} -> {describe_code(code, mapping, info.bg_code)}")
        if event.state & 0x0001:
            self._paint_cell(info, ep, x, y, bg_rr, fg_rr, parts)
        self.status.config(text=" | ".join(parts))

    def _paint_cell(self, info, ep, x: int, y: int, bg_rr: Optional[int], fg_rr: Optional[int], parts: list[str]) -> None:
        try:
            val = int(self.paint_code.get(), 16) & 0xFF
            layer = self.paint_layer.get()
            raw_row = bg_rr if layer == "bg" else fg_rr
            if raw_row is None:
                parts.append(f"paint skipped: no {layer.upper()} raw row at this Y")
                return
            if layer == "fg" and x == 0:
                parts.append("paint skipped: x=0 is the '*' marker on FG rows")
                return
            info.raw[raw_row * ROW_BYTES + x] = val
            ep.level_plain[self.current_level * LEVEL_BYTES + raw_row * ROW_BYTES + x] = val
            parts.append(f"painted {layer.upper()}=0x{val:02X}")
            self.refresh()
            self._clear_ghost()
        except Exception as exc:
            parts.append(f"paint error: {exc}")

    def _on_level_motion(self, event) -> None:
        if not self.bundle:
            return
        if event.state & 0x0001:
            x, y = self._event_to_cell(event)
            self._draw_ghost(x, y)
        else:
            self._clear_ghost()

    def _clear_ghost(self) -> None:
        if hasattr(self, "canvas"):
            self.canvas.delete("ghost")
        self._ghost_tk = None
        self._ghost_cell = None

    def _make_code_stamp_image(self, code: int, *, alpha: int = 120) -> tuple[Image.Image, int, int]:
        """Return a semi-transparent stamp image plus min relative tile offset."""
        ep = self._ep()
        info = ep.levels[self.current_level]
        mapping = WORLD_MAP if self.current_level == 0 else TILE_MAP
        if code in (0, 0x20):
            img = Image.new("RGBA", (TILE, TILE), (255, 255, 255, 70))
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, TILE - 1, TILE - 1), outline=(255, 255, 0, 200))
            return img, 0, 0
        if code in (0x35, 0x36, 0x37):
            bank, tile_no = BACKGROUND_MAP.get(info.bg_code, DEFAULT_BG)
            tile = ep.tiles16.get(bank, tile_no + (code - 0x34))
            refs_img = tile.copy() if tile else Image.new("RGBA", (TILE, TILE), (255, 0, 255, 120))
            refs_img.putalpha(refs_img.getchannel("A").point(lambda a: min(a, alpha)))
            return refs_img, 0, 0
        refs = mapping.get(code, [])
        if not refs:
            img = Image.new("RGBA", (TILE, TILE), (255, 0, 255, 60))
            draw = ImageDraw.Draw(img)
            draw.rectangle((1, 1, TILE - 2, TILE - 2), outline=(255, 0, 255, 220))
            draw.text((2, 3), f"{code:02X}", fill=(255, 255, 0, 230))
            return img, 0, 0
        min_rx = min(rx for rx, _ry, _b, _t in refs)
        max_rx = max(rx for rx, _ry, _b, _t in refs)
        min_ry = min(ry for _rx, ry, _b, _t in refs)
        max_ry = max(ry for _rx, ry, _b, _t in refs)
        img = Image.new("RGBA", ((max_rx - min_rx + 1) * TILE, (max_ry - min_ry + 1) * TILE), (0, 0, 0, 0))
        for rx, ry, bank, tile_no in refs:
            tile = ep.tiles16.get(bank, tile_no)
            if tile:
                img.alpha_composite(tile, ((rx - min_rx) * TILE, (ry - min_ry) * TILE))
        img.putalpha(img.getchannel("A").point(lambda a: min(a, alpha)))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, img.width - 1, img.height - 1), outline=(255, 255, 0, 180))
        return img, min_rx, min_ry

    def _draw_ghost(self, x: int, y: int) -> None:
        self.canvas.delete("ghost")
        if not (0 <= x < LEVEL_W and 0 <= y < LEVEL_H):
            self._ghost_tk = None
            self._ghost_cell = None
            return
        try:
            code = int(self.paint_code.get(), 16) & 0xFF
        except Exception:
            return
        z = self._safe_zoom()
        stamp, min_rx, min_ry = self._make_code_stamp_image(code)
        if z != 1:
            stamp = stamp.resize((stamp.width * z, stamp.height * z), Image.Resampling.NEAREST)
        self._ghost_tk = ImageTk.PhotoImage(stamp)
        px = (x + min_rx) * TILE * z
        py = (y + min_ry) * TILE * z
        self.canvas.create_image(px, py, image=self._ghost_tk, anchor="nw", tags=("ghost",))
        self.canvas.create_rectangle(
            x * TILE * z,
            y * TILE * z,
            (x + 1) * TILE * z - 1,
            (y + 1) * TILE * z - 1,
            outline="#ffff00",
            width=2,
            tags=("ghost",),
        )
        self._ghost_cell = (x, y)

    def on_right_click(self, event) -> None:
        if not self.bundle:
            return
        x, y = self._event_to_cell(event)
        if not (0 <= x < LEVEL_W and 0 <= y < LEVEL_H):
            return
        ep = self._ep()
        info = ep.levels[self.current_level]
        SecretAgentRenderer.build_layout(info)
        bg_rr = info.bg_raw_for_y[y]
        fg_rr = info.fg_raw_for_y[y]
        layer = self.paint_layer.get()
        raw_row = bg_rr if layer == "bg" else fg_rr
        if raw_row is None:
            self.status.config(text=f"delete skipped: no {layer.upper()} raw row at {x},{y}")
            return
        if layer == "fg" and x == 0:
            self.status.config(text="delete skipped: x=0 is the '*' marker on FG rows")
            return
        val = 0x20 if layer == "bg" else 0x00
        info.raw[raw_row * ROW_BYTES + x] = val
        ep.level_plain[self.current_level * LEVEL_BYTES + raw_row * ROW_BYTES + x] = val
        self.status.config(text=f"deleted {layer.upper()} cell {x},{y} -> 0x{val:02X}")
        self.refresh()

    def _on_ctrl_wheel(self, event) -> None:
        self._zoom_delta(1 if event.delta > 0 else -1)

    def _zoom_delta(self, delta: int) -> None:
        self.zoom.set(max(1, min(8, self._safe_zoom() + delta)))
        self.refresh()

    def save_levels(self) -> None:
        ep = self._ep()
        out = self.filedialog.asksaveasfilename(title="Save encrypted SAM?03.GFX", initialfile=f"SAM{ep.number}03.GFX")
        if not out:
            return
        Path(out).write_bytes(encrypt_secret_agent(bytes(ep.level_plain), row_key_reset=42))
        self.messagebox.showinfo("Saved", f"Saved {out}")

    def export_png(self) -> None:
        ep = self._ep()
        out = self.filedialog.asksaveasfilename(title="Export PNG", initialfile=f"sa_ep{ep.number}_level{self.current_level:02d}.png", defaultextension=".png")
        if not out:
            return
        img = SecretAgentRenderer(ep).render(
            self.current_level,
            zoom=self._safe_zoom(),
            show_codes=self.show_codes.get(),
            show_unknown=self.show_unknown.get(),
            show_bg=self.show_bg.get(),
            show_fg=self.show_fg.get(),
        )
        img.save(out)

    def run(self) -> None:
        self.root.mainloop()

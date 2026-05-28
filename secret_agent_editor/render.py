from __future__ import annotations

from typing import Dict, List, Optional

from PIL import Image, ImageDraw

from .bundle import Episode
from .constants import LEVEL_H, LEVEL_W, ROW_BYTES, ROWS_PER_LEVEL, TILE
from .levels import LevelInfo
from .mapping import BACKGROUND_MAP, DEFAULT_BG, DrawRef, TILE_MAP, WORLD_MAP


class SecretAgentRenderer:
    def __init__(self, episode: Episode):
        self.ep = episode

    def render(
        self,
        level_index: int,
        *,
        zoom: int = 1,
        show_codes: bool = False,
        show_unknown: bool = True,
        show_bg: bool = True,
        show_fg: bool = True,
    ) -> Image.Image:
        info = self.ep.levels[level_index]
        bg_tile_ref = BACKGROUND_MAP.get(info.bg_code, DEFAULT_BG)
        bg_tile = self.ep.tiles16.get(*bg_tile_ref) or Image.new("RGBA", (TILE, TILE), (0, 0, 0, 255))
        base_tile = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 255))
        base_tile.alpha_composite(bg_tile)
        if len(info.control) > 1:
            self._composite_control_overlay(base_tile, info.control[1], level_index)

        img = Image.new("RGBA", (LEVEL_W * TILE, LEVEL_H * TILE), (0, 0, 0, 255))
        for y in range(LEVEL_H):
            for x in range(LEVEL_W):
                img.alpha_composite(base_tile, (x * TILE, y * TILE))

        self.build_layout(info)
        for raw_row in range(2, ROWS_PER_LEVEL):
            row = info.raw[raw_row * ROW_BYTES:raw_row * ROW_BYTES + LEVEL_W]
            if not row:
                continue
            is_fg = row[0] == ord("*")
            if is_fg and not show_fg:
                continue
            if not is_fg and not show_bg:
                continue
            target_y = self.raw_to_visual_y(info, raw_row, is_fg)
            if target_y is None:
                continue
            mapping = WORLD_MAP if level_index == 0 else TILE_MAP
            for x, code in enumerate(row):
                if x == 0 and code == ord("*"):
                    continue
                self.draw_code(img, x, target_y, code, mapping, info.bg_code, show_unknown=show_unknown)

        if show_codes:
            self.draw_code_overlay(ImageDraw.Draw(img), info)
        if zoom != 1:
            img = img.resize((img.width * zoom, img.height * zoom), Image.Resampling.NEAREST)
        return img

    def _composite_control_overlay(self, base_tile: Image.Image, code: int, level_index: int) -> None:
        if code in (0, 0x20):
            return
        mapping = WORLD_MAP if level_index == 0 else TILE_MAP
        refs = mapping.get(code)
        if not refs:
            return
        chosen = next(((b, t) for rx, ry, b, t in refs if rx == 0 and ry == 0), None)
        if chosen is None:
            chosen = (refs[-1][2], refs[-1][3])
        tile = self.ep.tiles16.get(*chosen)
        if tile:
            base_tile.alpha_composite(tile)

    def draw_code(
        self,
        img: Image.Image,
        x: int,
        y: int,
        code: int,
        mapping: Dict[int, List[DrawRef]],
        bg_code: int,
        *,
        show_unknown: bool,
    ) -> None:
        if code in (0, 0x20):
            return
        if code in (0x35, 0x36, 0x37):
            bank, tile_no = BACKGROUND_MAP.get(bg_code, DEFAULT_BG)
            tile = self.ep.tiles16.get(bank, tile_no + (code - 0x34))
            if tile:
                img.alpha_composite(tile, (x * TILE, y * TILE))
            return
        refs = mapping.get(code)
        if not refs:
            if show_unknown:
                draw = ImageDraw.Draw(img)
                draw.rectangle([x * TILE + 1, y * TILE + 1, x * TILE + 14, y * TILE + 14], outline=(255, 0, 255, 255))
                draw.text((x * TILE + 2, y * TILE + 3), f"{code:02X}", fill=(255, 255, 0, 255))
            return
        for relx, rely, bank, tile_no in refs:
            tx = x + relx
            ty = y + rely
            if 0 <= tx < LEVEL_W and 0 <= ty < LEVEL_H:
                tile = self.ep.tiles16.get(bank, tile_no)
                if tile:
                    img.alpha_composite(tile, (tx * TILE, ty * TILE))

    def draw_code_overlay(self, draw: ImageDraw.ImageDraw, info: LevelInfo) -> None:
        self.build_layout(info)
        for y in range(LEVEL_H):
            raw_row = info.bg_raw_for_y[y]
            if raw_row is not None:
                row = info.raw[raw_row * ROW_BYTES:raw_row * ROW_BYTES + LEVEL_W]
                for x, code in enumerate(row):
                    if code not in (0, 0x20):
                        draw.text((x * TILE + 1, y * TILE + 1), f"{code:02X}", fill=(255, 255, 255, 255))
            fg = info.fg_raw_for_y[y]
            if fg is not None:
                row = info.raw[fg * ROW_BYTES:fg * ROW_BYTES + LEVEL_W]
                for x, code in enumerate(row):
                    if x != 0 and code not in (0, 0x20):
                        draw.text((x * TILE + 1, y * TILE + 9), f"*{code:02X}", fill=(255, 255, 0, 255))

    @staticmethod
    def build_layout(info: LevelInfo) -> None:
        info.bg_raw_for_y = [None] * LEVEL_H
        info.fg_raw_for_y = [None] * LEVEL_H
        visual_y = 0
        for raw_row in range(2, ROWS_PER_LEVEL):
            row = info.raw[raw_row * ROW_BYTES:raw_row * ROW_BYTES + LEVEL_W]
            if not row:
                continue
            if row[0] == ord("*"):
                target = visual_y - 1
                if 0 <= target < LEVEL_H:
                    info.fg_raw_for_y[target] = raw_row
            else:
                if 0 <= visual_y < LEVEL_H:
                    info.bg_raw_for_y[visual_y] = raw_row
                visual_y += 1

    @staticmethod
    def raw_to_visual_y(info: LevelInfo, raw_row: int, is_fg: bool) -> Optional[int]:
        SecretAgentRenderer.build_layout(info)
        rows = info.fg_raw_for_y if is_fg else info.bg_raw_for_y
        for y, rr in enumerate(rows):
            if rr == raw_row:
                return y
        return None

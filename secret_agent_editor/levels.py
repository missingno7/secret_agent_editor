from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .constants import LEVEL_BYTES, LEVEL_H, LEVEL_W, ROW_BYTES


@dataclass
class LevelInfo:
    index: int
    raw: bytearray
    bg_code: int
    control: bytes
    bg_raw_for_y: list[Optional[int]] = field(default_factory=lambda: [None] * LEVEL_H)
    fg_raw_for_y: list[Optional[int]] = field(default_factory=lambda: [None] * LEVEL_H)


def parse_background_code(row0: bytes) -> int:
    match = re.match(rb"\s*(\d+)", row0[:LEVEL_W])
    return int(match.group(1)) if match else 0


def parse_levels(level_plain: bytearray) -> list[LevelInfo]:
    levels: list[LevelInfo] = []
    for i in range(0, len(level_plain) // LEVEL_BYTES):
        raw = bytearray(level_plain[i * LEVEL_BYTES:(i + 1) * LEVEL_BYTES])
        control = bytes(raw[ROW_BYTES:ROW_BYTES + LEVEL_W])
        levels.append(LevelInfo(i, raw, parse_background_code(raw[:LEVEL_W]), control))
    return levels

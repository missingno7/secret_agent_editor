from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .crypto import decrypt_secret_agent
from .graphics import Tileset16, decode_prographx_16x16
from .levels import LevelInfo, parse_levels


@dataclass
class Episode:
    number: int
    tiles16: Tileset16
    level_plain: bytearray
    level_path: Path
    levels: list[LevelInfo]


@dataclass
class GameBundle:
    source: Path
    tempdir: Optional[tempfile.TemporaryDirectory]
    episodes: dict[int, Episode]

    def cleanup(self) -> None:
        if self.tempdir is not None:
            self.tempdir.cleanup()


def prepare_source(path: Path) -> tuple[Path, Optional[tempfile.TemporaryDirectory]]:
    """Return a folder containing lower-case SAM files.

    Input can be either a game_data directory or any ZIP containing game_data.
    Installer/SHR extraction is intentionally not supported here; this project
    expects final game files.
    """
    if path.is_dir():
        return path, None
    if zipfile.is_zipfile(path):
        tempdir = tempfile.TemporaryDirectory(prefix="sa_game_data_")
        root = Path(tempdir.name)
        with zipfile.ZipFile(path) as zf:
            zf.extractall(root)
        flat = root / "_flat"
        flat.mkdir()
        for p in root.rglob("*"):
            if p.is_file() and p.parent != flat:
                dest = flat / p.name.lower()
                if not dest.exists():
                    shutil.copy2(p, dest)
        return flat, tempdir
    raise ValueError(f"Unsupported input: {path}. Use a game_data folder or a ZIP containing game_data.")


def load_game(path: Path) -> GameBundle:
    source, tempdir = prepare_source(path)
    episodes: dict[int, Episode] = {}
    for ep in (1, 2, 3):
        gfx16 = find_file(source, f"sam{ep}01.gfx")
        levels = find_file(source, f"sam{ep}03.gfx")
        if not gfx16 or not levels:
            continue
        tiles16 = decode_prographx_16x16(gfx16.read_bytes())
        level_plain = decrypt_secret_agent(levels.read_bytes(), row_key_reset=42)
        episodes[ep] = Episode(ep, tiles16, level_plain, levels, parse_levels(level_plain))
    if not episodes:
        if tempdir:
            tempdir.cleanup()
        raise ValueError("No SAM?01.GFX + SAM?03.GFX episode pair found.")
    return GameBundle(source, tempdir, episodes)


def find_file(root: Path, name: str) -> Optional[Path]:
    wanted = name.lower()
    direct = root / wanted
    if direct.exists():
        return direct
    for p in root.rglob("*"):
        if p.is_file() and p.name.lower() == wanted:
            return p
    return None

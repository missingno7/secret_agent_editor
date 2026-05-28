from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional


def default_input() -> Optional[Path]:
    for name in ("game_data", "game_data.zip", "/mnt/data/game_data.zip"):
        p = Path(name)
        if p.exists():
            return p
    return None


def export_preview(path: Path, out: Path, episode: int, level: int, zoom: int, show_codes: bool, show_unknown: bool) -> None:
    from .bundle import load_game
    from .render import SecretAgentRenderer

    bundle = load_game(path)
    try:
        ep = bundle.episodes[episode]
        img = SecretAgentRenderer(ep).render(level, zoom=zoom, show_codes=show_codes, show_unknown=show_unknown)
        img.save(out)
        print(f"Exported {out} from EP{episode} level {level}")
    finally:
        bundle.cleanup()


def dump_codes(path: Path, episode: int, level: int) -> None:
    from .bundle import load_game
    from .constants import LEVEL_W, ROW_BYTES, ROWS_PER_LEVEL
    from .mapping import BACKGROUND_MAP, DEFAULT_BG, TILE_MAP, WORLD_MAP, describe_code

    bundle = load_game(path)
    try:
        ep = bundle.episodes[episode]
        info = ep.levels[level]
        mapping = WORLD_MAP if level == 0 else TILE_MAP
        seen = sorted({info.raw[r * ROW_BYTES + x] for r in range(2, ROWS_PER_LEVEL) for x in range(LEVEL_W)})
        print(f"EP{episode} level {level}: bg_code={info.bg_code} bg_tile={BACKGROUND_MAP.get(info.bg_code, DEFAULT_BG)}")
        for code in seen:
            if code in (0, 0x20, ord("*"), 0x0D, 0x0A):
                continue
            print(f"0x{code:02X} {code:3d}: {describe_code(code, mapping, info.bg_code)}")
    finally:
        bundle.cleanup()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Secret Agent game_data level editor")
    parser.add_argument("path", nargs="?", help="game_data folder or ZIP containing SAM101.GFX/SAM103.GFX etc.")
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--level", type=int, default=0)
    parser.add_argument("--export-preview", help="Export PNG and exit")
    parser.add_argument("--zoom", type=int, default=1)
    parser.add_argument("--codes", action="store_true", help="Draw raw map codes in preview")
    parser.add_argument("--no-unknown", action="store_true", help="Do not mark unmapped codes")
    parser.add_argument("--dump-codes", action="store_true", help="Print used raw map codes and mapped bank/tile refs for one level")
    args = parser.parse_args(argv)

    path = Path(args.path) if args.path else default_input()
    if path is None:
        print("Provide a game_data folder/ZIP path.", file=sys.stderr)
        return 2
    if args.dump_codes:
        dump_codes(path, args.episode, args.level)
        return 0
    if args.export_preview:
        export_preview(path, Path(args.export_preview), args.episode, args.level, args.zoom, args.codes, not args.no_unknown)
        return 0
    from .gui import SecretAgentEditor

    app = SecretAgentEditor(path)
    app.run()
    return 0

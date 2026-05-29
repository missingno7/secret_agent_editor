from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .mapping import DrawRef, TILE_MAP, WORLD_MAP


@dataclass(frozen=True)
class CodeEntry:
    code: int
    title: str
    category: str
    notes: str = ""
    basis: str = ""


def _banks(refs: Iterable[DrawRef]) -> set[int]:
    return {b for _rx, _ry, b, _t in refs}


def _primary_bank(refs: list[DrawRef]) -> int | None:
    banks = sorted(_banks(refs))
    return banks[0] if len(banks) == 1 else None


def _bank_category(bank: int) -> str:
    return f"Tileset bank {bank:02d}"


# This picker is intentionally source-derived, not visual-semantics-derived.
# Camoto Studio gives the file/display structure, libgamemaps/fmt-map-sagent gives
# the SAMLEV map-code -> bank/tile references.  The safest logical grouping we
# can derive without a deeper EXE decompile is therefore:
#   * special map codes handled by the renderer/parser
#   * world-map codes, because Camoto uses a separate map2d-sagent-world format
#   * composite codes, because SAMLEV draws multiple relative tiles for them
#   * tileset bank buckets, because the bank index is part of the original game
#     tile reference and is not a guess based on appearance.
CATEGORY_ORDER = [
    "Used in current level",
    "Map specials / background",
    "Composite map codes",
    *[_bank_category(i) for i in range(16)],
    "World map codes",
    "All normal codes",
]

CATEGORY_HELP: Dict[str, str] = {
    "Used in current level": "Codes that actually occur in the selected level. This is data-derived from BG/FG rows.",
    "Map specials / background": "Renderer/parser special cases: empty/background cells and codes that use the level background tile rather than a fixed SAMLEV image ref.",
    "Composite map codes": "Codes whose SAMLEV/Camoto mapping draws more than one 16x16 tile at relative offsets around the map cell.",
    "World map codes": "Separate level-0 / overworld code table. Camoto marks this as map2d-sagent-world rather than normal map2d-sagent.",
    "All normal codes": "All normal-level map codes currently present in the SAMLEV/Camoto mapping table.",
}
for _b in range(16):
    CATEGORY_HELP[_bank_category(_b)] = (
        f"Normal-level codes whose SAMLEV/Camoto mapping resolves only to tileset bank {_b}. "
        "This is a structural source bucket, not a visual/gameplay guess."
    )

SPECIAL_CODES: Dict[int, CodeEntry] = {
    0x00: CodeEntry(0x00, "Transparent / no foreground", "Map specials / background", basis="map parser/render special"),
    0x20: CodeEntry(0x20, "Background fill cell", "Map specials / background", basis="map parser/render special"),
    0x35: CodeEntry(0x35, "Background-derived tile +1", "Map specials / background", basis="renderer special using level bg_code"),
    0x36: CodeEntry(0x36, "Background-derived tile +2", "Map specials / background", basis="renderer special using level bg_code"),
    0x37: CodeEntry(0x37, "Background-derived tile +3", "Map specials / background", basis="renderer special using level bg_code"),
}


def refs_signature(refs: list[DrawRef]) -> str:
    return ", ".join(f"{rx:+d},{ry:+d}:B{b}:T{t}" for rx, ry, b, t in refs) or "unmapped"


def infer_category(code: int, refs: list[DrawRef]) -> str:
    if code in SPECIAL_CODES:
        return "Map specials / background"
    if len(refs) > 1:
        return "Composite map codes"
    bank = _primary_bank(refs)
    if bank is not None:
        return _bank_category(bank)
    return "Composite map codes"


def title_for_code(code: int, refs: list[DrawRef]) -> str:
    if code in SPECIAL_CODES:
        return SPECIAL_CODES[code].title
    if len(refs) > 1:
        banks = "/".join(str(b) for b in sorted(_banks(refs)))
        return f"Composite code 0x{code:02X} ({len(refs)} refs, bank {banks})"
    if refs:
        _rx, _ry, b, t = refs[0]
        return f"Code 0x{code:02X} -> bank {b}, tile {t}"
    return f"Code 0x{code:02X}"


def build_code_entries() -> Dict[int, CodeEntry]:
    entries: Dict[int, CodeEntry] = dict(SPECIAL_CODES)
    for code, refs in TILE_MAP.items():
        cat = infer_category(code, refs)
        entries[code] = CodeEntry(
            code=code,
            title=title_for_code(code, refs),
            category=cat,
            notes=refs_signature(refs),
            basis="SAMLEV/Camoto map-code table",
        )
    return entries


def category_groups() -> Dict[str, List[int]]:
    groups: Dict[str, List[int]] = {name: [] for name in CATEGORY_ORDER}
    groups["Map specials / background"] = sorted(SPECIAL_CODES)
    for code, refs in TILE_MAP.items():
        cat = infer_category(code, refs)
        groups.setdefault(cat, []).append(code)
        if len(refs) > 1:
            groups["Composite map codes"].append(code)
    groups["World map codes"] = sorted(WORLD_MAP)
    groups["All normal codes"] = sorted(TILE_MAP)
    for k in list(groups):
        groups[k] = sorted(set(groups[k]))

    # Do not expose empty source buckets in the picker.  In practice some
    # tileset banks exist in SAM?01.GFX but have no known normal-level map-code
    # references in the SAMLEV/Camoto table, so offering them as empty picker
    # pages is just noise.
    return {name: groups[name] for name in CATEGORY_ORDER if groups.get(name)}


def code_title(code: int) -> str:
    return build_code_entries().get(code, CodeEntry(code, f"0x{code:02X}", "All normal codes")).title


def source_category_for_code(code: int, world: bool = False) -> str:
    if world:
        return "World map codes"
    return build_code_entries().get(code, CodeEntry(code, "", "Unmapped")).category

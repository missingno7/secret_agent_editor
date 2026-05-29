# Engine Research Leads

These notes summarize what the newly added OpenCrystalCaves source tree and
Secret Agent disassembly can contribute to future editor improvements.

## Highest-Value Editor Improvements

1. Add a semantic map-code database.

   The editor currently renders map codes through the Camoto/SAMLEV tile table,
   but it mostly treats gameplay meaning as unknown. The next useful layer is a
   `CodeSemantics` table with fields such as `kind`, `solid`, `solid_top`,
   `damage`, `death`, `pickup`, `actor`, `hazard`, `door`, `switch`,
   `render_in_front`, and `animated`.

2. Add gameplay overlays.

   Once semantic flags exist, the GUI can show optional overlays for collision,
   hazards, pickups, entrances/exits, enemies, switches, and foreground render
   priority. This would make the editor much more useful than a visual tile
   painter.

3. Improve the picker from structural buckets to gameplay buckets.

   The current picker is intentionally conservative: bank buckets, composite
   codes, world codes, and current-level codes. With verified semantics it can
   safely gain categories such as terrain, one-way platforms, doors, keys,
   switches, pickups, enemies, hazards, signs, and decorations.

4. Add diagnostics for invalid or suspicious level edits.

   Useful checks include missing player start/exit-like codes, doors without
   matching keys or switches, orphaned foreground rows, unexpected unmapped
   codes, and codes that overlap in composite rendering.

5. Add a research tool that extracts candidate tables from the unpacked EXEs.

   The disassembly has enough anchors to justify a small helper that scans the
   unpacked executables for strings, near pointers, repeated switch/table-like
   byte patterns, and cross-episode deltas.

## OpenCrystalCaves Patterns Worth Reusing

OpenCrystalCaves is for Crystal Caves, not Secret Agent, so its constants should
not be copied directly. Its architecture is still a very useful model:

- `occ/game/src/level_loader.cc` starts from raw level ids and produces typed
  tiles, actors, enemies, hazards, moving platforms, backgrounds, and unknown
  markers.
- `occ/game/export/tile.h` uses compact tile flags: solid, solid-top, damage,
  death, animated, render-in-front, and special collision behavior.
- `occ/game/src/level.cc` centralizes collision queries instead of spreading
  collision interpretation through the renderer.
- `occ/game/src/level_loader.cc` keeps unknown raw tile ids visible through
  `tile_unknown`, which matches the editor's reverse-engineering workflow.

The closest Secret Agent equivalent would be a new module such as
`secret_agent_editor/semantics.py` that wraps raw map codes in a richer record:

```python
CodeSemantics(
    code=0x00,
    name="...",
    kind="terrain|pickup|enemy|hazard|door|switch|decor|special",
    flags={...},
    basis="exe|camoto|observed|manual",
)
```

## Secret Agent Disassembly Anchors

The disassembly is still a linear first pass, but it already gives useful
starting points:

- `SAM1_strings.txt`, `SAM2_strings.txt`, and `SAM3_strings.txt` confirm the
  expected file names for tile, sprite, and level data: `SAM?01.GFX`,
  `SAM?02.GFX`, and `SAM?03.GFX`.
- The repeated string
  `~~~~~~~~~~~~~~~~~~|||||||||||||| !"#$%& ()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`
  appears in all three episodes and is a strong candidate for a map/symbol
  reference table.
- `SAM1_unpacked_linear_8086.asm` has the episode 1 file-name literals near
  load-module offsets around `0x10aa` through `0x10c5`.
- The unpacked executables contain many bit-shift, rotate, and XOR-heavy
  routines near the late graphics/decode area. These are candidates for
  validating the existing EGA tile and Secret Agent decode logic against the
  original executable.

## Suggested Next Pass

1. Generate a compact report from all three `SAM*_strings.txt` files with
   offsets and neighboring strings.
2. Build a byte-level extractor for the repeated symbol string and nearby data.
3. Compare code usage across all levels with the editor's known mapping and
   produce a frequency table per episode/level.
4. Manually label a small set of obvious codes from screenshots or gameplay,
   storing every label with a `basis` field so guessed labels remain separate
   from executable-confirmed labels.
5. Add the first GUI overlay for semantic flags, starting with `solid`,
   `solid_top`, `hazard`, and `pickup`.

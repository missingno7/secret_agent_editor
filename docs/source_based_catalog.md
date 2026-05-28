# Source-Based Code Picker Grouping

The picker grouping is intentionally based on source-backed structure rather
than visual guesses.

Confirmed source layers used by the editor:

1. `camoto-studio/data/games/secret-agent.xml` identifies the project layout:
   `SAM?01.GFX` is the 16x16 EGA tileset, `SAM?02.GFX` is the 8x8 spriteset,
   and `SAM?03.GFX` is a fixed archive of 2016-byte maps. It also separates
   normal levels (`map2d-sagent`) from the overworld (`map2d-sagent-world`).
2. `libgamemaps/src/fmt-map-sagent-mapping.hpp` contains the static map-code to
   relative bank/tile table, noted there as taken from Frenkel's SAMLEV level
   viewer.
3. The game data itself has 16 banks x 50 tiles in `SAM?01.GFX`. The bank number
   is part of each map-code reference, so bank buckets are a safe structural
   grouping.

Picker categories:

- `Map specials / background`: parser and renderer special codes such as empty
  cell, background fill, and background-derived tiles.
- `Composite map codes`: codes that draw multiple 16x16 tiles via relative
  offsets in the SAMLEV/Camoto mapping.
- `Tileset bank 00` through `Tileset bank 15`: codes whose mapping resolves
  only to one bank.
- `World map codes`: the separate overworld table.
- `Used in current level`: data derived from the currently open level.

This avoids implying gameplay semantics, such as enemy, item, or door behavior,
until those details are confirmed by deeper executable analysis.

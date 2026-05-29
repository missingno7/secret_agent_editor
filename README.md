# Secret Agent Editor

A small Python reverse-engineering viewer and level editor for Apogee's
**Secret Agent** game data.

The editor works with already-extracted game files. It intentionally does not
handle installer archives or SHR extraction. Point it at a `game_data` folder,
or at a ZIP that contains the final game files:

```text
SAM101.GFX / SAM201.GFX / SAM301.GFX  # 16x16 tile banks
SAM103.GFX / SAM203.GFX / SAM303.GFX  # level archives
```

## Features

- Loads episodes 1, 2, and 3 when their data files are present.
- Decodes the Secret Agent XOR/bit-reversal encryption used by map and tile
  files.
- Decodes ProGraphx `tls-sagent-8k` 16x16 EGA tiles.
- Renders normal levels and the world map using the Camoto/SAMLEV-derived
  map-code to tile mapping.
- Supports foreground `*` rows as overlays on the previous visual row.
- Provides a Tkinter GUI with zoom, scrollable maps, grid/raw-code/unknown-code
  overlays, cell inspection, background/foreground painting, a visual map-code
  picker, and a raw tile-bank atlas.
- Saves edited encrypted `SAM?03.GFX` level archives.
- Offers CLI helpers for PNG previews and raw map-code dumps.

## Requirements

- Python 3.10 or newer
- Pillow
- Tkinter, included with most desktop Python distributions

Install the runtime dependency directly:

```bash
pip install -r requirements.txt
```

Or install the project in editable mode:

```bash
pip install -e .
```

## Usage

Run the GUI without installing the package:

```bash
python main.py path/to/game_data
```

You can also open a ZIP that contains the extracted game data:

```bash
python main.py path/to/game_data.zip
```

After editable installation, the console command is available too:

```bash
secret-agent-editor path/to/game_data
```

If no path is provided, the app looks for `game_data` or `game_data.zip` in the
current working directory.

## CLI Helpers

Export a rendered PNG preview:

```bash
python main.py game_data.zip --episode 1 --level 3 --export-preview ep1_level03.png --zoom 1 --no-unknown
```

Dump the raw map codes used by one level:

```bash
python main.py game_data.zip --episode 1 --level 3 --dump-codes
```

Useful options:

- `--episode N`: episode number, usually `1`, `2`, or `3`
- `--level N`: level index, where `0` is the world map
- `--zoom N`: preview export scale
- `--codes`: draw raw map codes on exported previews
- `--no-unknown`: hide unknown-code markers on exported previews

## Editor Notes

- The map-code picker reflows automatically when the right panel or window is
  resized.
- Empty source-derived bank categories are hidden from the picker.
- Hold Shift while moving over the level grid to preview the currently selected
  map code as a ghost placement overlay.
- Shift + left click paints the selected code to the active background or
  foreground layer.
- Right click clears the active layer cell. Background cells become `0x20`;
  foreground cells become `0x00`.
- The raw `SAM?01.GFX` bank atlas remains available as a separate tab for
  reverse-engineering and debugging.

## Project Layout

```text
secret_agent_editor/
  crypto.py      # Secret Agent encryption/decryption helpers
  graphics.py    # ProGraphx EGA tile decoding
  levels.py      # 2016-byte level block parsing and encoding
  mapping.py     # Map-code to bank/tile references
  render.py      # Level renderer
  gui.py         # Tkinter GUI
  cli.py         # CLI entry point
```

Additional reverse-engineering notes live in `docs/`, including current engine
research leads from OpenCrystalCaves and the Secret Agent disassembly.

## Data And Legal Notes

This repository does not include Secret Agent game data. Use your own legally
obtained copy and keep extracted data files outside version control.

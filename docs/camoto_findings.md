# Camoto Findings Used In This Project

The most useful Secret Agent reference from the supplied Camoto Studio source
tree is:

```text
camoto-studio-master/data/games/secret-agent.xml
```

Confirmed details:

- Secret Agent has a separate level archive for each episode:
  - `sam103.gfx`
  - `sam203.gfx`
  - `sam303.gfx`
- The level archive uses the `xor-sagent-map` filter.
- Each level or world-map block is `2016` bytes.
- Archive offsets start after the first 2016-byte block: block 0 is the world
  map, block 1 is level 1, and so on.
- Camoto identifies two map formats:
  - `map2d-sagent-world` for the world map
  - `map2d-sagent` for normal levels
- Tilesets are identified as:
  - `sam?01.gfx`, format `tls-sagent-8k`, filter `xor-sagent-16sprite`
  - `sam?02.gfx`, format `tls-sagent-2k`, filter `xor-sagent-8sprite`

The Camoto Studio XML does not contain the complete map-code to tile mapping.
That mapping lives in the Camoto/libgamemaps code and is represented locally in
`secret_agent_editor/mapping.py`.

Note: the XML lists the offset for level 14 as `28244`, while the fixed-block
calculation `2016 * 14` gives `28224`. This project therefore parses level
archives as a sequence of fixed 2016-byte blocks instead of copying every XML
offset literally.

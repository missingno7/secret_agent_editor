from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from PIL import Image

from .constants import EGA_PALETTE
from .crypto import decrypt_secret_agent


@dataclass
class Tileset16:
    banks: List[List[Image.Image]]

    def get(self, bank: int, tile: int) -> Optional[Image.Image]:
        if 0 <= bank < len(self.banks) and 0 <= tile < len(self.banks[bank]):
            return self.banks[bank][tile]
        return None


def decode_prographx_16x16(encrypted: bytes) -> Tileset16:
    """Decode SAM?01.GFX into 16 banks x 50 masked 16x16 EGA tiles.

    Camoto identifies this as ``tls-sagent-8k``.  Each 8064-byte bank has a
    3-byte ProGraphx header followed by 50 tiles.  A tile is 16 rows * 2 byte
    cells * 5 planes = 160 bytes.  The planes are interleaved by row/cell:
    opaque mask, blue, green, red, intensity.
    """
    plain = decrypt_secret_agent(encrypted, row_key_reset=8064)
    banks: List[List[Image.Image]] = []
    bank_size = 8064
    tile_size = 160
    data_start = 3
    for bank_start in range(0, len(plain) - tile_size + 1, bank_size):
        chunk = plain[bank_start:bank_start + bank_size]
        if len(chunk) < data_start + 50 * tile_size:
            continue
        tiles: List[Image.Image] = []
        for t in range(50):
            off = data_start + t * tile_size
            tiles.append(_decode_masked_ega_tile_16(chunk[off:off + tile_size]))
        banks.append(tiles)
    return Tileset16(banks)


def _decode_masked_ega_tile_16(buf: bytes) -> Image.Image:
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = img.load()
    i = 0
    for y in range(16):
        for xb in range(2):
            if i + 5 > len(buf):
                return img
            opaque, blue, green, red, inten = buf[i:i + 5]
            i += 5
            for bit in range(8):
                mask = 0x80 >> bit
                if not (opaque & mask):
                    continue
                color = 0
                if blue & mask:
                    color |= 1
                if green & mask:
                    color |= 2
                if red & mask:
                    color |= 4
                if inten & mask:
                    color |= 8
                px[xb * 8 + bit, y] = (*EGA_PALETTE[color], 255)
    return img

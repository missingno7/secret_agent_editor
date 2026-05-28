from __future__ import annotations

from .constants import KEY


def reverse_bits(v: int) -> int:
    v = ((v & 0xF0) >> 4) | ((v & 0x0F) << 4)
    v = ((v & 0xCC) >> 2) | ((v & 0x33) << 2)
    v = ((v & 0xAA) >> 1) | ((v & 0x55) << 1)
    return v & 0xFF


def decrypt_secret_agent(data: bytes, *, row_key_reset: int | None = None) -> bytearray:
    """Decrypt Secret Agent GFX data.

    The same operation is used for tiles and maps, but with different key reset
    intervals.  Maps reset every 42 bytes; 16x16 tiles reset every 8064 bytes;
    8x8 sprites reset every 2048 bytes.
    """
    out = bytearray(len(data))
    for i, b in enumerate(data):
        k = KEY[(i % row_key_reset if row_key_reset else i) % len(KEY)]
        out[i] = reverse_bits(b) ^ k
    return out


def encrypt_secret_agent(data: bytes, *, row_key_reset: int | None = None) -> bytearray:
    out = bytearray(len(data))
    for i, b in enumerate(data):
        k = KEY[(i % row_key_reset if row_key_reset else i) % len(KEY)]
        out[i] = reverse_bits(b ^ k)
    return out

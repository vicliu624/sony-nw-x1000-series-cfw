"""Read-only parser for the fixed-size Japanese X1000 1.11 style table.

Recovered from SpiderApp 0x108c58 / 0xf577c. Unknown fields stay opaque.
This module deliberately provides no writer or firmware patch operation.
"""
from dataclasses import dataclass
import struct

SLOT_COUNT = 204
RECORD_BYTES = 0x149C
CHILD_BYTES = 0xA4
CHILD_SLOTS = 32
TABLE_BYTES = 8 + SLOT_COUNT * RECORD_BYTES


@dataclass(frozen=True)
class Child:
    words: tuple[int, ...]

    @property
    def kind(self) -> int:
        return self.words[0]

    @property
    def geometry(self) -> tuple[int, ...]:
        """Stored x/y/z/w/h; parent offsets and alignment are applied at runtime."""
        return tuple(x if x < 0x80000000 else x - 0x100000000 for x in self.words[1:6])


@dataclass(frozen=True)
class Layout:
    index: int
    header: tuple[int, ...]
    children: tuple[Child, ...]


def parse_style(data: bytes) -> tuple[Layout, ...]:
    if len(data) != TABLE_BYTES:
        raise ValueError('Expected the fixed 0x106c58-byte X1000 style table')
    count, initialized = struct.unpack_from('<II', data)
    if count > SLOT_COUNT or initialized != 1:
        raise ValueError('Unsupported style header')
    result = []
    for index in range(count):
        offset = 8 + index * RECORD_BYTES
        header = struct.unpack_from('<7I', data, offset)
        if header[0] > CHILD_SLOTS:
            raise ValueError(f'Layout {index}: too many child controls')
        children = tuple(
            Child(struct.unpack_from('<41I', data, offset + 28 + child * CHILD_BYTES))
            for child in range(header[0])
        )
        result.append(Layout(index, header, children))
    return tuple(result)

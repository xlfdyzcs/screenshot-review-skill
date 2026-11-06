#!/usr/bin/env python3
"""Generate abstract color tiles locally; no product images are read or shipped."""

import argparse
import json
import struct
import zlib
from pathlib import Path


def make_tile(path, accent):
    width, height = 390, 844
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)
        for x in range(width):
            color = (245, 246, 250)
            if 22 <= x < width - 22 and 32 <= y < 104:
                color = accent
            elif 22 <= x < width - 22 and 134 <= y < 750:
                color = (255, 255, 255)
                if 44 <= x < width - 44 and 175 <= y < 205:
                    color = (210, 215, 229)
                elif 44 <= x < width - 44 and 250 <= y < 580:
                    color = tuple(min(255, c + 95) for c in accent)
                elif 44 <= x < width - 44 and 630 <= y < 700:
                    color = accent
            pixels.extend(color)
    def chunk(kind, content):
        return struct.pack('>I', len(content)) + kind + content + struct.pack('>I', zlib.crc32(kind + content))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(bytes(pixels))) + chunk(b'IEND', b''))


def create(output):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Choose an empty demo output directory')
    output.mkdir(parents=True, exist_ok=True)
    make_tile(output / 'before.png', (95, 110, 160))
    make_tile(output / 'after.png', (99, 80, 215))
    data = {
        'review': {'project': 'color-tile-demo', 'revision': 'v1', 'title': '抽象色块审阅示例',
                   'captureNote': '仅用于演示审阅工具的抽象色块；并非真实应用截图。'},
        'cases': [{'id': 'A01', 'title': '通用色块示例', 'group': '演示', 'width': 390, 'height': 844,
                   'before': ['before.png'], 'after': ['after.png']}],
    }
    (output / 'manifest.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return str(output / 'manifest.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(create(args.output))
    except (ValueError, OSError) as error:
        parser.exit(1, f'Demo error: {error}\n')

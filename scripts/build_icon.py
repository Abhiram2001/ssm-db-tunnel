#!/usr/bin/env python3
"""
build_icon.py — Generate SsmDbTunnel.icns for the macOS application bundle.

Uses the same database-cylinder drawing logic as ui/icon.py (no external
dependencies; pure-Python PNG) to produce all required @1x / @2x sizes,
then delegates to macOS iconutil to assemble the final .icns file.

Usage (run from the project root):
    python scripts/build_icon.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui.icon import make_status_icon

# Required iconset image names → pixel dimensions.
# iconutil expects exactly these filenames inside a *.iconset directory.
_ICONSET_SIZES = [
    ('icon_16x16.png',      16),
    ('icon_16x16@2x.png',   32),
    ('icon_32x32.png',      32),
    ('icon_32x32@2x.png',   64),
    ('icon_128x128.png',    128),
    ('icon_128x128@2x.png', 256),
    ('icon_256x256.png',    256),
    ('icon_256x256@2x.png', 512),
    ('icon_512x512.png',    512),
    ('icon_512x512@2x.png', 1024),
]

OUT_ICNS = Path(__file__).parent.parent / 'SsmDbTunnel.icns'


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    iconset = tmp / 'SsmDbTunnel.iconset'
    iconset.mkdir()

    print('Generating icon sizes...')
    for filename, size in _ICONSET_SIZES:
        src = make_status_icon('idle', size=size)
        dst = iconset / filename
        shutil.copy(src, dst)
        print(f'  {filename} ({size}×{size})')

    print('Running iconutil...')
    result = subprocess.run(
        ['iconutil', '-c', 'icns', str(iconset), '-o', str(OUT_ICNS)],
        capture_output=True,
        text=True,
    )
    shutil.rmtree(str(tmp))

    if result.returncode != 0:
        print(f'iconutil failed:\n{result.stderr}', file=sys.stderr)
        sys.exit(1)

    print(f'Created: {OUT_ICNS}')


if __name__ == '__main__':
    main()

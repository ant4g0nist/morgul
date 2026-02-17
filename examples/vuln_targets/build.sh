#!/bin/bash
# Build the vulnerable imgparse binary and generate a crash-inducing input.
# Usage: ./examples/vuln_targets/build.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/imgparse.c"
OUT="/tmp/imgparse"
CRASH_INPUT="/tmp/crash_input.mgl"

echo "=== Building vulnerable imgparse ==="
cc -g -O0 -fno-stack-protector -o "$OUT" "$SRC"
echo "  Binary: $OUT"

echo ""
echo "=== Generating crash input ==="
# Python one-liner to craft a malformed MGL file:
#   - Valid magic "MGL\0"
#   - 64x64 image, 32bpp
#   - palette_count = 255 (way more than the 16-slot buffer)
#   - Palette data filled with 0x41 ('A') to make overflow obvious
python3 -c "
import struct

magic = b'MGL\x00'
width = struct.pack('<H', 64)
height = struct.pack('<H', 64)
bpp = struct.pack('B', 32)
palette_count = struct.pack('B', 255)  # overflow: 255 > 16 slots
data_offset = struct.pack('<I', 14 + 255 * 4)

header = magic + width + height + bpp + palette_count + data_offset

# 255 RGBA entries = 1020 bytes, overflows the 64-byte (16*4) palette buffer
palette = b'\x41\x42\x43\x44' * 255

# Some pixel data
pixels = b'\xDE\xAD' * 128

with open('$CRASH_INPUT', 'wb') as f:
    f.write(header + palette + pixels)

print(f'  Crash input: $CRASH_INPUT ({len(header + palette + pixels)} bytes)')
print(f'  Palette entries: 255 (buffer has 16 slots)')
print(f'  Overflow: {(255-16)*4} bytes past heap buffer')
"

echo ""
echo "=== Test it ==="
echo "  $OUT $CRASH_INPUT"
echo ""
echo "  (Should crash with heap corruption)"
echo ""
echo "=== Run Morgul triage ==="
echo "  PYTHONPATH=\"\$(lldb -P)\" uv run python examples/vuln_triage.py"

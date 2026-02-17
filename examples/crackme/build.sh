#!/bin/bash
# Build the crackme binary.
#
# Stripped (hard mode — no symbols):
#   ./build.sh
#
# With debug info (easy mode):
#   ./build.sh --debug

set -e
cd "$(dirname "$0")"

if [ "$1" = "--debug" ]; then
    echo "Building crackme (debug)..."
    clang++ -std=c++17 -g -o crackme crackme.cpp
    echo "Built: crackme (with symbols)"
else
    echo "Building crackme (stripped)..."
    clang++ -std=c++17 -O1 -o crackme crackme.cpp
    strip crackme
    echo "Built: crackme (stripped)"
fi

echo ""
echo "Test:"
echo "  ./crackme MORGUL-TEST-KEYS-HERE"
echo ""
echo "Analyze with Morgul:"
echo "  PYTHONPATH=\"\$(lldb -P)\" uv run python examples/reverse_unknown.py examples/crackme/crackme --task \"find the license validation algorithm and figure out what makes a valid key\""

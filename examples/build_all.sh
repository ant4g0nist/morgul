#!/bin/bash
# Build all example binaries in one go.
#
# Usage:
#   ./examples/build_all.sh
#
# Produces:
#   /tmp/morgul_test       — general test binary (basic_act, self_healing, agents, …)
#   /tmp/imgparse          — vulnerable image parser (vuln_triage)
#   /tmp/crash_input.mgl   — crash-inducing input for imgparse
#   examples/crackme/crackme — stripped crackme (reverse_unknown)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════════════╗"
echo "║  Building all Morgul example binaries            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. General test binary ────────────────────────────────────────────
echo "── [1/3] Test binary ──"
"$SCRIPT_DIR/build_test_binary.sh"
echo ""

# ── 2. Vulnerable imgparse + crash input ──────────────────────────────
echo "── [2/3] Vulnerable imgparse ──"
"$SCRIPT_DIR/vuln_targets/build.sh"
echo ""

# ── 3. Crackme (stripped) ─────────────────────────────────────────────
echo "── [3/3] Crackme ──"
"$SCRIPT_DIR/crackme/build.sh"
echo ""

# ── Summary ───────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════╗"
echo "║  All binaries built successfully                 ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  /tmp/morgul_test        — test binary           ║"
echo "║  /tmp/imgparse           — vuln target           ║"
echo "║  /tmp/crash_input.mgl    — crash input           ║"
echo "║  examples/crackme/crackme — crackme              ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Run examples with:"
echo "  PYTHONPATH=\"\$(lldb -P)\" uv run python examples/basic_act.py"
echo "  PYTHONPATH=\"\$(lldb -P)\" uv run python examples/vuln_triage.py --dashboard"
echo "  PYTHONPATH=\"\$(lldb -P)\" uv run python examples/reverse_unknown.py examples/crackme/crackme --dashboard"

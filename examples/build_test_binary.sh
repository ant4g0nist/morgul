#!/bin/bash
# Build a simple test binary for the examples.
# Usage: ./examples/build_test_binary.sh
set -e

SRC=$(mktemp /tmp/morgul_test_XXXXXX.c)
OUT="/tmp/morgul_test"

cat > "$SRC" <<'EOF'
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int add(int a, int b) {
    return a + b;
}

void greet(const char *name) {
    char buf[64];
    snprintf(buf, sizeof(buf), "Hello, %s!", name);
    printf("%s\n", buf);
}

void process_input(const char *input) {
    char buffer[32];
    strncpy(buffer, input, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\0';
    printf("Processed: %s\n", buffer);
}

int main(int argc, char **argv) {
    printf("morgul test binary\n");
    int result = add(40, 2);
    printf("add(40, 2) = %d\n", result);

    greet(argc > 1 ? argv[1] : "world");

    if (argc > 2) {
        process_input(argv[2]);
    }

    return 0;
}
EOF

cc -g -O0 -o "$OUT" "$SRC"
rm -f "$SRC"

echo "Built: $OUT"
echo ""
echo "Run examples with:"
echo "  PYTHONPATH=\"\$(lldb -P)\" uv run python examples/basic_act.py"

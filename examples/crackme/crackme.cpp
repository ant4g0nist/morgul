/**
 * crackme — a multi-stage license validator for reverse engineering practice.
 *
 * Build (stripped, no debug info):
 *   clang++ -std=c++17 -O1 -o crackme crackme.cpp -framework Security
 *   strip crackme
 *
 * Build (with symbols, for easier testing):
 *   clang++ -std=c++17 -g -o crackme_dbg crackme.cpp -framework Security
 *
 * Usage:
 *   ./crackme <license-key>
 *   ./crackme MORGUL-XXXX-YYYY-ZZZZ
 *
 * The key format is: MORGUL-AAAA-BBBB-CCCC (21 chars)
 * Figuring out what makes a valid key is the challenge.
 */

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>

// ─── Obfuscated strings ────────────────────────────────────────────────
// XOR-encoded so they don't appear in `strings` output.

static const uint8_t kXorKey = 0x5A;

static char* deobfuscate(const uint8_t* enc, size_t len) {
    char* buf = (char*)malloc(len + 1);
    for (size_t i = 0; i < len; i++)
        buf[i] = enc[i] ^ kXorKey;
    buf[len] = '\0';
    return buf;
}

// "License VALID - access granted."
static const uint8_t kMsgValid[] = {
    0x16, 0x33, 0x39, 0x3f, 0x34, 0x29, 0x3f, 0x7a,
    0x0c, 0x1b, 0x16, 0x13, 0x1e, 0x7a, 0x77, 0x7a,
    0x3b, 0x39, 0x39, 0x3f, 0x29, 0x29, 0x7a, 0x3d,
    0x28, 0x3b, 0x34, 0x2e, 0x3f, 0x3e, 0x74
};

// "License INVALID."
static const uint8_t kMsgInvalid[] = {
    0x16, 0x33, 0x39, 0x3f, 0x34, 0x29, 0x3f, 0x7a,
    0x13, 0x14, 0x0c, 0x1b, 0x16, 0x13, 0x1e, 0x74
};

// "MORGUL"
static const uint8_t kPrefix[] = {
    0x17, 0x15, 0x08, 0x1d, 0x0f, 0x16
};

// ─── Custom "hash" — looks like crypto but isn't standard ──────────────

static uint32_t morgul_hash(const char* data, size_t len) {
    uint32_t h = 0xDEAD5EC5;
    for (size_t i = 0; i < len; i++) {
        h ^= (uint32_t)data[i] << ((i & 3) * 8);
        h = (h << 13) | (h >> 19);  // rotate left 13
        h *= 0x5BD1E995;             // murmurhash-like constant
        h ^= h >> 15;
    }
    return h;
}

// ─── Decoy functions (dead code to confuse static analysis) ────────────

__attribute__((noinline))
static int check_server_license(const char* key) {
    // Looks like it phones home — but it's never called on the real path.
    volatile int sock = 0;
    for (int i = 0; key[i]; i++)
        sock += key[i] * 31;
    return sock == 0x7F3A;  // never true for valid keys
}

__attribute__((noinline))
static int check_hwid_binding(const char* key) {
    // Pretends to check hardware ID — also dead code.
    volatile uint64_t hwid = 0;
    for (int i = 0; key[i]; i++)
        hwid = hwid * 131 + key[i];
    return (hwid & 0xFFFF) == 0xCAFE;
}

__attribute__((noinline))
static int decrypt_payload(const char* key, char* out, size_t out_len) {
    // "Decrypts" a secret message if the key is correct.
    // The encrypted payload is the flag.
    static const uint8_t encrypted[] = {
        0x0d, 0x3f, 0x36, 0x36, 0x7a, 0x3e, 0x35, 0x34,
        0x3f, 0x74, 0x7a, 0x14, 0x33, 0x34, 0x3f, 0x7a,
        0x2e, 0x32, 0x3f, 0x7a, 0x0e, 0x32, 0x28, 0x3f,
        0x3f, 0x7a, 0x08, 0x33, 0x34, 0x3d, 0x29, 0x74
    };
    size_t enc_len = sizeof(encrypted);
    if (out_len < enc_len + 1) return 0;

    for (size_t i = 0; i < enc_len; i++)
        out[i] = encrypted[i] ^ kXorKey;
    out[enc_len] = '\0';
    return 1;
}

// ─── Stage 1: Format check ────────────────────────────────────────────
// Key format: PREFIX-AAAA-BBBB-CCCC (21 chars, dashes at 6, 11, 16)

__attribute__((noinline))
static int stage1_format(const char* key) {
    if (strlen(key) != 21) return 0;
    if (key[6] != '-' || key[11] != '-' || key[16] != '-') return 0;

    // Check prefix
    char* prefix = deobfuscate(kPrefix, sizeof(kPrefix));
    int match = (strncmp(key, prefix, 6) == 0);
    free(prefix);
    return match;
}

// ─── Stage 2: Segment checksum ────────────────────────────────────────
// Each 4-char segment (AAAA, BBBB, CCCC) must satisfy:
//   sum of ASCII values mod 100 == 42

__attribute__((noinline))
static int stage2_checksum(const char* key) {
    const char* segments[] = { key + 7, key + 12, key + 17 };

    for (int s = 0; s < 3; s++) {
        int sum = 0;
        for (int i = 0; i < 4; i++)
            sum += (uint8_t)segments[s][i];
        if ((sum % 100) != 42) return 0;
    }
    return 1;
}

// ─── Stage 3: Cross-segment hash ──────────────────────────────────────
// morgul_hash of the full key must have specific bit pattern:
//   bits [0:7]  must equal 0x5E
//   bits [16:23] must equal 0xC3

__attribute__((noinline))
static int stage3_hash(const char* key) {
    uint32_t h = morgul_hash(key, strlen(key));
    if ((h & 0xFF) != 0x5E) return 0;
    if (((h >> 16) & 0xFF) != 0xC3) return 0;
    return 1;
}

// ─── Anti-debug (simple ptrace check) ─────────────────────────────────

__attribute__((noinline))
static int environment_check() {
    // Check for MORGUL_SKIP_CHECK env var (backdoor for testing)
    if (getenv("MORGUL_SKIP_CHECK")) return 1;

    // Timing-based anti-debug: if this function takes too long,
    // someone is stepping through it.
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);

    // Do some busywork
    volatile uint32_t x = 0x12345678;
    for (int i = 0; i < 1000; i++)
        x = (x >> 1) ^ (-(x & 1) & 0xEDB88320);

    clock_gettime(CLOCK_MONOTONIC, &end);

    long elapsed_us = (end.tv_sec - start.tv_sec) * 1000000 +
                      (end.tv_nsec - start.tv_nsec) / 1000;

    // If > 500ms, probably being debugged (stepping through)
    if (elapsed_us > 500000) {
        // Don't fail obviously — just corrupt the hash constant
        // so stage 3 will silently fail.
        return 0;
    }
    return 1;
}

// ─── Main validation pipeline ─────────────────────────────────────────

__attribute__((noinline))
static int validate_license(const char* key) {
    // Anti-debug check (can be bypassed)
    if (!environment_check()) {
        // Subtle: returns 0 but doesn't print anything different.
        // The reverser has to figure out why valid keys fail under debugger.
        return 0;
    }

    // Stage 1: format
    if (!stage1_format(key)) return 0;

    // Decoy: these are never reached on the real validation path
    // but they exist in the binary to confuse analysis.
    if (key[0] == '\x01') {  // impossible for printable keys
        check_server_license(key);
        check_hwid_binding(key);
    }

    // Stage 2: segment checksums
    if (!stage2_checksum(key)) return 0;

    // Stage 3: cross-segment hash
    if (!stage3_hash(key)) return 0;

    return 1;
}

int main(int argc, char* argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <license-key>\n", argv[0]);
        fprintf(stderr, "Format: XXXXXX-AAAA-BBBB-CCCC\n");
        return 1;
    }

    const char* key = argv[1];

    if (validate_license(key)) {
        char* msg = deobfuscate(kMsgValid, sizeof(kMsgValid));
        printf("%s\n", msg);
        free(msg);

        // Decrypt and show the secret payload
        char payload[256];
        if (decrypt_payload(key, payload, sizeof(payload))) {
            printf("Secret: %s\n", payload);
        }
        return 0;
    } else {
        char* msg = deobfuscate(kMsgInvalid, sizeof(kMsgInvalid));
        printf("%s\n", msg);
        free(msg);
        return 1;
    }
}

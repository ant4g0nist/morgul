/*
 * imgparse.c — Intentionally vulnerable image header parser.
 *
 * Parses a custom "MGL" image format.  Contains a heap buffer overflow:
 * the palette_count field in the header is trusted without bounds checking,
 * so a crafted file can overflow the heap-allocated palette buffer and
 * corrupt adjacent metadata.
 *
 * Build:  cc -g -O0 -fno-stack-protector -o /tmp/imgparse imgparse.c
 * Crash:  /tmp/imgparse /tmp/crash_input.mgl
 *
 * File format (little-endian):
 *   [0..3]   magic:          "MGL\x00"
 *   [4..5]   width:          uint16_t
 *   [6..7]   height:         uint16_t
 *   [8]      bpp:            uint8_t  (bits per pixel)
 *   [9]      palette_count:  uint8_t  (number of RGBA palette entries)
 *   [10..13] data_offset:    uint32_t (offset to pixel data)
 *   [14..]   palette data:   palette_count * 4 bytes (RGBA)
 *   [data_offset..] pixel data
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#pragma pack(push, 1)
typedef struct {
    char     magic[4];       /* "MGL\0" */
    uint16_t width;
    uint16_t height;
    uint8_t  bpp;
    uint8_t  palette_count;  /* trusted — BUG: no upper-bound check */
    uint32_t data_offset;
} MGLHeader;
#pragma pack(pop)

typedef struct {
    uint8_t r, g, b, a;
} RGBAColor;

typedef struct {
    uint32_t    width;
    uint32_t    height;
    uint8_t     bpp;
    uint32_t    palette_size;   /* actual allocated slots */
    RGBAColor  *palette;        /* heap-allocated */
    uint8_t    *pixels;         /* heap-allocated */
    char        description[64]; /* metadata — corruption target */
} ImageCtx;

static ImageCtx *create_context(uint32_t w, uint32_t h, uint8_t bpp) {
    ImageCtx *ctx = (ImageCtx *)calloc(1, sizeof(ImageCtx));
    if (!ctx) return NULL;
    ctx->width  = w;
    ctx->height = h;
    ctx->bpp    = bpp;
    /* Allocate a small palette buffer — only 16 slots.
     * If the file claims more entries, the read overflows this buffer. */
    ctx->palette_size = 16;
    ctx->palette = (RGBAColor *)malloc(ctx->palette_size * sizeof(RGBAColor));
    if (!ctx->palette) { free(ctx); return NULL; }

    size_t pixel_bytes = (size_t)w * h * (bpp / 8);
    if (pixel_bytes > 0 && pixel_bytes < 1024 * 1024) {
        ctx->pixels = (uint8_t *)malloc(pixel_bytes);
    }
    snprintf(ctx->description, sizeof(ctx->description),
             "MGL image %ux%u @%ubpp", w, h, bpp);
    return ctx;
}

static void free_context(ImageCtx *ctx) {
    if (!ctx) return;
    free(ctx->palette);
    free(ctx->pixels);
    free(ctx);
}

static int parse_image(const char *path) {
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        fprintf(stderr, "Cannot open: %s\n", path);
        return 1;
    }

    MGLHeader hdr;
    if (fread(&hdr, sizeof(hdr), 1, fp) != 1) {
        fprintf(stderr, "Short read on header\n");
        fclose(fp);
        return 1;
    }

    if (memcmp(hdr.magic, "MGL", 3) != 0) {
        fprintf(stderr, "Bad magic: expected MGL\\0\n");
        fclose(fp);
        return 1;
    }

    printf("[*] MGL image: %ux%u, %u bpp, %u palette entries\n",
           hdr.width, hdr.height, hdr.bpp, hdr.palette_count);

    ImageCtx *ctx = create_context(hdr.width, hdr.height, hdr.bpp);
    if (!ctx) {
        fprintf(stderr, "Alloc failed\n");
        fclose(fp);
        return 1;
    }

    /* ===== VULNERABILITY =====
     * We read palette_count entries from the file directly into the
     * palette buffer, but the buffer only has 16 slots.  If the file
     * header says palette_count > 16, we overflow the heap buffer,
     * corrupting adjacent allocations (pixels pointer, description, etc.).
     */
    printf("[*] Reading %u palette entries into %u-slot buffer...\n",
           hdr.palette_count, ctx->palette_size);

    size_t read_bytes = (size_t)hdr.palette_count * sizeof(RGBAColor);
    size_t nread = fread(ctx->palette, 1, read_bytes, fp);
    printf("[*] Read %zu bytes of palette data\n", nread);

    /* Access fields that may have been corrupted by the overflow */
    printf("[*] Description: %s\n", ctx->description);
    printf("[*] Pixel buffer: %p\n", (void *)ctx->pixels);

    /* Try to use the (possibly corrupted) pixel pointer — this will crash
     * if the overflow corrupted ctx->pixels with controlled data. */
    if (ctx->pixels) {
        printf("[*] Reading pixel data...\n");
        size_t pixel_bytes = (size_t)ctx->width * ctx->height * (ctx->bpp / 8);
        if (pixel_bytes > 0 && pixel_bytes < 1024 * 1024) {
            fread(ctx->pixels, 1, pixel_bytes, fp);
            printf("[*] First pixel: 0x%02x\n", ctx->pixels[0]);
        }
    }

    free_context(ctx);
    fclose(fp);
    printf("[*] Done.\n");
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <file.mgl>\n", argv[0]);
        return 1;
    }
    return parse_image(argv[1]);
}

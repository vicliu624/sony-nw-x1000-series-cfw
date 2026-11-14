/* PC-only adapter for the unchanged M5GFX JPEG decoder. No display or RF. */
#include "lgfx_tjpgd.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
enum { COVER_PIXELS = 96, DECODER_POOL_BYTES = 3900, COMPRESSED_LIMIT = 524288 };
struct input {
    unsigned char *data;
    size_t bytes, at;
    unsigned pixels, nonzero_channels;
};
static uint32_t read_image(void *context, uint8_t *buffer, uint32_t count) {
    struct input *input = context;
    if (count > input->bytes - input->at)
        count = (uint32_t)(input->bytes - input->at);
    if (buffer)
        memcpy(buffer, input->data + input->at, count);
    input->at += count;
    return count;
}
static uint32_t output_image(void *context, void *pixels, JRECT *rect) {
    struct input *input = context;
    unsigned count = (rect->right - rect->left + 1) * (rect->bottom - rect->top + 1);
    input->pixels += count;
    unsigned char *data = pixels;
    for (unsigned i = 0; i < count * 3; i++)
        input->nonzero_channels += data[i] != 0;
    return 1;
}
int main(int argc, char **argv) {
    assert(argc == 2);
    FILE *file = fopen(argv[1], "rb");
    assert(file && !fseek(file, 0, SEEK_END));
    long length = ftell(file);
    assert(length > 0 && length <= COMPRESSED_LIMIT);
    rewind(file);
    struct input input = {0};
    input.bytes = (size_t)length;
    input.data = malloc(input.bytes);
    assert(input.data && fread(input.data, 1, input.bytes, file) == input.bytes);
    fclose(file);
    unsigned char *pool = malloc(DECODER_POOL_BYTES);
    assert(pool);
    lgfxJdec decoder;
    int prepared = lgfx_jd_prepare(&decoder, read_image, pool, DECODER_POOL_BYTES, &input);
    unsigned width = prepared ? 0 : decoder.width, height = prepared ? 0 : decoder.height;
    float scale = prepared ? 1 : COVER_PIXELS / (float)(width > height ? width : height);
    unsigned division = scale <= 0.125f ? 3 : scale <= 0.25f ? 2 : scale <= 0.5f ? 1 : 0;
    int decoded = prepared ? prepared : (int)lgfx_jd_decomp(&decoder, output_image, division);
    printf("{\"prepare\":%d,\"decode\":%d,\"width\":%u,\"height\":%u,"
           "\"division\":%u,\"pixels\":%u,\"nonzero_channels\":%u}\n",
           prepared, decoded, width, height, division, input.pixels, input.nonzero_channels);
    free(pool);
    free(input.data);
    return decoded ? 1 : 0;
}

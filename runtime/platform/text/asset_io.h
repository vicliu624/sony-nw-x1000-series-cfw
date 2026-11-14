#ifndef X1000_TEXT_ASSET_IO_H
#define X1000_TEXT_ASSET_IO_H
#include "../../store/stock_fs_bridge.h"
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
static unsigned asset_le32(const unsigned char *p) {
    return p[0] | ((unsigned)p[1] << 8) | ((unsigned)p[2] << 16) | ((unsigned)p[3] << 24);
}
static FILE *asset_open_readonly(const char *path, unsigned limit, unsigned *size) {
    int fd = open(path, O_RDONLY | O_NONBLOCK | O_NOFOLLOW);
    if (fd < 0)
        return 0;
    struct hb_target_stat s;
    if (hb_target_fstat(fd, &s) || !S_ISREG(s.st_mode) || s.st_size < 0 ||
        (unsigned long long)s.st_size > limit) {
        close(fd);
        return 0;
    }
    FILE *f = fdopen(fd, "rb");
    if (!f) {
        close(fd);
        return 0;
    }
    *size = (unsigned)s.st_size;
    return f;
}
#endif

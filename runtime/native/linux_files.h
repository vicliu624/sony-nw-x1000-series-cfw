#ifndef HB_LINUX_FILES_H
#define HB_LINUX_FILES_H
#ifdef HB_USE_POSIX_FILES
#include <dirent.h>
#endif
long hb_file_open_read(const char *path);
long hb_file_read(int fd, void *buffer, unsigned bytes);
long hb_file_write(int fd, const void *buffer, unsigned bytes);
long hb_file_close(int fd);
long hb_file_seek_end(int fd);
int hb_path_is_not_link(const char *path);
/* Directory representation is private to the selected Linux backend. */
struct hb_directory {
#ifdef HB_USE_POSIX_FILES
    DIR *stream;
#else
    int fd;
    unsigned char buffer[2048];
    unsigned used, offset;
#endif
    volatile int *stop;
};
int hb_directory_open(struct hb_directory *, const char *path, volatile int *stop);
int hb_directory_next(struct hb_directory *, char name[33]);
void hb_directory_close(struct hb_directory *);
#endif

#define _XOPEN_SOURCE 700
#include "internal.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <unistd.h>
#ifndef XW_HOST
#include "../../apps/qqmusic/qqmusic_volume.h"
#include "../../store/target_abi.h"
#include "../../store/termination.h"
extern int xw_stock_fcntl(int, int, ...) __asm__("fcntl");
extern int xw_stock_fstatvfs(int, struct statvfs *) __asm__("fstatvfs64");
#else
#define xw_stock_fcntl fcntl
#define xw_stock_fstatvfs fstatvfs
#endif
struct directory {
  int fd;
  unsigned long long device, inode;
  char path[2049];
#ifndef XW_HOST
  struct qq_volume volume;
#endif
};
int xw_filename_valid(const char *s) {
  size_t n;
  if (!s || !(n = strlen(s)) || n > 64 || s[0] == '.' || s[n - 1] == '.')
    return 0;
  for (size_t i = 0; i < n; i++)
    if (!((s[i] >= 'a' && s[i] <= 'z') || (s[i] >= 'A' && s[i] <= 'Z') ||
          (s[i] >= '0' && s[i] <= '9') || s[i] == '-' || s[i] == '_' ||
          s[i] == '.'))
      return 0;
  return 1;
}
int xw_storage_set_owner(xw_app *a, xw_storage_owner owner, void *context) {
  if (!a || a->stop)
    return XW_STORAGE_STOPPED;
  a->owner = owner;
  a->owner_context = context;
  return 0;
}
int xw_storage_access(xw_app *a) {
  if (!a || a->stop)
    return XW_STORAGE_STOPPED;
#ifndef XW_HOST
  if (*hb_store_termination_flag())
    return XW_STORAGE_STOPPED;
  if (!a->owner || a->owner(a->owner_context) != 1)
    return XW_STORAGE_OWNERSHIP;
#else
  if (!a->preview)
    return XW_STORAGE_OWNERSHIP;
  if (a->owner && a->owner(a->owner_context) != 1)
    return XW_STORAGE_OWNERSHIP;
#endif
  return 0;
}
static int close_directory(struct directory *d) {
#ifndef XW_HOST
  return qq_volume_close(&d->volume) ? XW_STORAGE_IO : 0;
#else
  return d->fd >= 0 && close(d->fd) ? XW_STORAGE_IO : 0;
#endif
}
static int check_directory(xw_app *a, struct directory *d) {
  struct stat s;
  int rc = xw_storage_access(a);
  if (rc)
    return rc;
  if (fstat(d->fd, &s) || !S_ISDIR(s.st_mode) ||
      (unsigned long long)s.st_dev != d->device ||
      (unsigned long long)s.st_ino != d->inode)
    return XW_STORAGE_BOUNDARY;
#ifndef XW_HOST
  struct qq_storage_plan plan;
  uint64_t required;
  memset(&plan, 0, sizeof plan);
  if (qq_volume_recheck(&d->volume, &plan, &required))
    return XW_STORAGE_BOUNDARY;
#else
  if (lstat(d->path, &s) || !S_ISDIR(s.st_mode) ||
      (unsigned long long)s.st_dev != d->device ||
      (unsigned long long)s.st_ino != d->inode)
    return XW_STORAGE_BOUNDARY;
#endif
  return 0;
}
static int open_directory(xw_app *a, struct directory *d, int resource) {
  struct stat s;
  int rc = xw_storage_access(a);
  memset(d, 0, sizeof(*d));
  d->fd = -1;
  if (rc)
    return rc;
#ifndef XW_HOST
  struct qq_storage_policy policy = {"/dev/mtdblock/2", "vfat"};
  struct qq_storage_plan plan;
  uint64_t required;
  qq_volume_init(&d->volume);
  memset(&plan, 0, sizeof plan);
  int n = snprintf(d->path, sizeof d->path, "/contents/HOMEBREW/%s/%s%s",
                   resource ? "apps" : "data", a->program->id,
                   resource ? "/assets" : "");
  if (n < 0 || (size_t)n >= sizeof d->path)
    return XW_STORAGE_INVALID;
  rc = qq_volume_open(&d->volume, &policy, d->path, &plan, &required);
  if (rc)
    return XW_STORAGE_BOUNDARY;
  d->fd = d->volume.directory;
#else
  const char *path = resource ? "assets" : a->preview_data;
  char resolved[4096], prefix[4096];
  if (!path)
    return XW_STORAGE_BOUNDARY;
  if (!realpath(path, resolved) || strlen(resolved) > 2048)
    return XW_STORAGE_BOUNDARY;
  /* Check every original absolute component before canonicalizing: accepting
   * realpath alone would silently accept a symlink supplied to --data. */
  if (path[0] != '/') {
    if (!getcwd(prefix, sizeof prefix) ||
        strlen(prefix) + strlen(path) + 2 > sizeof prefix)
      return XW_STORAGE_BOUNDARY;
    strcat(prefix, "/");
    strcat(prefix, path);
  } else {
    if (strlen(path) >= sizeof prefix)
      return XW_STORAGE_BOUNDARY;
    strcpy(prefix, path);
  }
  for (char *p = prefix + 1;; p++)
    if (*p == '/' || !*p) {
      char c = *p;
      *p = 0;
      if (lstat(prefix, &s) || !S_ISDIR(s.st_mode)) {
        *p = c;
        return XW_STORAGE_BOUNDARY;
      }
      *p = c;
      if (!c)
        break;
    }
  strcpy(d->path, resolved);
  d->fd = open(resolved, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
  if (d->fd < 0)
    return XW_STORAGE_BOUNDARY;
#endif
  if (fstat(d->fd, &s) || !S_ISDIR(s.st_mode) ||
      xw_stock_fcntl(d->fd, F_SETFD, FD_CLOEXEC) < 0) {
    close_directory(d);
    return XW_STORAGE_BOUNDARY;
  }
  d->device = s.st_dev;
  d->inode = s.st_ino;
  rc = check_directory(a, d);
  if (rc)
    close_directory(d);
  return rc;
}
static int child_path(struct directory *d, const char *name, char out[2200]) {
  int n = snprintf(out, 2200, "/proc/self/fd/%d/%s", d->fd, name);
  return n < 0 || n >= 2200 ? XW_STORAGE_INVALID : 0;
}
static int regular(int fd, struct directory *d, size_t limit, struct stat *s) {
  return fstat(fd, s) || !S_ISREG(s->st_mode) || s->st_nlink != 1 ||
                 s->st_size < 0 || (unsigned long long)s->st_size > limit ||
                 (unsigned long long)s->st_dev != d->device
             ? XW_STORAGE_BOUNDARY
             : 0;
}
static int read_file(xw_app *a, const char *name, void *out, size_t cap,
                     size_t *size, int resource) {
  struct directory d;
  struct stat s;
  char path[2200];
  int fd = -1, rc;
  size_t used = 0;
  if (size)
    *size = 0;
  if (!a || !a->program || !out || !size || !xw_filename_valid(name) ||
      cap > (resource ? 1048576u : 65536u))
    return XW_STORAGE_INVALID;
  rc = open_directory(a, &d, resource);
  if (rc)
    return rc;
  if ((rc = child_path(&d, name, path)))
    goto done;
  fd = open(path, O_RDONLY | O_NONBLOCK | O_NOFOLLOW);
  if (fd < 0) {
    rc = errno == ENOENT ? XW_STORAGE_MISSING : XW_STORAGE_BOUNDARY;
    goto done;
  }
  rc = regular(fd, &d, cap, &s);
  if (rc)
    goto done;
  while (used < (size_t)s.st_size) {
    if ((rc = check_directory(a, &d)))
      goto done;
    ssize_t n = read(fd, (char *)out + used, (size_t)s.st_size - used);
    if (n < 0 && errno == EINTR)
      continue;
    if (n <= 0) {
      rc = XW_STORAGE_IO;
      goto done;
    }
    used += (size_t)n;
  }
  {
    unsigned char extra;
    ssize_t n = read(fd, &extra, 1);
    if (n != 0) {
      rc = XW_STORAGE_BOUNDARY;
      goto done;
    }
  }
  rc = check_directory(a, &d);
  if (!rc)
    *size = used;
done:
  if (fd >= 0 && close(fd) && !rc)
    rc = XW_STORAGE_IO;
  if (close_directory(&d) && !rc)
    rc = XW_STORAGE_IO;
  if (rc)
    *size = 0;
  return rc;
}
int xw_data_read(xw_app *a, const char *name, void *out, size_t cap,
                 size_t *size) {
  return read_file(a, name, out, cap, size, 0);
}
int xw_resource_read(xw_app *a, const char *name, void *out, size_t cap,
                     size_t *size) {
  return read_file(a, name, out, cap, size, 1);
}
int xw_data_write(xw_app *a, const char *name, const void *data, size_t size) {
  struct directory d;
  struct stat s;
  struct statvfs space;
  char path[2200], temp[2200], lockpath[2200];
  int rc, fd = -1, lock = -1, created = 0, published = 0;
  size_t written = 0;
  if (!a || !a->program || (!data && size) || size > 65536 ||
      !xw_filename_valid(name))
    return XW_STORAGE_INVALID;
  rc = open_directory(a, &d, 0);
  if (rc)
    return rc;
  if (child_path(&d, name, path) || child_path(&d, ".sdk-write.tmp", temp) ||
      child_path(&d, ".sdk.lock", lockpath)) {
    rc = XW_STORAGE_INVALID;
    goto done;
  }
  if ((rc = check_directory(a, &d)))
    goto done;
  lock = open(lockpath, O_RDWR | O_CREAT | O_NOFOLLOW | O_NONBLOCK, 0600);
  if (lock < 0 || regular(lock, &d, 0, &s) || flock(lock, LOCK_EX | LOCK_NB)) {
    rc = XW_STORAGE_BOUNDARY;
    goto done;
  }
  if (!lstat(path, &s)) {
    if (!S_ISREG(s.st_mode) || s.st_nlink != 1 ||
        (unsigned long long)s.st_dev != d.device) {
      rc = XW_STORAGE_BOUNDARY;
      goto done;
    }
  } else if (errno != ENOENT) {
    rc = XW_STORAGE_BOUNDARY;
    goto done;
  }
  if (xw_stock_fstatvfs(d.fd, &space) || space.f_frsize < 512 ||
      space.f_frsize > 1048576 || space.f_bavail > ~0ULL / space.f_frsize ||
      space.f_bavail * space.f_frsize <
          1048576ULL + size + 3 * space.f_frsize) {
    rc = XW_STORAGE_SPACE;
    goto done;
  }
  if ((rc = check_directory(a, &d)))
    goto done;
  fd = open(temp, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK, 0600);
  if (fd < 0) {
    rc = XW_STORAGE_BOUNDARY;
    goto done;
  }
  created = 1;
  if (regular(fd, &d, 0, &s)) {
    rc = XW_STORAGE_BOUNDARY;
    goto done;
  }
  while (written < size) {
    if ((rc = check_directory(a, &d)))
      goto done;
    ssize_t n = write(fd, (const char *)data + written, size - written);
    if (n < 0 && errno == EINTR)
      continue;
    if (n <= 0) {
      rc = XW_STORAGE_IO;
      goto done;
    }
    written += (size_t)n;
  }
  if (fsync(fd)) {
    rc = XW_STORAGE_IO;
    goto done;
  }
  if (close(fd)) {
    fd = -1;
    rc = XW_STORAGE_IO;
    goto done;
  }
  fd = -1;
  if ((rc = check_directory(a, &d)))
    goto done;
  if (rename(temp, path)) {
    rc = XW_STORAGE_IO;
    goto done;
  }
  created = 0;
  published = 1;
  if (fsync(d.fd) || check_directory(a, &d))
    rc = XW_STORAGE_UNCERTAIN;
done:
  if (fd >= 0 && close(fd) && !rc)
    rc = XW_STORAGE_IO;
  /* Never perform further cleanup writes after ownership is lost. */
  if (created && !check_directory(a, &d) && unlink(temp) && !rc)
    rc = XW_STORAGE_IO;
  if (lock >= 0 && close(lock) && !rc)
    rc = published ? XW_STORAGE_UNCERTAIN : XW_STORAGE_IO;
  if (close_directory(&d) && !rc)
    rc = published ? XW_STORAGE_UNCERTAIN : XW_STORAGE_IO;
  return rc;
}

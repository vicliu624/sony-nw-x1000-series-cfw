#include "pcm_owner.h"
#include <dirent.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static int number(const char *s, unsigned *out) {
  unsigned n = 0;
  if (!*s)
    return 0;
  for (; *s; s++) {
    if (*s < '0' || *s > '9' || n > 214748364u || (n == 214748364u && *s > '7'))
      return 0;
    n = n * 10 + (unsigned)(*s - '0');
  }
  *out = n;
  return 1;
}
static int sound_node(const char *s) {
  return !strcmp(s, "/dev/sound/dsp") || !strcmp(s, "/dev/sound/dsp0") ||
         !strcmp(s, "/dev/dsp") || !strcmp(s, "/dev/dsp0");
}
int hb_pcm_find_owners(const char *proc, struct hb_pcm_owners *out,
                       volatile int *stop) {
  if (!proc || !out || !stop)
    return -1;
  memset(out, 0, sizeof(*out));
  if (*stop) {
    out->cancelled = 1;
    return 0;
  }
  DIR *processes = opendir(proc);
  if (!processes) {
    out->unreadable++;
    return -1;
  }
  struct dirent *process;
  while (out->processes < 128 && out->count < 8 &&
         (process = readdir(processes))) {
    if (*stop) {
      out->cancelled = 1;
      break;
    }
    unsigned pid;
    if (!number(process->d_name, &pid))
      continue;
    out->processes++;
    char directory[512], path[640], target[192];
    if (snprintf(directory, sizeof directory, "%s/%u/fd", proc, pid) >=
        (int)sizeof directory) {
      out->unreadable++;
      continue;
    }
    DIR *fds = opendir(directory);
    if (!fds) {
      out->unreadable++;
      continue;
    }
    struct dirent *entry;
    unsigned examined = 0;
    while (examined < 256 && out->count < 8 && (entry = readdir(fds))) {
      if (*stop) {
        out->cancelled = 1;
        break;
      }
      unsigned fd;
      if (!number(entry->d_name, &fd))
        continue;
      examined++;
      if (snprintf(path, sizeof path, "%s/%u", directory, fd) >=
          (int)sizeof path)
        continue;
      ssize_t n = readlink(path, target, sizeof(target) - 1);
      if (n < 0) {
        out->unreadable++;
        continue;
      }
      if (n == (ssize_t)sizeof(target) - 1)
        continue;
      target[n] = 0;
      if (!sound_node(target))
        continue;
      struct hb_pcm_owner *owner = &out->entries[out->count++];
      owner->pid = pid;
      owner->fd = fd;
      snprintf(path, sizeof path, "%s/%u/exe", proc, pid);
      n = readlink(path, target, sizeof(target) - 1);
      if (n < 0) {
        strcpy(owner->name, "UNKNOWN");
        continue;
      }
      target[n] = 0;
      const char *name = strrchr(target, '/');
      name = name ? name + 1 : target;
      snprintf(owner->name, sizeof owner->name, "%.47s", name);
    }
    closedir(fds);
  }
  closedir(processes);
  return 0;
}

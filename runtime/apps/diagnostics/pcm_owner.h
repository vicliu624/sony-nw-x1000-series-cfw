#ifndef HB_PCM_OWNER_H
#define HB_PCM_OWNER_H
struct hb_pcm_owner {
  unsigned pid, fd;
  char name[48];
};
struct hb_pcm_owners {
  struct hb_pcm_owner entries[8];
  unsigned count, processes, unreadable;
  int cancelled;
};
/* Read-only /proc metadata, bounded traversal. Never open a sound node,
 * signal a process, attach a debugger, or read process memory/cmdline. */
int hb_pcm_find_owners(const char *proc, struct hb_pcm_owners *,
                       volatile int *stop);
#endif

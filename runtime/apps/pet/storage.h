#ifndef HB_PET_STORAGE_H
#define HB_PET_STORAGE_H
#include "pet.h"
struct pet_storage {
  int fd, slot;
  unsigned generation;
  unsigned long long device, inode;
};
/* 1 loaded, 0 new, -1 unavailable, -2 corrupt. No system-path fallback. */
int pet_storage_open(struct pet_storage *, struct pet_state *);
int pet_storage_save(struct pet_storage *, const struct pet_state *,
                     volatile int *stop);
void pet_storage_close(struct pet_storage *);
#endif

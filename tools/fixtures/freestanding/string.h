/* Standard declarations for freestanding compiler-only fixture checks. */
#ifndef XW_FIXTURE_STRING_H
#define XW_FIXTURE_STRING_H
#include <stddef.h>
void *memcpy(void *,const void *,size_t);
void *memset(void *,int,size_t);
int memcmp(const void *,const void *,size_t);
int strcmp(const char *,const char *);
size_t strlen(const char *);
#endif

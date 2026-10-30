#define _POSIX_C_SOURCE 200809L
#include <time.h>
int hb_monotonic_millis(unsigned long long *out){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return -1;*out=(unsigned long long)t.tv_sec*1000u+(unsigned long long)t.tv_nsec/1000000u;return 0;}

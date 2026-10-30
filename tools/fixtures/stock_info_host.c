/* Freestanding memory primitives for the original-info ARM replay only. */
#include "stock_host_image.c"
#include <stddef.h>
void *memcpy(void *out,const void *in,size_t n){unsigned char *p=out;const unsigned char *q=in;while(n--)*p++=*q++;return out;}
void *memset(void *out,int c,size_t n){unsigned char *p=out;while(n--)*p++=(unsigned char)c;return out;}

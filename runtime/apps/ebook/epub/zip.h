#ifndef ER_EPUB_ZIP_H
#define ER_EPUB_ZIP_H
#include <stdint.h>
#include <stdio.h>
struct ez_entry {char name[256];uint32_t crc,compressed,bytes,offset;unsigned method,flags;};
struct ez_zip {FILE*file;uint32_t bytes,count;struct ez_entry *entries;};
int ez_open(struct ez_zip*,FILE*,uint32_t);
void ez_close(struct ez_zip*);
int ez_find(const struct ez_zip*,const char*);
unsigned char*ez_read(struct ez_zip*,const char*,unsigned,unsigned*);
int ez_resolve(const char*,const char*,char[256],char[128]);
uint32_t ez_crc(const unsigned char*,unsigned);
#endif

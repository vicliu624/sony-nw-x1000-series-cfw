#ifndef HB_STORE_PACKAGE_H
#define HB_STORE_PACKAGE_H
struct hb_package {
 char id[33],name[49],version[33];
 unsigned bytes;
 unsigned char sha256[32];
};
enum hb_package_result {
 HB_PACKAGE_OK=0, HB_PACKAGE_MANIFEST=-1, HB_PACKAGE_IO=-2,
 HB_PACKAGE_SIZE=-3, HB_PACKAGE_ELF=-4, HB_PACKAGE_HASH=-5
};
/* Pure C helpers. The filesystem adapter must reject links/non-regular files
 * and establish the app directory before invoking these routines. */
int hb_package_parse(const unsigned char *,unsigned,const char *expected_id,struct hb_package *);
int hb_package_verify_program(const struct hb_package *,void *,
                              int (*read_chunk)(void *,unsigned char *,unsigned));
#endif

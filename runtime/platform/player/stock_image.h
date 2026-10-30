/* Compatibility guard for private in-process JP1.11 bindings. */
#ifndef XW_STOCK_IMAGE_H
#define XW_STOCK_IMAGE_H
#include <stdint.h>
int xw_stock_image_match(uint32_t start,uint32_t bytes,const unsigned char digest[32]);
#endif

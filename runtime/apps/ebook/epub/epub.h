#ifndef ER_EPUB_H
#define ER_EPUB_H
#include "zip.h"
#include "xml.h"
#include "../../../../sdk/include/x1000/services/unicode_font.h"
#define EP_ITEMS 1024
#define EP_SPINE 512
#define EP_TOC 1024
#define EP_STYLES 256
#define EP_TOKENS 262144
#define EP_DRAW 4096
enum {EP_BOLD=1,EP_ITALIC=2,EP_UNDERLINE=4,EP_SUP=8,EP_SUB=16,EP_PRE=32,EP_HIDDEN=64,EP_BREAK_BEFORE=128};
enum {EPUB_START=0x110000,EP_END,EP_BR,EP_IMAGE=0x120000};
struct ep_style {int font,align,indent,top,bottom,left,right,height,imgw,imgh;unsigned flags;uint16_t color;unsigned char colored;};
struct ep_props {struct ep_style value;uint32_t mask;int font_relative;};
struct ep_rule {char selector[128];struct ep_props props;unsigned specificity;};
struct ep_item {char id[96],path[256];unsigned kind,nav;};
struct ep_nav {char title[160],path[256],fragment[128];unsigned depth;};
struct ep_token {uint32_t cp;uint16_t style,link;};
struct ep_anchor {char id[128];uint32_t token;};
struct ep_image {char path[256];unsigned width,height;};
struct ep_link {char path[256],fragment[128];};
struct ep_doc {struct ep_token*tokens;unsigned count,capacity;struct ep_style styles[EP_STYLES];unsigned style_count;struct ep_anchor anchors[1024];unsigned anchor_count;struct ep_image images[512];unsigned image_count;struct ep_link links[512];unsigned link_count;char title[160];};
struct ep_op {int16_t x,y,w,h;uint32_t cp;uint16_t style,link;};
struct ep_page {struct ep_op ops[EP_DRAW];unsigned count;uint32_t next;};
struct ep_book {struct ez_zip zip;struct ep_item items[EP_ITEMS];unsigned item_count,spine[EP_SPINE],spine_count,chapter;struct ep_nav toc[EP_TOC];unsigned toc_count;struct ep_rule rules[256];unsigned rule_count;struct ep_doc*doc;struct ep_page page;char title[160],error[128];unsigned warnings;volatile int*stop;unsigned char*cached_image;int cached_id,cached_w,cached_h;};
struct ep_book*epub_open(FILE*,uint32_t);
void epub_close(struct ep_book*);
int ep_load(struct ep_book*,unsigned);
int ep_layout(struct ep_book*,uint32_t,unsigned,const struct dx_font*,uint32_t);
void ep_render(struct ep_book*,const struct dx_font*,uint16_t*,unsigned,uint16_t,uint16_t);
int ep_previous(struct ep_book*,uint32_t,unsigned,const struct dx_font*,uint32_t*);
int ep_goto(struct ep_book*,const char*,const char*,uint32_t*);
void ep_css(struct ep_book*,const char*,unsigned);
struct ep_style ep_style_for(struct ep_book*,const struct ex_tag*,const struct ep_style*);
int ep_parse_doc(struct ep_book*,struct ep_doc*,const char*,unsigned);
unsigned char*ep_pixels(struct ep_book*,unsigned,int*,int*);
void ep_drop_image(struct ep_book*);
void ep_inline_props(struct ep_props*,const char*);
#endif

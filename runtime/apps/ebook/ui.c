#include "ui.h"
#include "epub/epub.h"
#include "../emulators/platform.h"
#include <stdio.h>
#include <string.h>
static const unsigned sizes[] = {16, 20, 24};
static const uint16_t paper[] = {0xffde, 0xf73a, 0x1106},
                      ink[] = {0x2987, 0x3945, 0xdedb},
                      muted[] = {0x7bef, 0x8bae, 0x8c93};
static const uint16_t accent = 0x33ce;
static void text(struct er_ui *u, int x, int y, const char *s, unsigned size,
                 uint16_t c, unsigned width) {
  er_text(&u->font, ep_canvas, x, y, s, size, c, width);
}
static void panel(int x, int y, int w, int h, uint16_t c) {
  ep_box(x + 4, y, w - 8, h, c);
  ep_box(x, y + 4, w, h - 8, c);
  ep_box(x + 1, y + 2, w - 2, h - 4, c);
}
static void button(struct er_ui *u, int x, int y, int w, const char *label,
                   int active) {
  panel(x, y + 2, w, 36, 0xce79);
  panel(x, y, w, 36, active ? accent : 0xffff);
  unsigned length = 0;
  const char *p = label;
  while (*p)
    length += dx_width(&u->font, dx_utf8(&p));
  text(u, x + (w - (int)length) / 2, y + 10, label, 16,
       active ? 0xffff : ink[0], w - 8);
}
static const char *encoding(unsigned n) {
  static const char *names[] = {"自动", "UTF-8", "GB18030", "UTF-16 LE",
                                "UTF-16 BE"};
  return n <= ER_UTF16BE ? names[n] : "未知";
}
static void title(struct er_ui *u, char out[256]) {
  if(u->book.epub&&u->book.epub->title[0]){snprintf(out,256,"%s",u->book.epub->title);return;}
  strcpy(out, u->items[u->selected].name);
  size_t n = strlen(out);
  if(n>=5&&!strcasecmp(out+n-5,".epub"))out[n-5]=0;else if(n>=4)out[n-4]=0;
}
int er_ui_init(struct er_ui *u, const char *font, const char *map) {
  memset(u, 0, sizeof(*u));
  u->pressed = -1;
  u->font_size = 20;
  u->book_root = "/contents/HOMEBREW/data/ebook/books";
  if (!dx_font_open(&u->font, font)) {
    strcpy(u->error, "FONT FILE MISSING OR DAMAGED");
    u->mode = ER_ERROR;
    return 0;
  }
  if (!er_maps_open(&u->maps, map)) {
    strcpy(u->error, "ENCODING MAP MISSING OR DAMAGED");
    u->mode = ER_ERROR;
    return 0;
  }
  u->mode = ER_SHELF;
  return 1;
}
void er_ui_shelf(struct er_ui *u) {
  if (!er_storage_open(&u->storage)) {
    snprintf(u->notice, sizeof u->notice, "用户存储未就绪");
    u->count = 0;
    return;
  }
  int n = er_books_scan(u->items);
  u->count = n < 0 ? 0 : (unsigned)n;
  if (n < 0)
    snprintf(u->notice, sizeof u->notice, "无法读取书籍目录");
  else if (u->storage.warning)
    snprintf(u->notice, sizeof u->notice, "可以阅读，暂不能保存进度");
  else
    u->notice[0] = 0;
}
static int reflow(struct er_ui *u) {
  uint32_t aligned;
  if (!er_align(&u->book, u->book.current, &aligned))
    return 0;
  u->book.current = aligned;
  return er_page_at(&u->book, aligned, &u->page);
}
int er_ui_select(struct er_ui *u, unsigned index) {
  if (index >= u->count)
    return 0;
  char path[512];
  snprintf(path, sizeof path, "%s/%s", u->book_root, u->items[index].name);
  if (!er_open(&u->book, path, ER_AUTO, &u->maps)) {
    snprintf(u->notice, sizeof u->notice, "无法打开书籍，请检查文件");
    return 0;
  }
  u->selected = index;
  struct er_mark *m = er_state_find(&u->storage.state, u->book.identity);
  if(m&&m->bytes==u->book.bytes&&m->size&&m->format==!!u->book.epub){
    if(u->book.epub){if(m->chapter<u->book.epub->spine_count&&ep_load(u->book.epub,m->chapter))u->book.current=m->offset;}
    else if(m->offset<=m->bytes){unsigned requested=m->encoding;if(requested!=u->book.requested){er_close(&u->book);if(!er_open(&u->book,path,requested,&u->maps))return 0;}u->book.current=m->offset;}
    u->font_size=m->size;u->theme=m->theme;
  }
  u->book.font = &u->font;
  u->book.size = u->font_size;
  u->book.stop = &ep_stop;
  if (!reflow(u)) {
    er_close(&u->book);
    snprintf(u->notice, sizeof u->notice, "正文读取失败");
    return 0;
  }
  u->mode = ER_READING;
  u->notice[0] = 0;
  u->dirty = u->discard = 0;
  u->history_count = 0;
  u->link_return=0;
  return 1;
}
int er_ui_save(struct er_ui *u) {
  if (!u->book.file || !u->dirty)
    return 1;
  struct er_state previous = u->storage.state;
  er_state_update(&u->storage.state, &u->book, u->theme);
  if (!er_storage_save(&u->storage)) {
    u->storage.state = previous;
    snprintf(u->notice, sizeof u->notice, "保存失败，再点书架可不保存返回");
    u->discard = 1;
    return 0;
  }
  u->dirty = 0;
  return 1;
}
static void shelf_back(struct er_ui *u) {
  if (!u->discard && !er_ui_save(u)) {
    u->mode = ER_MENU;
    return;
  }
  er_close(&u->book);
  u->mode = ER_SHELF;
  u->discard = u->dirty = 0;
}
void er_ui_close(struct er_ui *u) {
  er_close(&u->book);
  dx_font_close(&u->font);
  er_maps_close(&u->maps);
}
static void epub_turn(struct er_ui*u,int forward){struct ep_book*b=u->book.epub;unsigned old_chapter=b->chapter,chapter=old_chapter;uint32_t old=u->book.current,at=old;int cached=!forward&&u->history_count;
 if(forward){if(u->page.next<b->doc->count)at=u->page.next;else{if(chapter+1>=b->spine_count){strcpy(u->notice,"已经是最后一页");return;}chapter++;at=0;}}
 else if(cached){chapter=u->history_chapter[u->history_count-1];at=u->history[u->history_count-1];}
 else if(old){if(!ep_previous(b,old,u->book.size,&u->font,&at))return;}
 else if(chapter){chapter--;if(!ep_load(b,chapter))return;if(!ep_previous(b,b->doc->count,u->book.size,&u->font,&at))return;}
 else{strcpy(u->notice,"已经是第一页");return;}
 if(chapter!=b->chapter&&!ep_load(b,chapter)){strcpy(u->notice,"无法读取相邻章节");return;}
 if(!er_page_at(&u->book,at,&u->page)){strcpy(u->notice,"章节排版失败");return;}
 if(forward){if(u->history_count==128){memmove(u->history,u->history+1,127*sizeof(uint32_t));memmove(u->history_chapter,u->history_chapter+1,127*sizeof(uint16_t));u->history_count=127;}u->history[u->history_count]=old;u->history_chapter[u->history_count++]=(uint16_t)old_chapter;}else if(cached)u->history_count--;
 u->book.current=at;u->dirty=1;u->notice[0]=0;
}
static unsigned epub_percent(struct er_ui*u){struct ep_book*b=u->book.epub;uint64_t total=0,before=0,part=0;for(unsigned i=0;i<b->spine_count;i++){int z=ez_find(&b->zip,b->items[b->spine[i]].path);unsigned bytes=z<0?0:b->zip.entries[z].bytes;if(i<b->chapter)before+=bytes;if(i==b->chapter)part=b->doc->count?(uint64_t)bytes*u->page.next/b->doc->count:bytes;total+=bytes;}return total?(unsigned)((before+part)*100/total):0;}
static int epub_jump(struct er_ui*u,unsigned percent){struct ep_book*b=u->book.epub;uint64_t total=0,before=0;for(unsigned i=0;i<b->spine_count;i++){int z=ez_find(&b->zip,b->items[b->spine[i]].path);if(z>=0)total+=b->zip.entries[z].bytes;}uint64_t target=total*percent/100;unsigned chapter=b->spine_count-1;uint32_t at=0;for(unsigned i=0;i<b->spine_count;i++){int z=ez_find(&b->zip,b->items[b->spine[i]].path);unsigned n=z<0?0:b->zip.entries[z].bytes;if(target<before+n||i+1==b->spine_count){chapter=i;if(!ep_load(b,chapter))return 0;if(percent==100){if(!ep_previous(b,b->doc->count,u->book.size,&u->font,&at))return 0;}else at=n?(uint32_t)((target-before)*b->doc->count/n):0;break;}before+=n;}if(!er_page_at(&u->book,at,&u->page))return 0;u->book.current=at;u->history_count=0;u->dirty=1;return 1;}
void er_ui_turn(struct er_ui *u, int forward) {
  if(u->mode==ER_READING&&u->book.epub){epub_turn(u,forward);return;}
  if (u->mode != ER_READING)
    return;
  uint32_t at = u->book.current;
  int cached = !forward && u->history_count;
  if (forward) {
    if (u->page.next >= u->book.bytes) {
      snprintf(u->notice, sizeof u->notice, "已经是最后一页");
      return;
    }
    at = u->page.next;
  } else if (cached)
    at = u->history[u->history_count - 1];
  else if (!er_previous(&u->book, at, &at)) {
    snprintf(u->notice, sizeof u->notice, "翻页失败");
    return;
  }
  if (at == u->book.current) {
    snprintf(u->notice, sizeof u->notice, "已经是第一页");
    return;
  }
  struct er_page next;
  if (er_page_at(&u->book, at, &next)) {
    if (forward) {
      if (u->history_count == 128) {
        memmove(u->history, u->history + 1, 127 * sizeof(uint32_t));
        u->history_count = 127;
      }
      u->history[u->history_count++] = u->book.current;
    } else if (cached)
      u->history_count--;
    u->page = next;
    u->book.current = at;
    u->dirty = 1;
    u->notice[0] = 0;
  } else
    snprintf(u->notice, sizeof u->notice, "正文读取失败");
}
int er_ui_hit(int mode, int x, int y) {
  if (x < 0 || x >= 240 || y < 0 || y >= 432)
    return -1;
  if (y < 30 && x >= 176)
    return 20;
  if (mode == ER_ERROR)
    return y >= 384 ? 20 : -1;
  if (mode == ER_SHELF || mode==ER_TOC) {
    if (y >= 56 && y < 356 && x >= 8 && x < 232)
      return 10 + (y - 56) / 60;
    if (y >= 384 && y < 424)
      return x < 84 ? 21 : x >= 156 ? 22 : -1;
    return -1;
  }
  if (mode == ER_MENU) {
    if (y >= 54 && y < 318)
      return 30 + (y - 54) / 44;
    return -1;
  }
  if (mode == ER_JUMP) {
    if (y >= 188 && y < 256)
      return 40;
    if (y >= 272 && y < 314)
      return x < 90 ? 41 : x >= 150 ? 42 : -1;
    if (y >= 334 && y < 376)
      return 43;
    return -1;
  }
  if (mode == ER_READING) {
    if (y >= 30 && y < 384) {
      if (x < 80)
        return 21;
      if (x >= 160)
        return 22;
      return 23;
    }
    if (y >= 384)
      return 23;
  }
  return -1;
}
void er_ui_touch(struct er_ui *u, int x, int y) {
  if(u->mode==ER_READING&&u->book.epub&&y>=56&&y<382){
    struct ep_book*b=u->book.epub;
    for(unsigned i=0;i<b->page.count;i++){struct ep_op*op=b->page.ops+i;
      if(op->link&&x>=op->x-3&&x<op->x+op->w+3&&y>=op->y-3&&y<op->y+op->h+3){
        struct ep_link target=b->doc->links[op->link-1];unsigned chapter=b->chapter;uint32_t old=u->book.current,at;
        if(ep_goto(b,target.path,target.fragment,&at)&&er_page_at(&u->book,at,&u->page)){u->link_chapter=chapter;u->link_token=old;u->link_return=1;u->book.current=at;u->dirty=1;u->history_count=0;}
        else strcpy(u->notice,"链接目标无法打开");return;
      }
    }
  }
  int h = er_ui_hit(u->mode, x, y);
  if (h < 0)
    return;
  if (h == 20) {
    if (u->mode == ER_SHELF || u->mode == ER_ERROR)
      u->quit = 1;
    else if (u->mode == ER_READING)
      shelf_back(u);
    else
      u->mode = ER_READING;
    return;
  }
  if(u->mode==ER_TOC){struct ep_book*b=u->book.epub;if(h>=10&&h<15){unsigned i=u->toc_page*5+(unsigned)(h-10);if(i<b->toc_count){uint32_t at;if(ep_goto(b,b->toc[i].path,b->toc[i].fragment,&at)&&er_page_at(&u->book,at,&u->page)){u->book.current=at;u->mode=ER_READING;u->history_count=0;u->dirty=1;}else strcpy(u->notice,"目录目标无法打开");}}else if(h==21&&u->toc_page)u->toc_page--;else if(h==22&&(u->toc_page+1)*5<b->toc_count)u->toc_page++;return;}
  if (u->mode == ER_SHELF) {
    if (h >= 10 && h < 15) {
      unsigned i = u->shelf_page * 5 + (unsigned)(h - 10);
      if (i < u->count)
        er_ui_select(u, i);
    } else if (h == 21 && u->shelf_page)
      u->shelf_page--;
    else if (h == 22 && (u->shelf_page + 1) * 5 < u->count)
      u->shelf_page++;
    return;
  }
  if (u->mode == ER_READING) {
    if (h == 21)
      er_ui_turn(u, 0);
    else if (h == 22)
      er_ui_turn(u, 1);
    else if (h == 23)
      u->mode = ER_MENU;
    return;
  }
  if (u->mode == ER_MENU) {
    if (h == 30) {
      if(u->link_return&&u->book.epub){if(!ep_load(u->book.epub,u->link_chapter)||!er_page_at(&u->book,u->link_token,&u->page)){strcpy(u->notice,"无法返回原阅读位置");return;}u->book.current=u->link_token;u->link_return=0;u->history_count=0;u->dirty=1;}
      u->mode = ER_READING;
      u->notice[0] = 0;
    } else if (h == 31) {
      unsigned i = 0;
      while (i < 2 && sizes[i] != u->font_size)
        i++;
      u->font_size = sizes[(i + 1) % 3];
      u->book.size = u->font_size;
      u->history_count = 0;
      if (reflow(u))
        u->dirty = 1;
    } else if (h == 32) {
      u->theme = (u->theme + 1) % 3;
      u->dirty = 1;
    } else if (h == 33) {
      if(u->book.epub){u->toc_page=0;u->mode=ER_TOC;return;}
      char path[512];
      snprintf(path, sizeof path, "%s/%s", u->book_root,
               u->items[u->selected].name);
      unsigned n = (u->book.requested + 1) % 5;
      uint32_t at = u->book.current;
      er_close(&u->book);
      if (!er_open(&u->book, path, n, &u->maps)) {
        u->mode = ER_SHELF;
        snprintf(u->notice, sizeof u->notice, "所选编码无法打开书籍");
        return;
      }
      u->book.current = at > u->book.bytes ? u->book.start : at;
      u->book.size = u->font_size;
      u->book.font = &u->font;
      u->book.stop = &ep_stop;
      u->history_count = 0;
      if (reflow(u))
        u->dirty = 1;
    } else if (h == 34) {
      u->jump = u->book.epub?epub_percent(u):
          u->book.bytes
              ? (unsigned)((uint64_t)u->book.current * 100 / u->book.bytes)
              : 0;
      u->mode = ER_JUMP;
    } else if (h == 35)
      shelf_back(u);
    return;
  }
  if (u->mode == ER_JUMP) {
    if (h == 40) {
      if (x < 18)
        x = 18;
      if (x > 222)
        x = 222;
      u->jump = (unsigned)(x - 18) * 100 / 204;
    } else if (h == 41)
      u->jump = u->jump > 10 ? u->jump - 10 : 0;
    else if (h == 42)
      u->jump = u->jump < 90 ? u->jump + 10 : 100;
    else if (h == 43) {
      uint32_t at;
      if(u->book.epub){if(epub_jump(u,u->jump)){u->mode=ER_READING;u->notice[0]=0;}return;}
      if (u->jump == 100) {
        if (!er_previous(&u->book, u->book.bytes, &at))
          return;
      } else if (!er_align(&u->book,
                           (uint32_t)((uint64_t)u->book.bytes * u->jump / 100),
                           &at))
        return;
      if (er_page_at(&u->book, at, &u->page)) {
        u->book.current = at;
        u->history_count = 0;
        u->dirty = 1;
        u->mode = ER_READING;
        u->notice[0] = 0;
      }
    }
  }
}
void er_ui_render(struct er_ui *u) {
  unsigned theme = u->theme <= 2 ? u->theme : 0;
  uint16_t bg = paper[theme], fg = ink[theme];
  ep_box(0, 0, 240, 432, bg);
  ep_box(0, 0, 240, 1, accent);
  if (u->mode == ER_ERROR) {
    ep_box(0, 0, 240, 30, accent);
    ep_text(8, 10, "EBOOK READER", 0xffff);
    ep_text(184, 10, "APPS", 0xffff);
    ep_text(8, 80, u->error, ink[0]);
    ep_text(8, 106, "COPY THE COMPLETE APP FOLDER", ink[0]);
    ep_box(0, 384, 240, 48, accent);
    ep_text(72, 404, "BACK TO APPS", 0xffff);
    return;
  }
  text(u, 12, 10,
       u->mode == ER_SHELF  ? "书架"
       : u->mode == ER_MENU ? "阅读设置"
       : u->mode == ER_TOC ? "章节目录"
       : u->mode == ER_JUMP ? "跳转进度"
                            : "阅读",
       16, accent, 160);
  text(u, 184, 10,
       u->mode == ER_SHELF     ? "APPS"
       : u->mode == ER_READING ? "书架"
                               : "返回",
       16, fg, 48);
  ep_box(8, 34, 224, 1, theme == 2 ? 0x31e8 : 0xded9);
  if (u->mode == ER_SHELF) {
    char meta[48];
    snprintf(meta, sizeof meta, "本地书籍  /  %u本", u->count);
    text(u, 12, 38, meta, 16, muted[theme], 224);
    static const uint16_t covers[] = {0x33ce, 0x39ad, 0xb30b, 0xc48c, 0x72f2};
    for (unsigned i = 0; i < 5 && u->shelf_page * 5 + i < u->count; i++) {
      unsigned n = u->shelf_page * 5 + i;
      int y = 56 + (int)i * 60;
      panel(8, y, 224, 54, theme == 2 ? 0x1947 : 0xffff);
      ep_box(15, y + 7, 25, 39, covers[n % 5]);
      ep_box(18, y + 7, 2, 39, 0xffff);
      ep_box(23, y + 17, 12, 1, 0xffff);
      ep_box(23, y + 22, 9, 1, 0xffff);
      char name[256];
      strcpy(name, u->items[n].name);
      size_t ext=strlen(name)>=5&&!strcasecmp(name+strlen(name)-5,".epub")?5:4;name[strlen(name)-ext]=0;
      text(u, 50, y + 9, name, 16, fg, 176);
      const char*kind=strlen(u->items[n].name)>=5&&!strcasecmp(u->items[n].name+strlen(u->items[n].name)-5,".epub")?"EPUB":"TXT";
      if (u->items[n].bytes >= 1048576)
        snprintf(meta, sizeof meta, "%s  %u.%u MB",kind,
                 u->items[n].bytes / 1048576,
                 u->items[n].bytes % 1048576 * 10 / 1048576);
      else
        snprintf(meta, sizeof meta, "%s  %u KB",kind,
                 (u->items[n].bytes + 1023) / 1024);
      text(u, 50, y + 31, meta, 16, muted[theme], 176);
    }
    if (!u->count) {
      text(u, 32, 142, "书架还是空的", 20, fg, 200);
      text(u, 8, 188, "请放入ebook/books文件夹", 16, muted[theme], 224);
      text(u, 8, 216, "支持TXT与EPUB", 16, muted[theme], 224);
    }
    if (u->notice[0])
      text(u, 8, 361, u->notice, 16, accent, 224);
    button(u, 8, 384, 72, "上一页", u->pressed == 21);
    button(u, 160, 384, 72, "下一页", u->pressed == 22);
    char page[24];
    snprintf(page, sizeof page, "%u/%u", u->shelf_page + 1,
             u->count ? (u->count + 4) / 5 : 1);
    text(u, 96, 395, page, 16, muted[theme], 56);
    return;
  }
  if (u->mode == ER_READING) {
    char name[256];
    title(u, name);
    text(u, 8, 36, name, 16, muted[theme], 224);
    if(u->book.epub){ep_render(u->book.epub,&u->font,ep_canvas,u->book.size,fg,bg);}
    else {
    if (!u->page.count)
      text(u, 48, 152, "这是一本空书", 20, muted[theme], 180);
    for (unsigned i = 0; i < u->page.count; i++)
      text(u, 8, 56 + (int)i * (u->book.size + 6), u->page.lines[i],
           u->book.size, fg, 224);
    }
    ep_box(8, 384, 224, 1, theme == 2 ? 0x31e8 : 0xded9);
    char meta[64];
    unsigned pct =
        u->book.epub ? epub_percent(u) : u->book.bytes ? (unsigned)((uint64_t)u->page.next * 100 / u->book.bytes)
                      : 100;
    snprintf(meta, sizeof meta, "%u%%", pct);
    text(u, 12, 397, meta, 16, muted[theme], 60);
    text(u, 88, 397, "轻点中间设置", 16, accent, 144);
    if (u->notice[0])
      text(u, 8, 365, u->notice, 16, accent, 224);
    return;
  }
  if(u->mode==ER_TOC){struct ep_book*b=u->book.epub;for(unsigned i=0;i<5&&u->toc_page*5+i<b->toc_count;i++){unsigned n=u->toc_page*5+i;int y=56+(int)i*60;panel(8,y,224,54,theme==2?0x1947:0xffff);unsigned indent=b->toc[n].depth*10;if(indent>40)indent=40;text(u,18+(int)indent,y+18,b->toc[n].title,16,fg,204-indent);}button(u,8,384,72,"上一页",u->pressed==21);button(u,160,384,72,"下一页",u->pressed==22);char n[24];snprintf(n,sizeof n,"%u/%u",u->toc_page+1,(b->toc_count+4)/5);text(u,96,395,n,16,muted[theme],56);return;}
  if (u->mode == ER_MENU) {
    char labels[6][80];
    strcpy(labels[0],u->link_return?"返回跳转前":"继续阅读");
    snprintf(labels[1], sizeof labels[1], "字号  %u px", u->font_size);
    snprintf(labels[2], sizeof labels[2], "配色  %s",
             theme == 0   ? "日间"
             : theme == 1 ? "护眼"
                          : "夜间");
    snprintf(labels[3], sizeof labels[3], "编码  %s%s%s",
             encoding(u->book.requested), u->book.requested ? "" : " / ",
             u->book.requested ? "" : encoding(u->book.encoding));
    if(u->book.epub)strcpy(labels[3],"章节目录");
    strcpy(labels[4], "跳转阅读进度");
    strcpy(labels[5], u->discard ? "不保存，返回书架" : "保存并返回书架");
    for (unsigned i = 0; i < 6; i++) {
      int y = 54 + (int)i * 44;
      panel(8, y, 224, 38,
            u->pressed == (int)(30 + i) ? accent
            : theme == 2                ? 0x1947
                                        : 0xffff);
      text(u, 22, y + 11, labels[i], 16,
           u->pressed == (int)(30 + i) ? 0xffff : fg, 202);
    }
    text(u, 8, 342, u->notice[0] ? u->notice : "左右翻页，中间打开设置", 16,
         accent, 224);
    return;
  }
  if (u->mode == ER_JUMP) {
    char percent[16];
    snprintf(percent, sizeof percent, "%u%%", u->jump);
    text(u, 86, 128, percent, 32, fg, 128);
    ep_box(18, 218, 204, 6, theme == 2 ? 0x31e8 : 0xded9);
    ep_box(18, 218, (int)(u->jump * 204 / 100), 6, accent);
    panel(12 + (int)(u->jump * 204 / 100), 209, 14, 24, accent);
    button(u, 16, 274, 64, "-10%", u->pressed == 41);
    button(u, 160, 274, 64, "+10%", u->pressed == 42);
    button(u, 16, 336, 208, "跳到这里", u->pressed == 43);
    text(u, 24, 378, "拖动进度条，再点确认", 16, muted[theme], 208);
  }
}

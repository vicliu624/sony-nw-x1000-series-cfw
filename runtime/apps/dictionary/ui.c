#include "ui.h"
#include "../emulators/platform.h"
#include <stdio.h>
#include <string.h>
enum {
  PAPER = 0xffff,
  INK = 0x2987,
  TEAL = 0xb865,
  MUTED = 0x6b6d,
  BORDER = 0xe71c,
  BLUE = 0x2c19
};
static void text(struct dx_ui *u, int x, int y, const char *s, unsigned c) {
  dx_draw(&u->font, ep_canvas, x, y, s, (uint16_t)c);
}
static void roundrect(int x, int y, int w, int h, int r, unsigned c) {
  for (int j = 0; j < h; j++) {
    int trim = 0;
    if (j < r)
      trim = r - j;
    else if (j >= h - r)
      trim = j - (h - r) + 1;
    ep_box(x + trim, y + j, w - trim * 2, 1, (uint16_t)c);
  }
}
static void card(struct dx_ui *u, int x, int y, int w, int h, const char *label,
                 int active) {
  roundrect(x, y + 2, w, h, 5, BORDER);
  roundrect(x, y, w, h, 5,
            active == 1   ? 0x980e
            : active == 2 ? TEAL
            : active < 0  ? 0xf7be
                          : 0xffff);
  int width = 0;
  const char *p = label;
  while (*p)
    width += (int)dx_width(&u->font, dx_utf8(&p));
  text(u, x + (w - width) / 2, y + (h - 16) / 2, label,
       active > 0   ? 0xffff
       : active < 0 ? MUTED
                    : INK);
}
static void fail(struct dx_ui *u, const char *s) {
  u->mode = DX_ERROR;
  snprintf(u->error, sizeof u->error, "%s", s);
}
static int results(struct dx_ui *u) {
  u->result_count = 0;
  u->can_next = 0;
  unsigned len = (unsigned)strlen(u->input.query);
  if (!len)
    return 1;
  for (unsigned i = 0; i < 4 && u->start + i < u->dict.count; i++) {
    char word[64];
    if (!dx_word(&u->dict, u->start + i, word))
      return 0;
    if (strncmp(word, u->input.query, len))
      break;
    if (i == 3) {
      u->can_next = 1;
      break;
    }
    strcpy(u->words[i], word);
    if (!dx_text(&u->dict, u->start + i, u->article, sizeof u->article))
      return 0;
    char *p = strstr(u->article, "\n\n");
    p = p ? p + 2 : u->article;
    if (*p == '[') {
      char *q = strstr(p, "\n\n");
      if (q)
        p = q + 2;
    }
    unsigned n = 0;
    while (p[n] && p[n] != '\n' && n < sizeof u->snippets[i] - 1)
      n++;
    memcpy(u->snippets[i], p, n);
    u->snippets[i][n] = 0;
    u->result_count++;
  }
  return 1;
}
void dx_ui_refresh(struct dx_ui *u) {
  u->page = 0;
  if (!dx_lower(&u->dict, u->input.query, &u->lower)) {
    fail(u, "INVALID DICTIONARY INDEX");
    return;
  }
  u->start = u->lower;
  if (!results(u))
    fail(u, "INVALID DICTIONARY ENTRY");
}
int dx_ui_open(struct dx_ui *u, const char *dict, const char *font) {
  memset(u, 0, sizeof(*u));
  u->pressed = -1;
  dx_input_init(&u->input);
  if (!dx_font_open(&u->font, font)) {
    fail(u, "FONT FILE MISSING OR DAMAGED");
    return 0;
  }
  if (!dx_open(&u->dict, dict)) {
    fail(u, "WORD DATA MISSING OR DAMAGED");
    return 0;
  }
  dx_ui_refresh(u);
  return 1;
}
void dx_ui_close(struct dx_ui *u) {
  dx_close(&u->dict);
  dx_font_close(&u->font);
}
static int wrap(struct dx_ui *u) {
  unsigned first = 0, pos = 0, width = 0, space = 0;
  u->line_count = 0;
  while (u->article[pos]) {
    unsigned before = pos;
    const char *p = u->article + pos;
    unsigned cp = dx_utf8(&p);
    pos = (unsigned)(p - u->article);
    unsigned cw = dx_width(&u->font, cp);
    if (cp == '\n' || width + cw > 224) {
      if (u->line_count == 8192)
        return 0;
      unsigned end = before, next = pos;
      if (cp != '\n') {
        end = space > first ? space : before;
        next = end;
        while (u->article[next] == ' ')
          next++;
      }
      u->lines[u->line_count++] = (struct dx_line){first, end};
      first = pos = next;
      width = space = 0;
      continue;
    }
    if (cp == ' ')
      space = before;
    width += cw;
  }
  if (pos > first) {
    if (u->line_count == 8192)
      return 0;
    u->lines[u->line_count++] = (struct dx_line){first, pos};
  }
  return 1;
}
int dx_ui_hit(int mode, int x, int y) {
  if (x < 0 || x >= 240 || y < 0 || y >= 432)
    return -1;
  if (y < 28 && x >= 184)
    return 20;
  if (mode == DX_ERROR)
    return y >= 384 ? 20 : -1;
  if (mode == DX_ARTICLE) {
    if (y >= 392 && y < 428) {
      if (x < 84)
        return 21;
      if (x >= 156)
        return 22;
    }
    return -1;
  }
  if (x >= 196 && y >= 36 && y < 68)
    return 23;
  if (x >= 8 && x < 232 && y >= 76 && y < 208)
    return 10 + (y - 76) / 44;
  if (y >= 216 && y < 240) {
    if (x < 84)
      return 21;
    if (x >= 156)
      return 22;
  }
  if (y >= 248 && y < 376) {
    unsigned row = (unsigned)(y - 248) / 44, col = (unsigned)x / 80;
    if (row < 3 && x % 80 >= 4 && x % 80 < 76 && (y - 248) % 44 < 40)
      return (int)(row * 3 + col);
  }
  if (y >= 388 && y < 428) {
    if (x < 80)
      return 24;
    if (x < 160)
      return 25;
    return 26;
  }
  return -1;
}
void dx_ui_touch(struct dx_ui *u, int x, int y, uint32_t now) {
  int hit = dx_ui_hit(u->mode, x, y);
  if (hit < 0)
    return;
  if (hit == 20) {
    if (u->mode == DX_ARTICLE) {
      u->mode = DX_SEARCH;
      results(u);
    } else
      u->quit = 1;
    return;
  }
  if (u->mode == DX_ARTICLE) {
    if (hit == 21 && u->page)
      u->page--;
    if (hit == 22 && (u->page + 1) * 18 < u->line_count)
      u->page++;
    return;
  }
  if (u->mode != DX_SEARCH)
    return;
  if (hit >= 0 && hit < 9) {
    dx_input_key(&u->input, (unsigned)hit, now);
    dx_ui_refresh(u);
    return;
  }
  if (hit == 23) {
    dx_input_init(&u->input);
    dx_ui_refresh(u);
    return;
  }
  if (hit == 24) {
    dx_input_space(&u->input);
    dx_ui_refresh(u);
    return;
  }
  if (hit == 25) {
    dx_input_delete(&u->input);
    dx_ui_refresh(u);
    return;
  }
  if (hit == 21 && u->start >= u->lower + 3) {
    u->start -= 3;
    if (!results(u))
      fail(u, "INVALID ENTRY");
    return;
  }
  if (hit == 22 && u->can_next) {
    u->start += 3;
    if (!results(u))
      fail(u, "INVALID ENTRY");
    return;
  }
  int row = hit >= 10 && hit < 13 ? hit - 10 : hit == 26 ? 0 : -1;
  if (row >= 0 && row < u->result_count) {
    dx_input_commit(&u->input);
    if (!dx_text(&u->dict, u->start + (unsigned)row, u->article,
                 sizeof u->article) ||
        !wrap(u)) {
      fail(u, "CANNOT DISPLAY DEFINITION");
      return;
    }
    u->page = 0;
    u->mode = DX_ARTICLE;
  }
}
int dx_ui_tick(struct dx_ui *u, uint32_t now) {
  if (u->input.pending >= 0 && (uint32_t)(now - u->input.stamp) >= 700) {
    dx_input_commit(&u->input);
    return 1;
  }
  return 0;
}
void dx_ui_render(struct dx_ui *u) {
  ep_box(0, 0, 240, 432, PAPER);
  ep_box(0, 0, 240, 28, TEAL);
  if (u->mode == DX_ERROR) {
    ep_text(8, 10, "DICTIONARY", 0xffff);
    ep_text(190, 10, "APPS", 0xffff);
    ep_text(8, 70, u->error, INK);
    ep_text(8, 96, "REINSTALL APP WITH ASSETS", INK);
    ep_box(0, 384, 240, 48, INK);
    ep_text(76, 404, "BACK TO APPS", 0xffff);
    return;
  }
  text(u, 8, 6, u->mode == DX_ARTICLE ? "词条释义" : "英汉词典", 0xffff);
  text(u, 192, 6, u->mode == DX_ARTICLE ? "返回" : "APPS", 0xffff);
  if (u->mode == DX_ARTICLE) {
    for (unsigned i = 0; i < 18 && u->page * 18 + i < u->line_count; i++) {
      struct dx_line l = u->lines[u->page * 18 + i];
      char line[128];
      unsigned n = l.last - l.first;
      if (n >= sizeof line)
        n = sizeof line - 1;
      memcpy(line, u->article + l.first, n);
      line[n] = 0;
      unsigned color = l.first == 0 ? TEAL : line[0] == '[' ? BLUE : INK;
      text(u, 8, 44 + (int)i * 18, line, color);
      if (l.first == 0)
        text(u, 9, 44 + (int)i * 18, line, color);
      else {
        char *dot = strchr(line, '.');
        if (dot && dot - line <= 4 && dot[1] == ' ') {
          char label[8];
          unsigned len = (unsigned)(dot - line + 1);
          memcpy(label, line, len);
          label[len] = 0;
          text(u, 8, 44 + (int)i * 18, label, TEAL);
        }
      }
    }
    card(u, 8, 392, 72, 34, "上页", u->page ? u->pressed == 21 : -1);
    card(u, 160, 392, 72, 34, "下页",
         (u->page + 1) * 18 < u->line_count ? u->pressed == 22 : -1);
    char page[24];
    snprintf(page, sizeof page, "%u/%u", u->page + 1,
             (u->line_count + 17) / 18);
    text(u, 92, 402, page, MUTED);
    return;
  }
  roundrect(8, 36, 224, 32, 5, BORDER);
  roundrect(9, 37, 222, 30, 4, 0xf7be);
  unsigned len = (unsigned)strlen(u->input.query),
           cut = len > 21 ? len - 21 : 0;
  text(u, 16, 44, len ? u->input.query + cut : "输入英文单词",
       len ? INK : MUTED);
  ep_box(194, 40, 1, 24, BORDER);
  text(u, 200, 44, "清空", TEAL);
  if (u->input.pending >= 0 && len)
    ep_box(16 + ((int)len - 1 - (int)cut) * 8, 62, 8, 2, TEAL);
  for (int i = 0; i < u->result_count; i++) {
    int y = 76 + i * 44;
    ep_box(8, y + 40, 224, 1, BORDER);
    text(u, 16, y + 2, u->words[i], TEAL);
    text(u, 16, y + 21, u->snippets[i], MUTED);
  }
  if (!u->result_count) {
    text(u, 12, 88, len ? "没有匹配词条" : "九宫格多击输入", MUTED);
    text(u, 12, 120, "同键连按切换字母", MUTED);
    text(u, 12, 148, "换键或稍等即可确认", MUTED);
    text(u, 12, 176, "英文单词 / 词组查询", MUTED);
  }
  card(u, 8, 216, 72, 24, "上一组",
       u->start > u->lower ? u->pressed == 21 : -1);
  card(u, 160, 216, 72, 24, "下一组", u->can_next ? u->pressed == 22 : -1);
  if (u->result_count) {
    char n[20];
    snprintf(n, sizeof n, "%u", (u->start - u->lower) / 3 + 1);
    text(u, 112, 220, n, MUTED);
  }
  ep_box(0, 244, 240, 188, 0xef7d);
  static const char *keys[] = {"1 .'-", "2 ABC",  "3 DEF", "4 GHI", "5 JKL",
                               "6 MNO", "7 PQRS", "8 TUV", "9 WXYZ"};
  for (int i = 0; i < 9; i++)
    card(u, 4 + (i % 3) * 80, 248 + (i / 3) * 44, 72, 40, keys[i],
         u->pressed == i);
  card(u, 4, 388, 72, 38, "空格", u->pressed == 24);
  card(u, 84, 388, 72, 38, "删除", u->pressed == 25);
  card(u, 164, 388, 72, 38, "打开",
       u->result_count ? (u->pressed == 26 ? 1 : 2) : -1);
}

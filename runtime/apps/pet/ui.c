#include "ui.h"
#include "text.h"
#include <stdio.h>
#include <string.h>
static unsigned short *screen;
static void box(int x, int y, int w, int h, unsigned short c) {
  for (int j = y; j < y + h; j++)
    for (int i = x; i < x + w; i++)
      if (i >= 0 && i < 240 && j >= 0 && j < 432)
        screen[j * 240 + i] = c;
}
static struct pet_font *font;
void pet_ui_font(struct pet_font *f) { font = f; }
static const char *localize(const char *s) {
  static const char *table[][2] = {
      {"MENU", "菜单"},
      {"BACK", "返回"},
      {"TREAT", "零食"},
      {"PLAY", "玩耍"},
      {"REST", "休息"},
      {"WAKE", "叫醒"},
      {"HELP", "帮助"},
      {"RESET PET", "重新开始"},
      {"BACK TO APPS", "返回应用列表"},
      {"INTERACT", "互动"},
      {"SAVE FAILED", "保存失败"},
      {"SAVE NOT CONFIRMED", "尚未确认保存成功"},
      {"RETRY OR LEAVE UNSAVED", "可重试或不保存退出"},
      {"RETRY", "重试"},
      {"LEAVE UNSAVED", "不保存退出"},
      {"KEEP PLAYING", "继续陪伴"},
      {"MEET BSOD", "认识 BSOD"},
      {"TAP BSOD TO SAY HELLO", "点点 BSOD，打个招呼"},
      {"TAP SLEEPING PET TO WAKE", "睡着时点它即可叫醒"},
      {"MENU HAS MORE ACTIONS", "更多互动在菜单里"},
      {"TREATS ARE JUST FOR FUN", "零食只是小小乐趣"},
      {"NO HUNGER OR CHORES", "不用操心饥饿和数值"},
      {"ACTIONS AUTO SAVE", "互动后会自动保存"},
      {"HOME RETURNS TO SONY", "HOME 键返回索尼界面"},
      {"TIME AWAY IS SAFE", "离开也不用担心"},
      {"START AGAIN", "重新开始吗"},
      {"THIS RESETS YOUR PET", "将重置宠物的状态"},
      {"CHOOSE NO TO KEEP IT", "选取消可保留现状"},
      {"YES", "确定"},
      {"NO", "取消"},
      {"NOT SAVED  EXIT TO RETRY", "未保存，可退出重试"},
      {"A FRESH START", "重新认识一下吧"},
      {"HELLO FRIEND", "你好呀"},
      {"JUST TINKERING", "摆弄一下小电脑"},
      {"LETS PLAY", "一起玩吧"},
      {"GOOD NIGHT", "晚安"},
      {"GOOD MORNING", "早安"},
      {"THAT FEELS NICE", "摸摸真舒服"},
      {"YUM  THANK YOU", "好吃，谢谢你"},
      {"ALREADY AWAKE", "我已经醒啦"},
      {"SLEEPING  TAP WAKE", "正在休息，点我叫醒"},
      {"TAP WAKE TO GET UP", "点我就能叫醒"},
      {"TAP YOUR PET", "点我打个招呼"},
      {"RESTING  TAP TO WAKE", "正在休息，点我叫醒"},
      {"SAVE DAMAGED  RESET", "存档损坏，可重新开始"},
      {"SAVE UNAVAILABLE", "暂时无法保存"},
  };
  if (font)
    for (unsigned i = 0; i < sizeof table / sizeof table[0]; i++)
      if (!strcmp(s, table[i][0]))
        return table[i][1];
  return s;
}
static void text(int x, int y, const char *s, int scale, unsigned short c) {
  (void)scale;
  pet_text(font, screen, x, y, x >= 0 && x < 240 ? (unsigned)(240 - x) : 0, 1,
           localize(s), c);
}
static void button(int x, int y, int w, const char *s) {
  box(x, y, w, 42, 0x236c);
  text(x + (w - (int)pet_text_width(font, localize(s))) / 2, y + 14, s, 2,
       0xffff);
}
void pet_ui_init(struct pet_ui *u) {
  memset(u, 0, sizeof *u);
  pet_init(&u->pet);
}
void pet_ui_tap(struct pet_ui *u, int x, int y) {
  if (x < 0 || x >= 240 || y < 0 || y >= 432)
    return;
  if (u->page == PET_SAVE_ERROR) {
    if (y >= 220 && y < 262) {
      u->exit_requested = 1;
      return;
    }
    if (y >= 274 && y < 316) {
      u->discard = 1;
      u->exit_requested = 1;
      return;
    }
    if (y >= 330 && y < 376)
      u->page = PET_ROOM;
    return;
  }
  if (u->page == PET_MENU && y >= 384) {
    u->exit_requested = 1;
    return;
  }
  if (u->page == PET_MENU) {
    if (y < 42) {
      u->page = PET_ROOM;
      return;
    }
    if (y >= 76 && y < 118) {
      pet_act(&u->pet, PET_FEED);
      u->page = PET_ROOM;
    } else if (y >= 132 && y < 174) {
      pet_act(&u->pet, PET_PLAY);
      u->page = PET_ROOM;
    } else if (y >= 188 && y < 230) {
      pet_act(&u->pet, u->pet.state.sleeping ? PET_WAKE : PET_SLEEP);
      u->page = PET_ROOM;
    } else if (y >= 244 && y < 286)
      u->page = PET_HELP;
    else if (y >= 300 && y < 342)
      u->page = PET_RESET_CONFIRM;
    u->animation_ms = 0;
    return;
  }
  if (u->page == PET_HELP) {
    if (y >= 330 && y < 376)
      u->page = PET_ROOM;
    return;
  }
  if (u->page == PET_RESET_CONFIRM) {
    if (y >= 280 && y < 322) {
      if (x < 120) {
        pet_init(&u->pet);
        u->pet.message = "A FRESH START";
      }
      u->page = PET_ROOM;
    }
    return;
  }
  if (y < 42 && x >= 120) {
    u->page = PET_MENU;
    return;
  }
  if (y >= 96 && y < 336) {
    pet_act(&u->pet, u->pet.state.sleeping ? PET_WAKE : PET_STROKE);
    u->animation_ms = 0;
    return;
  }
}
static void sprite(const struct pet_ui *u, const unsigned char *bytes) {
  static const unsigned rows[] = {0, 3, 6, 4, 8, 6, 7, 1, 2};
  static const unsigned frames[] = {6, 4, 6, 5, 6, 6, 6, 8, 8};
  unsigned pose = u->pet.pose, row = rows[pose],
           frame = (u->animation_ms / (pose == PET_IDLE ? 600 : 160)) %
                   frames[pose];
  if (pose == PET_ASLEEP)
    frame = 0;
  /* Sprite records are RGB565 plus alpha8; the bounded sheet is in memory. */
  const unsigned char *p = bytes + (row * 8 + frame) * 96 * 104 * 3;
  for (int y = 0; y < 104; y++)
    for (int x = 0; x < 96; x++, p += 3) {
      unsigned a = p[2];
      if (!a)
        continue;
      int offset = 0;
      if (pose == PET_WALK_RIGHT || pose == PET_WALK_LEFT) {
        int step = (int)(u->animation_ms / 100 % 12);
        offset = step < 6 ? step * 3 : (12 - step) * 3;
        if (pose == PET_WALK_LEFT)
          offset = -offset;
      }
      int pos = (y * 2 + 110) * 240 + x * 2 + 24 + offset;
      unsigned src = p[0] | (unsigned)p[1] << 8, dst = screen[pos];
      unsigned r = (((src >> 11) * a + (dst >> 11) * (255 - a)) / 255),
               g = ((((src >> 5) & 63) * a + ((dst >> 5) & 63) * (255 - a)) /
                    255),
               b = (((src & 31) * a + (dst & 31) * (255 - a)) / 255);
      box(x * 2 + 24 + offset, y * 2 + 110, 2, 2,
          (unsigned short)((r << 11) | (g << 5) | b));
    }
}
void pet_ui_draw(const struct pet_ui *u, unsigned short *canvas,
                 const unsigned char *sprites) {
  screen = canvas;
  box(0, 0, 240, 432, 0x0843);
  box(0, 0, 240, 40, 0x1927);
  text(12, 13, "BSOD", 2, 0xffff);
  if (u->page == PET_ROOM || u->page == PET_MENU)
    text(168, 13, u->page == PET_MENU ? "BACK" : "MENU", 2, 0xffff);
  if (u->page == PET_MENU) {
    button(18, 76, 204, "TREAT");
    button(18, 132, 204, "PLAY");
    button(18, 188, 204, u->pet.state.sleeping ? "WAKE" : "REST");
    button(18, 244, 204, "HELP");
    button(18, 300, 204, "RESET PET");
    button(6, 386, 228, "BACK TO APPS");
    return;
  }
  if (u->page == PET_SAVE_ERROR) {
    text(18, 88, "SAVE FAILED", 2, 0xffff);
    text(12, 136, "SAVE NOT CONFIRMED", 1, 0xffff);
    text(12, 156, "RETRY OR LEAVE UNSAVED", 1, 0xffff);
    button(12, 220, 216, "RETRY");
    button(12, 274, 216, "LEAVE UNSAVED");
    button(12, 330, 216, "KEEP PLAYING");
    return;
  }
  if (u->page == PET_HELP) {
    text(12, 66, "MEET BSOD", 2, 0xffff);
    const char *lines[] = {"TAP BSOD TO SAY HELLO",
                           "TAP SLEEPING PET TO WAKE",
                           "MENU HAS MORE ACTIONS",
                           "TREATS ARE JUST FOR FUN",
                           "NO HUNGER OR CHORES",
                           "ACTIONS AUTO SAVE",
                           "HOME RETURNS TO SONY",
                           "TIME AWAY IS SAFE",
                           0};
    for (unsigned i = 0; lines[i]; i++)
      text(12, 112 + (int)i * 22, lines[i], 1, 0xdedb);
    button(12, 330, 216, "BACK");
  } else if (u->page == PET_RESET_CONFIRM) {
    text(24, 112, "START AGAIN", 2, 0xffff);
    text(18, 158, "THIS RESETS YOUR PET", 1, 0xffff);
    text(18, 180, "CHOOSE NO TO KEEP IT", 1, 0xffff);
    button(12, 280, 102, "YES");
    button(126, 280, 102, "NO");
  } else {
    box(45, 322, 150, 2, 0x1927);
    if (sprites)
      sprite(u, sprites);
    if (u->pet.pose == PET_ASLEEP)
      text(178, 144, "Z", 2, 0xbdf7);
    if (u->pet.pose == PET_EATING) {
      box(178, 285, 16, 12, 0xfd20);
      box(180, 282, 12, 3, 0xffe0);
    }
    if (u->pet.pose == PET_PLAYING) {
      int bounce = (int)(u->animation_ms / 160 % 4);
      box(184, 299 - bounce * 8, 12, 12, 0xfbb4);
    }
    text((240 - (int)pet_text_width(font, localize(u->pet.message))) / 2, 344,
         u->pet.message, 1, 0xffff);
    if (u->save_warning)
      text(12, 54, "NOT SAVED  EXIT TO RETRY", 1, 0xfd20);
  }
}

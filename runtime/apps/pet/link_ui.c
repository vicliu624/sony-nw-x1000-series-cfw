#include "link_ui.h"
#include <string.h>
static void box(unsigned short *p, int x, int y, int w, int h,
                unsigned short c) {
  for (int j = y; j < y + h; j++)
    for (int i = x; i < x + w; i++)
      if (i >= 0 && i < 240 && j >= 0 && j < 432)
        p[j * 240 + i] = c;
}
static void label(unsigned short *p, struct pet_font *f, int x, int y,
                  const char *s, unsigned lines) {
  pet_text(f, p, x, y, (unsigned)(240 - x - 12), lines, s, 0xffff);
}
static void button(unsigned short *p, struct pet_font *f, int x, int y,
                   int width, const char *s) {
  box(p, x, y, width, 42, 0x236c);
  int text_width = (int)pet_text_width(f, s);
  pet_text(f, p, x + (width - text_width) / 2, y + 13, (unsigned)width, 1, s,
           0xffff);
}
static const char *body(const struct pet_ui *u) {
  if (u->link.state == PET_LINK_WAITING)
    return u->link.question[0] ? u->link.question : "请回电脑查看并回答问题。";
  return u->link.state == PET_LINK_WAITING && u->link.question[0]
             ? u->link.question
         : u->link.summary[0] ? u->link.summary
                              : "暂时没有结果摘要。";
}
static unsigned offset(const struct pet_ui *u, struct pet_font *font) {
  const char *s = body(u);
  unsigned n = 0;
  for (unsigned i = 0; i < u->detail_page && s[n]; i++) {
    struct pet_text_result r =
        pet_text(font, 0, 12, 130, 216, 10, s + n, 0xffff);
    if (!r.consumed)
      break;
    n += r.consumed;
  }
  return n;
}
const char *pet_link_caption(const struct pet_ui *u) {
  if (!u->paired)
    return "未配对 Codex";
  if (!u->link_enabled)
    return "Codex 已断开";
  if (u->net_state == PET_NET_IDENTITY_ERROR)
    return "电脑身份不匹配";
  if (u->net_state == PET_NET_DISCOVERING)
    return "正在查找已配对电脑";
  if (u->net_state != PET_NET_CONNECTED)
    return u->net_state == PET_NET_CONNECTING ? "正在连接 Codex"
                                              : "Codex 已离线";
  switch (u->link.state) {
  case PET_LINK_WORKING:
    return "Codex 正在工作";
  case PET_LINK_WAITING:
    return "需要你回电脑回答";
  case PET_LINK_COMPLETED:
    return u->acknowledged == u->link.revision ? "本轮结果已读"
                                               : "本轮完成，点我查看";
  case PET_LINK_FAILED:
    return "任务出错，点我查看";
  case PET_LINK_INTERRUPTED:
    return "任务已中断";
  case PET_LINK_IDLE:
    return "Codex 正在待机";
  default:
    return "Codex 状态暂无更新";
  }
}
enum pet_pose pet_link_pose(const struct pet_ui *u) {
  if (u->pet.state.sleeping || u->pet.interaction_ms || !u->paired ||
      !u->link_enabled)
    return u->pet.pose;
  if (u->net_state != PET_NET_CONNECTED)
    return PET_IDLE;
  switch (u->link.state) {
  case PET_LINK_WORKING:
    return PET_WORKING;
  case PET_LINK_WAITING:
    return PET_HAPPY;
  case PET_LINK_COMPLETED:
    return u->acknowledged == u->link.revision ? PET_IDLE : PET_PLAYING;
  case PET_LINK_FAILED:
    return PET_TIRED;
  default:
    return PET_IDLE;
  }
}
int pet_link_ui_tap(struct pet_ui *u, int x, int y, struct pet_font *font) {
  if (u->page == PET_ROOM && u->paired && !u->pet.state.sleeping && y >= 96 &&
      y < 336) {
    u->page = u->link.thread[0] ? PET_CODEX_DETAILS : PET_CONNECTION;
    u->detail_page = 0;
    return 1;
  }
  if (u->page == PET_CONNECTION) {
    if (y >= 220 && y < 262 && u->paired)
      u->link_command =
          u->link_enabled ? PET_LINK_CMD_DISCONNECT : PET_LINK_CMD_CONNECT;
    else if (y >= 274 && y < 316 && u->paired)
      u->page = PET_FORGET_CONFIRM;
    else if (y >= 330 && y < 376)
      u->page = PET_MENU;
    return 1;
  }
  if (u->page == PET_FORGET_CONFIRM) {
    if (y >= 280 && y < 322) {
      if (x < 120)
        u->link_command = PET_LINK_CMD_FORGET;
      u->page = PET_CONNECTION;
    }
    return 1;
  }
  if (u->page == PET_CODEX_DETAILS) {
    if (y >= 384) {
      u->acknowledged = u->link.revision;
      u->page = PET_ROOM;
      return 1;
    }
    if (y >= 330 && y < 372) {
      if (x < 120) {
        if (u->detail_page)
          u->detail_page--;
      } else {
        const char *s = body(u);
        unsigned n = offset(u, font);
        struct pet_text_result r =
            pet_text(font, 0, 12, 130, 216, 10, s + n, 0xffff);
        if (r.truncated)
          u->detail_page++;
      }
    }
    return 1;
  }
  return 0;
}
int pet_link_ui_draw(const struct pet_ui *u, unsigned short *p,
                     struct pet_font *font) {
  if (u->page != PET_CONNECTION && u->page != PET_FORGET_CONFIRM &&
      u->page != PET_CODEX_DETAILS)
    return 0;
  box(p, 0, 0, 240, 432, 0x0843);
  box(p, 0, 0, 240, 40, 0x1927);
  label(p, font, 12, 13, "Codex 联动", 1);
  if (u->page == PET_CONNECTION) {
    label(p, font, 12, 62, pet_link_caption(u), 2);
    if (u->link_error && !u->paired)
      label(p, font, 12, 88, "配对文件无法使用", 1);
    if (u->paired) {
      label(p, font, 12, 104, u->computer, 1);
      label(p, font, 12, 126, u->peer, 1);
      label(p, font, 12, 150,
            u->net_state == PET_NET_DISCOVERING ? "正在自动查找"
            : u->discovered > 0                 ? "自动发现"
            : u->peer[0]                        ? "已保存地址（兼容）"
                                                : "等待发现结果",
            1);
      label(p, font, 12, 174, "点宠物查看任务", 1);
      button(p, font, 12, 220, 216, u->link_enabled ? "断开连接" : "重新连接");
      button(p, font, 12, 274, 216, "忘记此电脑");
      if (u->link_error)
        label(p, font, 12, 198, "操作未完成，可重试", 1);
    } else
      label(p, font, 12, 112,
            "先在电脑生成配对文件。\n复制 link.pair "
            "到：\nHOMEBREW/data/pet/\n安全弹出后重新打开宠物。",
            5);
    button(p, font, 12, 330, 216, "返回菜单");
  } else if (u->page == PET_FORGET_CONFIRM) {
    label(p, font, 12, 110, "忘记这台电脑吗？", 2);
    label(p, font, 12, 166, "仅移除配对。\n宠物存档会保留。", 3);
    button(p, font, 12, 280, 102, "确定");
    button(p, font, 126, 280, 102, "取消");
  } else {
    label(p, font, 12, 54, pet_link_caption(u), 2);
    label(p, font, 12, 90, u->link.title, 2);
    unsigned n = offset(u, font);
    struct pet_text_result r =
        pet_text(font, p, 12, 130, 216, 10, body(u) + n, 0xffff);
    if (u->detail_page)
      button(p, font, 12, 330, 102, "上一页");
    if (r.truncated)
      button(p, font, 126, 330, 102, "下一页");
    button(p, font, 12, 386, 216, "知道了");
  }
  return 1;
}

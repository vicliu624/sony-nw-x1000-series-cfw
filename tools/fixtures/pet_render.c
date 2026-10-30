#include "../../runtime/apps/pet/text.h"
#include "../../runtime/apps/pet/ui.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned short image[240 * 432];
int main(int argc, char **argv) {
  assert(argc == 4);
  struct pet_font font;
  assert(pet_font_open(&font, argv[3]));
  pet_ui_font(&font);
  FILE *f = fopen(argv[1], "rb");
  assert(f);
  unsigned n = 9 * 8 * 96 * 104 * 3;
  unsigned char *sprites = malloc(n);
  assert(sprites && fread(sprites, 1, n, f) == n);
  assert(!fclose(f));
  struct pet_ui ui;
  pet_ui_init(&ui);
  for (unsigned p = 0; p < 26; p++) {
    pet_ui_init(&ui);
    ui.page = p < 9     ? PET_ROOM
              : p == 9  ? PET_HELP
              : p == 10 ? PET_RESET_CONFIRM
              : p == 11 ? PET_SAVE_ERROR
              : p == 12 ? PET_MENU
                        : PET_ROOM;
    ui.pet.pose = p < 9 ? (enum pet_pose)p : PET_IDLE;
    ui.pet.state.sleeping = p == PET_ASLEEP;
    ui.save_warning = p == 13;
    if (p >= 14) {
      ui.paired = ui.link_enabled = p != 14;
      ui.net_state = p == 15 ? PET_NET_DISCOVERING : PET_NET_CONNECTED;
      strcpy(ui.computer, "Paired computer");
      strcpy(ui.peer, "192.168.50.210:4242");
      ui.discovered = 1;
      strcpy(ui.link.thread, "selected");
      strcpy(ui.link.title, "X1000 自制应用开发");
      strcpy(ui.link.question, "请确认下一步要继续开发还是先进行测试。这是一条"
                               "来自已配对 Codex 会话的问题，请回电脑回答。");
      strcpy(ui.link.summary,
             "任务已完成。\n中文显示、连接和提醒已读流程已通过本地验证。实机测"
             "试仍需单独进行。配对信息仅保存在外部存储。");
      ui.link.revision = 6;
      ui.page = p <= 16                         ? PET_CONNECTION
                : p == 17 || p == 18 || p == 23 ? PET_CODEX_DETAILS
                : p == 19                       ? PET_FORGET_CONFIRM
                                                : PET_ROOM;
      ui.link.state = p == 17   ? PET_LINK_WAITING
                      : p == 20 ? PET_LINK_WORKING
                      : p == 24 ? PET_LINK_FAILED
                                : PET_LINK_COMPLETED;
      if (p == 22)
        ui.net_state = PET_NET_OFFLINE;
      if (p == 23) {
        const char *line = "这是长摘要的后续内容，用来验证小屏幕分页。\n";
        for (unsigned i = 0; i < 9 && strlen(ui.link.summary) + strlen(line) <
                                          sizeof ui.link.summary;
             i++)
          strcat(ui.link.summary, line);
        ui.detail_page = 1;
      }
    }
    if (p == 25)
      ui.page = PET_HELP;
    for (unsigned a = 0; a < 16; a++) {
      ui.animation_ms = a * 160;
      pet_ui_draw(&ui, image, sprites);
    }
    char path[4096];
    snprintf(path, sizeof path, "%s/frame-%u.ppm", argv[2], p);
    f = fopen(path, "wb");
    assert(f);
    fprintf(f, "P6\n240 432\n255\n");
    for (unsigned i = 0; i < 240 * 432; i++) {
      unsigned short v = image[i];
      unsigned char rgb[3] = {(unsigned char)((v >> 11) * 255 / 31),
                              (unsigned char)(((v >> 5) & 63) * 255 / 63),
                              (unsigned char)((v & 31) * 255 / 31)};
      assert(fwrite(rgb, 1, 3, f) == 3);
    }
    assert(!fclose(f));
  }
  free(sprites);
  pet_ui_font(0);
  pet_font_close(&font);
  return 0;
}

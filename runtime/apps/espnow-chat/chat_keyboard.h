#ifndef XNOW_CHAT_KEYBOARD_H
#define XNOW_CHAT_KEYBOARD_H
#include <stdint.h>
#include "../../platform/espnow/xnow_chat.h"
enum chat_keyboard_mode { CHAT_KBD_ALPHA=0,CHAT_KBD_NUMBER=1,CHAT_KBD_SYMBOL=2 };
struct chat_keyboard {
    char text[XNOW_CHAT_MAX_TEXT+1];
    unsigned length,cursor,mode,cycle,pending_position;
    int pending_key;
    uint32_t stamp;
};
void chat_keyboard_init(struct chat_keyboard *,const char *);
int chat_keyboard_key(struct chat_keyboard *,unsigned,uint32_t);
int chat_keyboard_tick(struct chat_keyboard *,uint32_t);
void chat_keyboard_commit(struct chat_keyboard *);
void chat_keyboard_left(struct chat_keyboard *);
void chat_keyboard_right(struct chat_keyboard *);
void chat_keyboard_delete(struct chat_keyboard *);
void chat_keyboard_clear(struct chat_keyboard *);
void chat_keyboard_mode(struct chat_keyboard *);
void chat_keyboard_symbols(struct chat_keyboard *);
void chat_keyboard_space(struct chat_keyboard *);
#endif

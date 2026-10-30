#include "../runtime/apps/espnow-chat/chat_keyboard.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    struct chat_keyboard k;unsigned now=0;
    chat_keyboard_init(&k,0);
    for(int i=0;i<5;i++)assert(!chat_keyboard_key(&k,2,now+=100));
    chat_keyboard_right(&k);
    for(int i=0;i<3;i++)assert(!chat_keyboard_key(&k,5,now+=100));
    chat_keyboard_right(&k);
    for(int i=0;i<2;i++)assert(!chat_keyboard_key(&k,8,now+=100));
    chat_keyboard_right(&k);
    for(int i=0;i<2;i++)assert(!chat_keyboard_key(&k,3,now+=100));
    chat_keyboard_commit(&k);assert(!strcmp(k.text,"Blue"));
    chat_keyboard_left(&k);chat_keyboard_delete(&k);assert(!strcmp(k.text,"Ble"));
    chat_keyboard_mode(&k);assert(!chat_keyboard_key(&k,7,now));assert(!strcmp(k.text,"Bl7e"));
    chat_keyboard_right(&k);chat_keyboard_space(&k);assert(!strcmp(k.text,"Bl7e "));
    chat_keyboard_clear(&k);chat_keyboard_mode(&k);
    assert(!chat_keyboard_key(&k,2,0));assert(chat_keyboard_tick(&k,901));assert(!chat_keyboard_key(&k,2,902));assert(!strcmp(k.text,"aa"));
    chat_keyboard_init(&k,0);chat_keyboard_mode(&k);
    for(unsigned i=0;i<96;i++)assert(!chat_keyboard_key(&k,1,i));
    assert(chat_keyboard_key(&k,2,100)==-1&&k.length==96&&k.text[96]==0);
    chat_keyboard_delete(&k);assert(k.length==95);chat_keyboard_symbols(&k);assert(!chat_keyboard_key(&k,2,200));
    puts("XNOW keyboard: original Blue sequence, cursor edit, numeric mode, timed commit and capacity passed");return 0;
}

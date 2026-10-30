/* Stock-inspired telephone multi-tap. No dictionary, learning or persistence. */
#include "chat_keyboard.h"
#include <string.h>
static const char *alpha[10]={" 0",".@/:1","abcABC2","defDEF3","ghiGHI4","jklJKL5","mnoMNO6","pqrsPQRS7","tuvTUV8","wxyzWXYZ9"};
static const char *symbols[10]={"\\|0",".@/:1","?!2",",;3","()-4","_+=5","[]6","{}7","<>8","\"'9"};
void chat_keyboard_init(struct chat_keyboard *s,const char *text) {
    memset(s,0,sizeof(*s));s->pending_key=-1;
    if(text){while(s->length<XNOW_CHAT_MAX_TEXT&&text[s->length]){s->text[s->length]=text[s->length];s->length++;}}
    s->cursor=s->length;
}
void chat_keyboard_commit(struct chat_keyboard *s){s->pending_key=-1;s->cycle=0;}
static int insert(struct chat_keyboard *s,char c) {
    if(s->length>=XNOW_CHAT_MAX_TEXT)return -1;
    memmove(s->text+s->cursor+1,s->text+s->cursor,s->length-s->cursor+1);
    s->text[s->cursor++]=c;s->length++;return 0;
}
int chat_keyboard_tick(struct chat_keyboard *s,uint32_t now) {
    if(s->pending_key>=0&&(uint32_t)(now-s->stamp)>=900){chat_keyboard_commit(s);return 1;}return 0;
}
int chat_keyboard_key(struct chat_keyboard *s,unsigned key,uint32_t now) {
    const char *group;chat_keyboard_tick(s,now);if(key>9)return -1;
    if(s->mode==CHAT_KBD_NUMBER){chat_keyboard_commit(s);return insert(s,(char)('0'+key));}
    group=s->mode==CHAT_KBD_SYMBOL?symbols[key]:alpha[key];
    if(s->pending_key==(int)key){s->cycle=(s->cycle+1)%(unsigned)strlen(group);s->text[s->pending_position]=group[s->cycle];s->stamp=now;return 0;}
    chat_keyboard_commit(s);s->pending_position=s->cursor;
    if(insert(s,group[0]))return -1;
    s->pending_key=(int)key;s->stamp=now;return 0;
}
void chat_keyboard_left(struct chat_keyboard *s){chat_keyboard_commit(s);if(s->cursor)s->cursor--;}
void chat_keyboard_right(struct chat_keyboard *s){chat_keyboard_commit(s);if(s->cursor<s->length)s->cursor++;}
void chat_keyboard_delete(struct chat_keyboard *s) {
    chat_keyboard_commit(s);if(!s->cursor)return;
    memmove(s->text+s->cursor-1,s->text+s->cursor,s->length-s->cursor+1);s->cursor--;s->length--;
}
void chat_keyboard_clear(struct chat_keyboard *s){unsigned mode=s->mode;chat_keyboard_init(s,0);s->mode=mode;}
void chat_keyboard_mode(struct chat_keyboard *s){chat_keyboard_commit(s);s->mode=s->mode==CHAT_KBD_NUMBER?CHAT_KBD_ALPHA:CHAT_KBD_NUMBER;}
void chat_keyboard_symbols(struct chat_keyboard *s){chat_keyboard_commit(s);s->mode=s->mode==CHAT_KBD_SYMBOL?CHAT_KBD_ALPHA:CHAT_KBD_SYMBOL;}
void chat_keyboard_space(struct chat_keyboard *s){chat_keyboard_commit(s);(void)insert(s,' ');}

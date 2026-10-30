/* Runs without opening player devices; compatible with C99 and C++11. */
#include "xnow.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned sent,failed;
static int send_packet(void *context,const uint8_t packet[32]){
    struct xnow_view view;(void)context;
    assert(!xnow_decode(packet,32,&view)&&view.kind==XNOW_DATA);sent++;return 0;
}
static void event(void *context,int kind,const char *text,unsigned length){
    (void)context;(void)text;(void)length;if(kind==XNOW_CHAT_FAILED)failed++;
}
int main(void){
    struct xnow_chat chat;struct xnow_session session;uint8_t channel[48];
    assert(strlen(xnow_library_version())>0);
    xnow_session_init(&session,0);assert(session.next==XNOW_SESSION_PREFLIGHT);
    xnow_chat_init(&chat,0,send_packet,event);
    assert(!xnow_chat_submit(&chat,"hello",5,1,0));xnow_chat_tick(&chat,80);
    xnow_chat_tick(&chat,21000);assert(sent==1&&failed==1&&!chat.active);
    assert(!xnow_channel_command(channel,1,8)&&channel[2]==48&&channel[10]==8);
    printf("XNOW %s: linked consumer passed; no device access\n",xnow_library_version());
    return 0;
}

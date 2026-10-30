#include "../runtime/platform/espnow/xnow_chat.h"
#include <assert.h>
#include <stdio.h>
struct node {struct xnow_chat chat;int id,messages,delivered,failed;char received[97];};
struct transit {int source;uint8_t packet[32];};
static struct transit queue[4096];static unsigned head,tail,sent;static int dropping;
static int send_packet(void *context,const uint8_t packet[32]) {
    struct node *n=context;sent++;
    if(dropping==2 || (dropping==1&&sent%4==1))return 0;
    assert(tail<4096);queue[tail].source=n->id;memcpy(queue[tail++].packet,packet,32);
    if(dropping==1&&sent%5==0){assert(tail<4096);queue[tail]=queue[tail-1];tail++;}
    return 0;
}
static void event(void *context,int type,const char *text,unsigned length) {
    struct node *n=context;
    if(type==XNOW_CHAT_MESSAGE){n->messages++;memcpy(n->received,text,length);n->received[length]=0;}
    if(type==XNOW_CHAT_DELIVERED)n->delivered++;
    if(type==XNOW_CHAT_FAILED)n->failed++;
}
static void simulation(int drop) {
    struct node a,b;unsigned now;
    const char text_a[]="X1060 sends a multi-fragment message to Cardputer";
    const char text_b[]="Cardputer replies with UTF8 bytes: \xe4\xbd\xa0\xe5\xa5\xbd";
    memset(&a,0,sizeof(a));memset(&b,0,sizeof(b));a.id=0;b.id=1;
    xnow_chat_init(&a.chat,&a,send_packet,event);xnow_chat_init(&b.chat,&b,send_packet,event);
    head=tail=sent=0;dropping=drop;
    assert(!xnow_chat_submit(&a.chat,text_a,sizeof(text_a)-1,0x12345678,0));
    assert(!xnow_chat_submit(&b.chat,text_b,sizeof(text_b)-1,0x87654321,0));
    for(now=0;now<30000;now+=20) {
        while(head<tail){struct transit p=queue[head++];xnow_chat_receive(p.source?&a.chat:&b.chat,p.packet,now);}
        xnow_chat_tick(&a.chat,now);xnow_chat_tick(&b.chat,now);
    }
    if(drop==2){assert(a.failed==1&&b.failed==1&&!a.messages&&!b.messages);}
    else {
        assert(a.messages==1&&b.messages==1&&a.delivered==1&&b.delivered==1&&!a.failed&&!b.failed);
        assert(!strcmp(a.received,text_b)&&!strcmp(b.received,text_a));
    }
}
int main(void) {
    simulation(0);simulation(1);simulation(2);
    puts("XNOW chat: bidirectional fragmentation, UTF8 bytes, loss/retry, duplicate suppression and bounded failure passed");return 0;
}

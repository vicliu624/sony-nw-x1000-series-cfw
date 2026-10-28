/* Native touch chat. Message history is RAM-only; stdout preview is PC-only. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include "../../native/frontend.h"
#include "../../native/linux_devices.h"
#include "../../native/linux_signals.h"
#include "../../native/ui_font.h"
#include "../../platform/espnow/xnow_chat.h"
#include "../../platform/espnow/xnow_sd8686.h"
extern int chat_original_gettimeofday(void *,void *) __asm__("gettimeofday");
static unsigned short pixels[HB_DISPLAY_PIXELS];
static volatile int stopped;
static struct xnow_chat chat;
static struct xnow_sd8686 radio={-1,0};
static struct xnow_mailbox mailbox;
static int linked,dirty=1,shifted=1;
static char editor[97],notice[64]="RADIO BRIDGE NOT READY";
static unsigned edited,history_count,history_next;
struct entry {char text[97];uint32_t sequence;unsigned mine,state;};
static struct entry history[8];
static const char *keys[3]={"QWERTYUIOP","ASDFGHJKL","ZXCVBNM"};
static uint32_t now_ms(void) {
    struct {int32_t seconds,microseconds;} t;
    if(chat_original_gettimeofday(&t,0))return 0;
    return (uint32_t)((uint64_t)(uint32_t)t.seconds*1000u+(uint32_t)t.microseconds/1000u);
}
static void box(int x,int y,int w,int h,unsigned short color) {
    int i,j;for(j=y;j<y+h&&j<432;j++)for(i=x;i<x+w&&i<240;i++)if(i>=0&&j>=0)pixels[j*240+i]=color;
}
static unsigned short blend(unsigned short fg,unsigned short bg,unsigned a) {
    unsigned r=(((fg>>11)&31)*a+((bg>>11)&31)*(15-a)+7)/15;
    unsigned g=(((fg>>5)&63)*a+((bg>>5)&63)*(15-a)+7)/15;
    unsigned b=((fg&31)*a+(bg&31)*(15-a)+7)/15;
    return (unsigned short)((r<<11)|(g<<5)|b);
}
static int glyph_width(unsigned c){return hb_ui_advance[(c>=32&&c<=126?c:'?')-32];}
static void text(int x,int y,int width,const char *s,unsigned short fg,unsigned short bg) {
    int end=x+width;unsigned n;
    for(n=0;s[n]&&n<104;n++) {
        unsigned c=(unsigned char)s[n],g,advance;if(c<32||c>126)c='?';g=c-32;advance=hb_ui_advance[g];
        if(x+(int)advance>end)break;
        for(int yy=0;yy<16;yy++)for(unsigned xx=0;xx<advance&&xx<16;xx++) {
            unsigned v=hb_ui_font[g][yy][xx/2],a=xx&1?v&15:v>>4;
            if(a)box(x+(int)xx,y+yy,1,1,blend(fg,bg,a));
        }
        x+=(int)advance;
    }
}
static void add_history(const char *s,unsigned n,unsigned mine,uint32_t sequence) {
    struct entry *e=&history[history_next];memset(e,0,sizeof(*e));memcpy(e->text,s,n);e->mine=mine;e->sequence=sequence;e->state=mine?0:1;
    history_next=(history_next+1)%8;if(history_count<8)history_count++;dirty=1;
}
static void event(void *context,int type,const char *s,unsigned n) {
    (void)context;
    if(type==XNOW_CHAT_MESSAGE)add_history(s,n,0,chat.incoming_sequence);
    else {
        for(unsigned i=0;i<8;i++)if(history[i].mine&&history[i].sequence==chat.sequence)history[i].state=type==XNOW_CHAT_DELIVERED?1:2;
        snprintf(notice,sizeof(notice),"%s",type==XNOW_CHAT_DELIVERED?"PEER CONFIRMED":"NO PEER ACK - MAY HAVE ARRIVED");
    }
    dirty=1;
}
static int send_packet(void *context,const uint8_t packet[32]) {
    int result;(void)context;if(!linked)return -1;
    result=xnow_mailbox_send(&mailbox,packet);
    return result==XNOW_OK?0:result==XNOW_PENDING?1:-1;
}
static void check_radio(void) {
    if(linked)xnow_sd8686_close(&radio);
    linked=xnow_sd8686_open(&radio,&mailbox)==XNOW_OK;
    snprintf(notice,sizeof(notice),"%s",linked?"READY - WAITING FOR PEER":"RADIO BRIDGE NOT READY");dirty=1;
}
static void submit(void) {
    uint32_t token;int fd;ssize_t n;
    if(!linked){strcpy(notice,"CHECK RADIO BEFORE SENDING");dirty=1;return;}
    if(!edited||chat.active){strcpy(notice,chat.active?"WAIT FOR CURRENT MESSAGE":"TYPE A MESSAGE FIRST");dirty=1;return;}
    fd=open("/dev/urandom",O_RDONLY);if(fd<0)return;n=read(fd,&token,4);close(fd);if(n!=4)return;if(!token)token=1;
    if(!xnow_chat_submit(&chat,editor,edited,token,now_ms())) {
        add_history(editor,edited,1,chat.sequence);edited=0;editor[0]=0;strcpy(notice,"SENDING - WAIT FOR PEER ACK");dirty=1;
    }
}
static void draw(void) {
    char line[104],lines[40][104];unsigned count=0;
    box(0,0,240,432,0x0843);box(0,0,240,40,0x1a4b);text(10,11,220,"ESP-NOW CHAT",0xffff,0x1a4b);
    text(8,45,224,notice,linked?0x9ff3:0xffaf,0x0843);
    for(unsigned k=0;k<history_count;k++) {
        struct entry *e=&history[(history_next+8-history_count+k)%8];
        snprintf(line,sizeof(line),"%s%s",e->mine?(e->state==0?"ME? ":e->state==1?"ME> ":"ME! "):"RX> ",e->text);
        unsigned offset=0;
        while(line[offset]&&count<40) {
            int width=0;unsigned used=0;memset(lines[count],0,sizeof(lines[count]));
            while(line[offset+used]&&width+glyph_width((unsigned char)line[offset+used])<=220&&used<102){width+=glyph_width((unsigned char)line[offset+used]);used++;}
            if(!used)break;memcpy(lines[count++],line+offset,used);offset+=used;
        }
    }
    unsigned first=count>9?count-9:0;
    for(unsigned k=first;k<count;k++)text(8,68+(int)(k-first)*18,224,lines[k],0xef9e,0x0843);
    box(6,238,228,35,0x10c5);unsigned offset=edited>24?edited-24:0;text(11,247,218,editor+offset,0xffff,0x10c5);
    for(unsigned row=0;row<3;row++) {
        unsigned n=(unsigned)strlen(keys[row]);int left=(240-(int)n*23)/2;
        for(unsigned i=0;i<n;i++) {
            char key[2]={keys[row][i],0};if(!shifted)key[0]+='a'-'A';int x=left+(int)i*23;
            box(x,280+(int)row*30,21,27,0x2147);text(x+5,285+(int)row*30,18,key,0xffff,0x2147);
        }
    }
    const char *labels[]={shifted?"abc":"ABC","SPACE","DEL","SEND"};
    for(unsigned i=0;i<4;i++){box((int)i*60+2,372,56,26,i==3?0x1a4b:0x2147);text((int)i*60+5,377,52,labels[i],0xffff,i==3?0x1a4b:0x2147);}
    box(2,402,114,28,0x1a4b);box(122,402,116,28,0x1a4b);text(14,408,100,"BACK TO APPS",0xffff,0x1a4b);text(144,408,90,"CHECK RADIO",0xffff,0x1a4b);dirty=0;
}
static int tap(unsigned x,unsigned y) {
    if(y>=402){if(x<120)return 1;check_radio();return 0;}
    if(y>=372&&y<398){unsigned index=x/60;if(index==0)shifted=!shifted;else if(index==1&&edited<96)editor[edited++]=' ';else if(index==2&&edited)edited--;else if(index==3)submit();editor[edited]=0;dirty=1;return 0;}
    if(y>=280&&y<370) {
        unsigned row=(y-280)/30,n=(unsigned)strlen(keys[row]);int left=(240-(int)n*23)/2;
        if((int)x>=left&&(int)x<left+(int)n*23&&edited<96){unsigned key=((int)x-left)/23;char c=keys[row][key];if(!shifted)c+='a'-'A';editor[edited++]=c;editor[edited]=0;dirty=1;}
    }
    return 0;
}
static int graphical(void) {
    struct hb_devices devices;int pressed=0,failed;
    if(hb_stop_signals_install(&stopped))return 2;
    xnow_chat_init(&chat,0,send_packet,event);check_radio();draw();
    if(hb_devices_open(&devices,pixels,HB_DISPLAY_PIXELS,&stopped)){xnow_sd8686_close(&radio);return 2;}
    hb_devices_present(&devices);
    while(!stopped&&!devices.failed) {
        uint8_t packet[11];struct xnow_received received;
        if(linked) {
            int result=xnow_mailbox_receive(&mailbox,&received);
            if(result==XNOW_OK)xnow_chat_receive(&chat,received.packet,now_ms());
            else if(result<0){linked=0;xnow_sd8686_close(&radio);strcpy(notice,"RADIO LOST - CHECK CONNECTION");dirty=1;}
            xnow_chat_tick(&chat,now_ms());
        }
        if(dirty){draw();hb_devices_present(&devices);}hb_devices_flush(&devices);
        int got=hb_devices_next_touch(&devices,packet,25);if(got<0)break;
        if(got>0){struct hb_touch t;hb_touch_decode(packet,&t);if(t.down)pressed=1;else if(pressed){pressed=0;if(t.in_bounds&&tap(t.x,t.y))break;}}
    }
    failed=devices.failed;if(hb_devices_close(&devices)<0)failed=1;xnow_sd8686_close(&radio);return stopped?0:failed?2:0;
}
int main(int argc,char **argv) {
    if(argc==2&&!strcmp(argv[1],"--help")){puts("ESP-NOW Chat: touch keyboard, RAM-only history, BACK TO APPS. Requires qualified radio bridge; no automatic installation. --render-preview writes RGB565 stdout without device access.");return 0;}
    if(argc==2&&!strcmp(argv[1],"--version")){puts("0.1.0-dev.1");return 0;}
    if(argc==2&&!strcmp(argv[1],"--render-preview")) {
        add_history("HELLO FROM CARDPUTER",20,0,1);add_history("HELLO FROM WALKMAN",18,1,2);history[1].state=1;
        strcpy(editor,"TYPE A MESSAGE");edited=(unsigned)strlen(editor);strcpy(notice,"PREVIEW - NOT CONNECTED");draw();
        return fwrite(pixels,1,sizeof(pixels),stdout)==sizeof(pixels)?0:74;
    }
    if(argc!=1)return 64;
    return graphical();
}

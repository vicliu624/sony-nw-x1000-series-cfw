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
#include <x1000/services/espnow_chat.h>
#include "chat_ipc.h"

#include "chat_keyboard.h"
extern int chat_original_gettimeofday(void *,void *) __asm__("gettimeofday");
static unsigned short pixels[HB_DISPLAY_PIXELS];
static volatile int stopped;
static struct xnow_chat chat;
static struct chat_client client={.command=-1,.events=-1};
static unsigned owner_phase,owner_finished;
static int linked,dirty=1,editing;
static struct chat_keyboard keyboard;
static char editor[97],notice[64]="RADIO BRIDGE NOT READY";
static unsigned edited,history_count,history_next;
static int preview_mode,scroll_from_bottom,clip_top,clip_bottom=432;
#define CHAT_BG 0x0882
#define CHAT_HEADER 0x10e4
#define CHAT_IN 0x1946
#define CHAT_OUT 0x126a
#define CHAT_ACCENT 0x5eb9
#define CHAT_TEXT 0xefbe
#define CHAT_MUTED 0x8d36
#define CHAT_INPUT 0x1105
struct entry {char text[97];uint32_t sequence;unsigned mine,state;};
static struct entry history[8];
static uint32_t now_ms(void) {
    struct {int32_t seconds,microseconds;} t;
    if(chat_original_gettimeofday(&t,0))return 0;
    return (uint32_t)((uint64_t)(uint32_t)t.seconds*1000u+(uint32_t)t.microseconds/1000u);
}
static void box(int x,int y,int w,int h,unsigned short color) {
    int i,j;for(j=y;j<y+h&&j<432&&j<clip_bottom;j++)for(i=x;i<x+w&&i<240;i++)if(i>=0&&j>=0&&j>=clip_top)pixels[j*240+i]=color;
}
static void round_box(int x,int y,int w,int h,int radius,unsigned short color) {
    for(int row=0;row<h;row++) {
        int dy=row<radius?radius-row:row>=h-radius?row-(h-radius-1):0,inset=0;
        if(dy){inset=radius;while(inset>0&&(radius-inset+1)*(radius-inset+1)+dy*dy<=radius*radius)inset--;}
        box(x+inset,y+row,w-2*inset,1,color);
    }
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
static void small_text(int x,int y,int width,const char *s,unsigned short fg,unsigned short bg) {
    int end=x+width;
    for(unsigned n=0;s[n]&&n<104;n++) {
        unsigned c=(unsigned char)s[n];if(c<32||c>126)c='?';unsigned g=c-32,advance=(hb_ui_advance[g]*3+3)/4;
        if(x+(int)advance>end)break;
        for(int yy=0;yy<12;yy++)for(unsigned xx=0;xx<advance;xx++) {
            unsigned sx=xx*4/3,sy=(unsigned)yy*4/3;if(sx>=16)continue;
            unsigned v=hb_ui_font[g][sy][sx/2],a=sx&1?v&15:v>>4;
            if(a)box(x+(int)xx,y+yy,1,1,blend(fg,bg,a));
        }
        x+=(int)advance;
    }
}
static void key_button(int x,int y,int width,const char *label,const char *digit) {
    int used=0;for(unsigned i=0;label[i];i++)used+=glyph_width((unsigned char)label[i]);
    box(x+1,y+1,width-2,42,0x2147);
    text(x+(width-used)/2,y+(digit?4:13),width-4,label,0xffff,0x2147);
    if(digit)text(x+width/2-4,y+23,14,digit,0x9ff3,0x2147);
}
static void draw_keyboard(void) {
    static const char *letters[9]={".@/:","ABC","DEF","GHI","JKL","MNO","PQRS","TUV","WXYZ"};
    static const char *symbols[9]={".@/:","?!",",;","()-","_+=","[]","{}","<>","\"'"};
    static const char *controls[3]={"DEL","LEFT","RIGHT"};
    int x=8,y=48;char count[40];
    box(0,0,240,432,0x0843);box(0,0,240,40,0x1a4b);text(10,11,220,"TYPE MESSAGE",0xffff,0x1a4b);
    box(0,40,240,100,0x10c5);
    for(unsigned i=0;i<=keyboard.length;i++) {
        char c[2]={keyboard.text[i],0};int width=c[0]?glyph_width((unsigned char)c[0]):3;
        if(x+width>230){x=8;y+=19;}if(y>121)break;
        if(i==keyboard.cursor)box(x,y,1,17,0x9ff3);
        if(c[0])text(x,y,width,c,0xffff,0x10c5);
        if(keyboard.pending_key>=0&&i==keyboard.pending_position)box(x,y+17,width,1,0xffe0);
        x+=width;
    }
    snprintf(count,sizeof(count),"%u/96  TAP AGAIN TO CYCLE",keyboard.length);text(8,147,224,count,0x9cf3,0x0843);
    for(unsigned row=0;row<3;row++)for(unsigned col=0;col<4;col++) {
        unsigned number=row*3+col+1;char digit[2]={(char)('0'+number),0};
        if(col==3)key_button(180,172+(int)row*44,60,controls[row],0);
        else if(keyboard.mode==CHAT_KBD_NUMBER)key_button((int)col*60,172+(int)row*44,60,digit,0);
        else key_button((int)col*60,172+(int)row*44,60,keyboard.mode==CHAT_KBD_SYMBOL?symbols[number-1]:letters[number-1],digit);
    }
    key_button(0,304,120,keyboard.mode==CHAT_KBD_NUMBER?"123 / Aa":"Aa / 123",0);
    key_button(120,304,60,"0",0);key_button(180,304,60,"CLEAR",0);
    key_button(0,348,60,keyboard.mode==CHAT_KBD_SYMBOL?"ABC":"SYM",0);
    key_button(60,348,120,"SPACE",0);key_button(180,348,60,"SET",0);
    box(1,393,118,38,0x1a4b);box(121,393,118,38,0x1a4b);
    text(29,404,90,"CANCEL",0xffff,0x1a4b);text(172,404,60,"OK",0xffff,0x1a4b);dirty=0;
}
static void add_history(const char *s,unsigned n,unsigned mine,uint32_t sequence) {
    struct entry *e=&history[history_next];memset(e,0,sizeof(*e));memcpy(e->text,s,n);e->mine=mine;e->sequence=sequence;e->state=mine?0:1;
    history_next=(history_next+1)%8;if(history_count<8)history_count++;scroll_from_bottom=0;dirty=1;
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
static void check_radio(void) {
    if(client.pid>0&&!owner_finished){strcpy(notice,"RADIO SESSION ACTIVE");dirty=1;return;}
    if(client.pid>0){
        chat_client_close(&client);
        if(client.pid>0){strcpy(notice,"FINISHING PREVIOUS SESSION");dirty=1;return;}
    }
    owner_finished=0;linked=0;owner_phase=CHAT_STARTING;
    int started=chat_client_start(&client);
    if(started){owner_finished=1;owner_phase=0;strcpy(notice,started==-2?"MANAGED LAUNCHER REQUIRED":"RADIO WORKER UNAVAILABLE");}
    else strcpy(notice,"PREPARING RADIO - PLEASE WAIT");
    dirty=1;
}
static void read_owner(void){
    for(unsigned i=0;i<16;i++){
        struct chat_event e;int rc=chat_client_event(&client,&e);
        if(rc==0)return;
        if(rc<0){linked=0;if(!owner_finished){owner_phase=CHAT_REPAIR_REQUIRED;strcpy(notice,"RECOVERY NEEDS INSPECTION");}dirty=1;return;}
        if(e.kind==CHAT_STATE||e.kind==CHAT_ERROR){
            owner_phase=e.state;linked=e.kind==CHAT_STATE&&e.state==CHAT_READY;
            strcpy(notice,e.state==CHAT_READY?"READY - WAITING FOR PEER":e.state==CHAT_RESTORING?"RESTORING NORMAL WIFI":e.state==CHAT_REPAIR_REQUIRED?"RECOVERY NEEDS INSPECTION":"PREPARING RADIO - PLEASE WAIT");dirty=1;
        }else if(e.kind==CHAT_RECEIVED){chat.incoming_sequence=e.token;event(0,XNOW_CHAT_MESSAGE,e.text,e.length);}
        else if(e.kind==CHAT_CONFIRMED||e.kind==CHAT_FAILED){chat.sequence=e.token;chat.active=0;event(0,e.kind==CHAT_CONFIRMED?XNOW_CHAT_DELIVERED:XNOW_CHAT_FAILED,e.text,e.length);}
        else if(e.kind==CHAT_FINISHED){linked=0;owner_finished=1;owner_phase=e.state?CHAT_REPAIR_REQUIRED:0;strcpy(notice,e.state?"RADIO SESSION FAILED":"NORMAL WIFI RESTORED");dirty=1;}
    }
}
static void submit(void) {
    uint32_t token;int fd;ssize_t n;
    if(!linked){strcpy(notice,"CHECK RADIO BEFORE SENDING");dirty=1;return;}
    if(!edited||chat.active){strcpy(notice,chat.active?"WAIT FOR CURRENT MESSAGE":"TYPE A MESSAGE FIRST");dirty=1;return;}
    fd=open("/dev/urandom",O_RDONLY);if(fd<0)return;n=read(fd,&token,4);close(fd);if(n!=4)return;if(!token)token=1;
    if(!chat_client_send(&client,editor,edited,token)) {
        chat.active=1;add_history(editor,edited,1,token);edited=0;editor[0]=0;strcpy(notice,"SENDING - WAIT FOR PEER ACK");dirty=1;
    }
}
struct chat_bubble {char lines[12][104];unsigned count;int width,height;struct entry *entry;};
static struct chat_bubble bubbles[8];
static void prepare_bubble(struct chat_bubble *b,struct entry *e) {
    unsigned offset=0;int widest=0;memset(b,0,sizeof(*b));b->entry=e;
    while(e->text[offset]&&b->count<12) {
        int width=0;unsigned used=0,last_space=0;
        while(e->text[offset+used]&&used<102) {
            int next=glyph_width((unsigned char)e->text[offset+used]);if(width+next>164)break;
            if(e->text[offset+used]==' ')last_space=used;
            width+=next;used++;
        }
        if(e->text[offset+used]&&last_space)used=last_space;
        if(!used)used=1;
        memcpy(b->lines[b->count],e->text+offset,used);width=0;
        for(unsigned i=0;i<used;i++)width+=glyph_width((unsigned char)b->lines[b->count][i]);
        if(width>widest)widest=width;
        b->count++;offset+=used;while(e->text[offset]==' ')offset++;
    }
    if(!b->count)b->count=1;
    b->width=widest+24;if(b->width<56)b->width=56;
    b->height=(int)b->count*18+18;
}
static void draw(void) {
    int total=0,y;char counter[24];
    if(editing){draw_keyboard();return;}
    clip_top=0;clip_bottom=432;
    box(0,0,240,432,CHAT_BG);box(0,0,240,64,CHAT_HEADER);
    for(int dy=-6;dy<=6;dy++){int distance=dy<0?-dy:dy;box(12+distance,29+dy,2,2,CHAT_TEXT);}
    round_box(34,14,32,32,10,CHAT_OUT);round_box(41,22,18,11,4,CHAT_ACCENT);box(43,31,4,5,CHAT_ACCENT);
    text(76,12,132,"Cardputer",CHAT_TEXT,CHAT_HEADER);small_text(76,34,128,"ESP-NOW chat",CHAT_MUTED,CHAT_HEADER);
    for(int yy=-7;yy<=7;yy++)for(int xx=-7;xx<=7;xx++)if(xx*xx+yy*yy>=27&&xx*xx+yy*yy<=49&&!(xx>1&&yy<-2))box(221+xx,29+yy,1,1,CHAT_ACCENT);
    box(223,21,5,2,CHAT_ACCENT);box(226,21,2,5,CHAT_ACCENT);
    round_box(12,74,216,25,12,0x1125);round_box(21,84,5,5,2,linked?CHAT_ACCENT:CHAT_MUTED);
    const char *status=preview_mode?"Design preview / offline":!linked?(owner_phase==CHAT_STARTING?"Preparing radio...":owner_phase==CHAT_RESTORING?"Restoring normal Wi-Fi...":owner_phase==CHAT_REPAIR_REQUIRED?"Recovery needs inspection":"Radio not ready - tap refresh"):chat.active?"Sending message...":!strncmp(notice,"NO PEER ACK",11)?"Message not confirmed":"Waiting for nearby Cardputer";
    small_text(33,81,187,status,CHAT_MUTED,0x1125);
    for(unsigned k=0;k<history_count;k++){prepare_bubble(&bubbles[k],&history[(history_next+8-history_count+k)%8]);total+=bubbles[k].height+(bubbles[k].entry->mine?25:12);}
    int maximum=total>232?total-232:0;
    if(scroll_from_bottom>maximum)scroll_from_bottom=maximum;
    if(scroll_from_bottom<0)scroll_from_bottom=0;
    y=total>232?346-total+scroll_from_bottom:110;
    clip_top=108;clip_bottom=348;
    for(unsigned k=0;k<history_count;k++) {
        struct chat_bubble *b=&bubbles[k];struct entry *e=b->entry;
        int x=e->mine?228-b->width:12;unsigned short color=e->mine?CHAT_OUT:CHAT_IN;
        round_box(x,y,b->width,b->height,12,color);
        for(unsigned i=0;i<b->count;i++)text(x+12,y+9+(int)i*18,b->width-22,b->lines[i],CHAT_TEXT,color);
        if(e->mine)small_text(x+8,y+b->height+4,b->width-8,e->state==0?"Sending...":e->state==1?"Confirmed":"Unconfirmed",e->state==1?CHAT_ACCENT:CHAT_MUTED,CHAT_BG);
        y+=b->height+(e->mine?25:12);
    }
    clip_top=0;clip_bottom=432;
    box(0,351,240,1,0x21c8);snprintf(counter,sizeof(counter),"%u / 96",edited);small_text(181,355,49,counter,CHAT_MUTED,CHAT_BG);
    round_box(10,370,220,50,15,CHAT_INPUT);unsigned offset=edited>18?edited-18:0;
    text(23,386,154,edited?editor+offset:"Message...",edited?CHAT_TEXT:CHAT_MUTED,CHAT_INPUT);
    unsigned short send_color=linked&&edited&&!chat.active?CHAT_ACCENT:0x21e8;
    round_box(186,375,39,40,12,send_color);
    for(int dy=-7;dy<=7;dy++){int distance=dy<0?-dy:dy;box(199,395+dy,16-distance*2,1,linked?CHAT_HEADER:CHAT_MUTED);}
    box(199,394,7,2,send_color);dirty=0;
}
static int tap(unsigned x,unsigned y) {
    if(editing) {
        if(y>=392){
            if(x>=120){chat_keyboard_commit(&keyboard);memcpy(editor,keyboard.text,keyboard.length+1);edited=keyboard.length;}
            editing=0;dirty=1;return 0;
        }
        if(y>=172&&y<304){
            unsigned row=(y-172)/44,col=x/60;
            if(col<3)(void)chat_keyboard_key(&keyboard,row*3+col+1,now_ms());
            else if(row==0)chat_keyboard_delete(&keyboard);
            else if(row==1)chat_keyboard_left(&keyboard);
            else chat_keyboard_right(&keyboard);
        } else if(y>=304&&y<348){
            if(x<120)chat_keyboard_mode(&keyboard);else if(x<180)(void)chat_keyboard_key(&keyboard,0,now_ms());else chat_keyboard_clear(&keyboard);
        } else if(y>=348&&y<392){
            if(x<60)chat_keyboard_symbols(&keyboard);else if(x<180)chat_keyboard_space(&keyboard);else chat_keyboard_commit(&keyboard);
        }
        dirty=1;return 0;
    }
    if(y<64){if(x<30)return 1;if(x>=202)check_radio();return 0;}
    if(y>=370&&y<421) {
        if(x<182){chat_keyboard_init(&keyboard,editor);editing=1;dirty=1;}else submit();
    }
    return 0;
}
static int graphical(void) {
    struct hb_devices devices;int pressed=0,failed,press_x=0,press_y=0,quitting=0;
    if(hb_stop_signals_install(&stopped))return 2;
    check_radio();draw();
    if(hb_devices_open(&devices,pixels,HB_DISPLAY_PIXELS,&stopped)){chat_client_close(&client);return 2;}
    hb_devices_present(&devices);
    while(!stopped&&!devices.failed) {
        uint8_t packet[11];read_owner();
        if(quitting&&owner_finished)break;
        if(editing&&chat_keyboard_tick(&keyboard,now_ms()))dirty=1;
        if(dirty){draw();hb_devices_present(&devices);}hb_devices_flush(&devices);
        int got=hb_devices_next_touch(&devices,packet,25);if(got<0)break;
        if(got>0&&!quitting){
            struct hb_touch t;hb_touch_decode(packet,&t);
            if(t.down){if(!pressed){press_x=(int)t.x;press_y=(int)t.y;}pressed=1;}
            else if(pressed){
                int dx=(int)t.x-press_x,dy=(int)t.y-press_y;pressed=0;
                if(!editing&&press_y>=108&&press_y<348&&(dy>16||dy<-16)&&dx>=-48&&dx<=48){scroll_from_bottom+=dy;dirty=1;}
                else if(t.in_bounds&&dx>=-14&&dx<=14&&dy>=-14&&dy<=14&&tap(t.x,t.y)){chat_client_stop(&client);quitting=1;owner_phase=CHAT_RESTORING;linked=0;dirty=1;}
            }
        }
    }
    chat_client_close(&client);failed=devices.failed;if(hb_devices_close(&devices)<0)failed=1;return stopped?0:failed?2:0;
}
int main(int argc,char **argv) {
    if(argc==2&&!strcmp(argv[1],"--help")){puts("ESP-NOW Chat: on-demand telephone touch keyboard, RAM-only history, BACK TO APPS. Uses an independent native radio owner and restores normal WiFi on exit. Connect stock WiFi first; user-storage files only. --render-preview and --render-keyboard-preview write RGB565 stdout without device access.");return 0;}
    if(argc==2&&!strcmp(argv[1],"--version")){puts("0.1.0-dev.3");return 0;}
    if(argc==2&&!strcmp(argv[1],"--selftest")) {
        strcpy(editor,"OLD");edited=3;
        if(tap(20,395)||!editing)return 1;
        tap(70,180);tap(20,410);
        if(editing||strcmp(editor,"OLD"))return 2;
        tap(20,395);tap(70,180);tap(160,410);
        if(editing||strcmp(editor,"OLDa"))return 3;
        tap(200,395);if(strcmp(editor,"OLDa"))return 4;
        if(!tap(16,30))return 5;
        puts("CHAT UI SELFTEST: modal input, cancel, accept, unavailable-radio draft and back passed");return 0;
    }
    if(argc==2&&(!strcmp(argv[1],"--render-preview")||!strcmp(argv[1],"--render-keyboard-preview"))) {
        const char *a="Hello from Cardputer.";const char *b="Loud and clear. How is it going?";const char *c="Looks good. Let's test both ways.";
        add_history(a,(unsigned)strlen(a),0,1);add_history(b,(unsigned)strlen(b),1,2);history[1].state=1;add_history(c,(unsigned)strlen(c),0,3);preview_mode=1;
        strcpy(editor,"Hello Cardputer");edited=(unsigned)strlen(editor);strcpy(notice,"PREVIEW - NOT CONNECTED");
        if(!strcmp(argv[1],"--render-keyboard-preview")){chat_keyboard_init(&keyboard,editor);editing=1;}
        draw();
        return fwrite(pixels,1,sizeof(pixels),stdout)==sizeof(pixels)?0:74;
    }
    if(argc!=1)return 64;
    return graphical();
}

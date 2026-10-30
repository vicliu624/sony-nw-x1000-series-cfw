#ifndef XNOW_CARDPUTER_CHAT_UI_H
#define XNOW_CARDPUTER_CHAT_UI_H
/* Shared native RGB565 renderer: the PC preview executes this exact code. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../../../native/ui_font.h"
namespace xnow_ui {
enum { W=240,H=135,BG=0x0882,HEADER=0x10e4,IN=0x1946,OUT=0x126a,
       ACCENT=0x5eb9,TEXT=0xefbe,MUTED=0x8d36,COMPOSER=0x1105 };
struct Message {const char *text;unsigned mine,state;};
struct Canvas {
    uint16_t *pixels;int top=0,bottom=H;
    void box(int x,int y,int w,int h,uint16_t color) {
        for(int row=y;row<y+h&&row<bottom&&row<H;row++)
            for(int col=x;col<x+w&&col<W;col++)if(row>=top&&col>=0)pixels[row*W+col]=color;
    }
    void round(int x,int y,int w,int h,int radius,uint16_t color) {
        for(int row=0;row<h;row++){
            int dy=row<radius?radius-row:row>=h-radius?row-(h-radius-1):0,inset=0;
            if(dy){inset=radius;while(inset>0&&(radius-inset+1)*(radius-inset+1)+dy*dy<=radius*radius)inset--;}
            box(x+inset,y+row,w-2*inset,1,color);
        }
    }
    static int advance(unsigned char ch,bool tiny=false){
        if(ch<32||ch>126)ch='?';
        return tiny?(hb_ui_advance[ch-32]+1)/2:(hb_ui_advance[ch-32]*3+3)/4;
    }
    static uint16_t blend(uint16_t fg,uint16_t bg,unsigned a){
        unsigned r=(((fg>>11)&31)*a+((bg>>11)&31)*(15-a)+7)/15;
        unsigned g=(((fg>>5)&63)*a+((bg>>5)&63)*(15-a)+7)/15;
        unsigned b=((fg&31)*a+(bg&31)*(15-a)+7)/15;
        return (r<<11)|(g<<5)|b;
    }
    void text(int x,int y,int width,const char *s,uint16_t fg,uint16_t bg,bool tiny=false){
        int right=x+width;
        for(unsigned n=0;s[n]&&n<100;n++){
            unsigned char ch=(unsigned char)s[n];if(ch<32||ch>126)ch='?';
            int adv=advance(ch,tiny);if(x+adv>right)break;
            for(int row=0;row<(tiny?8:12);row++)for(int col=0;col<adv;col++){
                unsigned sx=tiny?col*2:col*4/3,sy=tiny?row*2:row*4/3;if(sx>=16)continue;
                unsigned v=hb_ui_font[ch-32][sy][sx/2],a=sx&1?v&15:v>>4;
                if(a)box(x+col,y+row,1,1,blend(fg,bg,a));
            }
            x+=adv;
        }
    }
};
struct Lines {char text[8][97];int count=0,width=0;};
inline Lines wrap(const char *text){
    Lines out;unsigned at=0;
    while(text[at]&&out.count<8){
        unsigned start=at,lastSpace=at;int width=0;
        while(text[at]&&width+Canvas::advance((unsigned char)text[at])<=180){
            if(text[at]==' ')lastSpace=at;
            width+=Canvas::advance((unsigned char)text[at++]);
        }
        if(text[at]&&lastSpace>start){at=lastSpace;width=0;for(unsigned i=start;i<at;i++)width+=Canvas::advance((unsigned char)text[i]);}
        unsigned length=at-start;if(length>96)length=96;
        memcpy(out.text[out.count],text+start,length);out.text[out.count][length]=0;
        if(width>out.width)out.width=width;
        out.count++;while(text[at]==' ')at++;
    }
    return out;
}
inline void render(uint16_t *pixels,const Message *messages,unsigned count,const char *draft,
                   unsigned channel,bool paired,bool ready,bool active,const char *notice){
    Canvas c;c.pixels=pixels;c.box(0,0,W,H,BG);c.box(0,0,W,26,HEADER);
    c.round(6,4,18,17,6,OUT);c.round(10,8,10,6,2,ACCENT);c.box(11,14,2,3,ACCENT);
    c.text(30,0,150,"X1060",TEXT,HEADER);
    c.text(30,15,153,notice,MUTED,HEADER,true);
    c.round(188,4,46,16,7,ready?OUT:IN);char label[20];snprintf(label,sizeof(label),"CH %02u",channel);
    c.text(196,8,36,label,ready?ACCENT:MUTED,ready?OUT:IN,true);
    c.top=29;c.bottom=99;
    if(!count){
        c.text(49,48,190,ready?"Waiting for X1060":"Radio unavailable",TEXT,BG);
        c.text(42,69,180,paired?"Peer seen. Send a message.":"Same channel. Fn+P to pair.",MUTED,BG,true);
    }
    int y=98;
    for(unsigned k=0;k<count&&k<8;k++){
        const Message &m=messages[count-1-k];Lines lines=wrap(m.text);
        int height=lines.count*13+7,width=lines.width+16;if(width<38)width=38;
        y-=height;int x=m.mine?W-12-width:6;uint16_t color=m.mine?OUT:IN;
        c.round(x,y,width,height,6,color);
        for(int line=0;line<lines.count;line++)c.text(x+8,y+4+line*13,width-16,lines.text[line],TEXT,color);
        if(m.mine){uint16_t status=m.state==1?ACCENT:m.state==2?0xfbad:MUTED;c.box(232,y+height/2-1,3,3,status);}
        y-=4;if(y<29)break;
    }
    c.top=0;c.bottom=H;c.round(5,104,230,22,7,COMPOSER);
    unsigned length=(unsigned)strlen(draft),start=0;int width=0;
    for(unsigned i=0;i<length;i++)width+=Canvas::advance((unsigned char)draft[i]);
    while(width>182&&start<length)width-=Canvas::advance((unsigned char)draft[start++]);
    c.text(13,108,184,length?draft+start:"Type, then ENTER",length?TEXT:MUTED,COMPOSER);
    c.round(211,107,20,16,5,length&&ready&&!active?OUT:IN);
    uint16_t arrow=length&&ready&&!active?ACCENT:MUTED;
    for(int row=0;row<9;row++){int half=4-(row>4?row-4:4-row);c.box(218,110+row,half+1,1,arrow);}
    c.text(7,126,78,"ENTER send",MUTED,BG,true);c.text(92,126,90,"Fn+P pair",MUTED,BG,true);
    snprintf(label,sizeof(label),"%u/96",length);c.text(207,126,32,label,MUTED,BG,true);
}
}
#endif

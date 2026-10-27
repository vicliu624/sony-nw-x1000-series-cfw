#include "canvas.h"
#include "../native/font.inc"
static void rect(void *context,int x,int y,int w,int h,unsigned short color){
 struct hb_store_canvas *c=context;
 if(x<0||x>=240||y<0||y>=432||w<=0||w>240-x||h<=0||h>432-y)return;
 for(int j=y;j<y+h;j++)for(int i=x;i<x+w;i++)c->pixels[j*240+i]=color;
}
static void text(void *context,int x,int y,const char *value,int scale,unsigned short color){
 if(!value||(scale!=1&&scale!=2)||x<0||y<0||y>432-7*scale)return;
 for(unsigned n=0;n<40&&value[n]&&x<=240-5*scale;n++,x+=6*scale){
  unsigned char ch=(unsigned char)value[n];if(ch>='a'&&ch<='z')ch-=32;
  int g=ch>='0'&&ch<='9'?ch-'0':ch>='A'&&ch<='Z'?ch-'A'+10:-1;
  if(g>=0){
   for(int row=0;row<7;row++)for(int col=0;col<5;col++)
    if(glyph[g][row]&(1<<(4-col)))rect(context,x+col*scale,y+row*scale,scale,scale,color);
  }else if(ch=='.')rect(context,x+2*scale,y+6*scale,scale,scale,color);
  else if(ch=='?'){
   static const unsigned char question[7]={14,17,1,2,4,0,4};
   for(int row=0;row<7;row++)for(int col=0;col<5;col++)
    if(question[row]&(1<<(4-col)))rect(context,x+col*scale,y+row*scale,scale,scale,color);
  }else if(ch!=' ')rect(context,x,y+3*scale,3*scale,scale,color);
 }
}
int hb_store_canvas_init(struct hb_store_canvas *canvas,unsigned short *pixels,unsigned count,struct hb_store_painter *p){
 if(!canvas||!pixels||count<240u*432u||!p)return -1;
 canvas->pixels=pixels;canvas->count=count;
 p->context=canvas;p->rect=rect;p->text=text;return 0;
}

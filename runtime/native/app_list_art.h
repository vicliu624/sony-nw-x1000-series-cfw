/* Shared 240x432 application-list presentation. No files or device operations. */
#ifndef HB_APP_LIST_ART_H
#define HB_APP_LIST_ART_H
#include "../store/view.h"
#include "app_icons_data.h"
#include "ui_font.h"
#define HB_ART_BG 0x0863
#define HB_ART_ROW 0x10c5
#define HB_ART_TEXT 0xef9e
#define HB_ART_MUTED 0x94d4
static inline int hb_art_equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static inline const struct hb_app_art *hb_art_find(const char *id){
 unsigned n=sizeof hb_app_artwork/sizeof hb_app_artwork[0];
 for(unsigned i=0;i<n-1;i++)if(hb_art_equal(id,hb_app_artwork[i].id))return hb_app_artwork+i;
 return hb_app_artwork+n-1;
}
static inline unsigned short hb_art_blend(unsigned short fg,unsigned short bg,unsigned a){
 unsigned r=(((fg>>11)&31)*a+((bg>>11)&31)*(15-a)+7)/15;
 unsigned g=(((fg>>5)&63)*a+((bg>>5)&63)*(15-a)+7)/15;
 unsigned b=((fg&31)*a+(bg&31)*(15-a)+7)/15;
 return (unsigned short)((r<<11)|(g<<5)|b);
}
/* Proportional ASCII Noto raster, clipped with an ellipsis at a glyph boundary. */
static inline void hb_art_text(const struct hb_store_painter *p,int x,int y,int width,const char *s,unsigned short fg,unsigned short bg){
 int end=x+width;
 for(unsigned n=0;s&&s[n]&&n<64;n++){
  unsigned ch=(unsigned char)s[n];if(ch<32||ch>126)ch='?';unsigned g=ch-32,advance=hb_ui_advance[g];
  int ellipsis=s[n+1]&&x+(int)advance+12>end;
  if(ellipsis){for(int i=0;i<3;i++)p->rect(p->context,x+i*4,y+12,2,2,fg);break;}
  if(x+(int)advance>end)break;
  for(int yy=0;yy<16;yy++)for(unsigned xx=0;xx<advance&&xx<16;xx++){
   unsigned v=hb_ui_font[g][yy][xx/2];unsigned a=xx&1?v&15:v>>4;
   if(a)p->rect(p->context,x+(int)xx,y+yy,1,1,hb_art_blend(fg,bg,a));
  }
  x+=(int)advance;
 }
}
static inline void hb_art_icon(const struct hb_store_painter *p,int x,int y,const struct hb_app_art *art){
 for(int row=0;row<36;row++)for(int col=0;col<36;){
  unsigned short color=art->pixels[row*36+col];int first=col++;
  while(col<36&&art->pixels[row*36+col]==color)col++;
  if(color)p->rect(p->context,x+first,y+row,col-first,1,color);
 }
}
static inline void hb_art_header(const struct hb_store_painter *p,const char *title,unsigned count){
 p->rect(p->context,0,0,240,432,HB_ART_BG);
 p->rect(p->context,12,12,3,22,0x6df6);
 hb_art_text(p,23,13,165,title,HB_ART_TEXT,HB_ART_BG);
 char value[4];unsigned n=0;if(count>=10)value[n++]=(char)('0'+count/10);value[n++]=(char)('0'+count%10);value[n]=0;
 hb_art_text(p,208,13,23,value,HB_ART_MUTED,HB_ART_BG);
 p->rect(p->context,12,42,216,1,0x2148);
}
static inline void hb_art_row_with_art(const struct hb_store_painter *p,unsigned row,const char *id,const char *name,const char *detail,int selected,const struct hb_app_art *a){
 (void)id;int y=48+(int)row*52;unsigned short bg=selected?0x19e9:HB_ART_ROW;
 p->rect(p->context,8,y+1,224,47,bg);
 /* Stepped corners retain a crisp card outline on the native LCD. */
 p->rect(p->context,8,y+1,2,2,HB_ART_BG);p->rect(p->context,230,y+1,2,2,HB_ART_BG);
 p->rect(p->context,8,y+46,2,2,HB_ART_BG);p->rect(p->context,230,y+46,2,2,HB_ART_BG);
 hb_art_icon(p,14,y+6,a);
 hb_art_text(p,60,y+6,155,name&&*name?name:a->title,HB_ART_TEXT,bg);
 hb_art_text(p,60,y+25,155,detail&&*detail?detail:a->subtitle,HB_ART_MUTED,bg);
 p->rect(p->context,220,y+21,1,1,0x7bd0);p->rect(p->context,221,y+22,1,1,0x7bd0);p->rect(p->context,222,y+23,1,1,0x7bd0);p->rect(p->context,221,y+24,1,1,0x7bd0);p->rect(p->context,220,y+25,1,1,0x7bd0);
}
static inline void hb_art_row(const struct hb_store_painter *p,unsigned row,const char *id,const char *name,const char *detail,int selected){
 hb_art_row_with_art(p,row,id,name,detail,selected,hb_art_find(id));
}
static inline void hb_art_footer(const struct hb_store_painter *p,unsigned page,unsigned count,int market){
 unsigned pages=count?(count+5)/6:1;
 for(unsigned i=0;i<pages;i++)p->rect(p->context,120-(int)pages*5+(int)i*10,371,5,3,i==page?0x6df6:0x39ca);
 p->rect(p->context,8,384,224,1,0x2148);
 int first=market?80:96,second=market?160:168;
 hb_art_text(p,market?20:14,401,first-16,market?"Back":"Walkman",HB_ART_TEXT,HB_ART_BG);
 hb_art_text(p,first+16,401,second-first-20,"Prev",page?HB_ART_TEXT:0x526b,HB_ART_BG);
 hb_art_text(p,second+16,401,240-second-20,"Next",page+1<pages?HB_ART_TEXT:0x526b,HB_ART_BG);
}
#endif

#include "epub.h"
#include "../reader.h"
#include <stdlib.h>
#include <string.h>
extern int ep_image_info(struct ep_book*,unsigned,unsigned*,unsigned*);
extern void ep_image_draw(struct ep_book*,unsigned,uint16_t*,int,int,int,int);
static unsigned font_px(const struct ep_style*s,unsigned base){int n=(int)base*s->font/1000;if(n<8)n=8;if(n>64)n=64;return (unsigned)n;}
static int em(int value,unsigned font){int n=(int)((int64_t)value*font/1000);if(n< -224)n=-224;if(n>1000)n=1000;return n;}
static int closing(unsigned c){return c==0xff0c||c==0x3002||c==0xff01||c==0xff1f||c==0x3001||c==0xff09||c==0x300b||c==0x3011||c==0x201d||c==0x2019||c==0x2026||c==0x2014||c==','||c=='.'||c=='!'||c=='?'||c==';'||c==':';}
static int opening(unsigned c){return c==0xff08||c==0x300a||c==0x3010||c==0x201c||c==0x2018||c==0x300c;}
int ep_layout(struct ep_book*b,uint32_t at,unsigned base,const struct dx_font*font,uint32_t limit){struct ep_doc*d=b->doc;if(!d||at>d->count)return 0;if(!limit||limit>d->count)limit=d->count;struct ep_page*out=&b->page;memset(out,0,sizeof(*out));unsigned p=at;int y=0,first_line=0;unsigned iterations=0;
 while(p<limit){if(b->stop&&*b->stop)return 0;if(++iterations>EP_TOKENS+1024)return 0;struct ep_token*t=d->tokens+p;struct ep_style*s=d->styles+t->style;unsigned body=font_px(s,base);
  if(t->cp==EPUB_START){int top=em(s->top,body);if(top<0)top=0;if(top>150)top=150;if(y>0&&((s->flags&EP_BREAK_BEFORE)||y+top+(int)body>326))break;y+=top;first_line=1;p++;continue;}
  if(t->cp==EP_END){int bottom=em(s->bottom,body);if(bottom>0)y+=bottom;if(y>326)y=326;p++;first_line=0;continue;}
  unsigned start=p,word_end=0,word_ops=0;int word_width=0;struct ep_op line[256];unsigned n=0;int width=0,asc=0,desc=0,spacing=(int)(body*s->height/1000);if(spacing<(int)body)spacing=(int)body;int left=em(s->left,body)+(first_line?em(s->indent,body):0),right=em(s->right,body);if(left<0)left=0;if(right<0)right=0;if(left+right>140){left=right=0;}int available=224-left-right;int hard_break=0;
  while(p<limit&&n<256){t=d->tokens+p;s=d->styles+t->style;if(t->cp==EPUB_START||t->cp==EP_END)break;if(t->cp==EP_BR){p++;hard_break=1;break;}if(!n&&t->cp==' '&&!(s->flags&EP_PRE)){p++;start=p;continue;}unsigned size=font_px(s,base),actual=(s->flags&(EP_SUP|EP_SUB))?size*65/100:size;if(actual<8)actual=8;int w=0,h=(int)actual,rise=s->flags&EP_SUP?(int)size/2:0,drop=s->flags&EP_SUB?(int)size*3/10:0;
   if(t->cp>=EP_IMAGE){unsigned iw,ih;if(!ep_image_info(b,t->cp-EP_IMAGE,&iw,&ih)){iw=24;ih=20;b->warnings++;}w=(int)iw;h=(int)ih;if(s->imgh){h=s->imgh<0?-s->imgh:em(s->imgh,size);w=(int)((uint64_t)iw*h/ih);}if(s->imgw){w=s->imgw<0?-s->imgw:em(s->imgw,size);if(!s->imgh)h=(int)((uint64_t)ih*w/iw);}if(w>available){h=h*available/w;w=available;}if(h>300){w=w*300/h;h=300;}if(w<1)w=1;if(h<1)h=1;rise=drop=0;}
   else w=(int)(dx_width(font,t->cp)*actual/16)+(!!(s->flags&EP_BOLD))+(s->flags&EP_ITALIC?(int)actual/5:0);
   if(n&&width+w>available){if(word_ops){n=word_ops;p=word_end;width=word_width;}else if(n>1&&(closing(t->cp)||opening(line[n-1].cp))){n--;p--;width-=line[n].w;}break;}
   if(n&&t->cp==' '){word_ops=n;word_end=p+1;word_width=width;}
   line[n++]=(struct ep_op){(int16_t)width,0,(int16_t)w,(int16_t)h,t->cp,t->style,t->link};width+=w;if(h+rise>asc)asc=h+rise;if(drop>desc)desc=drop;int gap=(int)(size*s->height/1000);if(gap>spacing)spacing=gap;p++;
  }
  if(!n&&!hard_break){if(p==start){p++;b->warnings++;}continue;}
  int line_height=asc+desc;if(line_height<spacing)line_height=spacing;if(line_height<8)line_height=8;
  if(y+line_height>326&&y>0){p=start;break;}if(line_height>326)line_height=326;
  struct ep_style*block_style=d->styles+d->tokens[start<d->count?start:d->count-1].style;int x=8+left;if(block_style->align==1)x+=(available-width)/2;else if(block_style->align==2)x+=available-width;int justify=block_style->align==3&&!hard_break&&p<limit&&d->tokens[p].cp!=EP_END&&n>1?available-width:0;if(justify<0)justify=0;
  for(unsigned i=0;i<n;i++){if(out->count==EP_DRAW)return 0;struct ep_op op=line[i];struct ep_style*st=d->styles+op.style;unsigned size=font_px(st,base);int rise=st->flags&EP_SUP?(int)size/2:0,drop=st->flags&EP_SUB?(int)size*3/10:0;if(op.cp>=EP_IMAGE)rise=drop=0;op.x=(int16_t)(x+op.x+(n>1?(int)(justify*i/(n-1)):0));op.y=(int16_t)(56+y+asc-op.h-rise+drop);out->ops[out->count++]=op;}
  y+=line_height;first_line=0;if(y>=326)break;
 }
 out->next=p;if(p==at&&p<limit)return 0;return 1;}
void ep_render(struct ep_book*b,const struct dx_font*f,uint16_t*surface,unsigned base,uint16_t fg,uint16_t bg){(void)base;for(unsigned i=0;i<b->page.count;i++){struct ep_op*op=b->page.ops+i;struct ep_style*s=b->doc->styles+op->style;if(op->cp>=EP_IMAGE){ep_image_draw(b,op->cp-EP_IMAGE,surface,op->x,op->y,op->w,op->h);continue;}unsigned cp=op->cp;char text[5];unsigned n;if(cp<128){text[0]=(char)cp;n=1;}else if(cp<0x800){text[0]=0xc0|(cp>>6);text[1]=0x80|(cp&63);n=2;}else if(cp<0x10000){text[0]=0xe0|(cp>>12);text[1]=0x80|((cp>>6)&63);text[2]=0x80|(cp&63);n=3;}else{text[0]=0xf0|(cp>>18);text[1]=0x80|((cp>>12)&63);text[2]=0x80|((cp>>6)&63);text[3]=0x80|(cp&63);n=4;}text[n]=0;uint16_t color=s->colored?s->color:fg;if(bg<0x4000&&color<0x4000)color=fg;
  if(s->flags&EP_ITALIC){/* row-shift the actual rendered glyph; no font resource mutation */uint16_t temp[240*64];unsigned rows=(unsigned)op->h;if(rows>64)rows=64;for(unsigned j=0;j<rows;j++)for(unsigned x=0;x<240;x++)temp[j*240+x]=bg;er_text(f,temp,0,0,text,rows,color,80);unsigned width=dx_width(f,cp)*rows/16;for(unsigned j=0;j<rows;j++)for(unsigned x=0;x<width;x++){int px=op->x+(int)x+(int)(rows-1-j)/5,py=op->y+(int)j;if(px>=0&&px<240&&py>=0&&py<432&&temp[j*240+x]!=bg)surface[py*240+px]=temp[j*240+x];}}
  else er_text(f,surface,op->x,op->y,text,(unsigned)op->h,color,80);
  if(s->flags&EP_BOLD)er_text(f,surface,op->x+1,op->y,text,(unsigned)op->h,color,80);
  if(s->flags&EP_UNDERLINE){int y=op->y+op->h;if(y<382)for(int x=0;x<op->w&&op->x+x<240;x++)if(op->x+x>=0)surface[y*240+op->x+x]=color;}
 }}
int ep_previous(struct ep_book*b,uint32_t current,unsigned base,const struct dx_font*f,uint32_t*out){uint32_t pos=0,previous=0;if(!current){*out=0;return 1;}unsigned guard=0;while(pos<current){if(++guard>EP_TOKENS)return 0;previous=pos;if(!ep_layout(b,pos,base,f,current))return 0;if(b->page.next<=pos)return 0;pos=b->page.next;}*out=previous;return 1;}

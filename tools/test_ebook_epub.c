#include "../runtime/apps/ebook/ui.h"
#include "../runtime/apps/ebook/epub/epub.h"
#include "../runtime/apps/emulators/platform.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct er_ui u;
extern unsigned char*ep_pixels(struct ep_book*,unsigned,int*,int*);
int main(int argc,char**argv){assert(argc==2||argc==3);if(argc==3){struct er_book bad={0};assert(!er_open(&bad,argv[1],ER_AUTO,0));return 0;}assert(er_ui_init(&u,"work/ebook-data/font.bin","work/ebook-data/gb18030.bin"));assert(er_open(&u.book,argv[1],ER_AUTO,&u.maps));assert(u.book.epub);u.book.font=&u.font;u.book.size=20;u.font_size=20;u.mode=ER_READING;struct ep_book*b=u.book.epub;unsigned pages=0,images=0,links=0,sup=0,sub=0;assert(b->spine_count&&b->toc_count);
for(unsigned c=0;c<b->spine_count;c++){assert(ep_load(b,c));for(unsigned j=0;j<b->doc->image_count;j++){int w,h;assert(ep_pixels(b,j,&w,&h));assert(w>0&&h>0);images++;}uint32_t at=0;unsigned guard=0;do{assert(er_page_at(&u.book,at,&u.page));assert(u.page.next>at||at==b->doc->count);for(unsigned j=0;j<b->page.count;j++){struct ep_op*o=b->page.ops+j;assert(o->x>=0&&o->x+o->w<=240&&o->y>=56&&o->y+o->h<=382);unsigned f=b->doc->styles[o->style].flags;sup+=!!(f&EP_SUP);sub+=!!(f&EP_SUB);links+=!!o->link;}u.book.current=at;er_ui_render(&u);if(c==6&&guard==0){FILE*out=fopen("work/ebook-preview/06-epub.rgb565","wb");assert(out);assert(fwrite(ep_canvas,2,240*432,out)==240*432);fclose(out);}at=u.page.next;pages++;assert(++guard<10000);}while(at<b->doc->count);}
/* Link activation and return use the actual UI hit path. */
int tested_link=0;for(unsigned c=0;c<b->spine_count&&!tested_link;c++){assert(ep_load(b,c));for(uint32_t pos=0;pos<b->doc->count;){assert(er_page_at(&u.book,pos,&u.page));uint32_t next=u.page.next;for(unsigned j=0;j<b->page.count;j++){struct ep_op op=b->page.ops[j];if(op.link){u.book.current=pos;u.mode=ER_READING;er_ui_touch(&u,op.x+op.w/2,op.y+op.h/2);assert(u.link_return);u.mode=ER_MENU;er_ui_touch(&u,100,70);assert(!u.link_return&&u.book.epub->chapter==c&&u.book.current==pos);tested_link=1;break;}}if(tested_link||next<=pos)break;pos=next;}}
for(unsigned i=0;i<b->toc_count;i++){uint32_t at;assert(ep_goto(b,b->toc[i].path,b->toc[i].fragment,&at));assert(er_page_at(&u.book,at,&u.page));}
u.mode=ER_MENU;er_ui_touch(&u,50,205);assert(u.mode==ER_TOC);er_ui_touch(&u,50,80);assert(u.mode==ER_READING);u.mode=ER_JUMP;u.jump=100;er_ui_touch(&u,100,350);assert(u.mode==ER_READING&&b->chapter+1==b->spine_count);u.mode=ER_JUMP;u.jump=0;er_ui_touch(&u,100,350);assert(u.mode==ER_READING&&b->chapter==0&&u.book.current==0);
struct er_state state={0},restored;unsigned char raw[ER_STATE_BYTES];u.book.current=2;er_state_update(&state,&u.book,2);er_state_encode(&state,raw);assert(er_state_decode(&restored,raw,sizeof raw));struct er_mark*m=er_state_find(&restored,u.book.identity);assert(m&&m->format==1&&m->chapter==b->chapter&&m->offset==2);
/* Convert a TXT slot to the legacy version and recalculate its checksum. */
memset(&state,0,sizeof state);er_state_encode(&state,raw);memcpy(raw,"XREAD1\0\0",8);raw[8]=1;unsigned hash=2166136261u;for(unsigned j=0;j<sizeof raw;j++)hash=(hash^((j>=20&&j<24)?0:raw[j]))*16777619u;for(unsigned j=0;j<4;j++)raw[20+j]=(unsigned char)(hash>>(8*j));assert(er_state_decode(&restored,raw,sizeof raw));
printf("EPUB complete: spine=%u toc=%u pages=%u images=%u link-glyphs=%u sup=%u sub=%u warnings=%u\n",b->spine_count,b->toc_count,pages,images,links,sup,sub,b->warnings);er_ui_close(&u);return 0;}

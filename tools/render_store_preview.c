#include "../runtime/store/canvas.h"
#include <stdio.h>
#include <assert.h>
static unsigned short storage[240*432+2];
static int backend(void *context,enum hb_store_action action,volatile int *stop){(void)context;(void)action;(void)stop;return 0;}
static void output(const char *directory,const char *name,struct hb_store_session *s,struct hb_store_painter *p){
 char path[1024];assert(snprintf(path,sizeof path,"%s/%s.ppm",directory,name)<(int)sizeof path);
 assert(!hb_store_view_draw(s,"Demo 0.1.2",p));
 assert(storage[0]==0x1234&&storage[240*432+1]==0xabcd);
 FILE *f=fopen(path,"wb");assert(f);fprintf(f,"P6\n240 432\n255\n");
 for(unsigned i=1;i<=240*432;i++){
  unsigned v=storage[i];unsigned char rgb[3]={(unsigned char)(((v>>11)&31)*255/31),(unsigned char)(((v>>5)&63)*255/63),(unsigned char)((v&31)*255/31)};
  assert(fwrite(rgb,1,3,f)==3);
 }assert(!fclose(f));
}
int main(int argc,char **argv){
 assert(argc==2);storage[0]=0x1234;storage[240*432+1]=0xabcd;
 struct hb_store_canvas canvas;struct hb_store_painter p;struct hb_store_session s;
 assert(!hb_store_canvas_init(&canvas,storage+1,240*432,&p));
 struct hb_store_backend b={0,backend};assert(!hb_store_session_init(&s,b));
 output(argv[1],"list",&s,&p);
 assert(!hb_store_session_request(&s,HB_STORE_INSTALL));output(argv[1],"confirm",&s,&p);
 assert(!hb_store_session_begin(&s));output(argv[1],"working",&s,&p);
 assert(!hb_store_session_execute(&s));output(argv[1],"complete",&s,&p);
 s.result=HB_RECOVERY_REQUIRED;output(argv[1],"recovery",&s,&p);
 return 0;
}

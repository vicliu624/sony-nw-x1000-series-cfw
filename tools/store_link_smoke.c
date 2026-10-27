/* Offline link/runtime probe only. Never a device application entry point. */
#define _XOPEN_SOURCE 700
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include "../runtime/store/target_abi.h"
#include "../runtime/store/install_posix.h"
#include "../runtime/store/session_local.h"
#include "../runtime/store/canvas.h"
#include "../runtime/store/ui_loop.h"
#include "../runtime/store/catalog_posix.h"
#include "../runtime/store/catalog_view.h"
#include "../runtime/store/catalog_loop.h"
#include "../runtime/store/browser.h"
#include "../runtime/store/termination.h"
#include "../runtime/store/app.h"
#include "../runtime/store/cleanup_plan.h"
extern int __libc_start_main(int (*)(int,char **,char **),int,char **,void (*)(void),void (*)(void),void (*)(void),void *);
extern int __snprintf_chk(char *,size_t,int,size_t,const char *,...);
extern void hb_link_fault(const char *,unsigned);
extern void hb_link_cancel_write(unsigned,volatile int *);
extern void hb_link_signal_write(unsigned);
static volatile sig_atomic_t previous_received;
static void previous_handler(int number){(void)number;previous_received=1;}
static unsigned short ui_pixels[240*432];
struct ui_fixture {int sample,presents;enum hb_store_action action;};
static int ui_present(void *context){struct ui_fixture *f=context;f->presents++;return 0;}
static int ui_next(void *context,unsigned char *packet){
 struct ui_fixture *f=context;int sample=f->sample++;
 if(sample>=8)return -2; /* Missing an intended exit is a test failure. */
 unsigned x=sample/2==1?160:20;
 unsigned y=sample/2==0?(f->action==HB_STORE_INSTALL?180:f->action==HB_STORE_RECOVER?240:300):400;
 unsigned rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;
 memset(packet,0,11);packet[1]=(unsigned char)(sample%2==0);
 packet[2]=(unsigned char)(rx>>8);packet[3]=(unsigned char)rx;
 packet[4]=(unsigned char)(ry>>8);packet[5]=(unsigned char)ry;return 1;
}
static int catalog_next(void *context,unsigned char *packet){
 struct ui_fixture *f=context;int sample=f->sample++;
 if(sample>=2)return -2;
 unsigned rx=(20*2929+239)/240,ry=((431-60)*5281+431)/432;
 memset(packet,0,11);packet[1]=(unsigned char)(sample==0);
 packet[2]=(unsigned char)(rx>>8);packet[3]=(unsigned char)rx;
 packet[4]=(unsigned char)(ry>>8);packet[5]=(unsigned char)ry;return 1;
}
static int browser_next(void *context,unsigned char *packet){
 struct ui_fixture *f=context;int sample=f->sample++;
 if((int)f->action==3){
  if(sample>=4)return -2;
  unsigned y=sample<2?112:400,rx=(20*2929+239)/240,ry=((431-y)*5281+431)/432;
  memset(packet,0,11);packet[1]=(unsigned char)(sample%2==0);packet[2]=(unsigned char)(rx>>8);packet[3]=(unsigned char)rx;packet[4]=(unsigned char)(ry>>8);packet[5]=(unsigned char)ry;return 1;
 }
 static const unsigned taps[][2]={{20,60},{20,180},{160,400},{20,400},{20,400},
  {20,60},{20,240},{160,400},{20,400},{20,400},{20,400}};
 if(f->action!=HB_STORE_INSTALL&&sample>=2)return f->action==HB_STORE_RECOVER?-1:-2;
 if(sample>=22)return -2;
 const unsigned *point=taps[sample/2];
 unsigned rx=(point[0]*2929+239)/240,ry=((431-point[1])*5281+431)/432;
 memset(packet,0,11);packet[1]=(unsigned char)(sample%2==0);
 packet[2]=(unsigned char)(rx>>8);packet[3]=(unsigned char)rx;
 packet[4]=(unsigned char)(ry>>8);packet[5]=(unsigned char)ry;return 1;
}
struct app_fixture {struct ui_fixture ui;int opened,closed,mode;unsigned short *pixels;};
static int app_open(void *context,unsigned short *pixels,unsigned count,volatile int *stop,struct hb_store_ui_io *io){
 struct app_fixture *f=context;f->opened++;f->pixels=pixels;
 if(!pixels||count!=240u*432u||*stop)return -1;
 if(f->mode==1)return -1;
 if(f->mode==2&&raise(SIGTERM))return -1;
 if(f->mode==3)f->ui.action=(enum hb_store_action)3;
 io->context=&f->ui;io->next=browser_next;io->present=ui_present;return 0;
}
static int app_close(void *context){
 struct app_fixture *f=context;f->closed++;
 /* Buffers must still be live when close runs. */
 f->pixels[0]=0;
 return 0;
}
static int confirmed(const char *root,const char *source,enum hb_store_action action){
 struct hb_store_local_session session;
 if(hb_store_local_session_init(&session,root,source,"demo",4096))return -99;
 struct hb_store_canvas canvas;struct hb_store_painter painter;
 if(hb_store_canvas_init(&canvas,ui_pixels,240*432,&painter))return -99;
 struct ui_fixture fixture={0,0,action};
 struct hb_store_ui_io io={&fixture,ui_next,ui_present};
 if(hb_store_ui_run(&session.interaction,"Demo",&painter,&io)||fixture.presents!=5||
    !session.interaction.has_result)return -99;
 return session.interaction.result;
}
static int probe(int argc,char **argv,char **env) {
 char buffer[64];(void)env;
 if(argc==5&&!strcmp(argv[1],"--selection-change")){
  struct hb_store_local_session session;struct hb_bundle *bundle=malloc(sizeof *bundle);volatile int stop=0;
  if(!bundle||hb_store_local_session_init(&session,argv[2],argv[3],"demo",4096)||
     hb_bundle_check(argv[3],"demo",&stop,bundle)||hb_bundle_identity(bundle,session.expected_identity))return 84;
  free(bundle);session.has_expected_identity=1;
  if(hb_store_session_request(&session.interaction,HB_STORE_INSTALL))return 84;
  char backup[512];int size=__snprintf_chk(backup,sizeof backup,2,sizeof backup,"%s-old",argv[3]);
  if(size<0||size>=(int)sizeof backup||rename(argv[3],backup)||rename(argv[4],argv[3]))return 85;
  if(hb_store_session_confirm(&session.interaction)||session.interaction.result!=HB_INSTALL_INVALID)return 86;
  return 0;
 }
 if(argc==4&&(!strcmp(argv[1],"--app")||!strcmp(argv[1],"--app-open-fail")||!strcmp(argv[1],"--app-stop-open")||!strcmp(argv[1],"--app-self"))){
  struct app_fixture fixture={0};
  fixture.mode=!strcmp(argv[1],"--app")?0:!strcmp(argv[1],"--app-open-fail")?1:!strcmp(argv[1],"--app-stop-open")?2:3;
  struct hb_store_platform platform={&fixture,app_open,app_close};
  int status=hb_store_app_run(argv[2],argv[3],4096,&platform);
  if(fixture.opened!=1||fixture.closed!=1||status!=(fixture.mode==1?-1:0))return 80;
  if(fixture.mode==0&&fixture.ui.sample!=22)return 81;
  if((fixture.mode==1||fixture.mode==2)&&fixture.ui.sample)return 82;
  if(fixture.mode==3&&fixture.ui.sample!=4)return 83;
  return 0;
 }
 if(argc==4&&!strcmp(argv[1],"--signal-copy")){
  void (*prior)(int)=signal(SIGTERM,previous_handler);if(prior==SIG_ERR)return 75;
  if(hb_store_termination_begin()||hb_store_termination_begin()!=-1)return 75;
  volatile int *stop=hb_store_termination_flag();
  struct hb_store_local_session session;
  if(hb_store_local_session_init(&session,argv[2],argv[3],"demo",4096))return 75;
  session.external_stop=stop;hb_link_signal_write(2);
  if(hb_store_session_request(&session.interaction,HB_STORE_INSTALL)||hb_store_session_confirm(&session.interaction)||
     !*stop||session.interaction.result!=HB_RECOVERY_REQUIRED)return 76;
  hb_link_signal_write(0);
  if(raise(SIGTERM)||!*stop||previous_received)return 77;
  if(hb_store_termination_end()||raise(SIGTERM)||!previous_received||signal(SIGTERM,prior)==SIG_ERR)return 78;
  *stop=0;
  if(hb_store_session_request(&session.interaction,HB_STORE_RECOVER)||hb_store_session_confirm(&session.interaction)||session.interaction.result)return 79;
  return 0;
 }
 if(argc==4&&!strcmp(argv[1],"--cancel-copy")){
  struct hb_store_local_session session;volatile int stop=0;
  if(hb_store_local_session_init(&session,argv[2],argv[3],"demo",4096))return 71;
  session.external_stop=&stop;hb_link_cancel_write(2,&stop);
  if(hb_store_session_request(&session.interaction,HB_STORE_INSTALL)||hb_store_session_confirm(&session.interaction))return 71;
  /* Stop also suppresses further cleanup writes. Pending state must be kept
   * for explicit recovery rather than claiming a clean cancellation. */
  if(!stop||session.interaction.result!=HB_RECOVERY_REQUIRED||
     hb_store_session_request(&session.interaction,HB_STORE_INSTALL)!=-1)return 72;
  hb_link_cancel_write(0,0);stop=0;
  if(hb_store_session_request(&session.interaction,HB_STORE_RECOVER)||hb_store_session_confirm(&session.interaction)||session.interaction.result)return 73;
  return 0;
 }
 if(argc==7&&!strcmp(argv[1],"--scan")){
  struct hb_store_catalog *c=malloc(sizeof *c);struct hb_bundle *w=malloc(sizeof *w);
  if(!c||!w)return 69;
  volatile int stop=0;int status=hb_store_catalog_scan(argv[2],&stop,c,w),expected=atoi(argv[3]);
  int ok=expected<0?(status<0&&c->count==0):
   (!status&&c->count==(unsigned)expected&&c->rejected==(unsigned)atoi(argv[4]));
  if(ok&&expected>0){
   ok=!strcmp(c->entries[0].package.id,argv[5])&&!strcmp(c->entries[c->count-1].package.id,argv[6]);
   for(unsigned i=1;i<c->count;i++)if(strcmp(c->entries[i-1].package.id,c->entries[i].package.id)>=0)ok=0;
  }
  free(c);free(w);return ok?0:70;
 }
 if(argc==4&&(!strcmp(argv[1],"--browser")||!strcmp(argv[1],"--browser-stop")||!strcmp(argv[1],"--browser-error"))){
  struct hb_store_browser *browser=malloc(sizeof *browser);if(!browser)return 66;
  struct hb_store_canvas canvas;struct hb_store_painter painter;
  if(hb_store_canvas_init(&canvas,ui_pixels,240*432,&painter))return 66;
  enum hb_store_action mode=!strcmp(argv[1],"--browser")?HB_STORE_INSTALL:
   !strcmp(argv[1],"--browser-stop")?HB_STORE_RECOVER:HB_STORE_CANCEL_IDLE;
  struct ui_fixture fixture={0,0,mode};struct hb_store_ui_io io={&fixture,browser_next,ui_present};volatile int stop=0;
  int status=hb_store_browser_run(argv[2],argv[3],4096,browser,&painter,&io,&stop);
  free(browser);
  if(mode==HB_STORE_INSTALL)return status==0&&fixture.sample==22?0:67;
  return status==(mode==HB_STORE_RECOVER?0:-1)&&fixture.sample==3?0:68;
 }
 if(argc==6&&!strcmp(argv[1],"--transaction")){
  volatile int stop=0;
  hb_link_fault(argv[2],(unsigned)strtoul(argv[5],0,10));
  (void)stop;
  int status=confirmed(argv[3],argv[4],!strcmp(argv[2],"recover")?HB_STORE_RECOVER:HB_STORE_INSTALL);
  return status?61:0;
 }
 int result=__snprintf_chk(buffer,sizeof buffer,2,sizeof buffer,"%s:%u:%llu","sony",17U,0x100000011ULL);
 if(result!=(int)(sizeof("sony:17:4294967313")-1)||strcmp(buffer,"sony:17:4294967313"))return 41;
 if(argc!=8)return 43;
 struct hb_store_catalog *catalog=malloc(sizeof *catalog);
 struct hb_bundle *workspace=malloc(sizeof *workspace);
 volatile int catalog_stop=0;
 if(!catalog||!workspace)return 62;
 if(hb_store_catalog_scan(argv[7],&catalog_stop,catalog,workspace)||catalog->count!=1||
    catalog->rejected!=2||strcmp(catalog->entries[0].package.id,"demo"))return 63;
 struct hb_store_canvas catalog_canvas;struct hb_store_painter catalog_painter;
 struct ui_fixture catalog_fixture={0,0,HB_STORE_INSTALL};
 struct hb_store_ui_io catalog_io={&catalog_fixture,catalog_next,ui_present};
 if(hb_store_canvas_init(&catalog_canvas,ui_pixels,240*432,&catalog_painter))return 65;
 int selected=hb_store_catalog_run(catalog,&catalog_painter,&catalog_io);
 if(selected!=0||catalog_fixture.presents!=1)return 65;
 char selected_source[512];strcpy(selected_source,catalog->entries[selected].folder);
 catalog_stop=1;
 if(hb_store_catalog_scan(argv[7],&catalog_stop,catalog,workspace)!=-1||catalog->count)return 64;
 free(workspace);free(catalog);
 struct stat info;
 if(lstat(argv[1],&info)||!S_ISREG(info.st_mode)||info.st_size!=19||info.st_nlink!=1)return 44;
 int fd=open(argv[1],O_RDONLY);
 if(fd<0)return 45;
 if(fstat(fd,&info)||info.st_size!=19){close(fd);return 46;}
 if(read(fd,buffer,sizeof buffer)!=19||memcmp(buffer,"stock-file-fixture\n",19)){close(fd);return 47;}
 if(close(fd))return 48;
 DIR *directory=opendir(argv[2]);if(!directory)return 49;
 struct dirent *entry;int found=0;errno=0;
 while((entry=readdir(directory)))if(!strcmp(entry->d_name,"fixture.dat"))found++;
 int directory_errno=errno;
 if(closedir(directory)||directory_errno||found!=1)return 50;
 struct statvfs space;
 if(statvfs(argv[2],&space)||!space.f_frsize||space.f_bavail>space.f_blocks)return 51;
 volatile int stop=0;
 if(confirmed(argv[3],selected_source,HB_STORE_INSTALL))return 52;
 if(confirmed(argv[3],argv[5],HB_STORE_INSTALL))return 53;
 if(confirmed(argv[3],argv[5],HB_STORE_RECOVER))return 54;
 if(hb_store_install_local(argv[3],argv[4],"demo",1ULL<<60,&stop)!=HB_INSTALL_NO_SPACE)return 55;
 stop=1;
 if(hb_store_install_local(argv[3],argv[4],"demo",4096,&stop)!=HB_INSTALL_CANCELLED)return 56;
 stop=0;
 if(hb_store_install_local(argv[3],argv[6],"demo",4096,&stop)!=HB_INSTALL_INVALID)return 57;
 if(hb_store_recover_local(argv[3],"demo",&stop))return 58;
 return write(1,"stock-libc-smoke-ok\n",20)==20?0:42;
}
void hb_link_start(unsigned *stack) {
 __libc_start_main(probe,(int)stack[0],(char **)(stack+1),0,0,0,stack);
 for(;;){}
}

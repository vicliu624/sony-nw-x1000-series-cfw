#define HB_QFB_PAGE_BYTES 0x60000u
#define HB_QFB_MAP_BYTES (2u*HB_QFB_PAGE_BYTES)
#define HB_QFB_READY 0x80044e00u
#define HB_QFB_SUBMIT 0x40044e01u
#define HB_QFB_TIMEOUT_MODE 0x80044e04u
struct devices {int fb,touch;unsigned short*pixels;unsigned length;int pending,failed;};
static void release(struct devices*d){if(d->pixels){S(91,d->pixels,d->length,0);d->pixels=0;}if(d->fb>=0){S(6,d->fb,0,0);d->fb=-1;}if(d->touch>=0){S(6,d->touch,0,0);d->touch=-1;}}
static int acquire(struct devices*d){unsigned fix[32],var[40];d->fb=-1;d->touch=-1;d->pixels=0;d->pending=0;d->failed=0;if(stop_requested)return -1;d->fb=S(5,"/dev/fb/0",2,0);if(d->fb<0)return -1;if(stop_requested)goto fail;if(S(54,d->fb,0x4602,fix)||S(54,d->fb,0x4600,var))goto fail;
 /* Initial 240x432 RGB565 profile only. Query geometry/stride/bitfields before mapping. */
 if(var[0]!=240||var[1]!=432||var[4]||var[5]||var[6]!=16||fix[5]<HB_QFB_MAP_BYTES||fix[11]!=480||var[8]!=11||var[9]!=5||var[11]!=5||var[12]!=6||var[14]!=0||var[15]!=5)goto fail;
 if(stop_requested)goto fail;
 d->length=HB_QFB_MAP_BYTES;
 long p=x1000_oabi_call(192,0,d->length,3,1,d->fb,0);
 if(error(p))goto fail;
 d->pixels=(unsigned short*)p;
 if(stop_requested)goto fail;
 /* Stock SpiderApp initialization disables periodic timeout refresh after mmap.
    This cancels its timer, not work already queued by the original driver. */
 unsigned timeout_mode[2]={0,33};
 if(S(54,d->fb,HB_QFB_TIMEOUT_MODE,timeout_mode)||stop_requested)goto fail;
 d->touch=S(5,"/dev/icx_touch_screen",0,0);
 if(d->touch<0||stop_requested||S(54,d->touch,0x5404,0))goto fail;
 if(stop_requested)goto fail;
 return 0;
fail:release(d);return -1;}
static void flush_pending(struct devices*d){
 if(!d->pending||stop_requested||d->failed)return;
 /* Count0 queries without blocking. Busy is in the output, not the return code.
    Sentinels reject a kernel that silently ignores this proprietary request. */
 unsigned ready[3]={0,0xffffffffu,0xffffffffu};
 long result=S(54,d->fb,HB_QFB_READY,ready);
 if(result==-4)return;
 if(result||ready[1]>1||ready[2]>1){d->failed=1;return;}
 int page=ready[1]==0?0:ready[2]==0?1:-1;
 if(page<0||stop_requested)return;
 memcpy(d->pixels+(unsigned)page*(HB_QFB_PAGE_BYTES/2),canvas,sizeof canvas);
 if(stop_requested)return;
 /* Preserve Sony's observed tc_enable/t_color/alpha/rot/update defaults. */
 unsigned frame[6]={1,1,255,(unsigned)page,0,0};
 if(S(54,d->fb,HB_QFB_SUBMIT,frame)){d->failed=1;return;}
 d->pending=0;
}
static void present(struct devices*d){d->pending=1;flush_pending(d);}

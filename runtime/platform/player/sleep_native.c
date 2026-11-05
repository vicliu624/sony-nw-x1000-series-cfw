#include "sleep_native.h"
#include "sleep_host.h"
#include "stock_image.h"
#include "wireless_host.h"
#include "host_managed_service.h"
extern unsigned long pthread_self(void);
static struct xw_sleep_host host;
static unsigned restore_stage;
static int restore_error;
static uint32_t restore_words[3];
static uint32_t restore_sequence;
static struct {
 unsigned long owner;uint64_t epoch;uint32_t main_state,post_main,sequence,root_words[3];
} view;
static const struct {uint32_t address,bytes;unsigned char digest[32];} guards[]={
 {0x61310u,12u,"\x16\x9d\x17\x55\x40\xf1\xea\xd8\x6b\x5e\xf9\xac\x63\xec\x98\x92\xd5\x90\x18\x15\x4a\xcc\x3c\x72\x9b\x2b\x7b\xa6\x92\x41\xf4\x89"},
 {0x265510u,12u,"\x58\x90\xa6\xa0\x89\x20\x05\x31\xb9\x1e\xaa\x8d\xac\x2a\x48\x8d\x54\x55\xa4\x66\xdc\xde\xca\x41\x12\x7a\x3c\x0f\xfb\x8c\x34\xfe"},
 {0xb03e8u,124u,"\x19\xd2\x47\xfd\x76\x7a\xdf\x83\xe8\x3f\x7e\x5c\xe6\x98\x9c\x92\x55\xd6\xe9\xa4\x0a\x77\x1f\x6c\x48\x45\x39\xf5\xec\x86\x23\x60"},
 {0x267e28u,216u,"\x6c\x03\x91\x44\x24\x00\xe5\x92\x88\xb6\xf9\x0d\x97\xc6\xa1\xce\x20\xc5\xed\x75\x39\xfd\xe3\x30\x43\xff\x2a\x09\x0f\xb3\xbf\x1b"},
};
static int image(void){
 static const unsigned char restore_digest[32]="\x0e\x15\x08\x99\x6f\xf2\xe6\x9e\x1a\xd4\xbf\x1b\xbf\x71\x75\x59\x52\xcb\xa8\x50\x91\xc5\xa4\x3a\xe3\x23\x46\xbe\xb9\xe6\xcb\x43";
 if(xw_stock_image_match(0x61a1cu,88u,restore_digest))return XW_PLAYER_UNSUPPORTED;
 for(unsigned i=0;i<sizeof guards/sizeof *guards;i++)
  if(xw_stock_image_match(guards[i].address,guards[i].bytes,guards[i].digest))return XW_PLAYER_UNSUPPORTED;
 return 0;
}
static int sample(uint32_t words[5]){
 int rc=image();if(rc)return rc;
 if(((uintptr_t (*)(void))(uintptr_t)0x61310u)()!=0x682cdcu||
    ((uintptr_t (*)(void))(uintptr_t)0x265510u)()!=0x820f68u)return XW_PLAYER_UNSUPPORTED;
 const volatile unsigned char *main=(const volatile unsigned char *)(uintptr_t)0x682cdcu;
 const volatile uint32_t *root=(const volatile uint32_t *)(uintptr_t)0x613e60u;
 const volatile uint32_t *client=(const volatile uint32_t *)(uintptr_t)0x820f68u;
 if(root[0x2c/4]!=0x66efe8u||*(const volatile uint32_t *)(uintptr_t)0x66efe8u||client[1]!=2)return XW_PLAYER_BUSY;
 words[0]=(uint32_t)main[0]|((uint32_t)main[1]<<8);
 words[1]=client[5];words[2]=root[1];words[3]=root[2];words[4]=root[0x4c/4];
 return 0;
}
int xw_player_sleep_native_inactive(void){
 int rc=image();if(rc)return rc;
 if(((uintptr_t (*)(void))(uintptr_t)0x61310u)()!=0x682cdcu||
    ((uintptr_t (*)(void))(uintptr_t)0x265510u)()!=0x820f68u)return XW_PLAYER_UNSUPPORTED;
 const volatile unsigned char *main=(const volatile unsigned char *)(uintptr_t)0x682cdcu;
 const volatile uint32_t *root=(const volatile uint32_t *)(uintptr_t)0x613e60u;
 if(main[0]!=2||(main[1]!=1&&main[1]!=2)||((const volatile uint32_t *)(uintptr_t)0x820f68u)[1]!=1)return XW_PLAYER_UNAVAILABLE;
 if(root[0x2c/4]!=0x66efe8u||*(const volatile uint32_t *)(uintptr_t)0x66efe8u)return XW_PLAYER_BUSY;
 return 0;
}
static int valid(void *context,uint64_t epoch){
 if(context!=&view||epoch!=view.epoch||pthread_self()!=view.owner)return XW_PLAYER_STALE;
 uint32_t words[5];int rc=sample(words);if(rc)return rc;
 if((words[0]!=view.main_state&&words[0]!=view.post_main)||words[1]!=view.sequence)return XW_PLAYER_STALE;
 for(unsigned i=0;i<3;i++)if(words[i+2]!=view.root_words[i])return XW_PLAYER_STALE;
 return 0;
}
static int ack(void *context){
 int rc=valid(context,view.epoch);if(rc)return rc;
 return ((int (*)(void))(uintptr_t)0xb03e8u)();
}
int xw_player_sleep_native_begin(uint32_t callsite,unsigned long owner){
 if(!owner||pthread_self()!=owner)return XW_PLAYER_BUSY;
 uint32_t expected,post;
 switch(callsite){
 case 0x614f0u:expected=0x102u;post=0x202u;break;
 case 0x61648u:expected=post=0x202u;break;
 case 0x61940u:expected=0x703u;post=0x403u;break;
 case 0x61c5cu:expected=post=0x403u;break;
 default:return XW_PLAYER_UNSUPPORTED;
 }
 if(host.retirement.phase!=XW_SLEEP_IDLE)return XW_PLAYER_BUSY;
 uint32_t words[5];int rc=sample(words);if(rc)return rc;
 if(words[0]!=expected||words[1]==UINT32_MAX)return XW_PLAYER_UNSUPPORTED;
 uint64_t epoch=0;rc=xw_player_host_wireless_next_epoch(&epoch);if(rc)return XW_PLAYER_UNAVAILABLE;
 view.owner=owner;view.epoch=epoch;view.main_state=words[0];view.post_main=post;view.sequence=words[1];
 for(unsigned i=0;i<3;i++)view.root_words[i]=words[i+2];
 return xw_player_sleep_host_begin(&host,&view,valid,ack,epoch,owner);
}
static int restore_context(uint32_t words[5]){
 if(xw_player_host_original_exiting())return XW_PLAYER_CLOSED;
 int rc=sample(words);if(rc)return rc;
 if(words[1]<=view.sequence||words[1]==UINT32_MAX)return XW_PLAYER_STALE;
 if(((const volatile uint32_t *)(uintptr_t)0x613e2cu)[1])return XW_PLAYER_BUSY;
 return 0;
}
int xw_player_sleep_native_restore_begin(uint32_t root,unsigned long owner){
 if(!owner||pthread_self()!=owner||owner!=view.owner)return XW_PLAYER_BUSY;
 if(root!=0x613e60u||host.retirement.phase!=XW_SLEEP_ACKNOWLEDGED||restore_stage)return XW_PLAYER_CLOSED;
 uint32_t words[5];int rc=restore_context(words);if(rc)return rc;
 if(words[0]!=0x403u)return XW_PLAYER_UNSUPPORTED;
 restore_sequence=words[1];restore_stage=1;return 0;
}
int xw_player_sleep_native_restore_complete(int native_result,unsigned long owner){
 if(!owner||pthread_self()!=owner||owner!=view.owner)return XW_PLAYER_BUSY;
 if(restore_stage!=1||host.retirement.phase!=XW_SLEEP_ACKNOWLEDGED)return XW_PLAYER_CLOSED;
 if(native_result!=1)return XW_PLAYER_UNSUPPORTED;
 uint32_t words[5];int rc=restore_context(words);if(rc)return rc;
 if(words[0]!=0x403u||words[2]!=15||words[1]<restore_sequence)return XW_PLAYER_STALE;
 restore_sequence=words[1];
 for(unsigned i=0;i<3;i++)restore_words[i]=words[i+2];
 restore_stage=2;return 0;
}
static int restore_ready(void *context,uint64_t epoch){
 if(context!=&view||epoch!=view.epoch||pthread_self()!=view.owner||restore_stage!=2)return XW_PLAYER_STALE;
 uint32_t words[5];int rc=restore_context(words);
 if(!rc&&words[0]==0x403u)return XW_PLAYER_BUSY;
 if(!rc&&words[0]!=0x103u)rc=XW_PLAYER_STALE;
 if(!rc&&words[1]!=restore_sequence)rc=XW_PLAYER_STALE;
 for(unsigned i=0;!rc&&i<3;i++)if(words[i+2]!=restore_words[i])rc=XW_PLAYER_STALE;
 return rc;
}
int xw_player_sleep_native_poll(void){
 if(restore_stage==3)return restore_error;
 if(restore_stage!=2)return xw_player_sleep_host_poll(&host);
 int rc=xw_player_sleep_host_resume(&host,restore_ready);
 if(rc==XW_PLAYER_BUSY||rc==XW_PLAYER_ACCEPTED)return XW_PLAYER_ACCEPTED;
 if(rc){restore_stage=3;restore_error=rc;return rc;}
 restore_stage=0;view.owner=0;view.epoch=0;
 return 0;
}

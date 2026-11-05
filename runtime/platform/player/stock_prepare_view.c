#include "stock_prepare_view.h"
#include "stock_image.h"
extern unsigned long pthread_self(void);
struct guard {uint32_t address,bytes;unsigned char digest[32];};
static const struct guard guards[]={
 {0x265510u,12u,"\x58\x90\xa6\xa0\x89\x20\x05\x31\xb9\x1e\xaa\x8d\xac\x2a\x48\x8d\x54\x55\xa4\x66\xdc\xde\xca\x41\x12\x7a\x3c\x0f\xfb\x8c\x34\xfe"},
 {0x10d80u,0x8f4u,"\xdf\xcf\x7a\xab\x13\xcb\xda\x81\x8a\x38\xe9\xb8\x49\x4f\x2d\x30\x9e\xd6\x6f\xa1\xc5\xb8\x83\x64\x96\x47\x02\xc6\xf7\x4b\x2e\x72"},
 {0x489dcu,0x180u,"\x2e\xba\x56\x80\x94\xfe\xb9\x9c\x8a\x68\xd1\x39\x43\x08\x4d\x48\x1b\x51\xf0\x81\xdd\x24\x16\xb2\x9f\x92\xa7\x0a\x44\x09\x79\xfd"},
 {0x718c0u,0x30u,"\xd4\x41\x4b\xff\x91\xea\x76\x1f\x3f\xf5\x16\x38\x7e\xba\x19\xbb\xe5\xc7\xa6\x55\xad\xc3\x95\x72\x89\x03\x12\x1f\xe2\xdb\xe8\x4e"},
 {0x71a3cu,0x88u,"\x35\x1c\x83\x87\x30\x35\x72\xed\xa7\x24\x6a\xef\x46\x93\x8f\x5c\xb2\xea\x27\x53\xfe\x71\x48\xeb\xfb\x82\x91\xbf\x33\x61\xe0\xbe"},
 {0xda84u,12u,"\xa1\xff\x0f\xce\xcb\x6e\x34\xac\xc6\x0b\xef\x47\xd1\x64\x27\xf2\x31\x6a\xf5\x22\x53\x01\x61\x78\xe7\xb0\xe0\x38\x41\xb2\xc6\x72"},
 {0x4d7fc0u,44u,"\x07\x4c\x73\xe0\xf5\x6b\xe6\x59\x2f\x35\x54\xbe\xad\x6f\x00\xa0\xae\xf0\xd8\x15\xdf\xf4\x10\xeb\x3b\x85\x8b\x24\x70\xf1\x63\x25"}
};
int xw_stock_prepare_code_check(void){
 for(unsigned i=0;i<sizeof guards/sizeof *guards;i++)if(xw_stock_image_match(guards[i].address,guards[i].bytes,guards[i].digest))return XW_PLAYER_UNSUPPORTED;
 return 0;
}
static int sample(uint32_t out[3]){
 int rc=xw_stock_prepare_code_check();if(rc)return rc;
 const volatile uint32_t *root=(const volatile uint32_t *)(uintptr_t)0x613e60u;
 if(root[0x2c/4]!=0x66efe8u)return XW_PLAYER_UNSUPPORTED;
 const volatile uint32_t *tracker=(const volatile uint32_t *)(uintptr_t)0x66efe8u;
 uint32_t count=tracker[0];if(count>32)return XW_PLAYER_PROTOCOL;if(count||root[1]==3)return XW_PLAYER_BUSY;
 out[0]=root[1];out[1]=root[2];out[2]=root[0x4c/4];
 if(root[0x2c/4]!=0x66efe8u||tracker[0]||out[0]!=root[1]||out[1]!=root[2]||out[2]!=root[0x4c/4])return XW_PLAYER_BUSY;
 return 0;
}
int xw_stock_prepare_view_bind(struct xw_stock_prepare_view *p,uint32_t root,uint32_t command,uint64_t epoch,unsigned long original_owner){
 if(!p||root!=0x613e60u||(command!=3&&command!=6)||!epoch||!original_owner)return XW_PLAYER_INVALID;
 if(p->bound||p->busy||pthread_self()!=original_owner)return XW_PLAYER_BUSY;
 uint32_t words[3];p->busy=1;int rc=sample(words);p->busy=0;if(rc)return rc;
 p->epoch=epoch;p->owner=original_owner;p->command_word=words[0];p->auxiliary_word=words[1];p->state_word=words[2];p->bound=1;return 0;
}
int xw_stock_prepare_view_check(struct xw_stock_prepare_view *p,uint64_t epoch){
 if(!p||!p->bound)return XW_PLAYER_CLOSED;
 if(p->busy||p->owner!=pthread_self())return XW_PLAYER_BUSY;
 if(epoch!=p->epoch)return XW_PLAYER_STALE;
 uint32_t words[3];p->busy=1;int rc=sample(words);p->busy=0;if(rc)return rc;
 return words[0]==p->command_word&&words[1]==p->auxiliary_word&&words[2]==p->state_word?0:XW_PLAYER_STALE;
}
int xw_stock_prepare_view_unbind(struct xw_stock_prepare_view *p){
 if(!p)return XW_PLAYER_INVALID;
 if(p->busy||(p->bound&&p->owner!=pthread_self()))return XW_PLAYER_BUSY;
 p->bound=0;p->owner=0;p->epoch=0;return 0;
}

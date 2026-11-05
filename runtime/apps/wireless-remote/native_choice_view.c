#include "native_choice_view.h"
#include "../../platform/player/player.h"
extern unsigned long pthread_self(void);
extern int wr_view_code_valid(void);
extern int wr_view_resource_ready(void);
extern uintptr_t wr_view_root(void);
extern uintptr_t wr_view_pool(void);
extern uintptr_t wr_view_active(uintptr_t,uint32_t);
extern uintptr_t wr_view_menu_context(void);
extern uint32_t wr_view_menu_state(uintptr_t);
extern uint32_t *wr_view_params_get(uintptr_t,uint32_t *);
extern void wr_view_params_set(uintptr_t,const uint32_t *);
extern uint32_t wr_view_sid_get(void);
extern void wr_view_sid_set(uint32_t);
extern void wr_view_counts_get(uint32_t [3]);
extern void wr_view_counts_set(const uint32_t [2]);
static uint32_t word(uintptr_t address){return *(const volatile uint32_t *)address;}
static int owner(struct wr_native_choice_view *p){return p&&p->owner&&p->owner==pthread_self();}
static uint32_t menu_state(void){
 uintptr_t context=wr_view_menu_context();
 return context==0x683400u?wr_view_menu_state(context):0;
}
static uintptr_t existing(uintptr_t root){
 if(root!=0x63bd8cu||wr_view_pool()!=0x754ac0u)return 0;
 uintptr_t view=word(root+0x2b18u+29u*8u);
 if((view&3u)||view<0x754ac4u||view+0xacu>0x754ac0u+0x7644u)return 0;
 return word(view+32)==29&&word(view+0xa4u)==3?view:0;
}
static int inactive(uintptr_t root,uintptr_t view){
 /* Original active-layer query plus unchanged slot and an empty draw queue.
  * Physical/queued event ordering remains to be qualified before deployment. */
 return existing(root)==view&&!wr_view_active(root,29)&&!word(root+8)&&
  !word(root+0x2b18u+29u*8u+4);
}
static int settled(uintptr_t root){
 for(unsigned i=0;i<4;i++){
  uint32_t state=word(root+0x2ff8u+i*0x2e94u+0x2e2cu);
  if(state!=0&&state!=3)return 0;
 }
 return 1;
}
int wr_native_choice_view_begin(struct wr_native_choice_view *p,unsigned long gui_owner){
 if(!p||!gui_owner||gui_owner!=pthread_self())return XW_PLAYER_BUSY;
 if(p->held)return XW_PLAYER_BUSY;
 if(p->epoch==UINT32_MAX)return XW_PLAYER_UNAVAILABLE;
 if(wr_view_code_valid()!=1||wr_view_resource_ready()!=1)return XW_PLAYER_UNAVAILABLE;
 if(menu_state()!=0x0202u)return XW_PLAYER_BUSY;
 uintptr_t root=wr_view_root(),view=existing(root);
 if(!view)return XW_PLAYER_UNSUPPORTED;
 if(!wr_view_active(root,97)||!settled(root))return XW_PLAYER_BUSY;
 if(!inactive(root,view))return XW_PLAYER_BUSY;
 uint32_t params[15],counts[3];wr_view_params_get(view,params);wr_view_counts_get(counts);
 if(params[13]!=3||counts[0]!=3||counts[1]!=3||counts[2]!=3||wr_view_sid_get()!=13900)return XW_PLAYER_UNSUPPORTED;
 p->root=root;p->view=view;p->owner=gui_owner;
 p->original_sid=13900;p->original_count=3;p->closing=0;p->held=1;p->epoch++;p->acknowledged=0;
 uint32_t borrowed[2]={2,2};wr_view_counts_set(borrowed);
 params[13]=2;wr_view_params_set(view,params);wr_view_sid_set(13901);
 return 0;
}
int wr_native_choice_view_end(struct wr_native_choice_view *p){
 if(!owner(p))return XW_PLAYER_BUSY;
 if(!p->held)return XW_PLAYER_CLOSED;
 if(wr_view_code_valid()!=1||(menu_state()>>8)!=194u)return XW_PLAYER_BUSY;
 p->closing=1;return 0;
}
int wr_native_choice_view_acknowledge(struct wr_native_choice_view *p,uint32_t epoch){
 if(!owner(p))return XW_PLAYER_BUSY;
 if(!p->held||!p->closing)return XW_PLAYER_CLOSED;
 if(!epoch||epoch!=p->epoch)return XW_PLAYER_STALE;
 if(wr_view_code_valid()!=1||wr_view_root()!=p->root||existing(p->root)!=p->view)return XW_PLAYER_UNAVAILABLE;
 /* An interactive parent must be visible. The wireless list can also
  * finish restoration synchronously before entering its mode selector. */
 uint32_t state=menu_state();
 if(!((state==0x0202u&&wr_view_active(p->root,97))||
      (state==0x5a02u&&wr_view_active(p->root,123))))return XW_PLAYER_BUSY;
 if(!settled(p->root))return XW_PLAYER_BUSY;
 if(!inactive(p->root,p->view))return XW_PLAYER_BUSY;
 p->acknowledged=1;return 0;
}
int wr_native_choice_view_observe(struct wr_native_choice_view *p){
 if(!owner(p))return XW_PLAYER_BUSY;
 if(!p->held)return 0;
 if(!p->closing)return XW_PLAYER_BUSY;
 int rc=wr_native_choice_view_acknowledge(p,p->epoch);
 return rc?rc:wr_native_choice_view_poll(p);
}
int wr_native_choice_view_poll(struct wr_native_choice_view *p){
 if(!owner(p))return XW_PLAYER_BUSY;
 if(!p->held)return 0;
 if(!p->closing)return XW_PLAYER_BUSY;
 if(!p->acknowledged)return XW_PLAYER_BUSY;
 if(wr_view_code_valid()!=1||wr_view_root()!=p->root||existing(p->root)!=p->view)return XW_PLAYER_UNAVAILABLE;
 if(!inactive(p->root,p->view))return XW_PLAYER_BUSY;
 uint32_t params[15],counts[3];wr_view_params_get(p->view,params);wr_view_counts_get(counts);
 if(params[13]!=2||counts[0]!=2||counts[1]!=3||counts[2]!=2||wr_view_sid_get()!=13901)return XW_PLAYER_STALE;
 /* Restore only the two properties borrowed, preserving other native state. */
 params[13]=p->original_count;wr_view_params_set(p->view,params);
 uint32_t restored[2]={p->original_count,p->original_count};wr_view_counts_set(restored);
 wr_view_sid_set(p->original_sid);p->held=p->closing=0;
 return 0;
}

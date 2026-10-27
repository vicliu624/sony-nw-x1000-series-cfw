#include "fm_preferences.h"
#include <string.h>
void fm_preferences_open(struct fm_preferences *p,struct fm_band band){
 memset(p,0,sizeof(*p));fm_storage_init(&p->storage);p->saved.band=band;p->saved.frequency=band.low;p->saved.threshold=30;
 p->last_result=fm_storage_open(&p->storage);if(p->last_result)return;
 struct fm_state saved;p->last_result=fm_storage_load(&p->storage,band,&saved);
 if(!p->last_result){p->saved=saved;p->loaded=1;}
 else if(p->last_result==FM_STORAGE_EMPTY)p->last_result=0;
}
int fm_preferences_attach(struct fm_preferences *p,struct fm_radio *r){
 if(p->loaded&&fm_state_apply(r,&p->saved))return -1;
 struct fm_state state;
 if(fm_state_capture(r,&state)||fm_state_encode(&state,p->baseline,sizeof(p->baseline),&p->baseline_length))return -1;
 return 0;
}
int fm_preferences_sync(struct fm_preferences *p,const struct fm_radio *r,int force){
 if(!p||!r||r->scanning||r->error)return 0;
 struct fm_state state;unsigned char bytes[FM_STATE_MAX_BYTES];size_t length;
 if(fm_state_capture(r,&state)||fm_state_encode(&state,bytes,sizeof(bytes),&length))return -1;
 if(!force&&length==p->baseline_length&&!memcmp(bytes,p->baseline,length))return 0;
 if(p->storage.directory<0){
  if(!force||fm_storage_open(&p->storage)){p->last_result=FM_STORAGE_BOUNDARY;return 0;}
  /* Reopened storage may already contain newer generations. Select its last
   * good slot before committing the current in-memory preferences. */
  struct fm_state previous;(void)fm_storage_load(&p->storage,r->band,&previous);
 }
 int result=fm_storage_save(&p->storage,&state);p->last_result=result;
 p->write_failed=result<0;
 if(!result||result==FM_STORAGE_UNCERTAIN){memcpy(p->baseline,bytes,length);p->baseline_length=length;}
 return result;
}
int fm_preferences_close(struct fm_preferences *p){return p?fm_storage_close(&p->storage):0;}

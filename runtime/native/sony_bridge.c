#include "sony_bridge.h"
int hb_sony_request_frontend(void *context,hb_sony_lookup lookup,hb_sony_change change){
 unsigned id=0;int result;
 if(!context||!lookup||!change)return -1;
 result=lookup(context,"/contents/HOMEBREW/launcher/app",&id);
 if(result)return result;
 /* A proxy-managed registration is required by this adapter contract. */
 if((id>>16)!=3)return -2;
 /* Session resource ownership belongs to this integration boundary. */
 return change(context,id,(const char *const *)0,1);
}

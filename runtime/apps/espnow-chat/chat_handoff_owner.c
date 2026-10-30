#include "chat_handoff.h"
#include <x1000/services/espnow_control.h>
int chat_handoff_finish(struct chat_handoff *h,const struct xnow_control *control,unsigned failure){
 if(!control||!xnow_control_finished(control))return -1;
 return chat_handoff_write(h,failure);
}

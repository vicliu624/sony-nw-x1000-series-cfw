#include "xnow_owner_commands.h"
#include "xnow_full_control.h"
static struct xnow_endpoint *endpoint(void *p){return xnow_full_control_endpoint(p);}
static void stop(void *p){xnow_full_control_stop(p);}
int xnow_owner_commands_control(struct xnow_owner_commands *commands,struct xnow_full_control *control){
 if(!control||!control->initialized)return XNOW_ARGUMENT;
 return xnow_owner_commands_init(commands,control,endpoint,stop);
}

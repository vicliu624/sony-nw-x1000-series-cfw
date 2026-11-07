/* PC-only UI bring-up adapter: an initialized OpenMAX registry with no media
 * components. It does not execute Sony DSP firmware, decode or play audio.
 * Keep component requests failing explicitly; never claim media readiness.
 */
#include <stdint.h>
#include <unistd.h>
static unsigned initialized;
uint32_t OMX_Init(void){
 const char note[]="GUEST_EMPTY_MEDIA_REGISTRY_INIT\n";write(2,note,sizeof note-1);
 initialized=1;return 0;
}
uint32_t OMX_Deinit(void){initialized=0;return 0;}
uint32_t OMX_GetHandle(void **handle,char *name,void *data,void *callbacks){
 (void)name;(void)data;(void)callbacks;
 if(handle)*handle=0;
 const char note[]="GUEST_EMPTY_MEDIA_COMPONENT_REFUSED\n";write(2,note,sizeof note-1);
 return initialized?0x80001003u:0x80001010u;
}
uint32_t OMX_FreeHandle(void *handle){(void)handle;return 0x80001004u;}

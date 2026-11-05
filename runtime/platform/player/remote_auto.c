/* Opt-in reviewed original-player composition. No constructor, listener or
 * default RF start. The immutable supervisor validates user inputs off-thread. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "host_managed_service.h"
#include "player.h"
#include "wireless_host.h"
#include "remote_ready.h"
#include "../../apps/wireless-remote/settings_factory.h"
#include <sys/stat.h>
#if defined(__arm__) && !defined(HB_STORE_SONY_LIBC)
#define HB_STORE_SONY_LIBC
#endif
#include "../../store/target_abi.h"
#include "remote_factory_profile.h"
static struct wr_settings_factory factory;
static int blocked;
#ifdef XW_PLAYER_NATIVE_REMOTE_PAGE
struct wr_settings_backend *xw_player_host_remote_page_backend(void){
 return !blocked&&factory.initialized&&!xw_player_host_original_exiting()?&factory.backend:0;
}
#endif
static int qualified(void *context){
 (void)context;if(!xw_player_remote_software_ready())return 0;
 struct stat root,program;
 /* Program bytes/hash are fixed by the reviewed read-only root image. Full
  * service/owner/template hashes are rechecked by that supervisor before RF. */
 return !lstat("/",&root)&&!lstat(WR_SUPERVISOR_PATH,&program)&&S_ISREG(program.st_mode)&&
  program.st_nlink==1&&program.st_dev==root.st_dev&&program.st_size==WR_REMOTE_SUPERVISOR_BYTES;
}
void xw_player_host_remote_auto(void){
 if(blocked)return;
 if(!factory.initialized){
  if(!xw_player_host_wireless_has_authority()||xw_player_host_original_exiting())return;
  int rc=wr_settings_factory_bind(&factory,1,0,qualified);
  if(rc==XW_PLAYER_BUSY)return;
  if(rc){blocked=1;return;}
#ifdef WR_REMOTE_OWNER_VIEW
  if(wr_settings_factory_forward_owner_view(&factory)){blocked=1;return;}
#endif
 }
 if(factory.backend.phase==WR_SETTINGS_OFF&&!factory.held)return;
 if(factory.backend.phase==WR_SETTINGS_STARTING&&!xw_player_remote_state_active())
  (void)wr_settings_backend_request_stop(&factory.backend);
 (void)wr_settings_factory_tick(&factory);
}

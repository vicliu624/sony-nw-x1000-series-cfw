#include "transaction.h"

static int valid_id(const char *id) {
 unsigned i=0;
 if(!id||!*id)return 0;
 for(;id[i];i++) {
  char c=id[i];
  if(i>=32||!((c>='a'&&c<='z')||(c>='0'&&c<='9')||(c=='-'&&i)))return 0;
 }
 return 1;
}
static int valid_io(const struct hb_install_io *io) {
 return io&&io->begin&&io->end&&io->inspect&&io->space&&io->prepare&&
        io->verify&&io->sync&&io->move&&io->remove&&io->cancelled;
}
static int recover_locked(const struct hb_install_io *io) {
 void *c=io->context;
 int live=io->inspect(c,HB_LIVE),backup=io->inspect(c,HB_BACKUP);
 int stage=io->inspect(c,HB_STAGE);
 if(live==HB_SLOT_ERROR||backup==HB_SLOT_ERROR||stage==HB_SLOT_ERROR)
  return HB_RECOVERY_REQUIRED;
 /* Invalid live/backup directories are ambiguous: do not delete user data. */
 if(live==HB_INVALID||backup==HB_INVALID)return HB_RECOVERY_REQUIRED;
 if(backup==HB_VALID) {
  if(live==HB_ABSENT) {
   if(io->move(c,HB_BACKUP,HB_LIVE)||io->sync(c))return HB_RECOVERY_REQUIRED;
  } else if(io->remove(c,HB_BACKUP)||io->sync(c))return HB_RECOVERY_REQUIRED;
 }
 /* STAGE is never active. It can be discarded after preserving/restoring LIVE. */
 if(stage!=HB_ABSENT&&(io->remove(c,HB_STAGE)||io->sync(c)))
  return HB_RECOVERY_REQUIRED;
 return 0;
}
static int finish(const struct hb_install_io *io,int result) {
 io->end(io->context);return result;
}
int hb_install_recover(const struct hb_install_io *io,const char *id) {
 int result;
 if(!valid_io(io)||!valid_id(id))return HB_INSTALL_INVALID;
 if(io->begin(io->context,id))return HB_INSTALL_FAILED;
 result=recover_locked(io);return finish(io,result);
}
static int discard(const struct hb_install_io *io,int result) {
 void *c=io->context;
 int state=io->inspect(c,HB_STAGE);
 if(state==HB_SLOT_ERROR)return HB_RECOVERY_REQUIRED;
 if(state!=HB_ABSENT&&(io->remove(c,HB_STAGE)||io->sync(c)))
  return HB_RECOVERY_REQUIRED;
 return result;
}
int hb_install_apply(const struct hb_install_io *io,const char *id,
                     unsigned long long bytes,unsigned long long reserve) {
 void *c;
 int result,had_live;
 if(!valid_io(io)||!valid_id(id)||!bytes||bytes+reserve<bytes)
  return HB_INSTALL_INVALID;
 c=io->context;
 if(io->begin(c,id))return HB_INSTALL_FAILED;
 result=recover_locked(io);
 if(result)return finish(io,result);
 if(io->cancelled(c))return finish(io,HB_INSTALL_CANCELLED);
 /* additional_bytes includes staging allocation and a caller-defined reserve;
  * existing LIVE/BACKUP allocation must already be included in free-space data. */
 if(io->space(c,bytes+reserve))return finish(io,HB_INSTALL_NO_SPACE);
 if(io->prepare(c)||io->verify(c)||io->sync(c))
  return finish(io,discard(io,HB_INSTALL_FAILED));
 if(io->cancelled(c))return finish(io,discard(io,HB_INSTALL_CANCELLED));
 had_live=io->inspect(c,HB_LIVE);
 if(had_live!=HB_ABSENT&&had_live!=HB_VALID)return finish(io,HB_RECOVERY_REQUIRED);
 if(had_live==HB_VALID) {
  if(io->move(c,HB_LIVE,HB_BACKUP))return finish(io,discard(io,HB_INSTALL_FAILED));
  if(io->sync(c))return finish(io,HB_RECOVERY_REQUIRED);
 }
 /* Complete or undo this short switch even if cancellation arrives now. */
 if(io->move(c,HB_STAGE,HB_LIVE)) {
  if(had_live==HB_VALID&&(io->move(c,HB_BACKUP,HB_LIVE)||io->sync(c)))
   return finish(io,HB_RECOVERY_REQUIRED);
  return finish(io,discard(io,HB_INSTALL_FAILED));
 }
 if(io->sync(c))return finish(io,HB_RECOVERY_REQUIRED);
 if(had_live==HB_VALID&&(io->remove(c,HB_BACKUP)||io->sync(c)))
  return finish(io,HB_INSTALLED_CLEANUP_PENDING);
 return finish(io,HB_INSTALLED);
}

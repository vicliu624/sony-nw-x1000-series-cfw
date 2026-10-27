#include "download_recovery.h"
#include <string.h>
void hb_download_recovery_init(struct hb_download_recovery *r){if(r){memset(r,0,sizeof *r);hb_package_assembly_init(&r->bundle);}}
int hb_download_recovery_review(struct hb_download_record *record,const struct hb_package_download_plan *plan,const char *cache,struct hb_download_recovery *out){
 if(!out||out->prepared||out->bundle.state!=HB_ASSEMBLE_EMPTY)return HB_PARTIAL_INPUT;
 int result=hb_payload_cache_review(record,plan,cache,&out->cache);if(result)return result;
 result=hb_partial_bundle_review(record,plan,&out->bundle);
 if(result&&result!=HB_PARTIAL_ABSENT){out->cache.valid=0;return result;}
 out->prepared=1;return 0;
}
int hb_download_recovery_discard(struct hb_download_record *record,const struct hb_package_download_plan *plan,struct hb_download_recovery *review){
 if(!record||!plan||!plan->valid||!review||!review->prepared||hb_download_intent_matches(&record->intent,plan))return HB_PARTIAL_INPUT;
 if(review->bundle.state==HB_ASSEMBLE_REVIEW&&review->bundle.plan!=plan)return HB_PARTIAL_INPUT;
 if(record->stop&&*record->stop)return HB_PARTIAL_CANCELLED;
 int result;
 if(record->removed){
  result=hb_payload_cache_absent(plan,&review->cache);if(result)return result;
 }else {
  /* Recheck the other scope BEFORE first cache deletion. */
  struct hb_package_assembly current;hb_package_assembly_init(&current);
  result=hb_partial_bundle_review(record,plan,&current);if(result&&result!=HB_PARTIAL_ABSENT)return result;
  if(!result){
   if(review->bundle.state!=HB_ASSEMBLE_REVIEW||current.device!=review->bundle.device||current.inode!=review->bundle.inode||strcmp(current.folder,review->bundle.folder))return HB_PARTIAL_INPUT;
  }else if(review->bundle.state!=HB_ASSEMBLE_EMPTY&&review->bundle.state!=HB_ASSEMBLE_REVIEW)return HB_PARTIAL_INPUT;
  result=hb_payload_cache_discard(record,plan,&review->cache);if(result)return result;
 }
 result=hb_partial_bundle_discard(record,plan,&review->bundle);if(result)return result;
 review->prepared=0;return 0;
}

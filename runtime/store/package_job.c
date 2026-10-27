#include "package_job.h"
#include "install_posix.h"
#include "package_resume.h"
#include <string.h>
static int failed(struct hb_package_job *j,int error){j->error=error;j->state=HB_JOB_FAILED;return error;}
static int path_ok(const char *p){return p&&*p&&strlen(p)<512;}
void hb_package_job_init(struct hb_package_job *j){if(j){memset(j,0,sizeof *j);hb_download_task_init(&j->task);hb_package_assembly_init(&j->assembly);hb_download_record_init(&j->record);hb_download_recovery_init(&j->recovery);}}
int hb_package_job_begin(struct hb_package_job *j,const struct hb_package_download_plan *plan,const char *cache,const char *packages,const char *apps,const br_x509_trust_anchor *anchors,size_t count,unsigned long long reserve,unsigned timeout,volatile int *stop,const struct ares_options *options,int mask){
 if(!j||j->state!=HB_JOB_EMPTY||!plan||!plan->valid||!path_ok(cache)||!path_ok(packages)||!path_ok(apps)||!anchors||!count||!timeout)return HB_NET_INPUT;
 j->plan=*plan;strcpy(j->cache,cache);strcpy(j->packages,packages);strcpy(j->apps,apps);
 j->anchors=anchors;j->anchor_count=count;j->reserve=reserve;j->timeout_ms=timeout;j->stop=stop;j->options=options;j->option_mask=mask;j->index=0;j->error=0;j->state=HB_JOB_OPEN;return 0;
}
int hb_package_job_step(struct hb_package_job *j,unsigned cap){
 if(!j||j->state==HB_JOB_EMPTY||j->state==HB_JOB_INSTALLED)return HB_NET_INPUT;
 if(j->state==HB_JOB_FAILED)return j->error;
 if(j->stop&&*j->stop){
  /* Let the active transport observe stop and release DNS/socket/TLS now.
   * Inactive files remain subject to the explicit discard policy. */
  if(j->state==HB_JOB_FETCH)(void)hb_download_task_step(&j->task,0);
  return failed(j,HB_NET_CANCELLED);
 }
 if(j->state==HB_JOB_READY)return 1;
 if(j->state==HB_JOB_RECOVERY)return 2;
 int result;
 switch(j->state){
 case HB_JOB_OPEN:
  result=hb_download_record_load(&j->record,j->packages,&j->plan,j->stop);
  if(result&&result!=HB_RECORD_ABSENT){j->unowned_conflict=j->record.state==HB_RECORD_REVIEW&&!j->record.owns;return failed(j,result);}
  result=hb_package_assembly_reopen(&j->assembly,j->packages,&j->plan,j->stop,&j->workspace);
  if(!result){j->index=j->plan.network_files;j->state=HB_JOB_READY;return 1;}
  if(j->record.state==HB_RECORD_READY){
   result=hb_download_recovery_review(&j->record,&j->plan,j->cache,&j->recovery);if(result)return failed(j,result);
   j->state=HB_JOB_RECOVERY;return 2;
  }
  if(result!=HB_ASSEMBLY_ABSENT){j->unowned_conflict=1;return failed(j,result);}
  result=hb_payload_cache_unclaimed_absent(&j->plan,j->cache);if(result){j->unowned_conflict=1;return failed(j,result);}
  result=hb_download_record_save(&j->record,j->packages,&j->plan,j->reserve,j->stop);
  if(result==HB_RECORD_STAGED){
   result=hb_download_record_review_temporary(&j->record,j->packages,&j->plan,j->stop);
   if(!result){j->state=HB_JOB_RECOVERY;return 2;}
   j->unowned_conflict=1;return failed(j,result>0?HB_RECORD_IO:result);
  }
  if(result){j->unowned_conflict=result==HB_RECORD_EXISTS||(j->record.owns&&!j->record.identity_known);return failed(j,result);}
  result=hb_package_assembly_begin(&j->assembly,j->packages,&j->plan,j->reserve,j->stop);
  if(result)return failed(j,result);
  j->state=HB_JOB_BEGIN_FILE;return 0;
 case HB_JOB_BEGIN_FILE:
  if(j->index==j->plan.network_files){j->state=HB_JOB_VERIFY;return 0;}
  result=hb_download_task_begin_file(&j->task,&j->plan,j->index,j->anchors,j->anchor_count,j->cache,j->reserve,j->timeout_ms,j->stop,j->options,j->option_mask);
  if(result)return failed(j,result);
  j->state=HB_JOB_FETCH;return 0;
 case HB_JOB_FETCH:
  result=hb_download_task_step(&j->task,cap);if(result<0)return failed(j,result);
  if(result==1)j->state=HB_JOB_COPY;
  return 0;
 case HB_JOB_COPY:
  result=hb_package_assembly_add(&j->assembly,j->index,&j->task.file);if(result)return failed(j,result);
  result=hb_download_task_discard(&j->task);if(result)return failed(j,result);
  j->index++;j->state=HB_JOB_BEGIN_FILE;return 0;
 case HB_JOB_VERIFY:
  result=hb_package_assembly_finish(&j->assembly,&j->workspace);if(result)return failed(j,result);
  j->state=HB_JOB_READY;return 1;
 default:return HB_NET_INPUT;
 }
}
int hb_package_job_install(struct hb_package_job *j){
 if(!j||j->state!=HB_JOB_READY)return HB_NET_INPUT;
 if(j->stop&&*j->stop)return failed(j,HB_NET_CANCELLED);
 int result=hb_store_install_local_expected(j->apps,j->assembly.folder,j->plan.bundle.package.id,j->reserve,j->stop,j->plan.identity);
 if(result)return failed(j,result);
 j->state=HB_JOB_INSTALLED;return 0;
}
static int clear_temporary(struct hb_package_job *j){
 int result=hb_download_task_discard(&j->task);if(result)return result;
 if(j->record.owns){
  if(j->record.provisional){
   if(j->assembly.state!=HB_ASSEMBLE_EMPTY||j->index)return HB_NET_INPUT;
   return hb_download_record_discard(&j->record);
  }
  if(!j->recovery.prepared){result=hb_download_recovery_review(&j->record,&j->plan,j->cache,&j->recovery);if(result)return result;}
  return hb_download_recovery_discard(&j->record,&j->plan,&j->recovery);
 }
 if(j->unowned_conflict)return HB_NET_INPUT;
 if(j->assembly.state!=HB_ASSEMBLE_EMPTY)return hb_package_assembly_discard(&j->assembly);
 return 0;
}
int hb_package_job_discard(struct hb_package_job *j){
 if(!j||j->state==HB_JOB_EMPTY)return HB_NET_INPUT;
 if(j->stop&&*j->stop)return HB_NET_CANCELLED;
 int result=clear_temporary(j);if(result)return failed(j,result);
 hb_package_job_init(j);return 0;
}
int hb_package_job_restart(struct hb_package_job *j){
 if(!j||j->state!=HB_JOB_RECOVERY)return HB_NET_INPUT;
 if(j->stop&&*j->stop)return failed(j,HB_NET_CANCELLED);
 int result=clear_temporary(j);if(result)return failed(j,result);
 hb_download_task_init(&j->task);hb_package_assembly_init(&j->assembly);hb_download_record_init(&j->record);hb_download_recovery_init(&j->recovery);
 j->index=0;j->error=0;j->unowned_conflict=0;j->state=HB_JOB_OPEN;return 0;
}

int hb_package_job_cancel(struct hb_package_job *j){
 if(!j||j->state==HB_JOB_EMPTY||j->state==HB_JOB_INSTALLED)return HB_NET_INPUT;
 if(j->state==HB_JOB_FAILED)return j->error;
 if(j->state==HB_JOB_FETCH)(void)hb_download_task_cancel(&j->task);
 return failed(j,HB_NET_CANCELLED);
}

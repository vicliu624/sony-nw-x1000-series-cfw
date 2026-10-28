#include "qqmusic_program.h"
#include "qqmusic_job.h"
struct entry_context {struct qq_job_config job;const struct qq_preview_client_channels *channels;};
static int entry(const struct qq_entry_config *config,void *context){struct entry_context *e=context;return qq_entry_run_import_preview(config,&e->job,e->channels);}
int qq_program_run_import_preview(const struct qq_program_config *config,const struct qq_job_config *job,const struct qq_preview_client_channels *channels){
 struct entry_context e;if(!config||!job||!channels)return -1;
 e.job=*job;e.channels=channels;e.job.network_context=config->platform_context;e.job.prepare_network=config->ensure_network;e.job.cancel_network=config->cancel_network;e.job.network_stop=config->stop;
 return qq_program_run_bound(config,entry,&e);
}

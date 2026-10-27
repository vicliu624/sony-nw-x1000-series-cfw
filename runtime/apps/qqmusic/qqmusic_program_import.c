#include "qqmusic_program.h"
#include "qqmusic_job.h"
static int entry(const struct qq_entry_config *config,void *job){return qq_entry_run_import(config,job);}
int qq_program_run_import(const struct qq_program_config *config,const struct qq_job_config *job){
 struct qq_job_config bound;if(!config||!job)return -1;bound=*job;
 bound.network_context=config->platform_context;bound.prepare_network=config->ensure_network;
 bound.cancel_network=config->cancel_network;bound.network_stop=config->stop;
 return qq_program_run_bound(config,entry,&bound);
}

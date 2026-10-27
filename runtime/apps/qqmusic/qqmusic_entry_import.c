#include "qqmusic_entry.h"
#include "qqmusic_import_binding.h"
#include <stdlib.h>
#include <string.h>
static int attach(void *context,struct qq_runtime *runtime,struct qq_devices *devices,unsigned char *font,size_t bytes,unsigned short *pixels){return qq_import_binding_attach_mapped(context,runtime,devices,font,bytes,pixels);}
int qq_entry_run_import(const struct qq_entry_config *config,const struct qq_job_config *job){
 struct qq_import_binding *binding;int rc;
 if(!config||!config->volume||!config->volume->source||!config->volume->filesystem||!job||!job->volume.source||!job->volume.filesystem||strcmp(config->volume->source,job->volume.source)||strcmp(config->volume->filesystem,job->volume.filesystem))return -1;
 binding=calloc(1,sizeof(*binding));if(!binding)return -1;
 if(qq_import_binding_init(binding,job)){qq_import_binding_destroy(binding);free(binding);return -1;}
 rc=qq_entry_run_bound(config,attach,binding);qq_import_binding_destroy(binding);free(binding);return rc;
}

#include "qqmusic_entry.h"
#include "qqmusic_preview_binding.h"
#include <stdlib.h>
#include <string.h>
struct binding {struct qq_import_binding imports;struct qq_preview_binding preview;const struct qq_preview_client_channels *channels;volatile int *stop;};
static int attach(void *context,struct qq_runtime *runtime,struct qq_devices *devices,unsigned char *font,size_t bytes,unsigned short *pixels){
 struct binding *b=context;
 if(qq_import_binding_attach_mapped(&b->imports,runtime,devices,font,bytes,pixels))return -1;
 return qq_preview_binding_attach(&b->preview,&b->imports,b->channels,b->stop);
}
int qq_entry_run_import_preview(const struct qq_entry_config *config,const struct qq_job_config *job,const struct qq_preview_client_channels *channels){
 struct binding *b;int rc;
 if(!config||!config->volume||!job||!channels||!config->volume->source||!config->volume->filesystem||!job->volume.source||!job->volume.filesystem||strcmp(config->volume->source,job->volume.source)||strcmp(config->volume->filesystem,job->volume.filesystem))return -1;
 b=calloc(1,sizeof(*b));if(!b)return -1;b->channels=channels;b->stop=config->stop;
 if(qq_import_binding_init(&b->imports,job)){qq_import_binding_destroy(&b->imports);free(b);return -1;}
 rc=qq_entry_run_bound(config,attach,b);qq_preview_binding_destroy(&b->preview);qq_import_binding_destroy(&b->imports);free(b);return rc;
}

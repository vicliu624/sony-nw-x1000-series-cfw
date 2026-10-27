#include "qqmusic_file_import.h"
#include <string.h>
int qq_file_import(struct qq_volume *volume,const struct qq_storage_plan *plan,const struct qq_stage_file *source,
 const struct qq_import_conversion *config,const char *identity,const char *nonce,
 struct qq_output_file *output,struct qq_import_report *report){
 struct qq_source_file reader;struct qq_import_conversion conversion;int acquired=0,rc=-1;
 if(report)memset(report,0,sizeof(*report));
 if(!volume||!plan||!source||!config||!output||!report||output->stage.state!=QQ_STAGE_EMPTY||!config->maximum_output||plan->source<source->bytes||!plan->files[0]||config->io.source||config->io.destination||config->io.source_bytes||config->io.read_at||config->io.write||config->io.metadata||config->io.comment||config->io.comments_done)return -1;
 qq_source_init(&reader);
 if(qq_source_open(&reader,volume,plan,source,config->io.stop))return -1;
 if(qq_output_begin(output,volume,plan,identity,nonce,config->maximum_output,config->io.stop))goto done;
 acquired=1;conversion=*config;conversion.io.source=&reader;conversion.io.source_bytes=reader.bytes;conversion.io.read_at=qq_source_read_at;
 conversion.io.destination=output;conversion.io.write=qq_output_write;
 if(qq_import_convert(&conversion,report)||qq_output_finish(output,report->output_bytes))goto done;
 rc=0;
done:if(qq_source_close(&reader))rc=-1;
 if(rc){if(acquired)(void)qq_output_abort(output);memset(report,0,sizeof(*report));}
 qq_secret_clear(&conversion,sizeof(conversion));return rc;
}

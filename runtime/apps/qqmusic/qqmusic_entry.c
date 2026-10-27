#include "qqmusic_font.h"
#include "qqmusic_entry.h"
#include "qqmusic_asset.h"
#include <stdlib.h>
#include <string.h>
int qq_entry_run_bound(const struct qq_entry_config *config,qq_entry_setup setup,void *context) {
 static const unsigned char font_hash[32]=QQ_FONT_SHA256;
 struct qq_volume volume;struct qq_storage_plan plan;struct qq_runtime *runtime=0;
 struct qq_devices devices;struct qq_loop loop;struct qq_loop_io io;
 unsigned short *pixels=0;unsigned char *font=0;uint64_t required;
 struct qq_asset_mapping mapping={0};
 int runtime_open=0,devices_open=0,loop_open=0,rc=-1;
 if(!config||!config->volume||!config->resource_directory||!config->operations||!config->stop||*config->stop)return -1;
 qq_volume_init(&volume);memset(&plan,0,sizeof(plan));
 /* Existing resources only. A zero write plan grants no download capacity. */
 if(qq_volume_open(&volume,config->volume,config->resource_directory,&plan,&required))goto done;
 if(qq_asset_map(&volume,&plan,QQ_FONT_NAME,QQ_FONT_BYTES,font_hash,&mapping)||qq_ui_font_mapped(&mapping))goto done;
 font=mapping.data;
 runtime=calloc(1,sizeof(*runtime));pixels=calloc(QQ_UI_PIXELS,sizeof(*pixels));
 if(!runtime||!pixels||qq_runtime_init(runtime,config->operations))goto done;
 runtime_open=1;
 if(*config->stop||qq_devices_open(&devices,&io,pixels,QQ_UI_PIXELS,config->stop))goto done;
 devices_open=1;
 if(setup&&setup(context,runtime,&devices,font,QQ_FONT_BYTES,pixels))goto done;
 if(qq_loop_init(&loop,runtime,&io,pixels,QQ_UI_PIXELS))goto done;
 loop_open=1;do{rc=qq_loop_step(&loop);}while(!rc);rc=rc<0?-1:0;
done:
 if(loop_open){qq_loop_close(&loop);if(loop.failed)rc=-1;}
 else {if(runtime_open)qq_runtime_close(runtime);if(devices_open&&qq_devices_close(&devices))rc=-1;}
 if(pixels){qq_secret_clear(pixels,QQ_UI_PIXELS*sizeof(*pixels));free(pixels);}
 if(runtime){qq_secret_clear(runtime,sizeof(*runtime));free(runtime);}
 /* Invalidate borrowed renderer pointers before freeing the font bytes. */
 if(mapping.data){(void)qq_ui_font(0,0);if(qq_asset_unmap(&mapping))rc=-1;}
 if(qq_volume_close(&volume))rc=-1;
 return rc;
}
int qq_entry_run(const struct qq_entry_config *config){return qq_entry_run_bound(config,0,0);}

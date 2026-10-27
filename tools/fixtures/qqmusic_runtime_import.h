/* Synthetic task backend: exercises real runtime/UI dispatch, not disk IO. */
static struct qq_runtime import_snapshot;
static void source_preset_checks(void){static const unsigned bitrate[]={128,192,320};static const char *file[]={"O4M0MEDIA02.mgg","O6M0MEDIA02.mgg","O8M0MEDIA02.mgg"};unsigned i;
 for(i=0;i<3;i++){runtime.ui.quality=bitrate[i];assert(runtime.ui.page==QQ_UI_DETAIL&&runtime.app.view==QQ_APP_TRACK);assert(qq_runtime_touch(&runtime,100,375,now)==1&&qq_runtime_step(&runtime,now,100000)==1);assert(strstr(mock.request.body,"CgiGetEVkey")&&strstr(mock.request.body,file[i])&&!strstr(mock.request.body,"M500")&&!strstr(mock.request.body,".mp3"));assert(qq_runtime_touch(&runtime,15,40,now)==1&&!runtime.active&&runtime.app.view==QQ_APP_TRACK&&runtime.ui.page==QQ_UI_DETAIL);}
}
static struct {unsigned begins,polls,cancels;int live,fail_begin,result;struct qq_resource copied;struct qq_runtime_import_progress progress;} importer;
static int import_begin(void *context,const struct qq_song *song,const struct qq_resource_intent *intent,const struct qq_resource *resource,const struct qq_export_plan *layout,uint64_t clock,uint64_t expires){
 (void)context;assert(!importer.live&&runtime.importing&&runtime.ui.page==QQ_UI_PROGRESS&&expires>clock);
 assert(!strcmp(song->mid,"MID02")&&!strcmp(intent->filename,"O4M0MEDIA02.mgg")&&resource->encrypted&&resource->ekey[0]&&resource->url[0]&&layout->identity[0]);
 importer.begins++;importer.live=1;importer.copied=*resource;return importer.fail_begin?-1:0;
}
static int import_poll(void *context,uint64_t clock,struct qq_runtime_import_progress *progress){(void)context;(void)clock;assert(importer.live);importer.polls++;*progress=importer.progress;return importer.result;}
static void import_cancel(void *context){(void)context;assert(importer.live&&runtime.app.selected.mid[0]&&runtime.app.login.session.state==QQ_READY&&runtime.app.login.credential.musicid);importer.live=0;importer.cancels++;qq_resource_clear(&importer.copied);}
static void import_reset(void){struct qq_runtime_import_ops operations={0,import_begin,import_poll,import_cancel};assert(!importer.live);runtime=import_snapshot;memset(&importer,0,sizeof(importer));assert(qq_runtime_bind_import(&runtime,&operations)==0);}
static void import_start(uint64_t clock){assert(qq_runtime_touch(&runtime,100,375,clock)==1&&runtime.importing&&!runtime.ui.import_complete&&!runtime.app.resource.url[0]&&importer.copied.url[0]);}
static void import_checks(unsigned short *pixels){uint64_t clock=now+1;import_snapshot=runtime;assert(runtime.resource_received_ms==now&&runtime.resource_issued_ms==now-1&&runtime.resource_expires_ms==runtime.resource_issued_ms+60000);
 import_reset();import_start(clock);assert(qq_runtime_bind_import(&runtime,0)<0);importer.progress.percent=10;
 assert(qq_runtime_step(&runtime,clock+1,100000)==0&&runtime.ui.page==QQ_UI_PROGRESS&&runtime.ui.percent==10);
 assert(qq_ui_draw(&runtime.ui,pixels,QQ_UI_PIXELS)==0);
 importer.progress.stage=1;importer.progress.percent=50;assert(qq_runtime_step(&runtime,clock+2,100000)==0);
 importer.progress.stage=3;importer.progress.percent=100;importer.progress.published=1;importer.result=1;
 assert(qq_runtime_step(&runtime,import_snapshot.resource_expires_ms+1,100000)==1&&runtime.ui.page==QQ_UI_RESULT&&runtime.ui.import_complete&&importer.cancels==1&&!importer.copied.url[0]);
 assert(qq_ui_draw(&runtime.ui,pixels,QQ_UI_PIXELS)==0);
 assert(qq_runtime_step(&runtime,import_snapshot.resource_expires_ms+2,100000)==0&&runtime.ui.page==QQ_UI_RESULT);
 assert(qq_runtime_touch(&runtime,100,360,import_snapshot.resource_expires_ms+2)==1&&runtime.app.view==QQ_APP_SONGS);
 import_reset();import_start(clock);importer.result=1;importer.progress.stage=3;importer.progress.percent=100;
 assert(qq_runtime_step(&runtime,clock+1,100000)<0&&!runtime.ui.import_complete&&runtime.error==QQ_RUN_IMPORT&&importer.cancels==1);
 import_reset();import_start(clock);importer.progress.review=1;importer.result=-1;
 assert(qq_runtime_step(&runtime,clock+1,100000)<0&&runtime.error==QQ_RUN_REVIEW&&runtime.ui.import_review&&!runtime.ui.import_complete);
 assert(qq_ui_draw(&runtime.ui,pixels,QQ_UI_PIXELS)==0);
 import_reset();importer.fail_begin=1;assert(qq_runtime_touch(&runtime,100,375,clock)<0&&importer.cancels==1&&!runtime.importing&&runtime.ui.page==QQ_UI_RESULT);
 import_reset();import_start(clock);assert(qq_runtime_touch(&runtime,100,375,clock+1)==1&&!runtime.importing&&runtime.ui.page==QQ_UI_DETAIL&&importer.cancels==1&&!runtime.app.resource.url[0]);
 import_reset();runtime.resource_expires_ms=0;assert(qq_runtime_touch(&runtime,100,375,clock)<0&&runtime.error==QQ_RUN_AUTHORIZATION&&!importer.begins&&!runtime.app.resource.url[0]);
 import_reset();assert(qq_runtime_touch(&runtime,100,375,runtime.resource_expires_ms)<0&&runtime.error==QQ_RUN_AUTHORIZATION&&!importer.begins);
 import_reset();runtime.resource_received_ms=clock+1;assert(qq_runtime_touch(&runtime,100,375,clock)<0&&!importer.begins&&runtime.error==QQ_RUN_AUTHORIZATION);
 import_reset();import_start(clock);assert(qq_runtime_step(&runtime,runtime.resource_expires_ms,100000)<0&&runtime.error==QQ_RUN_AUTHORIZATION&&importer.polls==1&&importer.cancels==1);
 import_reset();import_start(clock);importer.progress.stage=1;importer.progress.percent=50;assert(qq_runtime_step(&runtime,runtime.resource_expires_ms+1,100000)==0&&runtime.importing&&runtime.ui.stage==1);
 importer.progress.stage=3;importer.progress.percent=100;importer.progress.published=1;importer.result=1;assert(qq_runtime_step(&runtime,runtime.resource_expires_ms+2,100000)==1&&runtime.ui.import_complete);
 import_reset();import_start(clock);assert(qq_runtime_step(&runtime,clock-1,100000)<0&&runtime.error==QQ_RUN_CLOCK&&importer.cancels==1&&runtime.ui.page==QQ_UI_LOGIN);
 import_reset();import_start(clock);qq_runtime_close(&runtime);assert(importer.cancels==1&&!runtime.app.selected.mid[0]&&!runtime.app.login.credential.musicid);
 import_reset();import_start(clock);importer.progress.percent=10;assert(qq_runtime_step(&runtime,clock+1,100000)==0);importer.progress.percent=9;
 assert(qq_runtime_step(&runtime,clock+2,100000)<0&&runtime.error==QQ_RUN_IMPORT&&!runtime.ui.import_complete);
 import_reset();import_start(clock);importer.progress.published=1;importer.progress.percent=100;importer.progress.stage=3;
 assert(qq_runtime_step(&runtime,clock+1,100000)<0&&runtime.error==QQ_RUN_REVIEW&&runtime.ui.import_review&&!runtime.ui.import_complete);
 import_reset();import_start(clock);importer.progress.published=1;importer.progress.percent=100;importer.progress.stage=2;importer.result=1;
 assert(qq_runtime_step(&runtime,clock+1,100000)<0&&runtime.error==QQ_RUN_REVIEW&&runtime.ui.import_review&&!runtime.ui.import_complete);
 assert(!importer.live);runtime=import_snapshot;
}

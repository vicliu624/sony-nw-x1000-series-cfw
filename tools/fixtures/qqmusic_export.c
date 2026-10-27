#include "../../runtime/apps/qqmusic/qqmusic_export.h"
#include <assert.h>
#include <string.h>
static struct qq_song song;
static struct qq_resource_intent intent;
static struct qq_export_plan first,second;
static void text(char *out,const char *s) {memcpy(out,s,strlen(s)+1);}
int main(void) {
 unsigned char actual[32]={1},recorded[32]={1};unsigned i;
 text(song.mid,"SONG01");text(song.media_mid,"MEDIA01");text(song.album_mid,"ALBUM01");song.album_id=42;song.track=3;song.disc=1;
 text(song.artist,"CON");text(song.album,"../专辑:名");text(song.title,"歌/曲?名 🎵");
 assert(qq_resource_intent_init(&intent,song.mid,song.media_mid,0,QQ_MGG_96)==0);
 assert(qq_export_plan(&song,&intent,0,&first)==0&&first.version==1);
 assert(first.relative[0]!='/'&&!strchr(first.relative,':')&&!strchr(first.relative,'?')&&!strchr(first.relative,'\\'));
 assert(strstr(first.relative,"q-CON-")&&strstr(first.relative,"01-03 q-歌_曲_名 🎵"));
 assert(qq_export_plan(&song,&intent,0,&second)==0&&!strcmp(first.relative,second.relative));
 assert(qq_export_existing_check(&first,0,0,0,0)==QQ_EXPORT_NEW);
 assert(qq_export_existing_check(&first,1,first.identity,recorded,actual)==QQ_EXPORT_REUSE);
 actual[0]=2;assert(qq_export_existing_check(&first,1,first.identity,recorded,actual)==QQ_EXPORT_CONFLICT);
 assert(qq_export_existing_check(&first,1,"different",recorded,recorded)==QQ_EXPORT_CONFLICT);
 assert(qq_export_existing_check(&first,1,0,recorded,recorded)==QQ_EXPORT_CONFLICT);
 text(song.mid,"song01");assert(qq_resource_intent_init(&intent,song.mid,song.media_mid,0,QQ_MGG_96)==0);
 assert(qq_export_plan(&song,&intent,0,&second)==0&&strcmp(first.identity,second.identity));
 text(song.mid,"SONG01");assert(qq_resource_intent_init(&intent,song.mid,song.media_mid,0,QQ_MP3_320)==0);
 assert(qq_export_plan(&song,&intent,0,&second)==0&&strcmp(first.identity,second.identity));
 assert(qq_resource_intent_init(&intent,song.mid,song.media_mid,0,QQ_MGG_96)==0);
 for(i=0;i<120;i++) memcpy(song.title+i*3,"中",3);
 song.title[360]=0;assert(qq_export_plan(&song,&intent,0,&second)==0&&strlen(second.relative)<513);
 {const char *p=second.relative;unsigned slashes=0;for(;*p;p++) if(*p=='/') slashes++;assert(slashes==2);}
 song.title[360]=(char)0xc0;song.title[361]=(char)0x80;song.title[362]=0;
 assert(qq_export_plan(&song,&intent,0,&second)<0&&!second.relative[0]);
 song.title[0]=0;song.artist[0]=0;song.album[0]=0;
 assert(qq_export_plan(&song,&intent,0,&second)==0&&strstr(second.relative,"Unknown artist")&&strstr(second.relative,"Untitled"));
 text(song.media_mid,"OTHER");assert(qq_export_plan(&song,&intent,0,&second)<0);
 return 0;
}

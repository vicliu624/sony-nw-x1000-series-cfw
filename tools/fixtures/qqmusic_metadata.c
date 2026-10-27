#include "../../runtime/apps/qqmusic/qqmusic_metadata.h"
#include <assert.h>
#include <string.h>
#include <unistd.h>
static struct qq_metadata metadata;
static struct qq_song song;
static struct qq_resource_intent intent;
static struct qq_track_tags tags;
static unsigned char buffer[65536];
static void source(const char *key,const char *value) {assert(qq_metadata_comment(&metadata,key,strlen(key),value,strlen(value))==0);}
int main(void) {
 size_t bytes;unsigned char saved[65536];size_t saved_bytes;
 memcpy(song.mid,"SONG01",7);memcpy(song.media_mid,"MEDIA01",8);memcpy(song.album_mid,"ALBUM01",8);song.album_id=42;
 memcpy(intent.song_mid,song.mid,7);memcpy(intent.media_mid,song.media_mid,8);
 memcpy(song.title,"接口标题",sizeof("接口标题"));memcpy(song.album,"接口专辑",sizeof("接口专辑"));song.track=9;song.disc=2;
 memcpy(song.date,"2026-10-26",11);
 qq_metadata_init(&metadata);source("TITLE","源标题 🎵");source("ARTIST","甲");source("ARTIST","乙");source("TRACKNUMBER","3");source("TRACKTOTAL","12");
 source("DATE","2025-03-04");source("YEAR","2025");source("GENRE","Jazz");source("COMPOSER","作曲甲");source("CUSTOM","保留字段");
 assert(qq_metadata_fill(&metadata,&song,&intent,"专辑艺人")==0&&qq_metadata_tags(&metadata,&tags)==0);
 assert(!strcmp(tags.title,"源标题 🎵")&&!strcmp(tags.artist,"甲 / 乙")&&!strcmp(tags.album,"接口专辑"));
 assert(!strcmp(tags.track,"3/12")&&!strcmp(tags.disc,"2")&&!strcmp(tags.year,"2025")&&!strcmp(tags.date,"2025-03-04"));
 assert(qq_id3_build(&tags,buffer,sizeof(buffer),&bytes)==0);memcpy(saved,buffer,bytes);saved_bytes=bytes;
 qq_metadata_init(&metadata);source("TITLE","one");assert(qq_metadata_comment(&metadata,"TITLE",5,"two",3)<0&&qq_metadata_tags(&metadata,&tags)<0);
 qq_metadata_init(&metadata);assert(qq_metadata_comment(&metadata,"METADATA_BLOCK_PICTURE",22,"test",4)==-2&&qq_metadata_tags(&metadata,&tags)<0);
 qq_metadata_init(&metadata);memcpy(intent.song_mid,"OTHER",6);assert(qq_metadata_fill(&metadata,&song,&intent,0)<0&&qq_metadata_tags(&metadata,&tags)<0);
 qq_metadata_init(&metadata);source("TRACKNUMBER","3/12");source("TRACKTOTAL","13");assert(qq_metadata_tags(&metadata,&tags)<0);
 assert(write(1,saved,saved_bytes)==(ssize_t)saved_bytes);return 0;
}

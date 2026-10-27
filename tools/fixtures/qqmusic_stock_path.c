#include "../../runtime/apps/qqmusic/qqmusic_stock_path.h"
#include <assert.h>
#include <string.h>
int main(void){struct qq_export_plan plan;char output[2049];memset(&plan,0,sizeof(plan));plan.version=1;strcpy(plan.relative,"q-艺人/q-专辑/01 q-歌曲.mp3");
 assert(qq_stock_music_root("/contents/MUSIC")==0&&qq_stock_music_root("/contents/MUSIC/QQMusic")==0);
 assert(qq_stock_music_path("/contents/MUSIC",&plan,output,sizeof(output))==0&&!strcmp(output,"/contents/MUSIC/q-艺人/q-专辑/01 q-歌曲.mp3"));
 assert(qq_stock_music_path("/contents/MUSIC/a/b/c/d/e",&plan,output,sizeof(output))==0);
 assert(qq_stock_music_root("/contents/MUSIC/a/b/c/d/e/f")<0);
 assert(qq_stock_music_root("/contents/MUSIC_BACKUP")<0&&qq_stock_music_root("/contents/OMGAUDIO")<0&&qq_stock_music_root("/MUSIC")<0);
 assert(qq_stock_music_root("/contents/MUSIC/../escape")<0&&qq_stock_music_root("/contents/MUSIC//bad")<0&&qq_stock_music_root("/contents/MUSIC/bad/")<0&&qq_stock_music_root("/contents/MUSIC/bad.")<0);
 assert(qq_stock_music_path("/contents/MUSIC",&plan,output,8)<0&&!output[0]);
 strcpy(plan.relative,"../q-专辑/01 q-歌曲.mp3");assert(qq_stock_music_path("/contents/MUSIC",&plan,output,sizeof(output))<0&&!output[0]);
 strcpy(plan.relative,"q-艺人/q-专辑/sub/01 q-歌曲.mp3");assert(qq_stock_music_path("/contents/MUSIC",&plan,output,sizeof(output))<0);
 strcpy(plan.relative,"q-艺人/q-专辑/01 q-歌曲.part");assert(qq_stock_music_path("/contents/MUSIC",&plan,output,sizeof(output))<0);
 return 0;
}

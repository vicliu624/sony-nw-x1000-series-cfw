#include "../../runtime/apps/qqmusic/qqmusic_catalog.h"
#include "../../runtime/apps/qqmusic/qqmusic_cgi.h"
#include <assert.h>
#include <string.h>
static struct qq_json json;
static struct qq_playlist_page lists;
static struct qq_song_page songs;
static void bad_list(const char *s) {
 uint64_t code;unsigned i;
 assert(qq_parse_playlists(&json,s,strlen(s),QQ_PLAYLIST_CREATED,&lists,&code)<0);
 for(i=0;i<sizeof(lists);i++) assert(((unsigned char *)&lists)[i]==0);
}
int main(void) {
 uint64_t code;struct qq_catalog_cursor cursor={0},before;size_t i;
 const char *created="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total\":2,\"bFinish\":true,\"v_playlist\":[{\"tid\":0,\"dirId\":201,\"dirName\":\"我喜欢\",\"songNum\":3},{\"id\":9007199254740993,\"dirid\":1,\"title\":\"测试歌单\",\"songnum\":12}]}}}";
 const char *collected="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total\":2,\"hasmore\":1,\"v_list\":[{\"dissid\":\"1234\",\"dirid\":0,\"dissname\":\"收藏歌单\",\"song_cnt\":2}]}}}";
 const char *page="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total_song_num\":2,\"hasmore\":1,\"songlist\":[{\"id\":9007199254740993,\"mid\":\"MID_01\",\"title\":\"中文歌曲 🎵\",\"name\":\"different fallback\",\"album\":{\"id\":42,\"mid\":\"ALBUM_01\",\"name\":\"专辑\"},\"singer\":[{\"name\":\"甲\"},{\"name\":\"乙\"}],\"index_album\":3,\"index_cd\":1,\"interval\":200,\"time_public\":\"2026-10-26\",\"file\":{\"media_mid\":\"MEDIA_01\"}}]}}}";
 assert(qq_parse_playlists(&json,created,strlen(created),QQ_PLAYLIST_CREATED,&lists,&code)==0);
 assert(lists.count==2&&!lists.more&&lists.entries[0].dirid==201&&lists.entries[1].id==9007199254740993ULL);
 assert(qq_parse_playlists(&json,collected,strlen(collected),QQ_PLAYLIST_COLLECTED,&lists,&code)==0&&lists.more);
 assert(qq_parse_songs(&json,page,strlen(page),&songs,&code)==0);
 assert(songs.count==1&&songs.more&&songs.entries[0].id==9007199254740993ULL);
 assert(!strcmp(songs.entries[0].title,"中文歌曲 🎵")&&!strcmp(songs.entries[0].artist,"甲 / 乙"));
 assert(songs.entries[0].track==3&&songs.entries[0].disc==2&&!strcmp(songs.entries[0].media_mid,"MEDIA_01"));
 assert(qq_catalog_advance(&cursor,1,1,2)==0&&cursor.offset==1);before=cursor;
 assert(qq_catalog_advance(&cursor,0,1,2)<0&&!memcmp(&cursor,&before,sizeof(cursor)));
 assert(qq_catalog_advance(&cursor,1,0,3)<0&&!memcmp(&cursor,&before,sizeof(cursor)));
 assert(qq_catalog_advance(&cursor,1,0,2)==0&&cursor.finished);
 assert(qq_catalog_advance(&cursor,1,0,2)<0);
 bad_list("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total\":2,\"bFinish\":true,\"v_playlist\":[]}}}");
 bad_list("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total\":2,\"bFinish\":false,\"v_playlist\":[]}}}");
 for(i=0;i<strlen(page);i++) {assert(qq_parse_songs(&json,page,i,&songs,&code)<0);assert(!songs.count&&!songs.entries[0].mid[0]);}
 {const char *denied="{\"code\":0,\"req_0\":{\"code\":1000}}";assert(qq_parse_songs(&json,denied,strlen(denied),&songs,&code)==QQ_AUTH_EXPIRED&&!songs.count);}
 {struct qq_request request;int node;uint64_t v;
 const char *comm="{\"ct\":\"11\",\"cv\":\"20090008\",\"tmeLoginType\":\"2\",\"qq\":\"123456\",\"authst\":\"synthetic_only\"}";
 assert(qq_build_catalog_cgi(&request,&json,comm,strlen(comm),QQ_REQ_FAVORITE_SONGS,123456,"synthetic*uin",0,201,16,16)==0);
 assert(strstr(request.body,"synthetic*uin"));
 assert(qq_json_parse(&json,request.body,strlen(request.body))==0);
 node=qq_json_get(&json,0,"req_0");assert(node>=0);node=qq_json_get(&json,(unsigned)node,"param");assert(node>=0);
 node=qq_json_get(&json,(unsigned)node,"song_begin");assert(node>=0&&qq_json_uint(&json,(unsigned)node,&v)==0&&v==16);
 assert(qq_build_catalog_cgi(&request,&json,comm,strlen(comm),QQ_REQ_CREATED,123456,0,0,0,0,16)==0&&strstr(request.body,"GetPlaylistByUin"));
 assert(qq_build_catalog_cgi(&request,&json,comm,strlen(comm),QQ_REQ_COLLECTED,123456,"synthetic_uin",0,0,0,16)==0&&strstr(request.body,"CgiGetPlaylistFavInfo"));
 assert(qq_build_catalog_cgi(&request,&json,comm,strlen(comm),QQ_REQ_PLAYLIST_SONGS,123456,0,555,3,0,16)==0&&strstr(request.body,"\"disstid\":555"));
 assert(qq_build_catalog_cgi(&request,&json,comm,strlen(comm),QQ_REQ_FAVORITE_SONGS,123456,"x\"injection",0,201,0,16)<0&&!request.host);
 assert(qq_build_catalog_cgi(&request,&json,comm,strlen(comm),QQ_REQ_CREATED,123456,0,0,0,1,16)<0);
 }
 return 0;
}

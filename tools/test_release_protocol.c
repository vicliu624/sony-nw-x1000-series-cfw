#include "../runtime/store/remote_catalog.h"
#include "../runtime/store/https_url.h"
#include "../runtime/store/http_response.h"
#include <stdio.h>
#include <string.h>
static int sink(void *p,const unsigned char *b,unsigned n){(void)p;(void)b;return (int)n;}
int main(void){
 char row[1024],url[1024];struct hb_remote_catalog c;const char *zero="0000000000000000000000000000000000000000000000000000000000000000";
 int n=snprintf(row,sizeof row,"HBSTORE2\nhello\t0.1.0\thttps://github.com/o/r/releases/download/v1/\t100\t%s\t120\t%s\thello--\n",zero,zero);
 if(hb_remote_catalog_parse((unsigned char *)row,(unsigned)n,&c)||c.count!=1||strcmp(c.entries[0].asset_prefix,"hello--"))return 1;
 if(hb_https_asset_url(url,sizeof url,c.entries[0].base_url,c.entries[0].asset_prefix,"assets/a_b.bin")||!strstr(url,"hello--6173736574732f615f622e62696e"))return 2;
 if(hb_https_asset_url(url,sizeof url,"https://example.test/","","assets/a.bin")||strcmp(url,"https://example.test/assets/a.bin"))return 3;
 if(!hb_https_asset_url(url,sizeof url,"http://example.test/","x--","app")||!hb_https_asset_url(url,sizeof url,"https://example.test/","../","app")||!hb_https_asset_url(url,sizeof url,"https://example.test/","x--","../x"))return 4;
 struct hb_download_stream body;struct hb_http_response h;unsigned char digest[32]={0};
 hb_download_stream_init(&body,3,digest,0,sink,0);hb_http_response_init(&h,&body);h.allow_redirects=1;
 const char *redirect="HTTP/1.1 302 Found\r\nLocation: https://release-assets.githubusercontent.com/test?x=1\r\nContent-Length: 999\r\n\r\nbody";
 if(hb_http_response_push(&h,(const unsigned char *)redirect,(unsigned)strlen(redirect))||h.state!=HB_HTTP_REDIRECT||body.received||!strstr(h.location,"https://release-assets"))return 5;
 hb_download_stream_init(&body,3,digest,0,sink,0);hb_http_response_init(&h,&body);
 if(!hb_http_response_push(&h,(const unsigned char *)redirect,(unsigned)strlen(redirect)))return 6;
 const char *bad="HTTP/1.1 302 Found\r\nLocation: http://example.test/plain\r\n\r\n";
 hb_download_stream_init(&body,3,digest,0,sink,0);hb_http_response_init(&h,&body);h.allow_redirects=1;
 if(!hb_http_response_push(&h,(const unsigned char *)bad,(unsigned)strlen(bad)))return 7;
 char large[9000];const char *prefix="HTTP/1.1 302 Found\r\nContent-Security-Policy: ";
 unsigned length=(unsigned)strlen(prefix);memcpy(large,prefix,length);memset(large+length,'a',4000);length+=4000;
 const char *tail="\r\nLocation: https://example.test/asset\r\n\r\n";memcpy(large+length,tail,strlen(tail));length+=(unsigned)strlen(tail);
 hb_download_stream_init(&body,3,digest,0,sink,0);hb_http_response_init(&h,&body);h.allow_redirects=1;
 if(hb_http_response_push(&h,(unsigned char *)large,length)||h.state!=HB_HTTP_REDIRECT)return 8;
 hb_download_stream_init(&body,3,digest,0,sink,0);hb_http_response_init(&h,&body);h.allow_redirects=1;
 const char *start="HTTP/1.1 302 Found\r\nX-Large: ";
 if(hb_http_response_push(&h,(const unsigned char *)start,(unsigned)strlen(start)))return 9;
 memset(large,'a',sizeof large);
 if(!hb_http_response_push(&h,(unsigned char *)large,sizeof large))return 10;
 puts("Release catalog, collision-free flat assets and HTTPS redirect parsing passed");return 0;
}

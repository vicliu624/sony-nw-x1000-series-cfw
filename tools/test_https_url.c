#include "../runtime/store/https_url.h"
#include <assert.h>
#include <string.h>
static void good(const char *text,const char *host,unsigned port,const char *path){struct hb_https_url value;assert(!hb_https_url_parse(text,&value));assert(!strcmp(value.host,host)&&value.port==port&&!strcmp(value.path,path));}
static void bad(const char *text){struct hb_https_url value,before;memset(&value,0x55,sizeof value);before=value;assert(hb_https_url_parse(text,&value)==-1&&!memcmp(&value,&before,sizeof value));}
int main(void){
 good("https://example.test","example.test",443,"/");
 good("HTTPS://EXAMPLE.TEST:8443/app?x=1#unused","example.test",8443,"/app?x=1");
 good("https://localhost?download=1","localhost",443,"/?download=1");
 good("https://xn--test.example/a%2Fb","xn--test.example",443,"/a%2Fb");
 good("https://example.test:65535/#x","example.test",65535,"/");
 bad("http://example.test/");bad("https://user@example.test/");bad("https://example.test:0/");bad("https://example.test:65536/");bad("https://example.test:443evil/");
 bad("https://127.0.0.1/");bad("https://[::1]/");bad("https://-bad.test/");bad("https://bad-.test/");bad("https://bad..test/");bad("https://example.test./");
 bad("https://example.test/x\r\nInjected: yes");bad("https://example.test/%0");bad("https://example.test/%xx");bad("https://example.test/\\evil");bad("https://example.test//evil");bad("https://example.test/#bad\n");
 char text[2200];strcpy(text,"https://example.test/");unsigned start=(unsigned)strlen(text);
 for(unsigned i=0;i<2047;i++)text[start+i]='a';
 text[start+2047]=0;
 good(text,"example.test",443,text+start-1);text[start+2047]='a';text[start+2048]=0;bad(text);
 return 0;
}

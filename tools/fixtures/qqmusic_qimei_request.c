/* PC-only production request generator. Stdout is private IPC, never a log. */
#include "../../runtime/apps/qqmusic/qqmusic_qimei.h"
#include "../../runtime/apps/qqmusic/qqmusic_http.h"
#include "qqmusic_profile.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static struct qq_request request;
static struct qq_cookie_jar cookies;
static char wire[12288];
int main(int argc,char **argv){
 volatile int stop=0;unsigned long long timestamp;size_t bytes;int rc=1;
 if(argc!=2)return 64;
 timestamp=strtoull(argv[1],0,10);
 if(qq_qimei_request(&request,QQ_PROFILE_QIMEI_PAYLOAD,strlen(QQ_PROFILE_QIMEI_PAYLOAD),timestamp,&stop,0))goto done;
 if(qq_http_request_wire(&request,&cookies,timestamp,wire,sizeof(wire),&bytes))goto done;
 if(write(1,wire,bytes)==(ssize_t)bytes)rc=0;
done:qq_secret_clear(&request,sizeof(request));qq_secret_clear(wire,sizeof(wire));return rc;
}

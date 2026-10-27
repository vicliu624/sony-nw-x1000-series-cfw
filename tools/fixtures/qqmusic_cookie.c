#include "../../runtime/apps/qqmusic/qqmusic_cookie.h"
#include <assert.h>
#include <string.h>
static struct qq_cookie_jar jar, before;
static void put(const char *host,const char *path,const char *s,uint64_t now,int expected) {
 int rc; before=jar;rc=qq_cookie_set(&jar,host,path,s,strlen(s),now);
 assert(expected?rc<0:rc==0);
 if(expected) assert(!memcmp(&jar,&before,sizeof(jar)));
}
static void header(const char *host,const char *path,uint64_t now,const char *expected) {
 char out[4096]; assert(qq_cookie_header(&jar,host,path,now,out,sizeof(out))==0);
 assert(!strcmp(out,expected));
}
int main(void) {
 const char *qr="ssl.ptlogin2.qq.com", *check="ssl.ptlogin2.graph.qq.com";
 char small[4], line[100]; unsigned i;
 qq_cookie_clear(&jar);
 put(qr,"/ptqrshow","qrsig=synthetic; Secure; HttpOnly",100,0);
 header(qr,"/ptqrlogin",100,"qrsig=synthetic");
 header("graph.qq.com","/oauth2.0/authorize",100,"");
 put(check,"/check_sig","p_skey=synthetic_key; Domain=.graph.qq.com; Path=/; Secure; Max-Age=60",100,0);
 header("graph.qq.com","/oauth2.0/authorize",159,"p_skey=synthetic_key");
 header("graph.qq.com","/oauth2.0/authorize",160,"");
 put(qr,"/a/b","pathcookie=value",100,0);
 header(qr,"/a/b",100,"qrsig=synthetic; pathcookie=value");
 header(qr,"/abc",100,"qrsig=synthetic");
 put(qr,"/","qrsig=new; Path=/",100,0);
 header(qr,"/",100,"qrsig=new");
 put(qr,"/","qrsig=; Max-Age=0; Path=/",101,0);
 header(qr,"/",101,"");
 put(qr,"/","future=x; Expires=Thu, 01 Jan 1970 00:02:00 GMT; Max-Age=20",100,0);
 header(qr,"/",119,"future=x");header(qr,"/",120,"");
 put(qr,"/","future=x; Expires=Thu, 01 Jan 1970 00:03:00 GMT",100,0);
 header(qr,"/",179,"future=x");header(qr,"/",180,"");
 put(qr,"/","future=x; Max-Age=-1",100,0);header(qr,"/",100,"");
 put(qr,"/","x=a; Domain=com",100,1);
 put(qr,"/","x=a; Domain=evil.invalid",100,1);
 put(qr,"/","x=a; Domain=graph.qq.com",100,1);
 put(qr,"/","x=a; Domain=qq.com.evil.invalid",100,1);
 put(qr,"/","x=a\r\nInjected: x",100,1);
 put(qr,"/","x=a; Domain=qq.com; Domain=qq.com",100,1);
 put(qr,"/","x=a; Path=/; Path=/",100,1);
 put(qr,"/","x=a; Max-Age=18446744073709551616",100,1);
 put(qr,"/","x=a; Max-Age=2",UINT64_MAX,1);
 put(qr,"/","x=a; Expires=Thu, 31 Feb 2028 00:00:00 GMT",100,0);
 header(qr,"/",100,"x=a"); /* Invalid expiry is ignored, not a response failure. */
 put(qr,"/","x=a; Max-Age=0",100,0);
 put(qr,"/","legacy=x; Expires=Thu, 01-Jan-1970 00:03:00 GMT",100,0);
 header(qr,"/",179,"legacy=x");header(qr,"/",180,"");
 put(qr,"/","legacy=x; Expires=Thursday, 01-Jan-70 00:03:00 GMT",100,0);
 header(qr,"/",179,"legacy=x");header(qr,"/",180,"");
 put(qr,"/","legacy=x; Expires=Thu Jan  1 00:03:00 1970",100,0);
 header(qr,"/",179,"legacy=x");header(qr,"/",180,"");
 put(qr,"/","legacy=x; Expires=Thu, 01-Jan-1960 00:03:00 GMT",100,0);header(qr,"/",100,"");
 put(qr,"/","x=a; Secure=yes",100,1);
 put(qr,"/","x=a; Path=/x?query",100,1);
 put("evil.invalid","/","x=a",100,1);
 qq_cookie_clear(&jar);
 put(qr,"/","x=a; Domain=qq.com",0,0);
 put(qr,"/","x=b",0,0);
 memset(small,'a',sizeof(small));
 assert(qq_cookie_header(&jar,qr,"/",0,small,sizeof(small))<0&&small[0]==0);
 /* Broad domain matches only explicitly supported service targets. */
 header("y.qq.com","/",0,"x=a");
 assert(qq_cookie_header(&jar,"evil.qq.com","/",0,small,sizeof(small))<0);
 qq_cookie_clear(&jar);
 for(i=0;i<QQ_COOKIE_LIMIT;i++) {
  memcpy(line,"cookie00=x",11);line[6]=(char)('0'+i/10);line[7]=(char)('0'+i%10);put(qr,"/",line,0,0);
 }
 put(qr,"/","overflow=x",0,1);
 put(qr,"/","cookie00=x; Max-Age=1",0,0);
 put(qr,"/","replacement=x",1,0);
 qq_cookie_clear(&jar);
 for(i=0;i<sizeof(jar);i++) assert(((unsigned char *)&jar)[i]==0);
 return 0;
}

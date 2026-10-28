#include "qqmusic_identity.h"
#include "qqmusic_cgi.h"
#include "../../../sdk/include/x1000/services/tls_platform.h"
#include <stdlib.h>
#include <string.h>
static const char *keys[]={"ct","cv","tmeLoginType","QIMEI36","OpenUDID","udid","aid","phonetype","os_ver","chid","tmeAppID"};
void qq_identity_clear(struct qq_identity *p){if(p)qq_secret_clear(p,sizeof(*p));}
int qq_identity_init(struct qq_identity *p,const char *comm,const char *guid,volatile int *stop,int (*seed)(unsigned char[48],volatile int *)) {
 struct qq_json *json=0;size_t n,i,j;unsigned count=0;char value[129],key[129];int node,rc=-1;
 if(!p)return -1;
 memset(p,0,sizeof(*p));if(!comm||!guid||!stop||*stop)return -1;
 for(n=0;n<sizeof(p->comm)&&comm[n];n++){}if(!n||n==sizeof(p->comm))return -1;
 for(i=0;i<sizeof(p->guid)&&guid[i];i++)if(!((guid[i]>='0'&&guid[i]<='9')||(guid[i]>='a'&&guid[i]<='z')||(guid[i]>='A'&&guid[i]<='Z')||guid[i]=='_'||guid[i]=='-'))return -1;
 if(!i||i==sizeof(p->guid))return -1;
 json=malloc(sizeof(*json));if(!json)return -1;
 if(qq_json_parse(json,comm,n)||json->nodes[0].type!=QQ_JSON_OBJECT)goto done;
 for(j=1;j<json->nodes[0].next;j=json->nodes[j+1].next){
  if(qq_json_string(json,(unsigned)j,key,sizeof(key)))goto done;
  for(i=0;i<sizeof(keys)/sizeof(keys[0]);i++)if(!strcmp(key,keys[i]))break;
  if(i==sizeof(keys)/sizeof(keys[0]))goto done;
  count++;
 }
 if(count!=sizeof(keys)/sizeof(keys[0]))goto done;
 for(i=0;i<sizeof(keys)/sizeof(keys[0]);i++){
  node=qq_json_get(json,0,keys[i]);if(node<0||qq_json_string(json,(unsigned)node,value,sizeof(value))||(!value[0]&&i!=3))goto done;
  if((i==0&&strcmp(value,"11"))||(i==2&&strcmp(value,"2")))goto done;
  if(i==3)p->qimei_bound=value[0]!=0;
 }
 memcpy(p->comm,comm,n+1);strcpy(p->guid,guid);p->stop=stop;p->seed=seed?seed:hb_tls_seed;p->ready=1;rc=0;
done:qq_secret_clear(json,sizeof(*json));free(json);qq_secret_clear(value,sizeof(value));return rc;
}
static void hex(char *out,const unsigned char *in,size_t n){static const char digits[]="0123456789abcdef";size_t i;for(i=0;i<n;i++){out[i*2]=digits[in[i]>>4];out[i*2+1]=digits[in[i]&15];}out[n*2]=0;}
int qq_identity_bind_qimei(struct qq_identity *p,const char *q36){
 struct qq_json *json;char comm[1025];size_t i,n,start,end;int node,rc=-1;
 if(!p||!p->ready||p->qimei_bound||p->session_pending||p->session_bound||!q36||!p->stop||*p->stop)return -1;
 for(i=0;i<=36&&q36[i];i++)if(!((q36[i]>='0'&&q36[i]<='9')||(q36[i]>='a'&&q36[i]<='z')||(q36[i]>='A'&&q36[i]<='Z')))return -1;
 if(i!=0&&i!=36)return -1;
 json=malloc(sizeof(*json));if(!json)return -1;memset(comm,0,sizeof(comm));n=strlen(p->comm);
 if(qq_json_parse(json,p->comm,n))goto done;
 node=qq_json_get(json,0,"QIMEI36");if(node<0||json->nodes[node].type!=QQ_JSON_STRING)goto done;
 start=json->nodes[node].start;end=json->nodes[node].end;
 if(start!=end||n+i>=sizeof(comm))goto done;
 memcpy(comm,p->comm,start);memcpy(comm+start,q36,i);memcpy(comm+start+i,p->comm+end,n-end+1);
 if(qq_json_parse(json,comm,n+i))goto done;
 memcpy(p->comm,comm,sizeof(comm));p->qimei_bound=1;rc=0;
done:
 qq_secret_clear(json,sizeof(*json));free(json);qq_secret_clear(comm,sizeof(comm));return rc;
}
int qq_identity_session_request(struct qq_identity *p,struct qq_request *out){
 struct qq_json *json;int rc;
 if(out)qq_secret_clear(out,sizeof(*out));
 if(!p||!out||!p->ready||!p->qimei_bound||p->session_pending||p->session_bound||!p->stop||*p->stop)return -1;
 json=malloc(sizeof(*json));if(!json)return -1;
 rc=qq_build_session_cgi(out,json,p->comm,strlen(p->comm));
 qq_secret_clear(json,sizeof(*json));free(json);
 if(!rc)p->session_pending=1;
 return rc;
}
static int quoted(char *out,size_t cap,size_t *used,const char *s){
 size_t i;
 for(i=0;s[i];i++){
  unsigned char c=(unsigned char)s[i];
  if(c<33||c>126)return -1;
  if(c=='"'||c=='\\'){
   if(*used+1>=cap)return -1;
   out[(*used)++]='\\';
  }
  if(*used+1>=cap)return -1;
  out[(*used)++]=(char)c;
 }
 out[*used]=0;return 0;
}
int qq_identity_session_accept(struct qq_identity *p,const struct qq_response *response){
 struct qq_json *json=0;struct qq_anonymous_session session;char comm[1025];size_t n,used;int rc=-1;
 memset(&session,0,sizeof(session));memset(comm,0,sizeof(comm));
 if(!p||!p->ready||!p->session_pending||p->session_bound)return -1;
 p->session_pending=0;
 if(!p->stop||*p->stop||!response||response->phase!=QQ_RX_DONE||response->head.status!=200||!response->body)goto done;
 json=malloc(sizeof(*json));if(!json)goto done;
 if(qq_parse_session_cgi(json,(const char *)response->body,response->body_bytes,&session))goto done;
 n=strlen(p->comm);while(n&&(p->comm[n-1]==' '||p->comm[n-1]=='\t'||p->comm[n-1]=='\r'||p->comm[n-1]=='\n'))n--;
 if(!n||p->comm[n-1]!='}')goto done;
 memcpy(comm,p->comm,n-1);used=n-1;
 if(used+9>=sizeof(comm))goto done;
 memcpy(comm+used,",\"uid\":\"",8);used+=8;
 if(quoted(comm,sizeof(comm),&used,session.uid)||used+10>=sizeof(comm))goto done;
 memcpy(comm+used,"\",\"sid\":\"",9);used+=9;
 if(quoted(comm,sizeof(comm),&used,session.sid)||used+3>=sizeof(comm))goto done;
 memcpy(comm+used,"\"}",3);
 /* Parse the final serialized object before committing either identifier. */
 if(qq_json_parse(json,comm,strlen(comm)))goto done;
 memcpy(p->comm,comm,sizeof(comm));p->session_bound=1;rc=0;
done:
 if(json){qq_secret_clear(json,sizeof(*json));free(json);}
 qq_secret_clear(&session,sizeof(session));qq_secret_clear(comm,sizeof(comm));return rc;
}
int qq_identity_prepare(void *context,struct qq_runtime_material *out){
 struct qq_identity *p=context;unsigned char bytes[48];size_t i;unsigned nonzero=0,nonff=0;int rc=-1;
 if(!out)return -1;
 qq_secret_clear(out,sizeof(*out));memset(bytes,0,sizeof(bytes));
 if(!p||!p->ready||!p->qimei_bound||p->session_pending||!p->stop||*p->stop||!p->seed||p->seed(bytes,p->stop)||*p->stop)goto done;
 for(i=0;i<sizeof(bytes);i++){nonzero|=bytes[i];nonff|=(unsigned)(bytes[i]^255);}
 if(!nonzero||!nonff||(p->have_previous&&!memcmp(bytes,p->previous,sizeof(bytes))))goto done;
 memcpy(p->previous,bytes,sizeof(bytes));p->have_previous=1;
 strcpy(out->comm,p->comm);strcpy(out->guid,p->guid);hex(out->state,bytes,32);hex(out->ui,bytes+32,16);rc=0;
done:qq_secret_clear(bytes,sizeof(bytes));return rc;
}

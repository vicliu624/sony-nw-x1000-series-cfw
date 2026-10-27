#include "epub.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void append(char*out,unsigned cap,const char*s,unsigned n){unsigned used=(unsigned)strlen(out);if(used>=cap-1)return;char decoded[1024];if(n>=sizeof decoded)n=sizeof decoded-1;ex_decode(s,n,decoded,sizeof decoded);n=(unsigned)strlen(decoded);if(n>cap-used-1)n=cap-used-1;memcpy(out+used,decoded,n);out[used+n]=0;}
static int item_id(struct ep_book*b,const char*id){for(unsigned i=0;i<b->item_count;i++)if(!strcmp(b->items[i].id,id))return (int)i;return -1;}
static int spine_path(struct ep_book*b,const char*path){for(unsigned i=0;i<b->spine_count;i++)if(!strcmp(b->items[b->spine[i]].path,path))return (int)i;return -1;}
static void trim_title(char*s){unsigned n=(unsigned)strlen(s);while(n&&(s[n-1]==' '||s[n-1]=='\n'||s[n-1]=='\r'||s[n-1]=='\t'))s[--n]=0;unsigned a=0;while(s[a]==' '||s[a]=='\n'||s[a]=='\r'||s[a]=='\t')a++;if(a)memmove(s,s+a,n-a+1);}
static int nav_read(struct ep_book*b,const char*path,int ncx){unsigned n;unsigned char*data=ez_read(&b->zip,path,1024*1024,&n);if(!data)return 0;struct ex_parser p={(const char*)data,n,0,0};struct ex_tag t;int active=ncx,nav_depth=0,depth=0,label=0,current=-1,stack[64];unsigned sp=0;
 while(ex_next(&p,&t)){
  if(t.kind==EX_START){if(!ncx&&ex_name(t.name,"nav")){char type[128];ex_attribute(&t,"type",type,sizeof type);if(strstr(type,"toc")){active=1;nav_depth=depth;}}if(ncx&&ex_name(t.name,"navPoint")){if(sp>=64){p.error=1;break;}stack[sp++]=current;if(b->toc_count<EP_TOC){current=(int)b->toc_count++;memset(b->toc+current,0,sizeof b->toc[current]);b->toc[current].depth=sp-1;}else current=-1;}
   if(ncx&&ex_name(t.name,"navLabel"))label=1;
   if(ncx&&ex_name(t.name,"content")&&current>=0){char src[512];if(ex_attribute(&t,"src",src,sizeof src)&&!ez_resolve(path,src,b->toc[current].path,b->toc[current].fragment))current=-1;}
   if(!ncx&&active&&ex_name(t.name,"ol"))sp++;
   if(!ncx&&active&&ex_name(t.name,"a")){char href[512];if(ex_attribute(&t,"href",href,sizeof href)&&b->toc_count<EP_TOC){current=(int)b->toc_count++;struct ep_nav*r=b->toc+current;memset(r,0,sizeof(*r));r->depth=sp?sp-1:0;if(ez_resolve(path,href,r->path,r->fragment))label=1;else current=-1;}}
   if(!t.self)depth++;
  }else if(t.kind==EX_TEXT){if(label&&current>=0)append(b->toc[current].title,sizeof b->toc[current].title,t.text,t.length);}
  else if(t.kind==EX_END){if(depth)depth--;if(ncx&&ex_name(t.name,"navLabel"))label=0;if(ncx&&ex_name(t.name,"navPoint")){if(sp)current=stack[--sp];else current=-1;}if(!ncx&&ex_name(t.name,"a")){label=0;current=-1;}if(!ncx&&active&&ex_name(t.name,"ol")&&sp)sp--;if(!ncx&&active&&ex_name(t.name,"nav")&&depth==nav_depth)active=0;}
 }
 unsigned count=0;for(unsigned i=0;i<b->toc_count;i++){trim_title(b->toc[i].title);if(b->toc[i].title[0]&&spine_path(b,b->toc[i].path)>=0)b->toc[count++]=b->toc[i];}b->toc_count=count;free(data);return !p.error;
}
struct ep_book*epub_open(FILE*f,uint32_t bytes){struct ep_book*b=calloc(1,sizeof(*b));if(!b)return 0;b->cached_id=-1;if(!ez_open(&b->zip,f,bytes))goto fail;unsigned n;unsigned char*data=ez_read(&b->zip,"mimetype",64,&n);if(!data||n<20||memcmp(data,"application/epub+zip",20)){free(data);goto fail;}free(data);
 if(ez_find(&b->zip,"META-INF/encryption.xml")>=0){snprintf(b->error,sizeof b->error,"Encrypted/obfuscated resources are not supported");goto fail;}
 data=ez_read(&b->zip,"META-INF/container.xml",65536,&n);if(!data)goto fail;struct ex_parser p={(const char*)data,n,0,0};struct ex_tag t;char opf[256]={0},fragment[128];while(ex_next(&p,&t))if(t.kind==EX_START&&ex_name(t.name,"rootfile")){char path[512];if(ex_attribute(&t,"full-path",path,sizeof path)&&ez_resolve("",path,opf,fragment))break;}free(data);if(!opf[0]||p.error)goto fail;
 data=ez_read(&b->zip,opf,2*1024*1024,&n);if(!data)goto fail;p=(struct ex_parser){(const char*)data,n,0,0};char spine_ids[EP_SPINE][96];unsigned spine_count=0;int title=0,fixed=0;
 while(ex_next(&p,&t)){
  if(t.kind==EX_START){if(ex_name(t.name,"package")){char version[32];if(ex_attribute(&t,"version",version,sizeof version)&&version[0]!='2'&&version[0]!='3'){p.error=1;break;}}
   else if(ex_name(t.name,"title"))title=1;
   else if(ex_name(t.name,"meta")){char property[128];if(ex_attribute(&t,"property",property,sizeof property)&&!strcmp(property,"rendition:layout"))fixed=1;}
   else if(ex_name(t.name,"item")){if(b->item_count==EP_ITEMS){p.error=1;break;}struct ep_item*r=b->items+b->item_count;char href[512],media[128],properties[256];if(!ex_attribute(&t,"id",r->id,sizeof r->id)||!ex_attribute(&t,"href",href,sizeof href)||!ex_attribute(&t,"media-type",media,sizeof media)||!ez_resolve(opf,href,r->path,fragment)){p.error=1;break;}r->kind=!strcmp(media,"application/xhtml+xml")?1:!strcmp(media,"text/css")?2:!strcmp(media,"application/x-dtbncx+xml")?3:0;r->nav=ex_attribute(&t,"properties",properties,sizeof properties)&&strstr(properties,"nav");b->item_count++;}
   else if(ex_name(t.name,"itemref")){char linear[32];if(ex_attribute(&t,"linear",linear,sizeof linear)&&!strcmp(linear,"no"))continue;if(spine_count==EP_SPINE||!ex_attribute(&t,"idref",spine_ids[spine_count],96)){p.error=1;break;}spine_count++;}
  }else if(t.kind==EX_TEXT){if(title)append(b->title,sizeof b->title,t.text,t.length);if(fixed){char layout[128];ex_decode(t.text,t.length,layout,sizeof layout);if(strstr(layout,"pre-paginated")){p.error=1;break;}}}
  else if(t.kind==EX_END){if(ex_name(t.name,"title"))title=0;if(ex_name(t.name,"meta"))fixed=0;}
 }
 free(data);if(p.error||!spine_count)goto fail;trim_title(b->title);
 for(unsigned i=0;i<spine_count;i++){int at=item_id(b,spine_ids[i]);if(at<0||b->items[at].kind!=1)goto fail;b->spine[b->spine_count++]=(unsigned)at;}
 for(unsigned i=0;i<b->item_count&&!b->toc_count;i++)if(b->items[i].nav)nav_read(b,b->items[i].path,0);
 for(unsigned i=0;i<b->item_count&&!b->toc_count;i++)if(b->items[i].kind==3)nav_read(b,b->items[i].path,1);
 if(!b->toc_count)for(unsigned i=0;i<b->spine_count;i++){struct ep_nav*r=b->toc+b->toc_count++;strcpy(r->path,b->items[b->spine[i]].path);snprintf(r->title,sizeof r->title,"Chapter %u",i+1);}
 if(!ep_load(b,0))goto fail;return b;
 fail:epub_close(b);return 0;
}
static void doc_free(struct ep_doc*d){if(d){free(d->tokens);free(d);}}
void epub_close(struct ep_book*b){if(!b)return;ep_drop_image(b);doc_free(b->doc);ez_close(&b->zip);free(b);}
int ep_load(struct ep_book*b,unsigned chapter){if(chapter>=b->spine_count||b->stop&&*b->stop)return 0;unsigned n;unsigned char*data=ez_read(&b->zip,b->items[b->spine[chapter]].path,2*1024*1024,&n);if(!data)return 0;struct ep_doc*d=calloc(1,sizeof(*d));if(!d){free(data);return 0;}unsigned old=b->chapter;b->chapter=chapter;unsigned previous_rules=b->rule_count;b->rule_count=0;int ok=ep_parse_doc(b,d,(const char*)data,n);b->rule_count=previous_rules;free(data);if(!ok){b->chapter=old;doc_free(d);return 0;}ep_drop_image(b);doc_free(b->doc);b->doc=d;return 1;}
int ep_goto(struct ep_book*b,const char*path,const char*fragment,uint32_t*out){int chapter=spine_path(b,path);if(chapter<0)return 0;if((unsigned)chapter!=b->chapter&&!ep_load(b,(unsigned)chapter))return 0;*out=0;if(fragment&&*fragment){for(unsigned i=0;i<b->doc->anchor_count;i++)if(!strcmp(b->doc->anchors[i].id,fragment)){*out=b->doc->anchors[i].token;return 1;}return 0;}return 1;}

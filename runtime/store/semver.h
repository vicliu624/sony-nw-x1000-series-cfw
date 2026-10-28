/* Bounded SemVer 2.0 precedence. Numeric identifiers never overflow integers. */
#ifndef HB_SEMVER_H
#define HB_SEMVER_H
#include <string.h>
struct hb_semver {const char *part[3],*pre;unsigned length[3],pre_length;};
static inline int hb_sv_digit(char c){return c>='0'&&c<='9';}
static inline int hb_sv_parse(const char *s,struct hb_semver *v){
 if(!s||!v)return -1;
 unsigned size=(unsigned)strlen(s),i=0;if(!size||size>32)return -1;
 for(unsigned k=0;k<3;k++){
  unsigned start=i;while(i<size&&hb_sv_digit(s[i]))i++;
  if(i==start||(i-start>1&&s[start]=='0'))return -1;
  v->part[k]=s+start;v->length[k]=i-start;
  if(k<2&&(i==size||s[i++]!='.'))return -1;
 }
 v->pre=0;v->pre_length=0;
 if(i<size&&s[i]=='-'){
  unsigned begin=++i;v->pre=s+i;
  for(;;){unsigned start=i;int numeric=1;
   while(i<size&&s[i]!='.'&&s[i]!='+'){
    char c=s[i++];if(!hb_sv_digit(c)){numeric=0;if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||c=='-'))return -1;}
   }
   if(i==start||(numeric&&i-start>1&&s[start]=='0'))return -1;
   if(i==size||s[i]=='+')break;
   i++;
  }v->pre_length=i-begin;
 }
 if(i<size&&s[i]=='+'){
  i++;for(;;){unsigned start=i;
   while(i<size&&s[i]!='.'){char c=s[i++];if(!hb_sv_digit(c)&&!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||c=='-'))return -1;}
   if(i==start)return -1;
   if(i==size)break;
   i++;
  }
 }return i==size?0:-1;
}
static inline int hb_sv_piece(const char *a,unsigned na,const char *b,unsigned nb,int numeric){
 if(numeric&&na!=nb)return na<nb?-1:1;
 unsigned n=na<nb?na:nb;int r=memcmp(a,b,n);
 return r?(r<0?-1:1):na==nb?0:na<nb?-1:1;
}
/* Output -1/0/+1; malformed/legacy version strings return -1 without guessing. */
static inline int hb_semver_compare(const char *a,const char *b,int *out){
 struct hb_semver x,y;if(!out||hb_sv_parse(a,&x)||hb_sv_parse(b,&y))return -1;
 for(unsigned i=0;i<3;i++){int r=hb_sv_piece(x.part[i],x.length[i],y.part[i],y.length[i],1);if(r){*out=r;return 0;}}
 if(!x.pre||!y.pre){*out=x.pre?(y.pre?0:-1):y.pre?1:0;return 0;}
 unsigned i=0,j=0;
 while(i<x.pre_length&&j<y.pre_length){
  unsigned ia=i,jb=j;int nx=1,ny=1;
  while(i<x.pre_length&&x.pre[i]!='.'){if(!hb_sv_digit(x.pre[i]))nx=0;i++;}
  while(j<y.pre_length&&y.pre[j]!='.'){if(!hb_sv_digit(y.pre[j]))ny=0;j++;}
  int r=nx!=ny?(nx?-1:1):hb_sv_piece(x.pre+ia,i-ia,y.pre+jb,j-jb,nx);
  if(r){*out=r;return 0;}if(i<x.pre_length)i++;if(j<y.pre_length)j++;
 }
 *out=i==x.pre_length?(j==y.pre_length?0:-1):1;return 0;
}
#endif

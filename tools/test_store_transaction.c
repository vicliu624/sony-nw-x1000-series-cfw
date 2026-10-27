#include "../runtime/store/transaction.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

struct model {
 int slots[3],operations,fail_at,second_fail_at,held,ended,no_space,bad_package,cancel_at;
 unsigned long long required;
 unsigned unrelated;
};
static int step(struct model *m) {
 assert(m->held);m->operations++;
 return m->operations==m->fail_at||m->operations==m->second_fail_at;
}
static int begin(void *p,const char *id) {
 struct model *m=p;assert(!m->held);assert(!strcmp(id,"demo"));m->held=1;return 0;
}
static void end(void *p) { struct model *m=p;assert(m->held);m->held=0;m->ended++; }
static int inspect(void *p,enum hb_slot slot) {
 struct model *m=p;assert(m->held);
 return !m->slots[slot]?HB_ABSENT:m->slots[slot]==3?HB_INVALID:HB_VALID;
}
static int space(void *p,unsigned long long n) {
 struct model *m=p;assert(m->held);m->required=n;return m->no_space;
}
static int prepare(void *p) {
 struct model *m=p;assert(!m->slots[HB_STAGE]);
 if(step(m)){m->slots[HB_STAGE]=3;return -1;}
 m->slots[HB_STAGE]=2;return 0;
}
static int verify(void *p) {
 struct model *m=p;return step(m)||m->bad_package?-1:0;
}
static int sync_files(void *p) { return step(p)?-1:0; }
static int move(void *p,enum hb_slot from,enum hb_slot to) {
 struct model *m=p;assert(m->slots[from]&&!m->slots[to]);
 if(step(m))return -1;
 m->slots[to]=m->slots[from];m->slots[from]=0;return 0;
}
static int remove_slot(void *p,enum hb_slot slot) {
 struct model *m=p;assert(m->slots[slot]);
 if(step(m))return -1;
 m->slots[slot]=0;return 0;
}
static int cancelled(void *p) {
 struct model *m=p;return m->cancel_at>=0&&m->operations>=m->cancel_at;
}
static struct hb_install_io io(struct model *m) {
 struct hb_install_io result={m,begin,end,inspect,space,prepare,verify,sync_files,move,remove_slot,cancelled};
 return result;
}
static struct model model(int old) {
 struct model m;memset(&m,0,sizeof m);m.slots[HB_LIVE]=old;m.cancel_at=-1;m.unrelated=0xcafebabe;return m;
}
static void invariant(struct model *m) {
 assert(!m->held&&m->ended);assert(m->unrelated==0xcafebabe);
}
int main(void) {
 unsigned cases=0;
 for(int old=0;old<=1;old++) {
  struct model baseline=model(old);struct hb_install_io b=io(&baseline);
  assert(hb_install_apply(&b,"demo",1024,4096)==HB_INSTALLED);
  assert(baseline.required==5120&&baseline.slots[HB_LIVE]==2);
  int last=baseline.operations;invariant(&baseline);cases++;
  for(int failure=1;failure<=last;failure++) {
   struct model m=model(old);m.fail_at=failure;struct hb_install_io ops=io(&m);
   int result=hb_install_apply(&ops,"demo",1024,4096);assert(result!=HB_INSTALLED);
   invariant(&m);
   /* An interrupted update must retain a complete old or new app somewhere. */
   if(old)assert(m.slots[HB_LIVE]==1||m.slots[HB_LIVE]==2||m.slots[HB_BACKUP]==1);
   m.fail_at=0;assert(hb_install_recover(&ops,"demo")==0);invariant(&m);
   assert(!m.slots[HB_STAGE]&&!m.slots[HB_BACKUP]);
   assert(m.slots[HB_LIVE]==0||m.slots[HB_LIVE]==1||m.slots[HB_LIVE]==2);
   if(old)assert(m.slots[HB_LIVE]);
   cases++;
  }
 }
 for(int cancel=0;cancel<=3;cancel+=3) {
  struct model m=model(1);m.cancel_at=cancel;struct hb_install_io ops=io(&m);
  assert(hb_install_apply(&ops,"demo",1,0)==HB_INSTALL_CANCELLED);
  assert(m.slots[HB_LIVE]==1&&!m.slots[HB_STAGE]&&!m.slots[HB_BACKUP]);invariant(&m);cases++;
 }
 {
  struct model m=model(1);m.fail_at=6;m.second_fail_at=7;struct hb_install_io ops=io(&m);
  assert(hb_install_apply(&ops,"demo",1,0)==HB_RECOVERY_REQUIRED);
  assert(!m.slots[HB_LIVE]&&m.slots[HB_BACKUP]==1);
  m.fail_at=m.second_fail_at=0;
  assert(hb_install_recover(&ops,"demo")==0&&m.slots[HB_LIVE]==1);
  invariant(&m);cases++;
 }
 {
  struct model m=model(1);m.no_space=1;struct hb_install_io ops=io(&m);
  assert(hb_install_apply(&ops,"demo",1,0)==HB_INSTALL_NO_SPACE);
  assert(m.operations==0&&m.slots[HB_LIVE]==1);invariant(&m);cases++;
 }
 {
  struct model m=model(1);m.bad_package=1;struct hb_install_io ops=io(&m);
  assert(hb_install_apply(&ops,"demo",1,0)==HB_INSTALL_FAILED);
  assert(m.slots[HB_LIVE]==1&&!m.slots[HB_STAGE]);invariant(&m);cases++;
 }
 {
  struct model m=model(3);m.slots[HB_BACKUP]=1;struct hb_install_io ops=io(&m);
  assert(hb_install_recover(&ops,"demo")==HB_RECOVERY_REQUIRED);
  assert(m.operations==0&&m.slots[HB_LIVE]==3&&m.slots[HB_BACKUP]==1);invariant(&m);cases++;
 }
 {
  struct model m=model(1);struct hb_install_io ops=io(&m);
  assert(hb_install_apply(&ops,"../demo",1,0)==HB_INSTALL_INVALID);
  assert(hb_install_apply(&ops,"demo",~0ULL,1)==HB_INSTALL_INVALID);
  assert(!m.held&&!m.ended&&!m.operations);cases+=2;
 }
 printf("Store transaction core: %u cases passed\n",cases);return 0;
}

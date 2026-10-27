#include "../runtime/apps/emulators/gbc_schedule.h"
#include <assert.h>
#include <stdio.h>
/* Model a 2ms CPU/APU frame and a costly 24ms framebuffer presentation.
   Consume one frame of PCM every 16.743ms, after a fixed 34ms startup allowance.
   Same costs for both policies; no emulation speed or audio sample changes. */
static unsigned run(int optimized) {
  struct gb_schedule s = {0};
  unsigned now=0, frames=0, draws=0, gaps=0;
  int stock_next=0;
  gb_schedule_start(&s,now);
  for (;now<2000;) {
    int due=optimized ? (int32_t)(now-s.next)>=0 : (int)now>=stock_next;
    if (due) {
      now+=2; frames++;
      int draw=1;
      if(optimized) {gb_schedule_advance(&s);draw=gb_schedule_present(&s,now);}
      else stock_next=(int)(frames*16743u/1000u);
      if(draw) {draws++;now+=24;}
    } else now++;
    unsigned consumed=now>34 ? (now-34)*1000u/16743u : 0;
    if(consumed>frames) gaps++;
  }
  printf("%s: frames=%u draws=%u starvation_observations=%u\n",optimized?"new":"baseline",frames,draws,gaps);
  if(optimized) {assert(frames>=117);assert(draws<65);assert(!gaps);}
  return gaps;
}
int main(void) {
 assert(run(0)>0);assert(!run(1));
 struct gb_schedule s={0};gb_schedule_start(&s,0xfffffff0u);
 for(unsigned i=0;i<60000;i++)gb_schedule_advance(&s);
 assert(s.next==(uint32_t)(0xfffffff0u-34u+1004580u));
 assert(s.fraction==0);
 gb_schedule_start(&s,100);assert(s.next==66 && s.fraction==0);
 assert(!gb_schedule_present(&s,100));
 assert(gb_schedule_present(&s,200)); /* bounded redraw under severe overload */
 gb_schedule_recover(&s,1000);assert(s.next==966);
 puts("PCM lead, slow-display scheduling, wraparound, pause reset and bounded redraw passed");
 return 0;
}

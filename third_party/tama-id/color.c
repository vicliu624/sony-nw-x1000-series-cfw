/* Tamagotchi iD adapter. Interpreter only, silent, native 128x128.
 * Pointer-free, explicit LE snapshot; no raw Emu struct or JIT addresses saved.
 */
#include "color.h"
#include "core/tc.h"
#define ROM_SIZE 0x400000u
#define META_SIZE 100000u
typedef struct {Emu e;uint8_t rom[ROM_SIZE],pool[OVL_SLOTS*OVL_SIZE],meta[META_SIZE],dirty[64];uint16_t gram[128][128],display[128*128];uint32_t original;} Context;
static Context *ctx;
static int status,active;
static uint32_t fraction;
static int snapshot_source=1;
#ifdef A918_COLOR_MENU
static uint8_t input_queue[64];
static unsigned input_head,input_count;
static uint64_t input_us,input_ready[3];
static void input_apply(void){
 while(input_count){unsigned event=input_queue[input_head],b=event>>1;int down=event&1;uint8_t mask=ctx->e.btn_mask;
  if(!!(mask&(1u<<b))==down){input_head=(input_head+1)%64;input_count--;continue;}
  if(input_us<input_ready[b])break;
  if(down)mask|=1u<<b;else mask&=~(1u<<b);periph_buttons(&ctx->e,mask);input_ready[b]=input_us+50000;
  input_head=(input_head+1)%64;input_count--;
 }
}
#endif
void color_buttons_clear(void){
#ifdef A918_COLOR_MENU
 input_head=input_count=0;input_us=0;for(unsigned i=0;i<3;i++)input_ready[i]=0;
#endif
 if(ctx)periph_buttons(&ctx->e,0);
}
int color_input_pending(void){
#ifdef A918_COLOR_MENU
 return input_count!=0;
#else
 return 0;
#endif
}
static uint32_t hash(const void*p,unsigned n){const uint8_t*b=p;uint32_t h=2166136261u;while(n--)h=(h^*b++)*16777619u;return h;}
#ifdef A918_EXTERNAL
static uint32_t rom_crc(const uint8_t*p,unsigned n){
 static const uint32_t table[16]={0,0x1db71064,0x3b6e20c8,0x26d930ac,0x76dc4190,0x6b6b51f4,0x4db26158,0x5005713c,0xedb88320,0xf00f9344,0xd6d6a3e8,0xcb61b38c,0x9b64c2b0,0x86d3d2d4,0xa00ae278,0xbdbdf21c};
 uint32_t c=~0u;while(n--){c^=*p++;c=(c>>4)^table[c&15];c=(c>>4)^table[c&15];}return ~c;
}
#endif
static void put(uint8_t*p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static uint32_t get(const uint8_t*p){uint32_t v=0;for(unsigned i=0;i<4;i++)v|=(uint32_t)p[i]<<(8*i);return v;}
static void dirty(unsigned off){unsigned i=off/OVL_SIZE;ctx->dirty[i/8]|=1u<<(i%8);}
static int evict(Emu*e){for(int i=0;i<e->ovl.n;i++)if(e->ovl.base[i]!=0xffffffffu){unsigned off=e->ovl.base[i];if(off>ROM_SIZE-OVL_SIZE)return 0;memcpy(ctx->rom+off,e->ovl.mem[i],OVL_SIZE);dirty(off);tc_ovl_free(e,i);return 1;}return 0;}
static int erase(Emu*e,uint32_t off){(void)e;if(off>ROM_SIZE-0x10000u)return 0;memset(ctx->rom+off,255,0x10000);for(unsigned i=0;i<8;i++)dirty(off+i*OVL_SIZE);return 1;}
/* Every scalar is encoded as LE u64, irrespective of host width/padding.
 * Reconstruct ROM/LCD/overlay pointers with tc_init before loading this state. */
static unsigned state(int load,uint8_t*b){
 Emu*e=&ctx->e;unsigned n=96;
#define F(v) do{if(load){uint64_t z=get(b+n)|((uint64_t)get(b+n+4)<<32);v=z;}else{uint64_t z=(uint64_t)(v);put(b+n,(uint32_t)z);put(b+n+4,(uint32_t)(z>>32));}n+=8;}while(0)
#define A(v) do{unsigned z=sizeof(v);if(load)memcpy(v,b+n,z);else memcpy(b+n,v,z);n+=z;}while(0)
 for(int i=0;i<16;i++)F(e->r[i]);
 F(e->sp);F(e->alr);F(e->ahr);F(e->ttbr);F(e->idir);F(e->dbbr);F(e->pc);
 F(e->f_n);F(e->f_z);F(e->f_v);F(e->f_c);F(e->f_ie);F(e->il);F(e->psr_rest);
 F(e->ext_count);F(e->ext_val[0]);F(e->ext_val[1]);F(e->halted);F(e->halt_hard);F(e->wake_at);F(e->cycles);F(e->evt);F(e->last_tick);
 A(e->a0ram);A(e->ivram);A(e->dstram);A(e->ioram);
 F(e->cmu.unlocked);F(e->cmu.sccr);F(e->cmu.pllc);F(e->cmu.opt);F(e->cmu.osc3_hz);F(e->cmu.mclk_hz);
 for(int i=0;i<6;i++){F(e->t16[i].counter);F(e->t16[i].a_fired);F(e->t16[i].accum);}
 F(e->pending_irq);F(e->pending_level);F(e->wake_req);F(e->btn_mask);F(e->rtc_cyc);F(e->rtc_irq_cyc);
 F(e->flash_state);F(e->flash_dirty);F(e->flash_op_data);F(e->flash_toggle);F(e->flash_busy);F(e->flash_autoselect);F(e->flash_lost_writes);F(e->flash_big_ops);F(e->lcd_writes);
 F(e->lcd.cmd);F(e->lcd.argc);A(e->lcd.args);F(e->lcd.xs);F(e->lcd.xe);F(e->lcd.ys);F(e->lcd.ye);F(e->lcd.cx);F(e->lcd.cy);F(e->lcd.madctl);F(e->lcd.colmod);F(e->lcd.sleep_out);F(e->lcd.disp_on);F(e->lcd.inverted);A(e->lcd.pix_buf);F(e->lcd.pix_n);
 /* RGB565 is LE on disk, including on big-endian hosts. */
 for(unsigned y=0;y<128;y++)for(unsigned x=0;x<128;x++){if(load)ctx->gram[y][x]=(uint16_t)(b[n]|(b[n+1]<<8));else{b[n]=(uint8_t)ctx->gram[y][x];b[n+1]=(uint8_t)(ctx->gram[y][x]>>8);}n+=2;}
 F(fraction);
#undef F
#undef A
 return n;
}
void color_close(void){color_buttons_clear();active=0;if(ctx){color_free(ctx,sizeof(*ctx));ctx=0;}tc_ovl_evict=0;tc_big_erase=0;}
int color_status(void){return status;}
const uint16_t*color_pixels(void){
 if(!ctx)return 0;
#ifdef A918_COLOR_PERF
 if(!ctx->e.lcd.inverted&&!(ctx->e.lcd.madctl&8))return &ctx->gram[0][0];
#endif
 for(unsigned i=0;i<128*128;i++){uint16_t p=ctx->gram[i/128][i%128];if(ctx->e.lcd.inverted)p=~p;if(ctx->e.lcd.madctl&8)p=(uint16_t)(((p&31)<<11)|(p&0x7e0)|(p>>11));ctx->display[i]=p;}
 return ctx->display;
}
int color_visible(void){return ctx&&ctx->e.lcd.sleep_out&&ctx->e.lcd.disp_on;}
void color_probe_stats(uint32_t*out){if(!ctx)return;out[0]=ctx->e.pc;out[1]=ctx->e.cycles;out[2]=ctx->e.lcd_writes;out[3]=ctx->e.stop_pc;out[4]=ctx->e.stop_code;out[5]=ctx->e.cmu.mclk_hz;}
int color_open(void){
 color_close();status=COLOR_NO_STORAGE;if(!color_storage_available())return 0;
 status=COLOR_NO_RAM;ctx=color_alloc(sizeof(*ctx));if(!ctx)return 0;memset(ctx,0,sizeof(*ctx));fraction=0;
 int n=color_read(0,ctx->rom,ROM_SIZE,0);status=n==0?COLOR_NO_ROM:COLOR_BAD_ROM;
 if(n!=ROM_SIZE)return 0;uint8_t tail;if(color_read(0,&tail,1,ROM_SIZE)!=0)return 0;
#ifdef A918_EXTERNAL
 if(rom_crc(ctx->rom,ROM_SIZE)!=0x0c2e4116u)return 0;
#endif
 /* A compatible size alone is insufficient: validate reset target in ROM/RAM. */
 uint32_t pc=get(ctx->rom);if((pc&1)||!((pc>=0xc00000&&pc<0x1000000)||(pc<0x8000)))return 0;
 ctx->original=hash(ctx->rom,ROM_SIZE);tc_profile_plus_color(&ctx->e.dev);ctx->e.dev.flash_top_boot=false;ctx->e.dev.debug_strap_high=false;ctx->e.dev.ir_gpio=false;ctx->e.dev.sleep_flag=0xefc;ctx->e.dev.osc3_hz=18432000;tc_init(&ctx->e,ctx->rom,ctx->gram,ctx->pool,OVL_SLOTS);tc_ovl_evict=evict;tc_big_erase=erase;
 unsigned expected=state(0,ctx->meta);if(expected>META_SIZE){status=COLOR_BAD_SAVE;return 0;}
 n=color_read(snapshot_source,ctx->meta,expected,0);
 if(snapshot_source!=1&&n==0){status=COLOR_BAD_SAVE;return 0;}
 if(n){
  status=COLOR_BAD_SAVE;
  if(n!=(int)expected||get(ctx->meta)!=0x31494341||get(ctx->meta+4)!=1||get(ctx->meta+8)!=ctx->original||get(ctx->meta+12)!=expected||get(ctx->meta+16)!=hash(ctx->meta+32,expected-32))return 0;
  memcpy(ctx->dirty,ctx->meta+32,64);unsigned fileoff=expected;
  for(unsigned i=0;i<512;i++)if(ctx->dirty[i/8]&(1u<<(i%8))){if(color_read(snapshot_source,ctx->rom+i*OVL_SIZE,OVL_SIZE,fileoff)!=OVL_SIZE)return 0;fileoff+=OVL_SIZE;}
  if(color_read(snapshot_source,&tail,1,fileoff)!=0||get(ctx->meta+20)!=hash(ctx->rom,ROM_SIZE))return 0;
  tc_init(&ctx->e,ctx->rom,ctx->gram,ctx->pool,OVL_SLOTS);state(1,ctx->meta);
  /* Bounds on guest-controlled parser fields before re-entering the core. */
  if(ctx->e.lcd.argc<0||ctx->e.lcd.argc>16||ctx->e.lcd.pix_n<0||ctx->e.lcd.pix_n>2||ctx->e.ext_count<0||ctx->e.ext_count>2||fraction>=1000)return 0;
  periph_buttons(&ctx->e,0);
 }
 status=COLOR_OK;active=1;return 1;
}
void color_button(unsigned b,int down){if(!active||b>2)return;
#ifdef A918_COLOR_MENU
 if(input_count==64)color_buttons_clear();
 input_queue[(input_head+input_count)%64]=(uint8_t)((b<<1)|!!down);input_count++;input_apply();
#else
 uint8_t m=ctx->e.btn_mask;if(down)m|=1u<<b;else m&=~(1u<<b);periph_buttons(&ctx->e,m);
#endif
}
void color_tick(uint32_t ms){
 if(!active||status==COLOR_CORE_ERROR)return;if(ms>100)ms=100;
 /* Run bounded chunks; yield after ~8ms host time. No catch-up backlog.
  * A slow device slows the guest, while input/USB/supervision remain serviced. */
 unsigned hz=ctx->e.cmu.mclk_hz?ctx->e.cmu.mclk_hz:ctx->e.dev.osc3_hz;
 uint64_t v=(uint64_t)hz*ms+fraction;unsigned cycles=(unsigned)(v/1000);fraction=(uint32_t)(v%1000);if(cycles>2000000)cycles=2000000;
 uint32_t started=color_now_ms();
#ifdef A918_COLOR_PERF
 const unsigned chunk=16384,budget=24;
#else
 const unsigned chunk=4096,budget=8;
#endif
 while(cycles){unsigned n=cycles>chunk?chunk:cycles;
#ifdef A918_COLOR_MENU
 input_apply();uint64_t before=ctx->e.cycles;unsigned clock=ctx->e.cmu.mclk_hz?ctx->e.cmu.mclk_hz:ctx->e.dev.osc3_hz;
#endif
 if(tc_run(&ctx->e,ctx->e.cycles+n)||ctx->e.flash_lost_writes){status=COLOR_CORE_ERROR;break;}
#ifdef A918_COLOR_MENU
 if(input_count||ctx->e.btn_mask||input_us<input_ready[0]||input_us<input_ready[1]||input_us<input_ready[2])input_us+=(ctx->e.cycles-before)*1000000/clock;
 input_apply();
#endif
 cycles-=n;if((uint32_t)(color_now_ms()-started)>=budget)break;}
}
int color_save(void){
 if(!active)return 1;if(status==COLOR_CORE_ERROR)return 1;
 color_buttons_clear();while(evict(&ctx->e)){}
 unsigned n=state(0,ctx->meta);memcpy(ctx->meta+32,ctx->dirty,64);put(ctx->meta,0x31494341);put(ctx->meta+4,1);put(ctx->meta+8,ctx->original);put(ctx->meta+12,n);put(ctx->meta+16,hash(ctx->meta+32,n-32));put(ctx->meta+20,hash(ctx->rom,ROM_SIZE));
 if(!color_store(ctx->meta,n,ctx->rom,ROM_SIZE)){status=COLOR_SAVE_FAILED;return 0;}status=COLOR_OK;return 1;
}
#ifdef A918_COLOR_MENU
static int open_source(int source){snapshot_source=source;int ok=color_open();snapshot_source=1;return ok;}
int color_new_game(void){
#ifdef A918_EXTERNAL
 uint8_t head[32];if(!ctx||!ctx->original||color_read(3,head,sizeof(head),0)!=sizeof(head)||get(head)!=0x31494341||get(head+4)!=1||get(head+8)!=ctx->original)return 0;
#endif
 if(!color_save()||!color_archive_snapshot())return 0;if(!open_source(3)){open_source(2);return 0;}return color_save();
}
int color_restore_backup(void){uint8_t head[32];if(color_read(2,head,sizeof(head),0)!=(int)sizeof(head))return 0;if(!color_save())return 0;if(!open_source(2)){color_open();return 0;}return color_save();}
int color_menu_selftest(void){
 if(!color_open())return 1;
 color_button(0,1);color_button(0,0);if(ctx->e.btn_mask!=1)return 4;
 for(unsigned i=0;i<400&&ctx->e.btn_mask;i++)color_tick(16);
 if(ctx->e.btn_mask)return 5;
 if(!color_save())return 1;
 uint64_t before=ctx->e.cycles;
 if(!color_new_game()||!color_visible()||ctx->e.cycles==before)return 2;
 if(!color_restore_backup()||ctx->e.cycles!=before)return 3;
 color_close();return 0;
}
#endif
/* Synthetic-ROM regression entry, never entered during normal boot. */
int color_selftest(void){
#define CHECK(x) do{if(!(x)){color_close();return __LINE__;}}while(0)
 CHECK(color_open());
 color_button(0,1);CHECK(ctx->e.btn_mask==1);color_button(0,0);
#ifdef A918_COLOR_MENU
 CHECK(ctx->e.btn_mask==1);color_buttons_clear();
#endif
 CHECK(ctx->e.btn_mask==0);
 for(unsigned i=0;i<20;i++){
  uint32_t b=ctx->e.dev.rom_base;
  mem_write8(&ctx->e,b+0xaaa,0xaa);mem_write8(&ctx->e,b+0x554,0x55);mem_write8(&ctx->e,b+0xaaa,0xa0);mem_write8(&ctx->e,b+0x100000+i*OVL_SIZE,0x40+i);
  for(int j=0;j<8;j++)(void)mem_read8(&ctx->e,b+0x100000);
 }
 CHECK(!ctx->e.flash_lost_writes);
 ctx->e.r[5]=0x11223344;ctx->e.a0ram[73]=0xab;ctx->e.lcd.sleep_out=1;ctx->e.lcd.disp_on=1;ctx->gram[0][0]=0xf800;
 CHECK(color_pixels()[0]==0xf800);ctx->e.lcd.madctl=8;CHECK(color_pixels()[0]==0x001f);ctx->e.lcd.madctl=0;
 ctx->e.lcd.inverted=1;CHECK(color_pixels()[0]==(uint16_t)~0xf800);ctx->e.lcd.inverted=0;
 CHECK(color_save());uint32_t pc=ctx->e.pc;uint64_t cycles=ctx->e.cycles;color_close();CHECK(color_open());
 CHECK(ctx->e.r[5]==0x11223344&&ctx->e.a0ram[73]==0xab&&ctx->gram[0][0]==0xf800&&ctx->e.pc==pc&&ctx->e.cycles==cycles);
 for(unsigned i=0;i<20;i++)CHECK(mem_read8(&ctx->e,ctx->e.dev.rom_base+0x100000+i*OVL_SIZE)==0x40+i);
 CHECK(erase(&ctx->e,0x100000));CHECK(ctx->rom[0x100000]==255&&ctx->rom[0x110000]==0x48);CHECK(color_save());color_close();CHECK(color_open());CHECK(ctx->rom[0x100000]==255&&ctx->rom[0x110000]==0x48);
 color_close();return 0;
#undef CHECK
}
int color_real_rom_selftest(void){
 if(!color_open())return 1;
 for(unsigned i=0;i<1000&&status==COLOR_OK;i++)color_tick(16);
 if(status!=COLOR_OK||!color_visible()||!ctx->e.lcd_writes){color_close();return 2;}
 uint32_t before=hash(ctx->gram,sizeof(ctx->gram));if(!color_save()){color_close();return 3;}
 color_close();if(!color_open())return 4;
 int ok=hash(ctx->gram,sizeof(ctx->gram))==before;color_close();return ok?0:5;
}

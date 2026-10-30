#ifndef GLASS_MARBLE_H
#define GLASS_MARBLE_H
#include <stdint.h>
#include <stddef.h>
#define GM_COUNT 20
#define GM_PACKET (40+GM_COUNT*8)
/* Millimetres, seconds, screen axes right/down. Mosaico is the authority. */
struct gm_layout {float mw,mh,xw,xh,gap,offset;};
struct gm_ball {float x,y,vx,vy;};
struct gm_world {struct gm_layout layout;struct gm_ball ball[GM_COUNT];uint32_t session,sequence;};
struct gm_view {float x,y,w,h;int width,height;};
void gm_init(struct gm_world *,const struct gm_layout *,uint32_t);
void gm_step(struct gm_world *,float,float,float);
float gm_radius(unsigned);
int gm_layout_valid(const struct gm_layout *);
int gm_encode(const struct gm_world *,uint8_t *,size_t);
int gm_decode(struct gm_world *,const uint8_t *,size_t);
int gm_newer(uint32_t,uint32_t);
void gm_render(uint16_t *,const struct gm_view *,const struct gm_world *,float);
#endif

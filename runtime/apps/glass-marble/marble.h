#ifndef GLASS_MARBLE_H
#define GLASS_MARBLE_H
#include <stdint.h>
#include <stddef.h>
#define GM_COLUMNS 32
#define GM_PACKET (56+GM_COLUMNS*2)
/* Millimetres, seconds, screen axes right/down. Mosaico is the authority. */
struct gm_layout {float mw,mh,xw,xh,gap,offset;};
struct gm_world {struct gm_layout layout;uint32_t session,sequence;float surface[GM_COLUMNS],velocity[GM_COLUMNS],volume,slope;float fish_x,fish_y,fish_angle,fish_phase,swim_direction;};
struct gm_view {float x,y,w,h;int width,height;};
void gm_init(struct gm_world *,const struct gm_layout *,uint32_t);
/* Serialized authority only: simulation workspace is reused, not reentrant. */
void gm_step(struct gm_world *,float,float,float);
float gm_surface_y(const struct gm_world *,float);
float gm_water_volume(const struct gm_world *);
void gm_map_tilt(float,float,unsigned,int,int,float *,float *);
int gm_layout_valid(const struct gm_layout *);
int gm_encode(const struct gm_world *,uint8_t *,size_t);
int gm_decode(struct gm_world *,const uint8_t *,size_t);
int gm_newer(uint32_t,uint32_t);
void gm_render(uint16_t *,const struct gm_view *,const struct gm_world *,float);
int gm_scale2x(uint16_t *,int,int,const uint16_t *,size_t);
int gm_render_fast(uint16_t *,const struct gm_view *,const struct gm_world *,float,uint16_t *,size_t);
#endif

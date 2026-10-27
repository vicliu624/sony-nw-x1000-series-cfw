#ifndef A918_COLOR_H
#define A918_COLOR_H
#include <stdint.h>
enum {COLOR_OK,COLOR_NO_ROM,COLOR_BAD_ROM,COLOR_NO_RAM,COLOR_BAD_SAVE,COLOR_SAVE_FAILED,COLOR_CORE_ERROR,COLOR_NO_STORAGE};
int color_open(void);
void color_tick(uint32_t ms);
void color_button(unsigned button,int down);
void color_buttons_clear(void);
int color_input_pending(void);
int color_save(void);
void color_close(void);
int color_status(void);
const uint16_t *color_pixels(void);
int color_visible(void);
int color_new_game(void);
int color_restore_backup(void);
int color_archive_snapshot(void);
/* Platform: original ROM is read-only. Snapshot is atomic and ROM-bound. */
void *color_alloc(unsigned size);
void color_free(void *p,unsigned size);
int color_read(int snapshot,void *p,unsigned size,unsigned offset);
int color_store(const void *header,unsigned n,const void *rom,unsigned size);
int color_storage_available(void);
uint32_t color_now_ms(void);
#endif

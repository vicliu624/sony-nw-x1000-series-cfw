#ifndef HB_LANGUAGE_STORAGE_H
#define HB_LANGUAGE_STORAGE_H
/* Save only on verified visible VFAT, never the Sony settings database/NVP. */
int hb_language_saved_choice(void);
int hb_language_saved_id(char out[33]);
int hb_language_save_id(const char*);
/* Caller owns the returned pinned user-language directory fd. */
int hb_language_packages_fd(unsigned long long*);
/* choice1=en,7=jp,-1=follow original; 0=durable success,1=published but
 * directory sync warning,-1=no change,-2=storage identity not verified. */
int hb_language_save(int);
#endif

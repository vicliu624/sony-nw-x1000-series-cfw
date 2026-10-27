#ifndef HB_LANGUAGE_PREFERENCE_H
#define HB_LANGUAGE_PREFERENCE_H
#define HB_LANGUAGE_FILE "/contents/HOMEBREW/data/language/ui-language"
/* Sony configuration values, independently mapped to actual STX paths. */
#define HB_LANGUAGE_ENGLISH 1
#define HB_LANGUAGE_JAPANESE 7
int hb_language_parse(const char *,unsigned,int);
#endif

#ifndef HB_LANGUAGE_PACKAGE_H
#define HB_LANGUAGE_PACKAGE_H
#define HB_LP_ROOT "/contents/HOMEBREW/languages/"
#define HB_LP_ACTIVE "/contents/HOMEBREW/data/language/ui-language"
#define HB_LP_ID_MAX 32
#define HB_LP_MANIFEST_MAX 1024
#define HB_LP_STX_MAX 2097152u
#define HB_LP_RECORDS 7310u
struct hb_lp_package {char id[33],name[33],base[3];unsigned setting,stx_index,bytes,stock;unsigned char sha256[32];};
struct hb_lp_io {void*context;int(*open)(void*,const char*);int(*read)(void*,int,void*,unsigned);int(*close)(void*,int);void*(*allocate)(void*,unsigned);void(*release)(void*,void*);};
int hb_lp_id(const char*);
int hb_lp_choice(const char*,unsigned,char[33]);
int hb_lp_manifest(const char*,unsigned,struct hb_lp_package*);
int hb_lp_stx(const unsigned char*,unsigned);
int hb_lp_path(char[160],const char*,int);
int hb_lp_metadata(const struct hb_lp_io*,const char*,struct hb_lp_package*);
int hb_lp_matches(const unsigned char*,unsigned,const struct hb_lp_package*);
int hb_lp_selected_metadata(const struct hb_lp_io*,struct hb_lp_package*);
int hb_lp_read_wording(const struct hb_lp_io*,const struct hb_lp_package*,unsigned char*,unsigned);
int hb_lp_load(const struct hb_lp_io*,const char*,struct hb_lp_package*);
int hb_lp_selected(const struct hb_lp_io*,struct hb_lp_package*);
#endif

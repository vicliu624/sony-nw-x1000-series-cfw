#ifndef HB_DEVICE_INFO_DATA_H
#define HB_DEVICE_INFO_DATA_H
#define HB_INFO_MAX_PAGES 80
#define HB_INFO_ROWS 22
#define HB_INFO_COLS 38
struct hb_info_page {char title[HB_INFO_COLS];char lines[HB_INFO_ROWS][HB_INFO_COLS];unsigned count;};
struct hb_info_space {unsigned long long total,free,available;};
struct hb_device_info {struct hb_info_page pages[HB_INFO_MAX_PAGES];unsigned count;int fixture;};
typedef int (*hb_info_space_fn)(const char *,struct hb_info_space *);
int hb_info_collect(struct hb_device_info *,const char *,hb_info_space_fn);
int hb_info_stock_space(const char *,struct hb_info_space *);
void hb_info_size(char *,unsigned long long);
#endif

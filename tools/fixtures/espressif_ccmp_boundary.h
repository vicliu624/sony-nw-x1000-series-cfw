/* Host/ARM test shim for the pinned, unmodified upstream ccmp.c translation unit.
 * Replaces OS/log/AES boundaries only. AES callback records parameters; it does
 * not authenticate/decrypt. This is not an Espressif Wi-Fi hardware emulator. */
#ifndef ESPRESSIF_CCMP_BOUNDARY_H
#define ESPRESSIF_CCMP_BOUNDARY_H
#ifndef __ASSEMBLER__
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;
struct ieee80211_hdr {u16 frame_control,duration_id;u8 addr1[6],addr2[6],addr3[6];u16 seq_ctrl;} __attribute__((packed));
#define ETH_ALEN 6
#define AES_BLOCK_SIZE 16
#define BIT(n) (1u<<(n))
#define WLAN_FC_TODS 0x0100
#define WLAN_FC_FROMDS 0x0200
#define WLAN_FC_RETRY 0x0800
#define WLAN_FC_PWRMGT 0x1000
#define WLAN_FC_MOREDATA 0x2000
#define WLAN_FC_ISWEP 0x4000
#define WLAN_FC_ORDER 0x8000
#define WLAN_FC_TYPE_DATA 2
#define WLAN_FC_TYPE_MGMT 0
#define WLAN_FC_GET_TYPE(v) (((v)>>2)&3)
#define WLAN_FC_GET_STYPE(v) (((v)>>4)&15)
#define le_to_host16(v) (v)
#define host_to_le16(v) (v)
static inline unsigned esp_get_le16(const void *p){const u8 *b=p;return b[0]|(unsigned)b[1]<<8;}
static inline void esp_put_le16(void *p,unsigned v){u8 *b=p;b[0]=(u8)v;b[1]=(u8)(v>>8);}
#define WPA_GET_LE16(p) esp_get_le16(p)
#define WPA_PUT_LE16(p,v) esp_put_le16(p,v)
#define os_malloc malloc
#define os_free free
#define os_memcpy memcpy
#define os_memset memset
#define wpa_hexdump(...) ((void)0)
#define wpa_printf(...) ((void)0)
int aes_ccm_ad(const u8 *,size_t,const u8 *,size_t,const u8 *,size_t,const u8 *,size_t,const u8 *,u8 *);
int aes_ccm_ae(const u8 *,size_t,const u8 *,size_t,const u8 *,size_t,const u8 *,size_t,u8 *,u8 *);
u8 *ccmp_decrypt(const u8 *,const u8 *,const u8 *,size_t,size_t *,bool);
#endif
#endif

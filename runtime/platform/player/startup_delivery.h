#ifndef XW_PLAYER_STARTUP_DELIVERY_H
#define XW_PLAYER_STARTUP_DELIVERY_H
#include <stdint.h>
/* Private, single-start rendezvous. Trusted caller creates a fresh RAM IPC
 * directory, validates its ownership and supplies a fresh 32-hex nonce.
 * Both endpoints are connected Unix datagrams after the handshake. No network,
 * discovery, permanent listener or original-manager authority is provided. */
int xw_player_startup_listen(const char *directory);
int xw_player_startup_accept(int fd,const char *directory,const char *nonce,
 uint64_t generation,uint32_t grants);
int xw_player_startup_connect(const char *directory,const char *nonce,
 uint64_t generation,uint32_t grants,unsigned timeout_ms);
#endif

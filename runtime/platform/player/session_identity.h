/* Private value identity; addresses are compared, never dereferenced by clients. */
#ifndef XW_SESSION_IDENTITY_H
#define XW_SESSION_IDENTITY_H
#include <stdint.h>
struct xw_stock_session_key {uint32_t list,number;};
#endif

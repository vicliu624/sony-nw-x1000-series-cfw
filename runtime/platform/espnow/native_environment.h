#ifndef XNOW_NATIVE_ENVIRONMENT_H
#define XNOW_NATIVE_ENVIRONMENT_H

#include "xnow_endpoint_security.h"
#include "xnow_full_control.h"
#include "xnow_pn_file.h"
#include <stddef.h>
#include <stdint.h>

/* Private JP1.11 process adapter, not an SDK authority provider. The composing
 * entry supplies reviewed manifests and retains this profile for its lifetime.
 * Mount/file qualification does not grant Sony USB, APF or radio ownership. */
struct xnow_native_file {
    const char *path;
    unsigned bytes;
    uint8_t sha[32];
};

struct xnow_native_link {
    const char *path, *target;
};

struct xnow_native_profile {
    const struct xnow_native_file *stock_files;
    size_t stock_count;
    const struct xnow_native_link *stock_links;
    size_t link_count;
    const struct xnow_native_file *candidate_files;
    size_t candidate_count;
    const char *data_leaf;
    const struct xnow_native_file *root_radio;
    unsigned root_cold;
};

/* The endpoint retains security and PN callback addresses. Do not copy/move
 * this workspace while attached. Its composing owner closes pn.directory and
 * erases keys only after controller/endpoint retirement; partial prepare may
 * already own that descriptor. No automatic retry or counter reset occurs. */
struct xnow_native_security {
    uint8_t keys[32];
    struct xnow_pn_file pn;
    struct xnow_endpoint_security endpoint;
    int (*journal)(void *, const char *, int);
    void *journal_context;
};

#pragma GCC visibility push(hidden)
int xnow_native_root_guard(const struct xnow_native_profile *, enum xnow_session_action);
int xnow_native_candidate_guard(const struct xnow_native_profile *, enum xnow_session_action);
int xnow_native_storage_check(void);
/* leaf is NULL or one trusted directory component below the composed data leaf.
 * A successful descriptor belongs to the caller. No directory is created. */
int xnow_native_open_data(const struct xnow_native_profile *, const char *leaf);
int xnow_native_read_keys(const struct xnow_native_profile *, struct xnow_native_security *);
int xnow_native_prepare_security(const struct xnow_native_profile *, struct xnow_native_security *,
                                 struct xnow_full_control *, const uint8_t peer[6], unsigned resume);
/* Existing callbacks/old-libc bridge; neither function grants ownership. */
int xnow_native_random4(void *, uint8_t bytes[4]);
uint32_t xnow_native_milliseconds(void);
#pragma GCC visibility pop

#endif

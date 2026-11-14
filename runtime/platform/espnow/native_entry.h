#ifndef XNOW_NATIVE_ENTRY_H
#define XNOW_NATIVE_ENTRY_H

/* Entry composition shared by the finite experiment and managed RF owner.
 * Generic checks/security live in native_environment.c; no executable is
 * included here. Signal state, peer selection and logging belong to the entry. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/wait.h>
#include <poll.h>
#include <errno.h>
#include <signal.h>
#include "../../store/target_abi.h"
#include "native_environment.h"
#include "xnow_control.h"
#include "xnow_file_check.h"
#include "xnow_owner_gate.h"
#include "full_profile.h"
#include "native_inputs.h"

extern int stock_sscanf(const char *, const char *, ...) __asm__("sscanf");
#ifndef XNOW_USER_DATA_LEAF
#error The composing entry must select its user data directory
#endif
static struct xnow_native_profile native_environment = {
    stock_inputs, sizeof stock_inputs / sizeof *stock_inputs,
    stock_links, sizeof stock_links / sizeof *stock_links,
    exchange_inputs, sizeof exchange_inputs / sizeof *exchange_inputs,
    XNOW_USER_DATA_LEAF, 0, 0
};

static int journal_descriptor = -1;
static unsigned journal_bytes;
static int journal(const char *phase, int result)
{
    if (journal_descriptor >= 0) {
        char line[128];
        int bytes = snprintf(line, sizeof line, "phase=%s result=%d\n", phase, result);
        unsigned used = 0;
        if (bytes < 0 || (unsigned)bytes >= sizeof line || (unsigned)bytes > 8192 - journal_bytes)
            return -1;
        while (used < (unsigned)bytes) {
            ssize_t done = write(journal_descriptor, line + used, (unsigned)bytes - used);
            if (done < 0 && errno == EINTR) continue;
            if (done <= 0) return -1;
            used += (unsigned)done;
        }
        journal_bytes += (unsigned)bytes;
        return fsync(journal_descriptor) ? -1 : 0;
    }
    return printf("phase=%s result=%d\n", phase, result) < 0 || fflush(stdout) ? -1 : 0;
}

static int security_journal(void *context, const char *phase, int result)
{
    (void)context;
    return journal(phase, result);
}

static struct xnow_native_security native_security = { .journal = security_journal };
static uint8_t peer_address[6];
static unsigned resume_keys;
static volatile int stop_requested;

static void request_stop(int number) { (void)number; stop_requested = 1; }
static uint32_t milliseconds(void) { return xnow_native_milliseconds(); }
static int candidate_guard(void *context, enum xnow_session_action action)
{
    (void)context;
    return xnow_native_candidate_guard(&native_environment, action);
}
static int user_directory(const char *leaf) { return xnow_native_open_data(&native_environment, leaf); }
static int pn_guard(void *context) { (void)context; return xnow_native_storage_check(); }
static int read_session_keys(void) { return xnow_native_read_keys(&native_environment, &native_security); }
static int prepare_security(void *context, struct xnow_full_control *control)
{
    (void)context;
    return xnow_native_prepare_security(&native_environment, &native_security,
                                        control, peer_address, resume_keys);
}
static int rng4(void *context, uint8_t bytes[4]) { return xnow_native_random4(context, bytes); }
static int storage(void *context) { return candidate_guard(context, XNOW_SESSION_CONFIGURE); }
static int hex_digit(char value)
{
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    return -1;
}

#endif

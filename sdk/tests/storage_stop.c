/* Real SDK storage admission/publication with a synthetic ownership source.
 * Host writes only to a supplied test directory. ARM checks admission only. */
#include "../../runtime/platform/sdk/internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef XW_HOST
#include <sys/stat.h>
#else
#include "../../runtime/store/termination.h"
#include <signal.h>
#endif

static int pending_stop;
static int stopping(const xw_app *app) {
    (void)app;
    return pending_stop;
}
enum test_mode {
    LIVE,
    OWNER_STOP,
    BACKEND_STOP,
    OWNER_DENY,
    OWNER_REPLACE,
    CONTEXT_REPLACE,
    SIGNAL_STOP
};
struct owner_context {
    xw_app *app;
    const char *directory;
    enum test_mode mode;
    int observed;
};
static int denied(void *context) {
    (void)context;
    return 0;
}
static int owner(void *context) {
    struct owner_context *s = context;
    int ready = 1;
#ifdef XW_HOST
    char path[4096];
    struct stat info;
    int n = snprintf(path, sizeof path, "%s/.sdk-write.tmp", s->directory);
    ready = n > 0 && (size_t)n < sizeof path && !lstat(path, &info) && info.st_size == 4;
#endif
    if (ready && s->mode != LIVE) {
        s->observed = 1;
        if (s->mode == OWNER_STOP)
            xw_request_exit(s->app);
        if (s->mode == BACKEND_STOP)
            pending_stop = 1;
        if (s->mode == OWNER_DENY)
            return 0;
        if (s->mode == OWNER_REPLACE && xw_storage_set_owner(s->app, denied, context))
            return -1;
        if (s->mode == CONTEXT_REPLACE) {
            static struct owner_context replacement;
            replacement = (struct owner_context){s->app, s->directory, OWNER_DENY, 0};
            if (xw_storage_set_owner(s->app, owner, &replacement))
                return -1;
        }
#ifndef XW_HOST
        if (s->mode == SIGNAL_STOP && raise(SIGTERM))
            return -1;
#endif
    }
    return 1;
}

int main(int argc, char **argv) {
    if (argc < 2)
        return 64;
    const char *name = argv[1];
    xw_app *app = calloc(1, sizeof *app);
    if (!app)
        return 70;
    const xw_program program = {
        .api = XW_API_VERSION, .id = "storage-stop", .title = "Storage test"};
    app->program = &program;
    app->preview = 1;
    app->poll_stop = stopping;
    struct owner_context context = {app, argc > 2 ? argv[2] : 0, LIVE, 0};
    int expected = XW_STORAGE_STOPPED;
    if (!strcmp(name, "live")) {
        expected = XW_STORAGE_OK;
    } else if (!strcmp(name, "unbound")) {
#ifdef XW_HOST
        expected = XW_STORAGE_OK;
#else
        expected = XW_STORAGE_OWNERSHIP;
#endif
    } else if (!strcmp(name, "owner-stop")) {
        context.mode = OWNER_STOP;
    } else if (!strcmp(name, "backend-owner-stop")) {
        context.mode = BACKEND_STOP;
    } else if (!strcmp(name, "owner-deny")) {
        context.mode = OWNER_DENY;
        expected = XW_STORAGE_OWNERSHIP;
    } else if (!strcmp(name, "owner-replace")) {
        context.mode = OWNER_REPLACE;
        expected = XW_STORAGE_OWNERSHIP;
    } else if (!strcmp(name, "context-replace")) {
        context.mode = CONTEXT_REPLACE;
        expected = XW_STORAGE_OWNERSHIP;
    } else if (strcmp(name, "backend-stop") && strcmp(name, "registration-stop") &&
               strcmp(name, "signal-owner-stop") && strcmp(name, "signal-registration-stop")) {
        return 64;
    }
    int result = !strcmp(name, "unbound") ? 0 : xw_storage_set_owner(app, owner, &context);
    if (result)
        return 70;
    if (!strcmp(name, "backend-stop") || !strcmp(name, "registration-stop"))
        pending_stop = 1;

#ifndef XW_HOST
    int signals = !strcmp(name, "signal-owner-stop") || !strcmp(name, "signal-registration-stop");
    if (signals) {
        if (hb_store_termination_begin())
            return 70;
        app->poll_stop = xw_native_backend.stopping;
        if (!strcmp(name, "signal-owner-stop"))
            context.mode = SIGNAL_STOP;
        else if (raise(SIGTERM))
            return 70;
    }
#endif

    if (!strcmp(name, "registration-stop") || !strcmp(name, "signal-registration-stop")) {
        result = xw_storage_set_owner(app, 0, 0);
    } else {
#ifdef XW_HOST
        if (!context.directory)
            return 64;
        char path[4096];
        snprintf(path, sizeof path, "%s/state.bin", context.directory);
        FILE *file = fopen(path, "wb");
        if (!file || fwrite("old!", 1, 4, file) != 4 || fclose(file))
            return 70;
        app->preview_data = context.directory;
        result = xw_data_write(app, "state.bin", "new!", 4);
        char actual[4];
        file = fopen(path, "rb");
        if (!file || fread(actual, 1, 4, file) != 4 || fclose(file))
            return 70;
        int correct_content = !memcmp(actual, expected == XW_STORAGE_OK ? "new!" : "old!", 4);
        if (!correct_content) {
            fprintf(stderr, "%s: state was published after admission was revoked\n", name);
            result = 99;
        }
#else
        /* No filesystem or device IO: check the exact guard used by every operation. */
        result = xw_storage_access(app);
#endif
    }
    int observed = context.mode == LIVE || context.observed;
#ifndef XW_HOST
    if (signals && hb_store_termination_end())
        return 70;
#endif
    free(app);
    if (result != expected || !observed) {
        fprintf(stderr, "%s: result=%d expected=%d ownership_callback_observed=%d\n", name, result,
                expected, observed);
        return 1;
    }
    printf("SDK_STORAGE_STOP_PASS %s\n", name);
    return 0;
}

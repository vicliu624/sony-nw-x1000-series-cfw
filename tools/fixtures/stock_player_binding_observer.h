/* Optional PC guest observation on the GUI display owner. The preloaded player
 * library is fixed for the process lifetime. Only existing read-only diagnostic
 * exports are called; no service, native event or admission is requested.
 */
#ifndef XW_STOCK_PLAYER_BINDING_OBSERVER_H
#define XW_STOCK_PLAYER_BINDING_OBSERVER_H
static void guest_player_binding_observe(void) {
    typedef int (*binding_query)(void);
    static binding_query anchor_ready, pid_resolved;
    static unsigned resolved, observed;
    static int previous_available, previous_ready, previous_pid;
    int saved = errno;
    if (!resolved) {
        anchor_ready = (binding_query)dlsym(RTLD_DEFAULT, "xw_player_host_anchor_ready");
        pid_resolved = (binding_query)dlsym(RTLD_DEFAULT, "xw_player_host_pid_resolved");
        resolved = 1;
    }
    int available = anchor_ready && pid_resolved;
    int ready = available ? anchor_ready() : -1;
    int pid = available ? pid_resolved() : -1;
    if (!observed || previous_available != available || previous_ready != ready ||
        previous_pid != pid) {
        char line[140];
        int bytes =
            snprintf(line, sizeof line,
                     "GUEST_PLAYER_BINDING queries_available=%d anchor_ready=%d pid_resolved=%d\n",
                     available, ready, pid);
        if (bytes > 0 && (unsigned)bytes < sizeof line)
            write(2, line, (unsigned)bytes);
        previous_available = available;
        previous_ready = ready;
        previous_pid = pid;
        observed = 1;
    }
    errno = saved;
}
#endif

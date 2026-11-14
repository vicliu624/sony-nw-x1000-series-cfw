/* Strong fixture port for remote_auto's weak native GUI idle adapter. */
unsigned xw_fixture_remote_idle_active;
unsigned xw_fixture_remote_idle_calls;
int xw_player_host_remote_idle(int active) {
    xw_fixture_remote_idle_active = active != 0;
    xw_fixture_remote_idle_calls++;
    return 0;
}

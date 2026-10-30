#include "stock_info_host.c"
unsigned xw_test_mutex_result,xw_test_mutex_address,xw_test_mutex_locked,xw_test_unlocks;
int pthread_mutex_trylock(void *p){if((uintptr_t)p!=xw_test_mutex_address)return 22;if(xw_test_mutex_result)return (int)xw_test_mutex_result;if(xw_test_mutex_locked)return 16;xw_test_mutex_locked=1;return 0;}
int pthread_mutex_unlock(void *p){if((uintptr_t)p!=xw_test_mutex_address||!xw_test_mutex_locked)return 22;xw_test_mutex_locked=0;xw_test_unlocks++;return 0;}

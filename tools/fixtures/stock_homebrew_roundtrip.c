/* PC guest-only external process for original SpiderApp/APF lifecycle tests.
 * No launcher implementation, graphics, storage, network or RF acceptance.
 * The stock appproxy owns registration and return; this child only exits. */
#include <unistd.h>
int main(void){
 static const char entered[]="GUEST_HOMEBREW_ROUNDTRIP_CHILD_ENTERED\n";
 static const char leaving[]="GUEST_HOMEBREW_ROUNDTRIP_CHILD_EXITING\n";
 (void)write(2,entered,sizeof entered-1);
 (void)sleep(2);
 (void)write(2,leaving,sizeof leaving-1);
 return 0;
}

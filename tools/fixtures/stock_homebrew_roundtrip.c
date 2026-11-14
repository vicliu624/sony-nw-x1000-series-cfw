/* PC guest-only external process for original SpiderApp/APF lifecycle tests.
 * No launcher implementation, graphics, storage, network or RF acceptance.
 * The stock appproxy owns registration and return; this child only exits. */
#include <unistd.h>
#include <fcntl.h>
int main(void){
 static const char entered[]="GUEST_HOMEBREW_ROUNDTRIP_CHILD_ENTERED\n";
 static const char leaving[]="GUEST_HOMEBREW_ROUNDTRIP_CHILD_EXITING\n";
 /* sysmgr may redirect child stderr. The isolated guest console is the
  * explicit test observation channel; it is not installed on the device. */
 int console=open("/dev/console",O_WRONLY|O_NOCTTY);
 if(console<0)return 111;
 (void)write(console,entered,sizeof entered-1);
 (void)sleep(2);
 (void)write(console,leaving,sizeof leaving-1);
 (void)close(console);
 return 0;
}

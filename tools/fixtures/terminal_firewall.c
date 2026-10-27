#include "../../runtime/apps/terminal/terminal_firewall.h"
#include <string.h>
static int calls,failed;
static int run(char *const a[]){
 calls++;
 if(strcmp(a[0],"/sbin/iptables")||strcmp(a[2],"INPUT"))return -1;
 int add=!strcmp(a[1],"-I");unsigned offset=add?1:0;
 if(add&&strcmp(a[3],"1"))return -1;
 if(strcmp(a[3+offset],"-p")||strcmp(a[4+offset],"tcp")||strcmp(a[5+offset],"--dport")||strcmp(a[6+offset],"2323")||strcmp(a[7+offset],"-j")||strcmp(a[8+offset],"ACCEPT")||a[9+offset])return -1;
 if(failed){failed--;return -1;}return 0;
}
int main(void){
 struct hb_terminal_firewall f={0};
 if(hb_terminal_firewall_close(&f,run)||calls)return 1;
 failed=1;if(!hb_terminal_firewall_open(&f,run)||f.active||calls!=1)return 2;
 if(hb_terminal_firewall_open(&f,run)||!f.active)return 3;
 int before=calls;if(!hb_terminal_firewall_open(&f,run)||calls!=before)return 4;
 failed=2;if(hb_terminal_firewall_close(&f,run)||f.active||calls!=before+3)return 5;
 if(hb_terminal_firewall_open(&f,run))return 6;
 failed=3;if(!hb_terminal_firewall_close(&f,run)||!f.active)return 7;
 if(hb_terminal_firewall_close(&f,run)||f.active)return 8;
 return 0;
}

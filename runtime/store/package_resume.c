#define _XOPEN_SOURCE 700
#include "package_resume.h"
#include "cleanup_plan.h"
#include <sys/stat.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <errno.h>
#include "target_abi.h"
int hb_package_assembly_reopen(struct hb_package_assembly *a,const char *parent,const struct hb_package_download_plan *plan,volatile int *stop,struct hb_bundle *workspace){
 if(!a||a->state!=HB_ASSEMBLE_EMPTY||!parent||!plan||!plan->valid||!workspace||strlen(parent)>300)return HB_ASSEMBLE_INPUT;
 if(stop&&*stop)return HB_ASSEMBLE_CANCELLED;
 char canonical[PATH_MAX],folder[512];struct stat root,before,after;
 if(!realpath(parent,canonical)||strcmp(parent,canonical)||lstat(parent,&root)||!S_ISDIR(root.st_mode))return HB_ASSEMBLE_IO;
 unsigned n=(unsigned)strlen(parent);memcpy(folder,parent,n);if(n>1)folder[n++]='/';memcpy(folder+n,".bundle-",8);n+=8;
 unsigned id=(unsigned)strlen(plan->bundle.package.id);if(!id||id>32||n+id>=sizeof folder)return HB_ASSEMBLE_INPUT;memcpy(folder+n,plan->bundle.package.id,id+1);
 if(lstat(folder,&before))return errno==ENOENT?HB_ASSEMBLY_ABSENT:HB_ASSEMBLE_IO;
 if(!S_ISDIR(before.st_mode)||before.st_dev!=root.st_dev)return HB_ASSEMBLE_INPUT;
 unsigned char identity[32];int result=hb_bundle_check(folder,plan->bundle.package.id,stop,workspace);
 if(stop&&*stop)return HB_ASSEMBLE_CANCELLED;
 if(result||hb_bundle_identity(workspace,identity)||memcmp(identity,plan->identity,32))return HB_ASSEMBLE_INPUT;
 if(lstat(folder,&after)||!S_ISDIR(after.st_mode)||after.st_dev!=before.st_dev||after.st_ino!=before.st_ino)return HB_ASSEMBLE_IO;
 if(lstat(parent,&after)||!S_ISDIR(after.st_mode)||after.st_dev!=root.st_dev||after.st_ino!=root.st_ino)return HB_ASSEMBLE_IO;
 if(stop&&*stop)return HB_ASSEMBLE_CANCELLED;
 hb_package_assembly_init(a);a->plan=plan;a->stop=stop;strcpy(a->parent,parent);strcpy(a->folder,folder);strcpy(a->id,plan->bundle.package.id);memcpy(a->identity,identity,32);
 a->device=(unsigned long long)before.st_dev;a->inode=(unsigned long long)before.st_ino;a->added=plan->network_files;
 for(unsigned i=0;i<a->added;i++)a->seen[i]=1;
 a->state=HB_ASSEMBLE_READY;return 0;
}

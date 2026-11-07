#ifndef STOCK_MG_CONSTRUCTOR_MODEL_H
#define STOCK_MG_CONSTRUCTOR_MODEL_H
/* PC guest only: mg.ko's open/mmap and constructor completion contract.
 * The original 0x200 handler ignores ddmgInitialize's result and initializes
 * empty handle tables. No keys, crypto, authentication or protected media are
 * modeled here; every other operation is refused even after construction. */
#include <errno.h>
#include <stddef.h>
#include <sys/mman.h>
struct stock_mg_constructor {int fd;unsigned mappings,initialized;};
static struct stock_mg_constructor mg_constructor={-1,0,0};
static int stock_mg_constructor_ioctl(struct stock_mg_constructor *model,unsigned long command,void *argument){
 if(!model||model->fd<0){errno=EBADF;return -1;}
 if(command!=0x89a0){errno=ENOTTY;return -1;}
 if(!argument){errno=EFAULT;return -1;}
 if(*(const unsigned *)argument!=0x200){errno=EOPNOTSUPP;return -1;}
 model->initialized=1;return 0;
}
static void *stock_mg_constructor_map(struct stock_mg_constructor *model,void *address,size_t length,int prot,int flags,long offset,
 void *(*real_map)(void *,size_t,int,int,int,long)){
 if(!model||model->fd<0){errno=EBADF;return MAP_FAILED;}
 if(address||!length||length>1024*1024||prot!=(PROT_READ|PROT_WRITE)||flags!=MAP_SHARED||offset){errno=EINVAL;return MAP_FAILED;}
 if(model->mappings>=8){errno=ENOMEM;return MAP_FAILED;}
 void *mapped=real_map(address,length,prot,flags,model->fd,0);
 if(mapped!=MAP_FAILED)model->mappings++;
 return mapped;
}
#endif

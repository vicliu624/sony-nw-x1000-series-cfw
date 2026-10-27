#ifndef HB_LINUX_DEVICE_IO_H
#define HB_LINUX_DEVICE_IO_H
struct hb_device_pollfd {int fd;short events,revents;};
#ifdef HB_USE_POSIX_DEVICE_IO
long hb_device_io_open(const char *,int);
long hb_device_io_close(int);
long hb_device_io_ioctl(int,unsigned,void *);
long hb_device_io_map(unsigned,int);
long hb_device_io_unmap(void *,unsigned);
long hb_device_io_poll(struct hb_device_pollfd *,int);
#else
extern long x1000_oabi_call(long,long,long,long,long,long,long);
static inline long hb_device_io_open(const char *p,int f){return x1000_oabi_call(5,(long)p,f,0,0,0,0);}
static inline long hb_device_io_close(int fd){return x1000_oabi_call(6,fd,0,0,0,0,0);}
static inline long hb_device_io_ioctl(int fd,unsigned c,void *v){return x1000_oabi_call(54,fd,c,(long)v,0,0,0);}
static inline long hb_device_io_map(unsigned n,int fd){return x1000_oabi_call(192,0,n,3,1,fd,0);}
static inline long hb_device_io_unmap(void *p,unsigned n){return x1000_oabi_call(91,(long)p,n,0,0,0,0);}
static inline long hb_device_io_poll(struct hb_device_pollfd *p,int ms){return x1000_oabi_call(168,(long)p,1,ms,0,0,0);}
#endif
#endif

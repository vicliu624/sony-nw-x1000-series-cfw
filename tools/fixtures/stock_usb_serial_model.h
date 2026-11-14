/* Optional PC guest transport for usbconn. Only sysmgrd reads UART2; the
 * status/access page is shared by its original child processes. This observes
 * manager handoff, not USB gadget operation or physical volume ownership.
 */
#include "stock_usb_connection_model.h"
#include <poll.h>
#include <sys/mman.h>

#define XW_GUEST_USB_STATE_PATH "/tmp/guest-usb-transition.bin"
#define XW_GUEST_USB_STATE_MAGIC 0x31555342u
struct guest_usb_shared {
    volatile unsigned lock;
    unsigned magic;
    struct xw_guest_usb_connection connection;
};
static struct guest_usb_shared *guest_usb_shared;
struct guest_usb_serial {
    int writer;
    unsigned running;
    int status;
};
static struct guest_usb_serial *guest_usb_serial;
extern int pthread_create(unsigned long *, const void *, void *(*)(void *), void *);
extern int pthread_detach(unsigned long);

static void guest_usb_lock(void) {
    while (__sync_lock_test_and_set(&guest_usb_shared->lock, 1))
        usleep(1000);
}
static void guest_usb_unlock(void) { __sync_lock_release(&guest_usb_shared->lock); }
static int guest_usb_map(void) {
    if (guest_usb_shared)
        return 0;
    int (*real_open)(const char *, int, ...) = dlsym(RTLD_NEXT, "open");
    int (*real_close)(int) = dlsym(RTLD_NEXT, "close");
    void *(*real_map)(void *, size_t, int, int, int, long) = dlsym(RTLD_NEXT, "mmap");
    int fd = real_open(XW_GUEST_USB_STATE_PATH, O_RDWR | O_NOFOLLOW, 0);
    if (fd < 0)
        return -1;
    void *mapping = real_map(0, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    int saved = errno;
    real_close(fd);
    if (mapping == MAP_FAILED) {
        errno = saved;
        return -1;
    }
    struct guest_usb_shared *shared = mapping;
    if (shared->magic != XW_GUEST_USB_STATE_MAGIC) {
        munmap(mapping, 4096);
        errno = EINVAL;
        return -1;
    }
    guest_usb_shared = shared;
    return 0;
}
static int guest_usb_is_manager(void) {
    char path[256];
    ssize_t bytes = readlink("/proc/self/exe", path, sizeof path - 1);
    if (bytes < 0 || (size_t)bytes == sizeof path - 1)
        return 0;
    path[bytes] = 0;
    const char *name = strrchr(path, '/');
    return name && !strcmp(name + 1, "sysmgrd");
}
static void *guest_usb_serial_thread(void *argument) {
    struct guest_usb_serial *session = argument;
    int (*real_open)(const char *, int, ...) = dlsym(RTLD_NEXT, "open");
    int (*real_ioctl)(int, unsigned long, void *) = dlsym(RTLD_NEXT, "ioctl");
    int (*real_close)(int) = dlsym(RTLD_NEXT, "close");
    int fd = real_open("/dev/ttyAMA2", O_RDWR | O_NOCTTY | O_NONBLOCK, 0);
    struct {
        unsigned iflag, oflag, cflag, lflag;
        unsigned char line, cc[19];
    } term;
    if (fd >= 0) {
        if (real_ioctl(fd, 0x5401, &term)) {
            real_close(fd);
            fd = -1;
        } else {
            term.iflag = term.oflag = term.lflag = 0;
            term.cc[5] = term.cc[6] = 0;
            if (real_ioctl(fd, 0x5402, &term)) {
                real_close(fd);
                fd = -1;
            }
        }
    }
    __atomic_store_n(&session->status, fd >= 0 ? 1 : -(errno ? errno : EIO), __ATOMIC_RELEASE);
    if (fd >= 0) {
        const char ready[] = "GUEST_USB_INPUT_READY\n";
        write(2, ready, sizeof ready - 1);
        unsigned char packet[12];
        unsigned used = 0;
        while (__atomic_load_n(&session->running, __ATOMIC_ACQUIRE)) {
            ssize_t got = read(fd, packet + used, sizeof packet - used);
            if (got <= 0) {
                usleep(10000);
                continue;
            }
            used += (unsigned)got;
            if (used != sizeof packet)
                continue;
            used = 0;
            if (memcmp(packet, "XWU2", 4) || packet[5] || packet[6] || packet[7] ||
                !(packet[8] | packet[9] | packet[10] | packet[11]))
                continue;
            guest_usb_lock();
            int notify = xw_guest_usb_change(&guest_usb_shared->connection, packet[4]);
            if (notify > 0) {
                const unsigned char token = 1;
                if (write(session->writer, &token, 1) != 1) {
                    const char failed[] = "GUEST_USB_NOTIFICATION_WRITE_FAILED\n";
                    write(2, failed, sizeof failed - 1);
                }
            }
            unsigned char reply[12] = {'X',
                                       'W',
                                       'A',
                                       '2',
                                       packet[8],
                                       packet[9],
                                       packet[10],
                                       packet[11],
                                       guest_usb_shared->connection.status,
                                       guest_usb_shared->connection.access,
                                       guest_usb_shared->connection.pending,
                                       notify < 0 ? 255 : notify};
            guest_usb_unlock();
            char line[150];
            int n = snprintf(line, sizeof line,
                             "GUEST_USB_TRANSITION status=%u access=%u pending=%u notify=%u\n",
                             reply[8], reply[9], reply[10], reply[11]);
            write(2, line, (unsigned)n);
            /* Transport receipt only. It does not acknowledge Sony handoff. */
            (void)write(fd, reply, sizeof reply);
        }
        real_close(fd);
    }
    while (__atomic_load_n(&session->running, __ATOMIC_ACQUIRE))
        usleep(10000);
    real_close(session->writer);
    free(session);
    return 0;
}
static int guest_usb_open(void) {
    if (usb >= 0) {
        errno = EBUSY;
        return -1;
    }
    if (guest_usb_map())
        return -1;
    int descriptors[2];
    if (pipe(descriptors))
        return -1;
    guest_fcntl(descriptors[0], F_SETFD, FD_CLOEXEC);
    guest_fcntl(descriptors[1], F_SETFD, FD_CLOEXEC);
    guest_fcntl(descriptors[0], F_SETFL, O_NONBLOCK);
    guest_fcntl(descriptors[1], F_SETFL, O_NONBLOCK);
    if (guest_usb_is_manager()) {
        struct guest_usb_serial *session = calloc(1, sizeof *session);
        if (!session)
            goto failed;
        session->writer = descriptors[1];
        session->running = 1;
        unsigned long thread;
        int error = pthread_create(&thread, 0, guest_usb_serial_thread, session);
        if (error) {
            free(session);
            errno = error;
            goto failed;
        }
        pthread_detach(thread);
        for (unsigned attempt = 0;
             attempt < 250 && !__atomic_load_n(&session->status, __ATOMIC_ACQUIRE); attempt++)
            usleep(2000);
        int status = __atomic_load_n(&session->status, __ATOMIC_ACQUIRE);
        if (status != 1) {
            __atomic_store_n(&session->running, 0, __ATOMIC_RELEASE);
            close(descriptors[0]);
            errno = status < 0 ? -status : ETIMEDOUT;
            return -1;
        }
        guest_usb_serial = session;
    }
    usb = descriptors[0];
    usb_writer = descriptors[1];
    return usb;
failed:;
    int saved = errno;
    close(descriptors[0]);
    close(descriptors[1]);
    errno = saved;
    return -1;
}
static int guest_usb_ioctl(unsigned long command, void *value) {
    guest_usb_lock();
    int result = 0;
    if (command == XW_GUEST_USB_GET_STATUS && value)
        *(unsigned *)value = xw_guest_usb_status(&guest_usb_shared->connection);
    else if (command != XW_GUEST_USB_GET_STATUS &&
             !xw_guest_usb_access(&guest_usb_shared->connection, command)) {
        char line[100];
        int n = snprintf(line, sizeof line, "GUEST_USB_ACCESS value=%u\n",
                         guest_usb_shared->connection.access);
        write(2, line, (unsigned)n);
    } else {
        errno = command == XW_GUEST_USB_GET_STATUS ? EFAULT : EOPNOTSUPP;
        result = -1;
    }
    guest_usb_unlock();
    return result;
}
int poll(struct pollfd *items, nfds_t count, int timeout) {
    int (*next)(struct pollfd *, nfds_t, int) = dlsym(RTLD_NEXT, "poll");
    int result = next(items, count, timeout), saved = errno;
    if (result > 0 && usb >= 0 && guest_usb_shared) {
        for (nfds_t i = 0; i < count; i++)
            if (items[i].fd == usb && (items[i].revents & POLLIN)) {
                guest_usb_lock();
                unsigned ready = xw_guest_usb_poll(&guest_usb_shared->connection);
                unsigned char bytes[32];
                while (read(usb, bytes, sizeof bytes) > 0) {
                }
                items[i].revents =
                    (items[i].revents & ~(POLLIN | POLLRDNORM)) | (ready & items[i].events);
                guest_usb_unlock();
            }
        result = 0;
        for (nfds_t i = 0; i < count; i++)
            result += items[i].revents != 0;
    }
    errno = saved;
    return result;
}
static void guest_usb_close(void) {
    if (guest_usb_serial) {
        __atomic_store_n(&guest_usb_serial->running, 0, __ATOMIC_RELEASE);
        guest_usb_serial = 0;
    } else {
        int (*real_close)(int) = dlsym(RTLD_NEXT, "close");
        real_close(usb_writer);
    }
    usb = usb_writer = -1;
}
__attribute__((constructor)) static void guest_usb_program_observed(void) {
    char path[256];
    ssize_t bytes = readlink("/proc/self/exe", path, sizeof path - 1);
    if (bytes < 0 || (size_t)bytes == sizeof path - 1)
        return;
    path[bytes] = 0;
    const char *name = strrchr(path, '/');
    if (name && (!strcmp(name + 1, "Responder") || !strcmp(name + 1, "SpiderApp"))) {
        char line[100];
        int n = snprintf(line, sizeof line, "GUEST_USB_PROGRAM_STARTED name=%s\n", name + 1);
        write(2, line, (unsigned)n);
    }
}

/* Native nonblocking IPv4 client. Exact paired certificate pin, TLS1.2, fixed
 * token authenticated only after handshake; never exposes a shell/approval API.
 */
#include "link_client.h"
#include "discovery.h"
#include <arpa/inet.h>
#include <bearssl.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
extern int pet_net_fcntl(int, int, ...) __asm__("fcntl");
extern int pet_net_getsockopt(int, int, int, void *,
                              socklen_t *) __asm__("getsockopt");
struct pin_check {
  const br_x509_class *vtable;
  br_x509_knownkey_context known;
  br_sha256_context hash;
  unsigned char expected[32];
  unsigned certificates, bad;
};
struct pet_net {
  struct pet_net_config config;
  volatile int *stop;
  int socket, connecting, sent;
  struct pet_discovery discovery;
  int searching;
  int discovered;
  unsigned retry_delay;
  enum pet_net_state state;
  uint64_t deadline, next, last, nonce;
  br_ssl_client_context ssl;
  br_x509_minimal_context unused;
  br_x509_decoder_context decoder;
  struct pin_check pin;
  unsigned char tlsbuf[BR_SSL_BUFSIZE_BIDI], response[PET_LINK_FRAME_MAX + 2];
  unsigned received;
  struct pet_link_snapshot snapshot;
};
static void chain(const br_x509_class **ctx, const char *name) {
  struct pin_check *p = (struct pin_check *)ctx;
  p->certificates = p->bad = 0;
  p->known.vtable->start_chain(&p->known.vtable, name);
}
static void cert_start(const br_x509_class **ctx, uint32_t n) {
  struct pin_check *p = (struct pin_check *)ctx;
  if (!p->certificates)
    br_sha256_init(&p->hash);
  p->known.vtable->start_cert(&p->known.vtable, n);
}
static void cert_data(const br_x509_class **ctx, const unsigned char *data,
                      size_t n) {
  struct pin_check *p = (struct pin_check *)ctx;
  if (!p->certificates)
    br_sha256_update(&p->hash, data, n);
  p->known.vtable->append(&p->known.vtable, data, n);
}
static void cert_end(const br_x509_class **ctx) {
  struct pin_check *p = (struct pin_check *)ctx;
  if (!p->certificates) {
    unsigned char hash[32];
    unsigned diff = 0;
    br_sha256_out(&p->hash, hash);
    for (unsigned i = 0; i < 32; i++)
      diff |= hash[i] ^ p->expected[i];
    p->bad = !!diff;
  }
  p->certificates++;
  p->known.vtable->end_cert(&p->known.vtable);
}
static unsigned chain_end(const br_x509_class **ctx) {
  struct pin_check *p = (struct pin_check *)ctx;
  unsigned result = p->known.vtable->end_chain(&p->known.vtable);
  return p->bad || !p->certificates ? BR_ERR_X509_NOT_TRUSTED : result;
}
static const br_x509_pkey *key(const br_x509_class *const *ctx,
                               unsigned *usage) {
  const struct pin_check *p = (const struct pin_check *)ctx;
  return p->known.vtable->get_pkey(&p->known.vtable, usage);
}
static const br_x509_class pin_class = {sizeof(struct pin_check),
                                        chain,
                                        cert_start,
                                        cert_data,
                                        cert_end,
                                        chain_end,
                                        key};
static int random_bytes(unsigned char *p, unsigned n) {
  int fd = open("/dev/urandom", O_RDONLY | O_NOFOLLOW);
  if (fd < 0)
    return 0;
  unsigned used = 0;
  while (used < n) {
    ssize_t k = read(fd, p + used, n - used);
    if (k < 0 && errno == EINTR)
      continue;
    if (k <= 0)
      break;
    used += (unsigned)k;
  }
  int bad = close(fd);
  return used == n && !bad;
}
static void disconnect(struct pet_net *n, enum pet_net_state state,
                       uint64_t now) {
  if (n->socket >= 0)
    close(n->socket);
  n->socket = -1;
  n->connecting = 0;
  pet_discovery_close(&n->discovery);
  n->searching = 0;
  n->state = state;
  n->next = now + n->retry_delay;
  if (state != PET_NET_STOPPED && n->retry_delay < 30000)
    n->retry_delay = n->retry_delay > 15000 ? 30000 : n->retry_delay * 2;
}
struct pet_net *pet_net_create(const struct pet_net_config *config,
                               volatile int *stop) {
  if (!config || !stop || config->certificate_bytes > 4096 ||
      !config->certificate_bytes || !config->port || config->port > 65535 ||
      !memchr(config->ipv4, 0, sizeof config->ipv4))
    return 0;
  struct in_addr addr;
  if (inet_pton(AF_INET, config->ipv4, &addr) != 1)
    return 0;
  struct pet_net *n = calloc(1, sizeof *n);
  if (!n)
    return 0;
  pet_discovery_init(&n->discovery);
  n->retry_delay = 2000;
  n->socket = -1;
  n->config = *config;
  n->stop = stop;
  n->state = PET_NET_CONNECTING;
  br_x509_decoder_init(&n->decoder, 0, 0);
  br_x509_decoder_push(&n->decoder, config->certificate,
                       config->certificate_bytes);
  const br_x509_pkey *pkey = br_x509_decoder_get_pkey(&n->decoder);
  if (!pkey || pkey->key_type != BR_KEYTYPE_EC ||
      br_x509_decoder_last_error(&n->decoder)) {
    free(n);
    return 0;
  }
  br_sha256_context h;
  br_sha256_init(&h);
  br_sha256_update(&h, config->certificate, config->certificate_bytes);
  br_sha256_out(&h, n->pin.expected);
  return n;
}
void pet_net_destroy(struct pet_net *n) {
  if (!n)
    return;
  pet_discovery_close(&n->discovery);
  if (n->socket >= 0)
    close(n->socket);
  volatile unsigned char *p = (volatile unsigned char *)n;
  for (size_t i = 0; i < sizeof *n; i++)
    p[i] = 0;
  free(n);
}
static int begin(struct pet_net *n, uint64_t now) {
  n->socket = socket(AF_INET, SOCK_STREAM, 0);
  if (n->socket < 0)
    return 0;
  int flags = pet_net_fcntl(n->socket, F_GETFL);
  if (flags < 0 || pet_net_fcntl(n->socket, F_SETFL, flags | O_NONBLOCK) < 0 ||
      pet_net_fcntl(n->socket, F_SETFD, FD_CLOEXEC) < 0)
    return 0;
  /* All sockaddr fields below use the stock 32-bit wire layout. */
  struct sockaddr_in addr;
  memset(&addr, 0, sizeof addr);
  addr.sin_family = AF_INET;
  addr.sin_port = htons((unsigned short)n->config.port);
  inet_pton(AF_INET, n->config.ipv4, &addr.sin_addr);
  int rc = connect(n->socket, (const struct sockaddr *)&addr, sizeof addr);
  if (rc && errno != EINPROGRESS)
    return 0;
  br_ssl_client_init_full(&n->ssl, &n->unused, 0, 0);
  const br_x509_pkey *pkey = br_x509_decoder_get_pkey(&n->decoder);
  br_x509_knownkey_init_ec(&n->pin.known, &pkey->key.ec, BR_KEYTYPE_SIGN);
  n->pin.vtable = &pin_class;
  br_ssl_engine_set_x509(&n->ssl.eng, &n->pin.vtable);
  br_ssl_engine_set_versions(&n->ssl.eng, BR_TLS12, BR_TLS12);
  br_ssl_engine_set_buffer(&n->ssl.eng, n->tlsbuf, sizeof n->tlsbuf, 1);
  unsigned char entropy[40];
  if (!random_bytes(entropy, sizeof entropy))
    return 0;
  br_ssl_engine_inject_entropy(&n->ssl.eng, entropy, 32);
  n->nonce = 0;
  for (unsigned i = 32; i < 40; i++)
    n->nonce = (n->nonce << 8) | entropy[i];
  memset(entropy, 0, sizeof entropy);
  if (!br_ssl_client_reset(&n->ssl, 0, 0))
    return 0;
  n->deadline = now + 5000;
  n->connecting = !!rc;
  n->received = 0;
  n->sent = 0;
  n->state = PET_NET_CONNECTING;
  return 1;
}
int pet_net_tick(struct pet_net *n, uint64_t now) {
  if (!n)
    return 0;
  if (*n->stop) {
    disconnect(n, PET_NET_STOPPED, now);
    return 0;
  }
  if (n->socket < 0) {
    if (now < n->next)
      return 0;
    if (!n->searching) {
      n->searching =
          pet_discovery_start(&n->discovery, n->config.token, n->pin.expected,
                              n->config.ipv4, n->config.discovery_port, now);
      if (n->searching)
        n->state = PET_NET_DISCOVERING;
    }
    if (n->searching) {
      char address[16] = {0};
      unsigned port = 0;
      int found = pet_discovery_tick(&n->discovery, now, address, &port);
      if (!found)
        return 0;
      n->searching = 0;
      if (found > 0) {
        n->discovered = 1;
        memcpy(n->config.ipv4, address, sizeof address);
        n->config.port = port;
      } else
        n->discovered = 0;
    }
    if (!strcmp(n->config.ipv4, "0.0.0.0")) {
      disconnect(n, PET_NET_OFFLINE, now);
      return 0;
    }
    if (!begin(n, now)) {
      disconnect(n, PET_NET_OFFLINE, now);
      return 0;
    }
  }
  if (n->sent == 2) {
    if (now < n->next)
      return 0;
    unsigned char nonce[8];
    if (!random_bytes(nonce, sizeof nonce)) {
      disconnect(n, PET_NET_OFFLINE, now);
      return 0;
    }
    n->nonce = 0;
    for (unsigned i = 0; i < 8; i++)
      n->nonce = (n->nonce << 8) | nonce[i];
    n->received = 0;
    n->sent = 0;
    n->deadline = now + 5000;
  }
  if (now > n->deadline) {
    disconnect(n, PET_NET_OFFLINE, now);
    return 0;
  }
  if (n->connecting) {
    struct pollfd p = {n->socket, POLLOUT, 0};
    if (poll(&p, 1, 0) <= 0)
      return 0;
    int error = 0;
    socklen_t size = sizeof error;
    if (pet_net_getsockopt(n->socket, SOL_SOCKET, SO_ERROR, &error, &size) ||
        error) {
      disconnect(n, PET_NET_OFFLINE, now);
      return 0;
    }
    n->connecting = 0;
  }
  for (unsigned spin = 0; spin < 8; spin++) {
    unsigned state = br_ssl_engine_current_state(&n->ssl.eng);
    size_t size;
    unsigned char *buf;
    if (state == BR_SSL_CLOSED) {
      disconnect(n, n->pin.bad ? PET_NET_IDENTITY_ERROR : PET_NET_OFFLINE, now);
      return 0;
    }
    if (state & BR_SSL_SENDREC) {
      buf = br_ssl_engine_sendrec_buf(&n->ssl.eng, &size);
      ssize_t rc = send(n->socket, buf, size, MSG_NOSIGNAL);
      if (rc > 0) {
        br_ssl_engine_sendrec_ack(&n->ssl.eng, (size_t)rc);
        continue;
      }
      if (rc < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR))
        return 0;
      disconnect(n, PET_NET_OFFLINE, now);
      return 0;
    }
    if ((state & BR_SSL_SENDAPP) && !n->sent) {
      buf = br_ssl_engine_sendapp_buf(&n->ssl.eng, &size);
      if (size < 44)
        return 0;
      memcpy(buf, "PET1", 4);
      memcpy(buf + 4, n->config.token, 32);
      for (unsigned i = 0; i < 8; i++)
        buf[43 - i] = (unsigned char)(n->nonce >> (i * 8));
      br_ssl_engine_sendapp_ack(&n->ssl.eng, 44);
      br_ssl_engine_flush(&n->ssl.eng, 0);
      n->sent = 1;
      continue;
    }
    if (state & BR_SSL_RECVAPP) {
      buf = br_ssl_engine_recvapp_buf(&n->ssl.eng, &size);
      if (size > sizeof n->response - n->received) {
        disconnect(n, PET_NET_OFFLINE, now);
        return 0;
      }
      memcpy(n->response + n->received, buf, size);
      n->received += (unsigned)size;
      br_ssl_engine_recvapp_ack(&n->ssl.eng, size);
      if (n->received >= 2) {
        unsigned bytes = (unsigned)n->response[0] << 8 | n->response[1];
        if (bytes < 36 || bytes > PET_LINK_FRAME_MAX ||
            n->received > bytes + 2) {
          disconnect(n, PET_NET_OFFLINE, now);
          return 0;
        }
        if (n->received == bytes + 2) {
          if (!pet_link_decode(&n->snapshot, n->response + 2, bytes,
                               n->nonce)) {
            disconnect(n, PET_NET_OFFLINE, now);
            return 0;
          }
          n->last = now;
          n->retry_delay = 2000;
          n->state = PET_NET_CONNECTED;
          n->sent = 2;
          n->next = now + 2000;
          n->deadline = now + 7000;
          return 1;
        }
      }
      continue;
    }
    if (state & BR_SSL_RECVREC) {
      buf = br_ssl_engine_recvrec_buf(&n->ssl.eng, &size);
      ssize_t rc = recv(n->socket, buf, size, 0);
      if (rc > 0) {
        br_ssl_engine_recvrec_ack(&n->ssl.eng, (size_t)rc);
        continue;
      }
      if (rc < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR))
        return 0;
      disconnect(n, PET_NET_OFFLINE, now);
      return 0;
    }
    return 0;
  }
  return 0;
}
const struct pet_link_snapshot *pet_net_snapshot(const struct pet_net *n) {
  return n ? &n->snapshot : 0;
}
int pet_net_endpoint(const struct pet_net *n, char out[32]) {
  out[0] = 0;
  if (!n || !strcmp(n->config.ipv4, "0.0.0.0"))
    return -1;
  snprintf(out, 32, "%s:%u", n->config.ipv4, n->config.port);
  return n->discovered;
}
enum pet_net_state pet_net_status(const struct pet_net *n, uint64_t now) {
  if (!n)
    return PET_NET_STOPPED;
  if (n->state != PET_NET_IDENTITY_ERROR && n->state != PET_NET_STOPPED &&
      n->last && now >= n->last && now - n->last <= 10000)
    return PET_NET_CONNECTED;
  if (n->state == PET_NET_CONNECTED && now - n->last > 10000)
    return PET_NET_OFFLINE;
  return n->state;
}

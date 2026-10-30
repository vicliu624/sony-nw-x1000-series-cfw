#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
// clang-format off
#include <winsock2.h>
#include <ws2tcpip.h>
// clang-format on
using Socket = SOCKET;
static void close_socket(Socket s) { closesocket(s); }
#else
#include <arpa/inet.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
using Socket = int;
static const int INVALID_SOCKET = -1;
static void close_socket(Socket s) { close(s); }
#endif
#include "../discovery_wire.h"
#include "discovery_server.hpp"
#include <cstring>
#include <stdexcept>
namespace petbridge {
DiscoveryServer::DiscoveryServer(const std::string &bind_address,
                                 unsigned udp_port, unsigned tcp_port,
                                 const std::array<unsigned char, 32> &token,
                                 const std::array<unsigned char, 32> &pin)
    : socket_(static_cast<std::uintptr_t>(INVALID_SOCKET)) {
  if (!udp_port || udp_port > 65535 || !tcp_port || tcp_port > 65535)
    throw std::runtime_error("Invalid discovery port");
  Socket s = socket(AF_INET, SOCK_DGRAM, 0);
  if (s == INVALID_SOCKET)
    throw std::runtime_error("Cannot create discovery socket");
#ifdef _WIN32
  int exclusive = 1;
  setsockopt(s, SOL_SOCKET, SO_EXCLUSIVEADDRUSE,
             reinterpret_cast<const char *>(&exclusive), sizeof exclusive);
#endif
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(static_cast<unsigned short>(udp_port));
  if (inet_pton(AF_INET, bind_address.c_str(), &addr.sin_addr) != 1 ||
      ::bind(s, reinterpret_cast<sockaddr *>(&addr), sizeof addr)) {
    close_socket(s);
    throw std::runtime_error("Cannot bind LAN discovery socket");
  }
  socket_ = static_cast<std::uintptr_t>(s);
  try {
    thread_ = std::thread([this, s, tcp_port, token, pin] {
      while (!stop_.load()) {
        fd_set ready;
        FD_ZERO(&ready);
        FD_SET(s, &ready);
        timeval wait = {0, 200000};
        int rc =
            select(static_cast<int>(s + 1), &ready, nullptr, nullptr, &wait);
        if (rc <= 0)
          continue;
        unsigned char query[49], reply[82];
        sockaddr_in from{};
#ifdef _WIN32
        int size = sizeof from;
        int count = recvfrom(s, reinterpret_cast<char *>(query), sizeof query,
                             0, reinterpret_cast<sockaddr *>(&from), &size);
#else
        socklen_t size = sizeof from;
        int count = static_cast<int>(
            recvfrom(s, query, sizeof query, 0,
                     reinterpret_cast<sockaddr *>(&from), &size));
#endif
        if (count != 48 || !pet_discovery_query_check(query, 48, token.data()))
          continue;
        pet_discovery_reply(reply, token.data(), query + 8, pin.data(),
                            tcp_port);
        sendto(s, reinterpret_cast<const char *>(reply), sizeof reply, 0,
               reinterpret_cast<sockaddr *>(&from), sizeof from);
      }
    });
  } catch (...) {
    close_socket(s);
    throw;
  }
}
DiscoveryServer::~DiscoveryServer() {
  stop_ = true;
  if (thread_.joinable())
    thread_.join();
  if (socket_ != static_cast<std::uintptr_t>(INVALID_SOCKET))
    close_socket(static_cast<Socket>(socket_));
}
} // namespace petbridge

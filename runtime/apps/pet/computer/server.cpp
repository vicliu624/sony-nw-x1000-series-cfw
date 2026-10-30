/* Paired status-only LAN endpoint. Does not expose app-server or a shell. */
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
// clang-format off
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <bcrypt.h>
// clang-format on
using Socket = SOCKET;
static void close_socket(Socket s) { closesocket(s); }
#else
#include <arpa/inet.h>
#include <sys/random.h>
#include <sys/socket.h>
#include <unistd.h>
using Socket = int;
static const int INVALID_SOCKET = -1;
static void close_socket(Socket s) { close(s); }
#endif
#include "../../../../third_party/pet-json/json.hpp"
#include "../link_wire.h"
#include "discovery_server.hpp"
#include "tail.hpp"
#include <algorithm>
#include <array>
#include <bearssl.h>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <vector>
using Json = nlohmann::json;
static std::vector<unsigned char> read_bytes(const std::filesystem::path &p,
                                             std::size_t maximum) {
  std::ifstream f(p, std::ios::binary);
  std::vector<unsigned char> out;
  char c;
  while (f.get(c)) {
    if (out.size() == maximum)
      throw std::runtime_error("Oversized identity file");
    out.push_back(static_cast<unsigned char>(c));
  }
  if (!f.eof() || out.empty())
    throw std::runtime_error("Identity file unreadable");
  return out;
}
static bool hex(const std::string &s, unsigned char *out, unsigned bytes) {
  if (s.size() != bytes * 2)
    return false;
  for (unsigned i = 0; i < bytes; i++) {
    unsigned n = 0;
    for (unsigned j = 0; j < 2; j++) {
      unsigned c = static_cast<unsigned char>(s[i * 2 + j]);
      if (c >= '0' && c <= '9')
        c -= '0';
      else if (c >= 'a' && c <= 'f')
        c = c - 'a' + 10;
      else
        return false;
      n = n * 16 + c;
    }
    out[i] = static_cast<unsigned char>(n);
  }
  return true;
}
static int input(void *ctx, unsigned char *p, size_t n) {
  auto s = *static_cast<Socket *>(ctx);
  int r = recv(s, reinterpret_cast<char *>(p), static_cast<int>(n), 0);
  return r > 0 ? r : -1;
}
static int output(void *ctx, const unsigned char *p, size_t n) {
  auto s = *static_cast<Socket *>(ctx);
#ifdef _WIN32
  const int flags = 0;
#else
  const int flags = MSG_NOSIGNAL;
#endif
  int r =
      send(s, reinterpret_cast<const char *>(p), static_cast<int>(n), flags);
  return r > 0 ? r : -1;
}
static bool entropy(unsigned char *p, unsigned n) {
#ifdef _WIN32
  return BCryptGenRandom(nullptr, p, n, BCRYPT_USE_SYSTEM_PREFERRED_RNG) == 0;
#else
  return getrandom(p, n, 0) == static_cast<ssize_t>(n);
#endif
}
static void timeout(Socket s, unsigned milliseconds = 3000) {
#ifdef _WIN32
  DWORD ms = milliseconds;
  setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char *>(&ms),
             sizeof ms);
  setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char *>(&ms),
             sizeof ms);
#else
  timeval tv = {static_cast<long>(milliseconds / 1000),
                static_cast<long>((milliseconds % 1000) * 1000)};
  setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof tv);
  setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof tv);
#endif
}
static void copy_text(char *out, std::size_t capacity, const std::string &s) {
  auto value = petbridge::bounded_utf8(s, capacity - 1);
  std::memcpy(out, value.data(), value.size());
  out[value.size()] = 0;
}
int main(int argc, char **argv) {
  try {
    if (argc == 2 && std::string(argv[1]) == "--help") {
      std::cout << "pet-bridge <private-computer-config.json>\nRead-only "
                   "selected Codex rollout to paired X1000 over TLS1.2. No "
                   "Codex prompts or approvals are accepted. Close this "
                   "process to stop the endpoint.\n";
      return 0;
    }
    if (argc == 2 && std::string(argv[1]) == "--version") {
      std::cout << PET_BRIDGE_VERSION << "\n";
      return 0;
    }
    if (argc != 2) {
      std::cerr << "pet-bridge <private-computer-config.json>\n";
      return 64;
    }
    auto config_path =
        std::filesystem::absolute(std::filesystem::u8path(argv[1]));
    auto raw = read_bytes(config_path, 8192);
    auto config = Json::parse(raw);
    auto address = config.at("listen").get<std::string>();
    bool discover = config.value("discovery", false);
    auto port = config.at("port").get<unsigned>();
    if (!port || port > 65535)
      throw std::runtime_error("Invalid port");
    std::array<unsigned char, 32> token{};
    if (!hex(config.at("token").get<std::string>(), token.data(), 32))
      throw std::runtime_error("Invalid pairing token");
    auto cert = read_bytes(config_path.parent_path() /
                               std::filesystem::u8path(
                                   config.at("certificate").get<std::string>()),
                           4096);
    auto secret =
        read_bytes(config_path.parent_path() /
                       std::filesystem::u8path(
                           config.at("private_key").get<std::string>()),
                   2048);
    br_skey_decoder_context key;
    br_skey_decoder_init(&key);
    br_skey_decoder_push(&key, secret.data(), secret.size());
    auto ec = br_skey_decoder_get_ec(&key);
    if (!ec || ec->curve != BR_EC_secp256r1 || br_skey_decoder_last_error(&key))
      throw std::runtime_error("Invalid EC identity");
    petbridge::RolloutTail tail(
        std::filesystem::u8path(config.at("rollout").get<std::string>()),
        config.value("title", std::string("Codex")));
    if (!tail.poll())
      throw std::runtime_error(
          "Selected Codex rollout is unreadable or unsupported");
#ifdef _WIN32
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa))
      throw std::runtime_error("Winsock initialization failed");
#endif
    Socket listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener == INVALID_SOCKET)
      throw std::runtime_error("Socket failed");
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<unsigned short>(port));
    if (inet_pton(AF_INET, address.c_str(), &addr.sin_addr) != 1 ||
        bind(listener, reinterpret_cast<sockaddr *>(&addr), sizeof addr) ||
        listen(listener, 4)) {
      close_socket(listener);
      throw std::runtime_error("Cannot bind selected IPv4 address/port");
    }
    std::cout << "Paired Codex status endpoint " << address << ":" << port
              << " (TLS1.2; status only)\n"
              << std::flush;
    std::unique_ptr<petbridge::DiscoveryServer> discovery;
    if (discover) {
      std::array<unsigned char, 32> pin{};
      br_sha256_context hash;
      br_sha256_init(&hash);
      br_sha256_update(&hash, cert.data(), cert.size());
      br_sha256_out(&hash, pin.data());
      try {
        discovery = std::make_unique<petbridge::DiscoveryServer>(
            address, config.value("discovery_port", 4243u), port, token, pin);
        std::cout << "Authenticated LAN discovery enabled\n" << std::flush;
      } catch (const std::exception &e) {
        std::cerr << "LAN discovery unavailable: " << e.what() << "\n";
      }
    }
    for (;;) {
      Socket client = accept(listener, nullptr, nullptr);
      if (client == INVALID_SOCKET)
        break;
      timeout(client);
      br_ssl_server_context ssl;
      br_x509_certificate chain = {cert.data(), cert.size()};
      std::array<unsigned char, BR_SSL_BUFSIZE_BIDI> tlsbuf{};
      br_ssl_server_init_minf2g(&ssl, &chain, 1, ec);
      br_ssl_engine_set_buffer(&ssl.eng, tlsbuf.data(), tlsbuf.size(), 1);
      unsigned char seed[32];
      if (!entropy(seed, sizeof seed)) {
        close_socket(client);
        continue;
      }
      br_ssl_engine_inject_entropy(&ssl.eng, seed, sizeof seed);
      br_ssl_engine_set_versions(&ssl.eng, BR_TLS12, BR_TLS12);
      if (!br_ssl_server_reset(&ssl)) {
        close_socket(client);
        continue;
      }
      br_sslio_context io;
      br_sslio_init(&io, &ssl.eng, input, &client, output, &client);
      for (unsigned request_number = 0; request_number < 30; request_number++) {
        unsigned char request[44];
        if (br_sslio_read_all(&io, request, sizeof request) < 0) {
          break;
        }
        unsigned diff = 0;
        for (unsigned i = 0; i < 32; i++)
          diff |= request[4 + i] ^ token[i];
        if (std::memcmp(request, "PET1", 4) || diff) {
          break;
        }
        timeout(client, 10000);
        struct pet_link_snapshot snapshot {};
        snapshot.nonce = 0;
        for (unsigned i = 36; i < 44; i++)
          snapshot.nonce = (snapshot.nonce << 8) | request[i];
        bool available = tail.poll();
        const auto &observed = tail.observer().snapshot();
        if (observed.activity == petbridge::Activity::working &&
            !tail.fresh(90))
          available = false;
        snapshot.state = available ? static_cast<unsigned>(observed.activity)
                                   : static_cast<unsigned>(PET_LINK_UNKNOWN);
        snapshot.revision = observed.revision;
        copy_text(snapshot.thread, sizeof snapshot.thread, observed.thread_id);
        copy_text(snapshot.turn, sizeof snapshot.turn, observed.turn_id);
        copy_text(snapshot.title, sizeof snapshot.title, observed.title);
        copy_text(snapshot.summary, sizeof snapshot.summary, observed.summary);
        copy_text(snapshot.question, sizeof snapshot.question,
                  observed.question);
        unsigned char frame[PET_LINK_FRAME_MAX], size[2];
        size_t length;
        if (pet_link_encode(&snapshot, frame, sizeof frame, &length)) {
          size[0] = static_cast<unsigned char>(length >> 8);
          size[1] = static_cast<unsigned char>(length);
          if (br_sslio_write_all(&io, size, 2) == 0 &&
              br_sslio_write_all(&io, frame, length) == 0) {
            if (br_sslio_flush(&io))
              break;
          } else
            break;
        }
      }
      close_socket(client);
    }
    close_socket(listener);
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "Pet bridge: " << error.what() << "\n";
    return 2;
  }
}

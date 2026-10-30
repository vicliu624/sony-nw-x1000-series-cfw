#ifndef PET_COMPUTER_DISCOVERY_HPP
#define PET_COMPUTER_DISCOVERY_HPP
#include <array>
#include <atomic>
#include <cstdint>
#include <string>
#include <thread>
namespace petbridge {
class DiscoveryServer {
  std::atomic<bool> stop_{false};
  std::thread thread_;
  std::uintptr_t socket_;

public:
  DiscoveryServer(const std::string &bind, unsigned udp_port, unsigned tcp_port,
                  const std::array<unsigned char, 32> &token,
                  const std::array<unsigned char, 32> &pin);
  ~DiscoveryServer();
  DiscoveryServer(const DiscoveryServer &) = delete;
  DiscoveryServer &operator=(const DiscoveryServer &) = delete;
};
} // namespace petbridge
#endif

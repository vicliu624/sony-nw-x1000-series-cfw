#ifndef HB_PET_ROLLOUT_TAIL_HPP
#define HB_PET_ROLLOUT_TAIL_HPP
#include "observer.hpp"
#include <filesystem>
#include <fstream>
namespace petbridge {
/* Incomplete final lines are retained until newline. No unbounded getline. */
class RolloutTail {
  std::filesystem::path path_;
  Observer observer_;
  std::uint64_t file_id_=0,device_id_=0;
  bool identity_=false;
  std::string pending_;
  std::uintmax_t offset_ = 0;
  bool dropping_ = false;

public:
  RolloutTail(std::filesystem::path path, std::string title)
      : path_(std::move(path)), observer_(std::move(title)) {}
  bool poll();
  bool fresh(unsigned seconds)const;
  const Observer &observer() const { return observer_; }
};
} // namespace petbridge
#endif

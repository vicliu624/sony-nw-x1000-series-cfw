#ifndef HB_PET_CODEX_OBSERVER_HPP
#define HB_PET_CODEX_OBSERVER_HPP
#include <cstdint>
#include <string>
namespace petbridge {
enum class Activity {
  unknown,
  idle,
  working,
  waiting,
  completed,
  failed,
  interrupted
};
struct Snapshot {
  std::string thread_id, turn_id, title, summary, question;
  Activity activity = Activity::unknown;
  std::uint64_t revision = 0;
  bool question_pending = false;
};
class Observer {
  Snapshot snapshot_;

public:
  explicit Observer(std::string title = "Codex") : snapshot_{} {
    snapshot_.title = std::move(title);
  }
  bool consume(const std::string &line);
  const Snapshot &snapshot() const { return snapshot_; }
  std::string json() const;
  void reset();
};
const char *name(Activity);
std::string bounded_utf8(const std::string &, std::size_t bytes);
} // namespace petbridge
#endif

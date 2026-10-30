/* Read-only local rollout adapter, schema-dependent. No Codex command
 * execution, authentication reads, SQLite writes, thread resume or approval
 * responses. */
#include "observer.hpp"
#include "../../../../third_party/pet-json/json.hpp"
#include <utility>
namespace petbridge {
using Json = nlohmann::json;
const char *name(Activity a) {
  switch (a) {
  case Activity::idle:
    return "idle";
  case Activity::working:
    return "working";
  case Activity::waiting:
    return "waiting";
  case Activity::completed:
    return "completed";
  case Activity::failed:
    return "failed";
  case Activity::interrupted:
    return "interrupted";
  default:
    return "unknown";
  }
}
std::string bounded_utf8(const std::string &input, std::size_t limit) {
  std::string out;
  for (std::size_t i = 0; i < input.size() && out.size() < limit;) {
    unsigned char c = input[i];
    unsigned n = c < 0x80                 ? 1
                 : c >= 0xc2 && c <= 0xdf ? 2
                 : c >= 0xe0 && c <= 0xef ? 3
                 : c >= 0xf0 && c <= 0xf4 ? 4
                                          : 0;
    if (!n || i + n > input.size()) {
      i++;
      continue;
    }
    bool valid = true;
    for (unsigned j = 1; j < n; j++)
      if ((static_cast<unsigned char>(input[i + j]) & 0xc0) != 0x80)
        valid = false;
    if (!valid) {
      i++;
      continue;
    }
    if (out.size() + n > limit)
      break;
    if (c >= 32 || c == '\n')
      out.append(input, i, n);
    i += n;
  }
  return out;
}
static std::string string(const Json &j, const char *key) {
  auto i = j.find(key);
  return i != j.end() && i->is_string() ? i->get<std::string>() : std::string();
}
static bool human_reply(const std::string &text) {
  return !text.empty() &&
         text.find("<codex_internal_context") == std::string::npos &&
         text.find("<environment_context>") == std::string::npos;
}
bool Observer::consume(const std::string &line) {
  if (line.size() > 1024 * 1024)
    return false;
  auto root = Json::parse(line, nullptr, false);
  if (!root.is_object())
    return false;
  auto p = root.find("payload");
  if (p == root.end() || !p->is_object())
    return false;
  auto &payload = *p;
  auto kind = string(root, "type");
  auto type = string(payload, "type");
  auto thread = string(payload, "thread_id");
  if (!thread.empty() && !snapshot_.thread_id.empty() &&
      thread != snapshot_.thread_id)
    return false;
  bool changed = false;
  if (kind == "session_meta") {
    auto id = string(payload, "id");
    if (id.empty() || id.size() > 128)
      return false;
    if (!snapshot_.thread_id.empty() && snapshot_.thread_id != id)
      return false;
    if (snapshot_.thread_id.empty()) {
      snapshot_.thread_id = id;
      changed = true;
    }
  } else if (kind == "event_msg") {
    if (type == "task_started") {
      snapshot_.turn_id = bounded_utf8(string(payload, "turn_id"), 128);
      snapshot_.activity =
          snapshot_.question_pending ? Activity::waiting : Activity::working;
      snapshot_.summary.clear();
      changed = true;
    } else if (type == "task_complete") {
      auto id = string(payload, "turn_id");
      if (!snapshot_.turn_id.empty() && !id.empty() && id != snapshot_.turn_id)
        return false;
      snapshot_.activity =
          snapshot_.question_pending ? Activity::waiting : Activity::completed;
      snapshot_.summary =
          bounded_utf8(string(payload, "last_agent_message"), 765) +
          (string(payload, "last_agent_message").size() > 765 ? "…" : "");
      changed = true;
    } else if (type == "turn_aborted") {
      snapshot_.activity = Activity::interrupted;
      snapshot_.summary = bounded_utf8(string(payload, "reason"), 256);
      changed = true;
    } else if (type == "error" || type == "task_failed") {
      snapshot_.activity = Activity::failed;
      snapshot_.summary = bounded_utf8(string(payload, "message"), 256);
      changed = true;
    } else if (type == "item_completed") {
      auto item = payload.find("item");
      if (item != payload.end() && item->is_object() &&
          string(*item, "type") == "UserMessage") {
        auto content = item->find("content");
        std::string text = content == item->end() ? ""
                           : content->is_string() ? content->get<std::string>()
                                                  : content->dump();
        if (snapshot_.question_pending && human_reply(text)) {
          snapshot_.question_pending = false;
          snapshot_.question.clear();
          snapshot_.activity = Activity::working;
          changed = true;
        }
      }
    }
  } else if (kind == "response_item" &&
             (type == "custom_tool_call" || type == "function_call")) {
    auto tool = string(payload, "name");
    if (tool == "request_user_input" || tool == "request_user_input_async") {
      auto args = Json::parse(string(payload, "arguments"), nullptr, false);
      if (args.is_object()) {
        auto qs = args.find("questions");
        if (qs != args.end() && qs->is_array() && !qs->empty() &&
            (*qs)[0].is_object()) {
          std::string text;
          for (std::size_t i = 0; i < qs->size() && i < 3; i++) {
            if (!(*qs)[i].is_object())
              continue;
            auto question = string((*qs)[i], "question");
            if (question.empty())
              question = string((*qs)[i], "title");
            if (!text.empty())
              text += '\n';
            if (qs->size() > 1)
              text += std::to_string(i + 1) + ". ";
            text += question;
          }
          if (qs->size() > 3)
            text += "\n…";
          snapshot_.question =
              bounded_utf8(text, 765) + (text.size() > 765 ? "…" : "");
          snapshot_.question_pending = true;
          snapshot_.activity = Activity::waiting;
          changed = true;
        }
      }
    }
  }
  if (changed)
    snapshot_.revision++;
  return changed;
}
void Observer::reset() {
  auto title = snapshot_.title;
  snapshot_ = Snapshot{};
  snapshot_.title = std::move(title);
}
std::string Observer::json() const {
  Json j = {{"schema", 1},
            {"source", "codex-local-rollout"},
            {"thread", snapshot_.thread_id},
            {"turn", snapshot_.turn_id},
            {"title", snapshot_.title},
            {"state", name(snapshot_.activity)},
            {"revision", snapshot_.revision},
            {"summary", snapshot_.summary},
            {"question", snapshot_.question},
            {"can_approve", false}};
  return j.dump(-1, ' ', false, Json::error_handler_t::replace);
}
} // namespace petbridge

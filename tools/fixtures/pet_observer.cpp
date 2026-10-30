#include "../../runtime/apps/pet/computer/observer.hpp"
#include "../../runtime/apps/pet/computer/tail.hpp"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
using namespace petbridge;
int main(int argc, char **argv) {
  assert(argc == 2);
  Observer o;
  assert(!o.consume("not-json"));
  assert(!o.consume("[]"));
  assert(o.consume(R"({"type":"session_meta","payload":{"id":"selected"}})"));
  assert(!o.consume(R"({"type":"session_meta","payload":{"id":"another"}})"));
  assert(o.consume(
      R"({"type":"event_msg","payload":{"type":"task_started","turn_id":"turn1"}})"));
  assert(o.snapshot().activity == Activity::working);
  assert(!o.consume(
      R"({"type":"response_item","payload":{"type":"reasoning","text":"private reasoning"}})"));
  assert(o.consume(
      R"({"type":"response_item","payload":{"type":"custom_tool_call","name":"request_user_input_async","arguments":"{\"questions\":[{\"title\":\"需要你选择\"}]}"}})"));
  assert(o.snapshot().activity == Activity::waiting);
  assert(o.consume(
      R"({"type":"event_msg","payload":{"type":"task_complete","turn_id":"turn1","last_agent_message":"等待回答"}})"));
  assert(o.snapshot().activity == Activity::waiting);
  assert(!o.consume(
      R"({"type":"event_msg","payload":{"type":"task_complete","turn_id":"other","last_agent_message":"wrong"}})"));
  assert(!o.consume(
      R"({"type":"event_msg","payload":{"type":"item_completed","item":{"type":"UserMessage","content":"<codex_internal_context>continue</codex_internal_context>"}}})"));
  assert(o.snapshot().question_pending);
  assert(o.consume(
      R"({"type":"event_msg","payload":{"type":"item_completed","item":{"type":"UserMessage","content":"选择第一个"}}})"));
  assert(!o.snapshot().question_pending);
  assert(o.consume(
      R"({"type":"event_msg","payload":{"type":"task_complete","turn_id":"turn1","last_agent_message":"已经完成"}})"));
  assert(o.snapshot().activity == Activity::completed);
  assert(o.json().find("private reasoning") == std::string::npos);
  assert(o.json().find("已经完成") != std::string::npos);
  assert(o.consume(
      R"({"type":"event_msg","payload":{"type":"turn_aborted","turn_id":"turn1","reason":"interrupted"}})"));
  assert(o.snapshot().activity == Activity::interrupted);
  assert(bounded_utf8("中文abc", 4) == "中");
  o.reset();
  assert(o.snapshot().activity == Activity::unknown &&
         o.snapshot().thread_id.empty());
  auto folder = std::filesystem::u8path(argv[1]);
  std::filesystem::create_directories(folder);
  auto path = folder / "selected.jsonl", old = folder / "rotated.jsonl";
  std::filesystem::remove(old);
  {
    std::ofstream f(path);
    f << R"({"type":"session_meta","payload":{"id":"tail"}})" << '\n'
      << R"({"type":"event_msg","payload":{"type":"task_started","turn_id":"one"}})"
      << '\n';
  }
  petbridge::RolloutTail tail(path, "fixture");
  assert(tail.poll() &&
         tail.observer().snapshot().activity == Activity::working);
  {
    std::ofstream f(path, std::ios::app);
    f << R"({"type":"event_msg","payload":{"type":"task_complete","turn_id":"one"}})";
  }
  assert(tail.poll() &&
         tail.observer().snapshot().activity == Activity::working);
  {
    std::ofstream f(path, std::ios::app);
    f << '\n';
  }
  assert(tail.poll() &&
         tail.observer().snapshot().activity == Activity::completed);
  std::filesystem::rename(path, old);
  {
    std::ofstream f(path);
    f << R"({"type":"session_meta","payload":{"id":"tail"}})" << '\n'
      << R"({"type":"event_msg","payload":{"type":"task_started","turn_id":"two"}})"
      << '\n';
  }
  assert(tail.poll() && tail.observer().snapshot().turn_id == "two");
  {
    std::ofstream f(path, std::ios::app);
    f << std::string(1024 * 1024 + 1, 'x') << '\n'
      << R"({"type":"event_msg","payload":{"type":"task_complete","turn_id":"two"}})"
      << '\n';
  }
  assert(tail.poll() &&
         tail.observer().snapshot().activity == Activity::completed);
  std::filesystem::remove(path);
  std::filesystem::remove(old);
  std::cout
      << "Pet observer: real-event schema fixtures, question lifecycle, "
         "thread/turn isolation, no reasoning export and UTF8 limits passed\n";
}

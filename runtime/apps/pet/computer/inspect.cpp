#include "observer.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
int main(int argc, char **argv) {
  if (argc != 2) {
    std::cerr
        << "Read-only Codex observer: pet-inspect <selected-rollout.jsonl>\n";
    return 64;
  }
  std::ifstream input(std::filesystem::u8path(argv[1]));
  if (!input) {
    std::cerr << "Cannot read selected rollout\n";
    return 2;
  }
  petbridge::Observer observer;
  std::string line;
  while (std::getline(input, line))
    observer.consume(line);
  if (observer.snapshot().thread_id.empty()) {
    std::cerr << "Unsupported rollout: missing session identity\n";
    return 2;
  }
  std::cout << observer.json() << '\n';
  return 0;
}

#include "tail.hpp"
#include <chrono>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif
namespace petbridge {
bool RolloutTail::fresh(unsigned seconds) const {
  std::error_code ec;
  auto modified = std::filesystem::last_write_time(path_, ec);
  if (ec)
    return false;
  auto age = std::chrono::duration_cast<std::chrono::seconds>(
                 std::filesystem::file_time_type::clock::now() - modified)
                 .count();
  return age >= 0 && age <= seconds;
}
bool RolloutTail::poll() {
  std::uint64_t size, id, device;
#ifdef _WIN32
  HANDLE handle =
      CreateFileW(path_.c_str(), GENERIC_READ,
                  FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                  nullptr, OPEN_EXISTING, FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
  if (handle == INVALID_HANDLE_VALUE)
    return false;
  struct Guard {
    HANDLE h;
    ~Guard() { CloseHandle(h); }
  } guard{handle};
  BY_HANDLE_FILE_INFORMATION info;
  if (!GetFileInformationByHandle(handle, &info))
    return false;
  size = (static_cast<std::uint64_t>(info.nFileSizeHigh) << 32) |
         info.nFileSizeLow;
  id = (static_cast<std::uint64_t>(info.nFileIndexHigh) << 32) |
       info.nFileIndexLow;
  device = info.dwVolumeSerialNumber;
#else
  int handle = open(path_.c_str(), O_RDONLY | O_CLOEXEC);
  if (handle < 0)
    return false;
  struct Guard {
    int h;
    ~Guard() { close(h); }
  } guard{handle};
  struct stat info;
  if (fstat(handle, &info) || info.st_size < 0)
    return false;
  size = static_cast<std::uint64_t>(info.st_size);
  id = info.st_ino;
  device = info.st_dev;
#endif
  if (!identity_ || id != file_id_ || device != device_id_ || size < offset_) {
    offset_ = 0;
    pending_.clear();
    dropping_ = false;
    observer_.reset();
    identity_ = true;
    file_id_ = id;
    device_id_ = device;
  }
#ifdef _WIN32
  LARGE_INTEGER position;
  position.QuadPart = static_cast<LONGLONG>(offset_);
  if (!SetFilePointerEx(handle, position, nullptr, FILE_BEGIN))
    return false;
#else
  if (lseek(handle, static_cast<off_t>(offset_), SEEK_SET) < 0)
    return false;
#endif
  char bytes[8192];
  for (;;) {
#ifdef _WIN32
    DWORD count;
    if (!ReadFile(handle, bytes, sizeof bytes, &count, nullptr))
      return false;
    std::size_t used = count;
#else
    ssize_t count = read(handle, bytes, sizeof bytes);
    if (count < 0)
      return false;
    std::size_t used = static_cast<std::size_t>(count);
#endif
    if (!used)
      break;
    offset_ += used;
    for (std::size_t i = 0; i < used; i++) {
      char c = bytes[i];
      if (c == '\n') {
        if (!dropping_)
          observer_.consume(pending_);
        pending_.clear();
        dropping_ = false;
      } else if (!dropping_) {
        if (pending_.size() >= 1024 * 1024) {
          pending_.clear();
          dropping_ = true;
        } else
          pending_ += c;
      }
    }
  }
  return !observer_.snapshot().thread_id.empty();
}
} // namespace petbridge

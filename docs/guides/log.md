# Guide: `stormkit.log`

A small logging library: five severities, `std::format` syntax, named channels, and two sinks
(console and files). Setting it up takes one line.

```cpp
import std;
import stormkit;

using namespace stormkit;
```

## Hello, log

```cpp
auto logger = log::logger::create_logger_instance<log::console_logger>();

log::logger::ilog("server listening on port {}", port);
log::logger::wlog("configuration file not found, using defaults");
log::logger::elog("connection to {} lost: {}", host, error);
```

```
[ INFO    | 00 ] server listening on port 8080
[ WARNING | 00 ] configuration file not found, using defaults
[ ERROR   | 03 ] connection to db.local lost: Connection reset by peer
```

The number is the count of seconds since the logger was created. Lines are coloured by severity;
errors go to `stderr`, the rest to `stdout`.

## The logger is an object you keep

`create_logger_instance` returns the logger **by value**, and the logging system is alive exactly
as long as that object is:

```cpp
auto main(array_view<const string_view> args) -> int {
    auto logger = log::logger::create_logger_instance<log::console_logger>();   // registered here
    run();
    return 0;
}                                                                               // unregistered here
```

Two consequences:

- do not discard the return value — the logger would be destroyed on the same line;
- there is **one** logger per process. Creating a second one, or logging when there is none, is a
  contract violation.

When the logger has to live in a class member or be created in one function and used after it
returns, use `allocate_logger_instance<T>()`, which returns a `heap_ptr<T>`.

`log::logger::has_logger()` tells you whether logging is currently possible, which is useful in
library code that may run before the application has set things up.

## Severities

| Function | Severity | Shown by default |
| --- | --- | --- |
| `dlog` | `DEBUG` | no |
| `ilog` | `INFO` | yes |
| `wlog` | `WARNING` | yes |
| `elog` | `ERROR` | yes |
| `flog` | `FATAL` | yes |

`flog` marks a message as fatal; it does not stop the program. If you want to stop, follow it with
a contract or a return.

### Turning debug messages on

From the command line — call `parse_args` *before* creating the logger:

```cpp
auto main(array_view<const string_view> args) -> int {
    log::parse_args(args);          // looks for --debug or -d
    auto logger = log::logger::create_logger_instance<log::console_logger>();
    log::logger::dlog("only visible with --debug");
}
```

From code, by choosing the mask yourself:

```cpp
using log::severity;

auto logger = log::logger::create_logger_instance<log::console_logger>(severity::ERROR | severity::FATAL);

logger.set_severity_mask(severity::INFO | severity::WARNING | severity::ERROR | severity::FATAL | severity::DEBUG);
```

A message whose severity is masked out costs a flag test: its arguments are not formatted.

## Formatting

The format string is a `std::format` string, checked at compile time:

```cpp
log::logger::ilog("{:>8.2f} ms | {:#x} | {}", frame_time, address, name);
```

Anything formattable can be logged — including your own types, once they have a
[`format_as_fn` overload](core.md#making-your-types-formattable):

```cpp
struct player { string name; u32 score; };

template<typename CharT, typename FormatContext>
constexpr auto tag_invoke(format_as_fn<CharT>, const player& p, FormatContext& ctx) -> decltype(ctx.out()) {
    return std::format_to(ctx.out(), "{} ({} pts)", p.name, p.score);
}

log::logger::ilog("winner: {}", winner);
```

When the format string is only known at run time (loaded from a translation file, say), use the
`_runtime` variants: `log::logger::ilog_runtime(pattern, value)`.

## Modules: named channels

A *module* tags messages with a name, so that you can tell which part of the program is talking:

```cpp
using log::operator""_module;

inline constexpr auto NET = "net"_module;
inline constexpr auto GFX = log::module { "renderer" };

NET.ilog("connected to {}", host);
GFX.wlog("swapchain out of date, recreating");
```

```
[ INFO    | net | 01 ] connected to db.local
[ WARNING | renderer | 01 ] swapchain out of date, recreating
```

The name is a `string_view` into a literal, and `module` is a trivially copyable aggregate: declare
one `constexpr` module per subsystem and use it everywhere.

### One short name per file

Typing `NET.ilog` is fine; many code bases prefer a bare `ilog`. Declare forwarding functions next
to the module:

```cpp
namespace {
    constexpr auto LOG_MODULE = log::module { "net" };

    template<class... Args>
    auto ilog(std::format_string<Args...> fmt, Args&&... args) noexcept -> void { LOG_MODULE.ilog(fmt, std::forward<Args>(args)...); }
    template<class... Args>
    auto wlog(std::format_string<Args...> fmt, Args&&... args) noexcept -> void { LOG_MODULE.wlog(fmt, std::forward<Args>(args)...); }
    template<class... Args>
    auto elog(std::format_string<Args...> fmt, Args&&... args) noexcept -> void { LOG_MODULE.elog(fmt, std::forward<Args>(args)...); }
}
```

Having an `elog` in scope also enables the `LoggedTry…` family of error-propagation macros, which
log through it:

```cpp
#include <stormkit/core/tryx_expected.hpp>

auto load_level(const std::filesystem::path& path) noexcept -> system_result<level> {
    const auto bytes = LoggedTryX(io::readfile(path), std::format("cannot load level {}", path.string()));
    Return parse(bytes);
}
```

```
[ ERROR   | net | 02 ] cannot load level maps/e1m1.lvl
    > reason: No such file or directory
```

(StormKit used to ship `LOGGER("name")` macros that generated exactly these functions; the header
is currently absent from the tree. See the
[reference](../reference/log.md#logger-macros).)

## Logging to files

```cpp
auto logger = log::logger::create_logger_instance<log::file_logger>(std::filesystem::path { "logs" });

log::logger::ilog("starting");
NET.ilog("connected");
```

`file_logger` takes a **directory**. Messages without a module go to `logs/log.txt`; each module
gets its own `logs/<module>-log.txt`:

```
logs/log.txt        [INFO, 0] starting
logs/net-log.txt    [INFO, 0, net] connected
```

Every line is flushed immediately, so the files are complete even after a crash.

## Writing your own sink

Console and files cover most needs; for anything else (an in-game console, a network collector, a
test spy) derive from `logger`:

```cpp
class capture_logger final : public log::logger {
  public:
    using logger::logger;                                  // (start) and (start, mask)

    auto write(log::severity severity, const log::module& module, string_view message) noexcept -> void override {
        auto lock = std::unique_lock { mutex() };
        m_lines.emplace_back(std::format("{} {} {}", severity, module.name, message));
    }
    auto flush() noexcept -> void override {}

    auto lines() const noexcept -> const dynarray<string>& { return m_lines; }

  private:
    dynarray<string> m_lines;
};

auto logger = log::logger::create_logger_instance<capture_logger>();
```

`write` receives the fully formatted message and may be called from any thread — hence the lock.
To send messages to *several* destinations, write a sink that owns the others and forwards to
them.

## Thread safety

The logging functions can be called from any thread. Formatting happens on the calling thread
(into a thread-local buffer for short messages); only the final write is the sink's
responsibility.

Reference: [`stormkit.log`](../reference/log.md).

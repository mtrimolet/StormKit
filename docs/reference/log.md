# `stormkit.log` reference

```cpp
import stormkit.log;      // or: import stormkit;
```

| | |
| --- | --- |
| Library | `stormkit-log` |
| xmake option | `log` (default: on) |
| Depends on | `stormkit.core` |
| Namespace | `stormkit::log` |

---

## `severity`

```cpp
enum class severity : u8 {      // flag enum
    INFO    = 1 << 0,
    WARNING = 1 << 1,
    ERROR   = 1 << 2,
    FATAL   = 1 << 3,
    DEBUG   = 1 << 4,
};
```

Both the level of a message and, combined with `|`, a **mask** of the levels a logger lets through.
`as<string_view>(severity)` yields `"INFO"`, `"WARNING"`, `"ERROR"`, `"FATAL"` or `"DEBUG"`; the
type is therefore formattable.

## `parse_args`

```cpp
auto parse_args(array_view<const string_view> args) noexcept -> void;
```

Looks for `--debug` or `-d` in the program arguments. When present, loggers created afterwards
with the default mask also let `DEBUG` messages through. Call it **before** creating the logger.

---

## `logger`

```cpp
class logger {
  public:
    using clock_type = std::chrono::high_resolution_clock;

    explicit logger(clock_type::time_point start) noexcept;
    logger(clock_type::time_point start, severity mask) noexcept;
    virtual ~logger() noexcept;

    virtual auto write(severity severity, const module& module, string_view string) noexcept -> void = 0;
    virtual auto flush() noexcept -> void = 0;

    auto set_severity_mask(severity mask) noexcept -> void;
    auto severity_mask() const noexcept -> severity;
    auto start_time() const noexcept -> const clock_type::time_point&;
    auto mutex() noexcept -> std::mutex&;

    template<typename T, typename... Ts> static auto create_logger_instance(Ts&&... args) noexcept -> T;
    template<typename T, typename... Ts> static auto allocate_logger_instance(Ts&&... args) noexcept -> heap_ptr<T>;

    static auto has_logger() noexcept -> bool;
    static auto instance() noexcept -> logger&;

    // logging entry points, see below
};
```

The abstract sink **and** the static front-end of the logging system.

### Lifetime

There is at most **one logger per process**. Constructing a logger registers it as the global
instance; destroying it unregisters it.

| Member | Description |
| --- | --- |
| `create_logger_instance<T>(args...)` | Builds a `T` (a class derived from `logger`) passing the current time as the start time, followed by `args`. Returns it **by value**: keep the returned object alive for as long as you log. |
| `allocate_logger_instance<T>(args...)` | Same, on the heap. Use it when the logger must outlive the current scope or be stored in a member. |
| `has_logger()` | Whether a logger is currently registered. |
| `instance()` | The registered logger. Pre-condition: `has_logger()`. |

Creating a second logger while one is registered, or logging without one, is a contract violation.

### Severity mask

| Constructor | Mask |
| --- | --- |
| `logger(start)` | `INFO \| WARNING \| ERROR \| FATAL`, plus `DEBUG` when [`parse_args`](#parse_args) saw `--debug` |
| `logger(start, mask)` | exactly `mask` |

`set_severity_mask` changes it at run time. Messages whose severity is not in the mask are dropped
before any formatting takes place.

### Logging functions

All are `static`, `noexcept`, and forward to the registered instance.

```cpp
template<class... Ts> static auto log(severity, const module&, std::format_string<Ts...>, Ts&&...) -> void;
template<class... Ts> static auto log(severity,                std::format_string<Ts...>, Ts&&...) -> void;
template<class... Ts> static auto log_runtime(severity, const module&, string_view format, Ts&&...) -> void;
template<class... Ts> static auto log_runtime(severity,                string_view format, Ts&&...) -> void;
```

| Severity | Compile-time checked format | Run-time format string |
| --- | --- | --- |
| `DEBUG` | `dlog(fmt, args...)`, `dlog(module, fmt, args...)` | `dlog_runtime(...)` |
| `INFO` | `ilog(...)` | `ilog_runtime(...)` |
| `WARNING` | `wlog(...)` | `wlog_runtime(...)` |
| `ERROR` | `elog(...)` | `elog_runtime(...)` |
| `FATAL` | `flog(...)` | `flog_runtime(...)` |

- The format string follows `std::format`; anything formattable can be logged, including types
  made formattable through [`format_as_fn`](core-meta-string.md#stormkitcorestringformat).
- The `*_runtime` variants accept a format string that is not a constant expression
  (`std::vformat` semantics): a malformed string is a run-time error rather than a compile error.
- Messages of 64 characters or fewer are formatted into a thread-local stack buffer; longer ones
  allocate.
- `flog` only *labels* the message as fatal. It does not abort.

### Writing a custom sink

Derive from `logger`, forward the constructors, implement `write` and `flush`:

```cpp
class memory_logger final : public stormkit::log::logger {
  public:
    using logger::logger;
    auto write(stormkit::log::severity severity, const stormkit::log::module& module,
               stormkit::string_view message) noexcept -> void override {
        auto lock = std::unique_lock { mutex() };
        m_lines.emplace_back(std::format("[{}] {}: {}", severity, module.name, message));
    }
    auto flush() noexcept -> void override {}
  private:
    std::vector<std::string> m_lines;
};

auto logger = stormkit::log::logger::create_logger_instance<memory_logger>();
```

`write` receives the already formatted message. It can be called from any thread; `mutex()` is
provided for the sink's own use.

---

## `module`

```cpp
struct module {
    template<class... Ts> auto dlog(std::format_string<Ts...> fmt, Ts&&... args) const noexcept -> void;
    template<class... Ts> auto ilog(...) const noexcept -> void;
    template<class... Ts> auto wlog(...) const noexcept -> void;
    template<class... Ts> auto elog(...) const noexcept -> void;
    template<class... Ts> auto flog(...) const noexcept -> void;
    template<class... Ts> auto dlog_runtime(string_view fmt, Ts&&... args) const noexcept -> void;
    // ilog_runtime, wlog_runtime, elog_runtime, flog_runtime
    auto flush() const noexcept -> void;

    string_view name = "";
};

template<static_string str> constexpr auto operator""_module() noexcept -> module;
```

A **named channel**. A module is just a name; logging through it tags the message, which the
console sink prints and the file sink uses to pick the output file.

```cpp
using stormkit::log::operator""_module;

inline constexpr auto RENDERER = "renderer"_module;       // or: stormkit::log::module { "renderer" }

RENDERER.ilog("swapchain recreated ({}x{})", width, height);
stormkit::log::logger::wlog("audio"_module, "buffer underrun");
```

`name` is a `string_view`: it must refer to storage that outlives the module (a string literal).

<a id="logger-macros"></a>

### Free-function shortcuts

Earlier versions shipped `<stormkit/log/log_macro.hpp>` with `LOGGER("name")`,
`IN_MODULE_LOGGER("name")` and `NAMED_LOGGER(var, "name")`, which declared a module plus free
`dlog` / `ilog` / `wlog` / `elog` / `flog` functions bound to it. **That header is no longer in the
tree**, although the wsi, gpu and lua sources and several examples still use the macros.

Until it is restored, declare the equivalent yourself. This is also what the
[`LoggedTry*` macros](macros.md#try-statement-macros) need, since they call an unqualified `elog`:

```cpp
namespace {
    constexpr auto LOG_MODULE = stormkit::log::module { "my_app" };

    template<class... Args>
    auto ilog(std::format_string<Args...> fmt, Args&&... args) noexcept -> void {
        LOG_MODULE.ilog(fmt, std::forward<Args>(args)...);
    }
    template<class... Args>
    auto elog(std::format_string<Args...> fmt, Args&&... args) noexcept -> void {
        LOG_MODULE.elog(fmt, std::forward<Args>(args)...);
    }
    // dlog, wlog, flog likewise
}
```

Inside a module interface unit, use `inline constexpr` instead of an anonymous namespace.

---

## `console_logger`

```cpp
class console_logger final : public logger {
  public:
    explicit console_logger(clock_type::time_point start) noexcept;
    console_logger(clock_type::time_point start, severity mask) noexcept;
    auto write(severity severity, const module& module, string_view string) noexcept -> void override;
    auto flush() noexcept -> void override;
};
```

Writes one line per message, coloured by severity (ECMA-48 escape sequences):

```
[ INFO    | 03 ] window opened
[ ERROR   | renderer | 12 ] failed to allocate buffer
```

| Element | Meaning |
| --- | --- |
| first column | severity, left-aligned on 7 characters |
| module | present only when the message was logged through a named module |
| number | seconds elapsed since the logger was created |

`ERROR` and `FATAL` go to `stderr`, everything else to `stdout`.

| Severity | Colour (inverse video) |
| --- | --- |
| `INFO` | green |
| `WARNING` | magenta |
| `ERROR` | yellow |
| `FATAL` | red |
| `DEBUG` | cyan |

Non-copyable and non-movable.

## `file_logger`

```cpp
class file_logger final : public logger {
  public:
    file_logger(clock_type::time_point start, stdfs::path path) noexcept;
    file_logger(clock_type::time_point start, stdfs::path path, severity mask) noexcept;
    auto write(severity severity, const module& module, string_view string) noexcept -> void override;
    auto flush() noexcept -> void override;
};
```

Writes to text files inside the **directory** `path` (created when missing; a path that exists and
is not a directory is a contract violation).

| Message | File | Line format |
| --- | --- | --- |
| without module | `<path>/log.txt` | `[SEVERITY, seconds] message` |
| with module `m` | `<path>/m-log.txt` | `[SEVERITY, seconds, m] message` |

Each line is flushed as it is written. Non-copyable and non-movable.

```cpp
auto logger = stormkit::log::logger::create_logger_instance<stormkit::log::file_logger>(std::filesystem::path { "log/" });
```

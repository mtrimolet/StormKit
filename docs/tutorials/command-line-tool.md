# Tutorial: a command-line tool

**Libraries:** `main`, `core`, `log`

We will write `sksum`, a tool that prints a CRC-32 checksum for every file under a directory,
computing them on several threads. It is small, but it touches most of what a real program needs:
an entry point, argument parsing, file I/O, error propagation, concurrency and logging.

```console
> sksum assets --jobs=4
[ INFO    | sksum | 00 ] hashing 3 file(s) with 4 worker(s)
5f1c9a02  assets/logo.png
e4b7d310  assets/music/theme.ogg
[ ERROR   | sksum | 00 ] assets/locked.bin: Permission denied
2 file(s) hashed, 1 error(s)
```

## Setting up

The default configuration is enough (`core`, `log` and `main` are always or by default built).
Add a target, as in [Getting started](../getting-started.md#5-your-first-program):

```lua
-- examples/log/sksum/xmake.lua
target("sksum", function()
    add_rules("stormkit::example")
    add_files("src/*.cpp")
    set_group("examples/stormkit-log")
end)
```

Everything below goes in `examples/log/sksum/src/main.cpp`.

## Step 1 — the skeleton

```cpp
import std;
import stormkit;

#include <stormkit/core/tryx_expected.hpp>
#include <stormkit/main/main_macro.hpp>

using namespace stormkit;
using namespace std::literals;

namespace stdfs = std::filesystem;

namespace {
    constexpr auto LOG = log::module { "sksum" };
}

auto main(array_view<const string_view> args) -> int {
    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    LOG.ilog("{} argument(s)", std::ranges::size(args) - 1);
    return 0;
}
```

What is in place:

- `main_macro.hpp` lets us write a `main` that receives its arguments as a view of
  `string_view`s ([main guide](../guides/main.md)). It also means a crash prints a stack trace.
- `tryx_expected.hpp` provides the `TryX` macros we will use for error propagation.
- `LOG` is a [log module](../guides/log.md#modules-named-channels): every message sent through it
  is tagged `sksum`.
- `log::parse_args` makes `--debug` on the command line enable debug output.

## Step 2 — options

We accept a directory and an optional `--jobs=N`. Parsing can fail, so the parser returns an
`expected`; the error is a message for the user.

```cpp
struct options {
    stdfs::path root;
    u32         jobs = std::max(1u, std::thread::hardware_concurrency() / 2u);
};

auto parse_options(array_view<const string_view> args) noexcept -> std::expected<options, string> {
    auto out = options {};

    for (const auto arg : args.subspan(1)) {                  // skip the program name
        if (arg.starts_with("--jobs=")) {
            const auto value = to<u32>(arg.substr(7));        // system_result<u32>
            if (not value or *value == 0) return std::unexpected { std::format("invalid job count '{}'", arg.substr(7)) };
            out.jobs = *value;
        } else if (arg.starts_with("--")) {
            continue;                                         // someone else's option (e.g. --debug)
        } else {
            out.root = arg;
        }
    }

    if (out.root.empty()) return std::unexpected { "usage: sksum <directory> [--jobs=N] [--debug]"s };
    if (not stdfs::is_directory(out.root)) return std::unexpected { std::format("'{}' is not a directory", out.root.string()) };
    return out;
}
```

Two `core` tools are at work:

- [`to<u32>(text)`](../guides/core.md#to--a-conversion-that-may-fail) parses a number and returns
  an `expected` — malformed input is a normal outcome here, not a bug, so we use `to`, not `as`;
- the error type is simply a `string`. `std::expected` does not care, and neither does anything in
  StormKit.

## Step 3 — hashing one file

```cpp
auto checksum(const stdfs::path& path) noexcept -> system_result<hash32> {
    const auto bytes = TryX(io::readfile(path));
    Return hash::crc32(bytes);
}
```

- `io::readfile` returns `system_result<dynarray<byte>>`: the bytes, or the operating system's
  error.
- `TryX` unwraps the bytes, or makes `checksum` return that error immediately.
- `hash::crc32` takes any contiguous range of bytes and returns a `hash32`, a strong enum that
  cannot be confused with an ordinary integer.
- `Return` is spelled with a capital because of how `TryX` is implemented on some compilers
  ([details](../reference/macros.md#tryx-expression-macros)); use it whenever a function uses
  `TryX`.

The function is three lines and has no `if`. That is the point of the `expected` style: the happy
path reads top to bottom, and every failure is forwarded with its cause intact.

## Step 4 — finding the files

```cpp
auto list_files(const stdfs::path& root) noexcept -> dynarray<stdfs::path> {
    auto ec  = std::error_code {};
    auto out = dynarray<stdfs::path> {};

    for (auto it = stdfs::recursive_directory_iterator { root, stdfs::directory_options::skip_permission_denied, ec };
         not ec and it != stdfs::recursive_directory_iterator {};
         it.increment(ec)) {
        if (it->is_regular_file(ec)) out.emplace_back(it->path());
    }

    std::ranges::sort(out);
    return out;
}
```

Plain standard library: StormKit does not wrap what `<filesystem>` already does well. We use the
`std::error_code` overloads so that nothing throws through our `noexcept` functions, and sort so
that the output is deterministic.

## Step 5 — doing it in parallel

Reading and hashing files is independent work: ideal for a
[`thread_pool`](../guides/core.md#thread_pool).

```cpp
struct entry {
    stdfs::path                       path;
    std::future<system_result<hash32>> result;
};

auto hash_all(thread_pool& pool, const dynarray<stdfs::path>& files) noexcept -> dynarray<entry> {
    auto out = dynarray<entry> {};
    out.reserve(std::ranges::size(files));

    for (const auto& file : files)
        out.emplace_back(file, pool.post_task<system_result<hash32>>([file] noexcept { return checksum(file); }));

    return out;
}
```

- `post_task<T>` queues a callable and returns a `std::future<T>`. The return type is given
  explicitly because the pool stores type-erased closures.
- Each task captures its path **by value**: tasks may outlive the loop iteration.
- The result type is `system_result<hash32>` — errors cross the thread boundary as values, with no
  exception machinery.

## Step 6 — reporting

```cpp
auto report(dynarray<entry>& entries) noexcept -> u32 {
    auto errors = 0_u32;

    for (auto& [path, future] : entries) {
        const auto result = future.get();                      // waits for that task

        if (result) std::println("{:08x}  {}", as<underlying>(*result), path.generic_string());
        else {
            LOG.elog("{}: {}", path.generic_string(), result.error());
            ++errors;
        }
    }

    return errors;
}
```

- Futures are collected in submission order, so the output order does not depend on which thread
  finishes first.
- `as<underlying>(hash)` converts the strong enum to its integer for printing.
- `result.error()` is a `system_code`; formatting it yields the system's message
  (`Permission denied`, `The system cannot find the file specified.`).
- Checksums go to standard output with `std::println`, diagnostics go through the logger (errors
  on standard error). `sksum dir > sums.txt` therefore captures exactly the checksums.

## Step 7 — putting it together

```cpp
auto main(array_view<const string_view> args) -> int {
    using namespace stormkit::literals;

    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    const auto opts = parse_options(args);
    if (not opts) {
        LOG.elog("{}", opts.error());
        return 2;
    }

    const auto files = list_files(opts->root);
    if (std::ranges::empty(files)) {
        LOG.wlog("no file found under {}", opts->root.string());
        return 0;
    }

    auto pool = thread_pool { opts->jobs };
    pool.set_name("sksum");
    LOG.ilog("hashing {} file(s) with {} worker(s)", std::ranges::size(files), pool.worker_count());

    const auto start   = std::chrono::steady_clock::now();
    auto       entries = hash_all(pool, files);
    const auto errors  = report(entries);
    const auto elapsed = std::chrono::duration_cast<fsecond>(std::chrono::steady_clock::now() - start);

    const auto hashed  = std::ranges::size(files) - errors;
    const auto summary = std::format("{} file(s) hashed, {} error(s)", hashed, errors);
    std::println(get_stderr(), "{}", (errors == 0 ? GREEN_TEXT_STYLE : YELLOW_TEXT_STYLE) | summary);
    LOG.dlog("took {:.3f} s", elapsed.count());

    return errors == 0 ? 0 : 1;
}
```

The last touches:

- `pool.set_name("sksum")` names the worker threads (`sksum:0`, `sksum:1`, …) for debuggers and
  profilers.
- [`style | value`](../guides/core.md#styled-console-output) colours the summary; it goes to
  standard error so that it never pollutes redirected output.
- The timing is a debug message: invisible normally, shown with `--debug`.
- The exit status distinguishes success (`0`), partial failure (`1`) and bad usage (`2`).

## Build and run

```console
> xmake f && xmake b stormkit::examples::sksum
> xmake run stormkit::examples::sksum . --jobs=8 --debug
```

## What to take away

| Need | Tool | Where |
| --- | --- | --- |
| a portable `main` with parsed arguments | `main_macro.hpp` | [main guide](../guides/main.md) |
| "this can fail" in a signature | `system_result<T>`, `std::expected<T, E>` | [core guide](../guides/core.md#error-handling-with-expected) |
| forwarding errors | `TryX` / `Return` | [macros](../reference/macros.md) |
| parsing text | `to<T>` | [casts](../reference/core-typesafe.md#to) |
| reading files | `io::readfile` | [filesystem](../reference/core-foundation.md#stormkitcorefilesystem) |
| background work | `thread_pool::post_task` | [parallelism](../reference/core-containers.md#stormkitcoreparallelismthreadpool) |
| diagnostics | `log::module` | [log guide](../guides/log.md) |

## Going further

- Add a `--verify <file>` mode that reads a previous output with `io::readfile<io::open_mode::UTF8>`
  and [`split`](../guides/core.md#algorithms), and reports files whose checksum changed.
- Send the log to files with `log::file_logger` when a `--log-dir` option is given.
- Hash large files in chunks with `io::binary_file` and the `seed` parameter of `hash::crc32`,
  instead of loading them whole.

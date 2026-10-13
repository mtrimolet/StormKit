# Guide: `stormkit.main`

`stormkit-main` answers one question: *where does my program start?* — and gives the same answer
on every platform.

## The problem it solves

A portable C++ program does not have one entry point. Windows GUI applications start in
`WinMain`, macOS and iOS applications start inside the system's application object, and even on
Linux you receive `argc` / `argv` rather than something pleasant to use. Each also needs its own
bit of setup before useful work can begin.

`stormkit-main` owns the platform entry point, does that setup, and then calls a function you
write.

## Using it

```cpp
import std;
import stormkit;

#include <stormkit/main/main_macro.hpp>

using namespace stormkit;

auto main(array_view<const string_view> args) -> int {
    for (auto&& arg : args) std::println("{}", arg);
    return 0;
}
```

Three things to get right:

1. **Include `main_macro.hpp` after your imports and other includes**, and only in this file. The
   header is a single `#define main user_main`; anything named `main` after it gets renamed.
2. **Use exactly this signature**: `array_view<const string_view>` in, `int` out. The entry point
   declares `user_main` with it, and a mismatch is a link error.
3. **Link `stormkit-main`.** Inside the StormKit tree, the `stormkit::example` rule does it; in a
   consuming project, the `stormkit::application` rule does.

`args[0]` is the program name, as with `argv`.

## What happens before your code runs

| On | The entry point |
| --- | --- |
| every platform | converts `argv` to `string_view`s; installs the crash handlers that print a **stack trace** on `std::terminate` and on a segmentation fault; names the thread `stormkit:main_thread` |
| Windows | provides both `main` and `WinMain`, so the same code links as a console or a GUI program; attaches the standard streams to the parent console when there is one; switches the console to UTF-8 |
| macOS | sets up what an application bundle expects before handing over |

The crash handlers are the part you will notice: an uncaught exception or a failed contract ends
with a readable call stack instead of a bare abort.

## Passing the arguments on

Several libraries read options from the command line. Hand them the arguments first thing:

```cpp
auto main(array_view<const string_view> args) -> int {
    log::parse_args(args);      // --debug / -d
    wsi::parse_args(args);      // --x11 / --wayland (Linux)

    auto logger = log::logger::create_logger_instance<log::console_logger>();
    // …
}
```

Each `parse_args` ignores what it does not recognise, so the same list can go to all of them, and
to your own parsing.

## A pattern for fallible programs

`main` returns an `int`, but the interesting part of a program returns `expected`. Splitting the
two keeps error handling in one place:

```cpp
#include <stormkit/core/tryx_expected.hpp>
#include <stormkit/main/main_macro.hpp>

auto run(array_view<const string_view> args) noexcept -> system_result<void> {
    auto input = TryX(io::readfile(args[1]));
    DiscardTryX(io::writefile(args[2], input));
    Return {};
}

auto main(array_view<const string_view> args) -> int {
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    if (std::ranges::size(args) < 3) {
        log::logger::elog("usage: {} <input> <output>", args[0]);
        return 2;
    }

    if (const auto result = run(args); not result) {
        log::logger::elog("{}", result.error());
        return 1;
    }
    return 0;
}
```

## Doing without it

Nothing forces you to use `stormkit-main`. A classic `int main(int argc, char** argv)` works with
every other StormKit library; call `setup_signal_handler()` yourself if you want the stack traces.

The unit-test library goes the other way and builds on it: `stormkit-test` *defines* the
`user_main` for you. See the [test guide](test.md).

Reference: [`stormkit.main`](../reference/main-test.md#stormkitmain).

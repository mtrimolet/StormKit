# `stormkit.main` and `stormkit.test` reference

Two small static libraries that own the program entry point.

---

## `stormkit.main`

| | |
| --- | --- |
| Library | `stormkit-main` (always static, always built) |
| Depends on | `stormkit.core` |
| Header | `<stormkit/main/main_macro.hpp>` |

The module `stormkit.main` exports nothing. The library provides the **platform entry point** and
calls a function you define:

```cpp
auto user_main(stormkit::array_view<const stormkit::string_view> args) -> int;
```

`<stormkit/main/main_macro.hpp>` consists of `#define main user_main`, so that you can keep writing
`main`:

```cpp
import std;
import stormkit;

#include <stormkit/main/main_macro.hpp>   // after the imports, before your main

using namespace stormkit;

auto main(array_view<const string_view> args) -> int {
    std::println("{} argument(s)", std::ranges::size(args));
    return 0;
}
```

What the entry point does before calling you:

| Step | All platforms | Windows | macOS |
| --- | --- | --- | --- |
| Collects `argv` into `string_view`s (`args[0]` is the program name) | ✔ | ✔ | ✔ |
| [`setup_signal_handler()`](core-containers.md#stormkitcoresignal_handler) — stack trace on crash | ✔ | ✔ | ✔ |
| Names the thread `stormkit:main_thread` | ✔ | ✔ | ✔ |
| Attaches `stdin` / `stdout` / `stderr` to the parent console, switches it to UTF-8 | | ✔ | |
| Provides both `main` and `WinMain` (console and GUI subsystems) | | ✔ | |
| Sets up the application bundle context | | | ✔ |

Notes:

- The macro renames **every** `main` token that follows it in the translation unit. Include it
  last, and only in the file that defines the entry point.
- The return type must be `int` (`i32`) and the parameter exactly
  `array_view<const string_view>`; the entry point declares `user_main` with that signature.
- Linking: with xmake, the `stormkit::example` / `stormkit::application` rules add the dependency;
  otherwise link `stormkit-main` in addition to the libraries you use.
- Using `stormkit-main` is optional. A regular `int main(int, char**)` works; you just do not get
  the setup above.

---

## `stormkit.test`

| | |
| --- | --- |
| Library | `stormkit-test` (always static; built when the `tests` option is on) |
| Depends on | `stormkit.core`, `stormkit-main` |
| Header | `<stormkit/test/test_macro.hpp>` |
| Namespace | `test` (global, **not** `stormkit::test`) |

A minimal unit-test framework. The library also contains the `main` of the test executable.

```cpp
namespace test {
    struct test_func {
        string                name;
        std::function<void()> func;
    };

    struct test_suite {
        test_suite(string&& name, dynarray<test_func>&& tests,
                   source_location_arg location = std::source_location::current()) noexcept;
    };

    auto expects(bool cond, string_view message,
                 source_location_arg location = std::source_location::current()) noexcept;

    auto parse_args(array_view<const string_view> args) noexcept -> void;
    auto run_tests() noexcept -> int;

    struct test_suite_holder { /* registry entry: name, tests, location, run_test(), run_tests() */ };
}
```

| Name | Description |
| --- | --- |
| `test_suite` | Constructing one **registers** a named suite and its tests in a global registry. Declare it as a namespace-scope object so that registration happens during static initialisation. |
| `test_func` | A test: a name and a callable. |
| `expects(cond, message)` | Records a failure for the running test when `cond` is false. It does **not** abort or throw: the test keeps running. |
| `EXPECTS(expr)` | Macro from `test_macro.hpp`: `test::expects(expr, "expr")`. |
| `parse_args(args)` | Reads the command line options below. |
| `run_tests()` | Runs the selected tests; returns `0` when all passed, `-1` otherwise. |

### Writing tests

```cpp
import std;
import stormkit.core;
import stormkit.test;

#include <stormkit/test/test_macro.hpp>

using namespace stormkit::core;

namespace {
    auto _ = test::test_suite {
        "core.string",
        {
          { "split.basic",
            [] static noexcept {
                const auto parts = split("a,b,c", ",");
                EXPECTS(std::ranges::size(parts) == 3);
                EXPECTS(parts[1] == "b");
            } },
          { "to_lower.ascii",
            [] static noexcept { EXPECTS(to_lower("ABC") == "abc"); } },
        }
    };
} // namespace
```

- Do not define `main`; the library supplies it (`test::parse_args(args); return test::run_tests();`).
- Wrap expressions containing a top-level comma in parentheses: `EXPECTS((a[1, 2] == 2));`.
- `test_macro.hpp` and `contract_macro.hpp` both define `EXPECTS`; never include both.

### Command line

| Option | Effect |
| --- | --- |
| `--verbose`, `-v` | Prints each test name, its result, the failing expression and its line. |
| `--plain`, `-p` | Disables the ✔ / ❌ glyphs in the summary. |
| `--test_name=<name>` | Runs only the test with that name (searched across all suites). |

Default output is one line per suite:

```
Running test suite core.string (2 tests)
✔ 2 test PASSED
```

### xmake integration

With the `tests` option enabled, every `tests/<module>/**.cpp` becomes a binary target
`stormkit::tests::<module>-<file>` linked against `stormkit::test` and `stormkit::<module>`.
The build script scans the file for the suite name and the test names and registers each one as an
xmake test case (run with `--test_name=<name>`), so:

```console
> xmake f --tests=y
> xmake b
> xmake test
```

Test cases are named `<suite>/<test>` and grouped by suite (`xmake test -g <suite>`).

Because detection is textual, keep the `test_suite { "name", { { "test", ...` layout shown above,
and avoid `<` and `>` in test names (they are replaced by `_`).

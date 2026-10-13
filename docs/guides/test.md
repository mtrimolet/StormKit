# Guide: `stormkit.test`

StormKit tests itself with a deliberately tiny framework: suites, tests, and one check. This guide
shows how to write tests with it, how they are built and run, and where its limits are.

Enable it with `--tests=y`.

## A test file

```cpp
import std;
import stormkit.core;
import stormkit.test;

#include <stormkit/test/test_macro.hpp>

using namespace stormkit::core;

namespace {
    auto _ = test::test_suite {
        "core.string.algorithms",
        {
          { "split.on_separator",
            [] static noexcept {
                const auto parts = split("a,b,c", ",");

                EXPECTS(std::ranges::size(parts) == 3);
                EXPECTS(parts[0] == "a");
                EXPECTS(parts[2] == "c");
            } },
          { "to_upper.ascii",
            [] static noexcept { EXPECTS(to_upper("stormkit") == "STORMKIT"); } },
        }
    };
} // namespace
```

That is the whole anatomy:

- a **suite** is a `test::test_suite` object with a name and a list of tests. Constructing it
  registers it, so it is declared as a namespace-scope variable — the name `_` signals that it is
  never referred to;
- a **test** is a name and a callable taking nothing;
- **`EXPECTS(expression)`** records a failure when the expression is false.

There is no `main` in a test file: `stormkit-test` provides it.

The framework lives in the global namespace `test`, not in `stormkit::test`.

## How `EXPECTS` behaves

`EXPECTS` does **not** stop the test. A failing check marks the test as failed and execution
continues with the next line:

```cpp
[] static noexcept {
    const auto result = parse("12");

    EXPECTS(result.has_value());       // if this fails…
    EXPECTS(*result == 12);            // …this still runs, on an empty expected
}
```

Guard the lines that would be undefined behaviour:

```cpp
EXPECTS(result.has_value());
if (not result) return;
EXPECTS(*result == 12);
```

Two more things to know about the macro:

- the preprocessor splits arguments on commas, so wrap any expression that contains a top-level
  comma in parentheses: `EXPECTS((matrix[1, 2] == 5));`, `EXPECTS((std::pair { 1, 2 } == value));`
- it shares its name with the contract macro of `<stormkit/core/contract_macro.hpp>`. A file
  includes one or the other, never both.

## Compile-time checks

Much of StormKit is `constexpr`, and the cheapest test is one the compiler runs:

```cpp
static_assert(as<u8>(200) == 200);
static_assert(meta::is<decltype(as<short>(2)), short>);
static_assert(math::determinant(math::imat2 { 1, 2, 3, 4 }) == -2);
```

Put these at namespace scope in the test file. They cost nothing at run time and fail the build
with the exact expression.

## Building and running

With `--tests=y`, the build turns **each file** under `tests/<library>/` into its own executable,
linked against the test library and that library:

```
tests/core/typesafe/flags.cpp     →  target stormkit::tests::core-flags
tests/math/linear-vector.cpp      →  target stormkit::tests::math-linear-vector
```

```console
> xmake f --tests=y
> xmake b
> xmake test
```

`xmake test` runs every test case separately: the build script reads each file, finds the suite
name and the test names, and registers them with xmake one by one (each is the test executable
launched with `--test_name=<name>`). The report is therefore per test, named `<suite>/<test>`.

Because that discovery is textual, follow the layout shown at the top: the suite name as a string
literal right after `test_suite {`, each test as `{ "name", callable }`.

### Running a test binary by hand

Each executable can be run directly, which is what you want under a debugger:

```console
> xmake run stormkit::tests::core-algorithms --verbose
Running test suite core.string.algorithms (2 tests)
   > file: tests/core/string/algorithms.cpp
     running test split.on_separator
     Passed
     running test to_upper.ascii
     Passed
✔ 2 test PASSED
```

(Here for the file at the top of this page, saved as `tests/core/string/algorithms.cpp`.)

| Option | Effect |
| --- | --- |
| `-v`, `--verbose` | names each test; on failure prints the expression and its line |
| `-p`, `--plain` | no ✔ / ❌ glyphs, for terminals and logs that cannot show them |
| `--test_name=<name>` | runs a single test |

The process exits with `0` when everything passed and a non-zero status otherwise.

Without `--verbose` a failure only shows up in the counts — pass the flag to see *which*
expectation failed.

## Adding tests for a library

1. Create `tests/<library>/<something>.cpp`. Any sub-directory layout works; the target name is
   derived from the file name, so keep file names unique within a library.
2. Import what you test and `stormkit.test`, include `test_macro.hpp`.
3. Declare one suite per file.
4. Re-run `xmake f` so the new file is picked up, then `xmake b && xmake test`.

Tests for an optional library are only built when that library is enabled.

## Organising suites

Names are free-form; StormKit's own tests use dotted paths that mirror the module
(`core.parallelism`, `core.math.linear.vector`) and prefix test names with the feature
(`locked.write`, `linear.vector.add`). A consistent scheme pays off with `--test_name` and with
xmake's group filter (`xmake test -g <suite>`).

Tests in a suite share nothing but the file. For common setup, write a helper function and call it
from each test; there are no fixtures.

## Testing concurrent code

A test is an ordinary function: start threads, wait, check.

```cpp
{ "locked.write",
  [] static noexcept {
      static constexpr auto ITERATIONS = 100'000;
      auto counter = locked { 0 };

      const auto work = [&counter] noexcept {
          for (auto i = 0; i != ITERATIONS; ++i) counter.write([](auto& value) static noexcept { value += 1; });
      };

      auto first  = std::async(std::launch::async, work);
      auto second = std::async(std::launch::async, work);
      first.wait();
      second.wait();

      EXPECTS(counter.unsafe() == ITERATIONS * 2);
  } },
```

Building with `--sanitizers=y` makes such tests far more valuable.

## What it does not do

The framework is intentionally small. It has no test fixtures, no parameterised tests, no
matchers, no death tests, and `EXPECTS` reports the expression text but not the values of its
operands. For value output, log them yourself before the check, or compare in a way that makes the
expression self-explanatory.

If you outgrow it, nothing in StormKit depends on it: any test framework that can link a C++
module library will do.

The [testing tutorial](../tutorials/testing.md) applies all this to a small library of your own.

Reference: [`stormkit.test`](../reference/main-test.md#stormkittest).

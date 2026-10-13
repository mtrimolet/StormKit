# Tutorial: testing your own code

**Libraries:** `core`, `math`, `test` (and `main`)

We will write a small piece of library code — an axis-aligned grid with a couple of algorithms —
and test it three ways: at compile time, with unit tests, and through contract checks. Then we
wire the tests into xmake so that `xmake test` runs them.

The subject is deliberately simple; the point is the workflow.

## Setting up

```console
> xmake f --tests=y
```

The test framework is in the global namespace `test`; the build turns every `.cpp` under
`tests/<library>/` into a test executable linked against `stormkit::test` and
`stormkit::<library>` ([guide](../guides/test.md#building-and-running)).

We will put the code under test directly in the test file to keep the tutorial self-contained. In
a real project it would live in its own module, imported by the test.

Create `tests/math/grid.cpp`:

```cpp
import std;
import stormkit.core;
import stormkit.math;
import stormkit.test;

#include <stormkit/test/test_macro.hpp>

using namespace stormkit;
using namespace stormkit::literals;
```

## Step 1 — the code under test

A fixed-size 2D grid of cells, addressed with `math` types:

```cpp
template<typename T>
class grid {
  public:
    constexpr grid(const math::uextent2& extent, const T& fill = T {})
        : m_extent { extent }, m_cells(as<usize>(extent.width) * extent.height, fill) {
        expects(extent.width > 0 and extent.height > 0, "a grid cannot be empty");
    }

    constexpr auto extent() const noexcept -> const math::uextent2& { return m_extent; }

    constexpr auto contains(const math::ivec2& cell) const noexcept -> bool {
        return cell.x() >= 0 and cell.y() >= 0 and is(cell.x(), m_extent.width - 1u) or
               (cell.x() >= 0 and cell.y() >= 0 and as<u32>(cell.x()) < m_extent.width and as<u32>(cell.y()) < m_extent.height);
    }

    template<typename Self>
    constexpr auto at(this Self& self, const math::ivec2& cell) noexcept -> meta::forward_const_to<Self, T>& {
        expects(self.contains(cell), "cell out of bounds");
        return self.m_cells[as<usize>(cell.y()) * self.m_extent.width + as<usize>(cell.x())];
    }

    constexpr auto count(const T& value) const noexcept -> usize { return as<usize>(std::ranges::count(m_cells, value)); }

    constexpr auto neighbours(const math::ivec2& cell) const noexcept -> dynarray<math::ivec2> {
        constexpr auto OFFSETS = std::array { math::ivec2 { 0, -1 }, math::ivec2 { 1, 0 }, math::ivec2 { 0, 1 }, math::ivec2 { -1, 0 } };

        auto out = dynarray<math::ivec2> {};
        for (const auto& offset : OFFSETS)
            if (const auto next = add(cell, offset); contains(next)) out.emplace_back(next);
        return out;
    }

  private:
    math::uextent2 m_extent;
    dynarray<T>    m_cells;
};
```

`contains` has a bug: the first half of its `or` is a leftover that makes the function return
`true` for any cell in the last column, whatever its row. We leave it in and let the tests find
it.

Elsewhere the class shows the StormKit idioms a test should exercise:

- pre-conditions stated with `expects`;
- `as` for every signed/unsigned conversion;
- a deducing-`this` accessor (`at`) that returns `T&` or `const T&` as appropriate;
- `math` vectors and extents in the interface, `add` for vector arithmetic.

## Step 2 — compile-time tests

The class is `constexpr`, so the cheapest tests run inside the compiler. Put them right after the
class:

```cpp
static_assert(grid<int> { { 4u, 3u } }.extent() == math::uextent2 { 4u, 3u });
static_assert(grid<int> { { 4u, 3u }, 7 }.count(7) == 12);

static_assert([] {
    auto g = grid<int> { { 4u, 3u } };
    g.at({ 1, 2 }) = 5;
    return g.at({ 1, 2 }) == 5 and g.count(5) == 1 and g.count(0) == 11;
}());

static_assert([] {
    const auto g = grid<int> { { 4u, 3u } };
    return std::ranges::size(g.neighbours({ 0, 0 })) == 2;           // a corner has two neighbours
}());
```

An immediately-invoked `constexpr` lambda is the trick for multi-statement compile-time tests.

Build (`xmake b`): everything passes. A corner has two neighbours, and none of these cases goes
near the last column, so the bug is still hiding. Compile-time tests only prove what they
exercise. Add a case that does:

```cpp
static_assert(not grid<int> { { 4u, 3u } }.contains({ 3, 7 }));      // column 3 exists, row 7 does not
```

Now the build **fails**, on that line, with the expression in the error message: a bug caught
before the program ever ran.

Fix `contains`:

```cpp
constexpr auto contains(const math::ivec2& cell) const noexcept -> bool {
    return cell.x() >= 0 and cell.y() >= 0 and as<u32>(cell.x()) < m_extent.width and as<u32>(cell.y()) < m_extent.height;
}
```

The negative checks come first on purpose: `as<u32>` of a negative number is a contract violation,
and short-circuit evaluation guarantees we never get there.

## Step 3 — unit tests

Not everything can or should run at compile time, and run-time tests give better reporting when
there are many cases. Add a suite:

```cpp
namespace {
    auto _ = test::test_suite {
        "math.grid",
        {
          { "grid.contains.inside",
            [] static noexcept {
                const auto g = grid<int> { { 4u, 3u } };

                EXPECTS(g.contains({ 0, 0 }));
                EXPECTS(g.contains({ 3, 2 }));
            } },
          { "grid.contains.outside",
            [] static noexcept {
                const auto g = grid<int> { { 4u, 3u } };

                EXPECTS(not g.contains({ 4, 0 }));
                EXPECTS(not g.contains({ 0, 3 }));
                EXPECTS(not g.contains({ 3, 7 }));
                EXPECTS(not g.contains({ -1, 0 }));
                EXPECTS(not g.contains({ 0, -1 }));
            } },
          { "grid.at.read_write",
            [] static noexcept {
                auto g = grid<int> { { 4u, 3u } };
                g.at({ 2, 1 }) = 42;

                EXPECTS(g.at({ 2, 1 }) == 42);
                EXPECTS(g.count(42) == 1);

                const auto& cg = g;
                static_assert(meta::is<decltype(cg.at({ 0, 0 })), const int&>);
                static_assert(meta::is<decltype(g.at({ 0, 0 })), int&>);
            } },
          { "grid.neighbours.counts",
            [] static noexcept {
                const auto g = grid<int> { { 4u, 3u } };

                EXPECTS(std::ranges::size(g.neighbours({ 0, 0 })) == 2);      // corner
                EXPECTS(std::ranges::size(g.neighbours({ 1, 0 })) == 3);      // edge
                EXPECTS(std::ranges::size(g.neighbours({ 1, 1 })) == 4);      // interior
            } },
          { "grid.neighbours.are_adjacent",
            [] static noexcept {
                const auto g      = grid<int> { { 4u, 3u } };
                const auto origin = math::ivec2 { 2, 1 };

                for (const auto& n : g.neighbours(origin)) {
                    const auto delta = sub(n, origin);
                    EXPECTS(g.contains(n));
                    EXPECTS(dot(delta, delta) == 1);                        // exactly one step away
                }
            } },
        }
    };
} // namespace
```

Observations:

- **One behaviour per test, named for it.** `grid.contains.outside` tells you what broke without
  opening the file.
- **Type-level expectations sit next to value-level ones.** The two `static_assert`s in
  `grid.at.read_write` check that const-ness propagates — a property no run-time check can see.
- **Property-style checks** (`are_adjacent`) state a rule for every result rather than listing
  expected values; they survive changes to iteration order.
- **`math` does the arithmetic in the test too**: `sub`, `dot`.
- Expressions with braces and commas inside `EXPECTS(...)` are fine here because every comma is
  nested inside parentheses of a call. A comma at the top level of the macro argument needs an
  extra pair: `EXPECTS((a, b));`.

## Step 4 — run them

```console
> xmake f --tests=y        # picks up the new file
> xmake b
> xmake test
```

The build script found the suite name and the five test names in the file and registered each as
its own test case, `math.grid/grid.contains.inside` and so on.

To iterate on one file, run its executable directly:

```console
> xmake run stormkit::tests::math-grid --verbose
Running test suite math.grid (5 tests)
   > file: tests/math/grid.cpp
     running test grid.contains.inside
     Passed
     ...
✔ 5 test PASSED
```

Put the bug back in `contains` and run again with `--verbose`; the failing expectation is printed
with its line:

```
     running test grid.contains.outside
FAILURE on expression "not g.contains({ 3, 7 })"
          > line: <line of the EXPECTS>
     Not Passed
```

Remember that `EXPECTS` does not stop the test: the remaining checks of `grid.contains.outside`
still ran, which is why only the one wrong case is reported.

A single test: `xmake run stormkit::tests::math-grid --test_name=grid.contains.outside --verbose`.

## Step 5 — what about the contracts?

`at` has a pre-condition. Calling `g.at({ 9, 9 })` does not return an error: it terminates the
program with a report naming the call site. That is by design — it is a bug in the caller, and the
contract is what catches it during development.

Can the *presence* of the contract be tested? Not directly: the framework has no "expect
termination" check, and a `static_assert` cannot assert that an expression fails to compile. What
can and should be tested is the **predicate the contract relies on** — here `contains`, which the
suite above covers from every side.

That division is the general pattern:

- test the **decision** (`contains`) with unit tests;
- let the **contract** (`expects(self.contains(cell))`) enforce it, everywhere, in every build.

## Step 6 — tests in your own project

Inside the StormKit tree nothing more is needed: dropping the file under `tests/math/` was enough.

In a project of your own, three things have to be true of the test executable:

1. it links `stormkit-test`, which provides the `main` that parses the options and runs the
   suites, and `stormkit-main`, which provides the platform entry point;
2. it links the libraries under test;
3. xmake knows what to run. `add_tests` declares a test case; a non-zero exit status marks it as
   failed.

```lua
target("grid-tests", function()
    set_kind("binary")
    set_languages("cxxlatest", "clatest")
    -- link stormkit-test, stormkit-main and the libraries under test here, the way your project
    -- consumes StormKit (see the build reference)
    add_files("tests/grid.cpp")

    add_tests("all")
    add_tests("contains.outside", { runargs = "--test_name=grid.contains.outside" })
end)
```

Then `xmake test` in your project, and the same command in CI.

## What to take away

| Level | Tool | Catches |
| --- | --- | --- |
| compile time | `static_assert` on `constexpr` code | logic errors, type errors — with zero run-time cost |
| unit | `test::test_suite`, `EXPECTS` | behaviour, case by case, with per-test reporting |
| always-on | `expects` / `ensures` | misuse, at the call site, in every build |

Writing the code `constexpr` and with contracts from the start is what makes the first and third
rows available at all.

## Going further

- Build with `--sanitizers=y`: the same tests then also detect out-of-bounds accesses and
  undefined behaviour.
- Move `grid` into a module of its own (`grid.cppm`) and `import` it from the test; nothing else
  changes.
- Add a flood-fill algorithm on top of `neighbours` and test it with property checks: the filled
  region is connected, contains the start cell, and never crosses a wall.

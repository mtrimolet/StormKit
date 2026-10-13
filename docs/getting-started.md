# Getting started

This page takes you from a fresh checkout to a running program that uses StormKit.

## 1. Prerequisites

| Tool | Notes |
| --- | --- |
| [xmake](https://xmake.io) ≥ 3.0.0 | the only build system supported |
| A C++23/26 compiler with `import std;` | Clang with libc++ is what CI exercises on every platform; clang-cl with the MSVC STL is exercised on Windows |
| git | the build embeds the current branch and commit |
| a Vulkan driver | only for the `gpu` library |

You do not need to install any library by hand: xmake downloads and builds the third-party
dependencies the first time you configure.

StormKit relies on recent language features (deducing `this`, `= delete("reason")`, static
`operator()`, multi-dimensional `operator[]`, pack indexing). Use the newest compiler you can.

## 2. Get the sources

```console
> git clone https://github.com/TapzCrew/StormKit.git
> cd StormKit
```

## 3. Configure

```console
> xmake f -m release --toolchain=llvm --runtimes=c++_static
```

Answer `y` when xmake offers to install the missing packages.

By default this builds `core`, `main`, `math`, `log` and `image`, as static libraries, plus the
examples of those libraries. Add options to get more:

```console
> xmake f -m debug --toolchain=llvm --runtimes=c++_static --wsi=y --gpu=y --entities=y --lua=y --tests=y
```

| Option | What it adds |
| --- | --- |
| `--wsi=y` | windowing (needs `log`) |
| `--gpu=y` | Vulkan rendering (needs `log`, `image`, `wsi`) |
| `--entities=y` | the ECS |
| `--lua=y` | Luau scripting (needs `log`) |
| `--tests=y` | the test library and the unit tests |
| `-k shared` | shared libraries instead of static |

The full list is in the [build reference](reference/build.md#configuration). `xmake f --menu`
shows the same options interactively.

## 4. Build

```console
> xmake b
```

The first build compiles the standard library module and every dependency; later builds are
incremental. Run an example to check everything works:

```console
> xmake run stormkit::examples::console-logger
[ INFO    | 00 ] This is an information
[ DEBUG   | 00 ] This is a debug information
...
```

## 5. Your first program

The quickest way to experiment is to add a target next to the existing examples. Example targets
are declared inside the xmake namespaces `stormkit` and `examples`, hence the
`stormkit::examples::` prefix on the command line.

Create `examples/log/hello/xmake.lua`:

```lua
target("hello", function()
    add_rules("stormkit::example")
    add_files("src/*.cpp")
    set_group("examples/stormkit-log")
end)
```

and `examples/log/hello/src/main.cpp`:

```cpp
import std;
import stormkit;

#include <stormkit/main/main_macro.hpp>

using namespace stormkit;

auto main(array_view<const string_view> args) -> int {
    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    const auto size = math::uextent2 { 1920u, 1080u };
    log::logger::ilog("StormKit {} on {}", STORMKIT_VERSION, STORMKIT_GIT_BRANCH);
    log::logger::ilog("a {} screen has {} pixels", size, size.width * size.height);

    for (auto i : range(1uz, std::ranges::size(args))) log::logger::dlog("argument {}: {}", i, args[i]);

    return 0;
}
```

Then:

```console
> xmake f           # re-scan the project so the new target is picked up
> xmake b stormkit::examples::hello
> xmake run stormkit::examples::hello one two --debug
```

What each line is doing:

| Line | Meaning |
| --- | --- |
| `import std;` | the standard library, as a module |
| `import stormkit;` | every StormKit library that was enabled at configure time |
| `#include <stormkit/main/main_macro.hpp>` | renames your `main` so that StormKit's entry point can call it with a ready-made argument list — see the [main guide](guides/main.md) |
| `using namespace stormkit;` | `core` lives in an inline namespace, so this brings `u32`, `array_view`, `range`, … into scope, and makes the other libraries reachable as `log::`, `math::`, … |
| `log::parse_args(args)` | lets `--debug` on the command line enable debug messages |
| `create_logger_instance<console_logger>()` | installs the process-wide logger; it lives as long as the returned object |

## 6. Importing only what you need

`import stormkit;` is the convenient umbrella. Each library, and each part of `core`, is also a
module of its own:

```cpp
import stormkit.core;                    // all of core
import stormkit.core.typesafe;           // only the casts, ref_ptr, flags, …
import stormkit.math;
import stormkit.log;
```

Smaller imports do not change what you link against; they only narrow what is visible.

## 7. Headers you will still include

Modules cannot export macros. A few headers therefore remain:

| Header | Gives you |
| --- | --- |
| `<stormkit/main/main_macro.hpp>` | the `main` rename |
| `<stormkit/core/contract_macro.hpp>` | `EXPECTS`, `ENSURES`, `ASSERT` |
| `<stormkit/core/try_expected.hpp>`, `<stormkit/core/tryx_expected.hpp>` | the `Try…` early-return macros |
| `<stormkit/test/test_macro.hpp>` | `EXPECTS` for tests |

In a module unit they go in the global module fragment (between `module;` and
`export module …;`); in a plain source file, anywhere before use. See the
[macro reference](reference/macros.md).

## 8. Using StormKit from another project

StormKit's build scripts locate their sources through `$(projectdir)`, so StormKit has to be the
**root** xmake project when it is built: it cannot simply be pulled into another project with
`includes()`.

The intended route is therefore the **package** one. `xmake install` (or `xmake package`) produces
the libraries, the module interface files and the headers, and the `stormkit::application` /
`stormkit::library` rules are written for projects that consume an xmake package named `stormkit`,
selecting libraries through the `stormkit.components` target value:

```lua
target("my-app", function()
    set_kind("binary")
    set_languages("cxxlatest", "clatest")
    add_rules("stormkit::application")
    set_values("stormkit.components", { "log", "wsi" })
    add_files("src/*.cpp", "src/*.cppm")
end)
```

Details are in the
[build reference](reference/build.md#stormkitapplication-and-stormkitlibrary). While you are
evaluating the toolkit, adding a target inside the StormKit tree, as in step 5, is the path of
least resistance.

## Where to go next

- [Concepts and conventions](concepts.md) — ten minutes that make every other page easier to read
- the [core guide](guides/core.md)
- a first [tutorial](tutorials/command-line-tool.md)

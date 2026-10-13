# Macro reference

C++ modules cannot export macros, so everything in this page comes from a classic header that you
`#include` in the global module fragment of your translation unit:

```cpp
module;                                   // only needed inside a module unit
#include <stormkit/core/try_expected.hpp>
export module my.module;
import std;
import stormkit;
```

In a plain `.cpp` file, put the `#include` lines before the `import` lines.

| Header | Contents |
| --- | --- |
| [`<stormkit/core/contract_macro.hpp>`](#contract-macros) | `EXPECTS`, `ENSURES`, `ASSERT` |
| [`<stormkit/core/try_expected.hpp>`](#try-statement-macros) | `Try`, `TryTo`, … (statement form) |
| [`<stormkit/core/tryx_expected.hpp>`](#tryx-expression-macros) | `TryX`, `TryXOr`, `Return`, … (expression form) |
| [`<stormkit/core/platform_macro.hpp>`](#platform-macros) | compiler / OS / attribute detection |
| [`<stormkit/core/macro_utils.hpp>`](#preprocessor-utilities) | preprocessor meta-programming helpers |
| [`<stormkit/core/config.hpp>`](#configuration-macros) | generated build configuration |
| [`<stormkit/<lib>/api.hpp>`](#api-macros) | `STORMKIT_<LIB>_API` export macros |
| [`<stormkit/main/main_macro.hpp>`](#main-macro) | `main` → `user_main` rename |
| [`<stormkit/test/test_macro.hpp>`](#test-macro) | test flavoured `EXPECTS` |
| [`<stormkit/lua/lua.hpp>`](#lua-header) | Luau + sol2 includes |
| [`<stormkit/gpu/vulkan.hpp>`](#vulkan-header) | Vulkan + volk includes |
| `<stormkit/core/platform/windows.hpp>` | `<windows.h>` with `NOMINMAX`, `WIN32_LEAN_AND_MEAN`, and `DELETE` undefined |

## Contract macros

`<stormkit/core/contract_macro.hpp>`

| Macro | Expands to |
| --- | --- |
| `EXPECTS(cond)` | `stormkit::expects(cond, "cond")` |
| `EXPECTS(cond, location)` | `stormkit::expects(cond, "cond", location)` |
| `ENSURES(cond[, location])` | `stormkit::ensures(cond, "cond"[, location])` |
| `ASSERT(cond[, location])` | `stormkit::assert(cond, "cond"[, location])` |

The stringified condition becomes the failure message. See
[contract](core-foundation.md#stormkitcorecontract) for what a failure does.

> `<stormkit/test/test_macro.hpp>` also defines `EXPECTS`. Do not include both headers in the same
> translation unit.

## Try statement macros

`<stormkit/core/try_expected.hpp>`

These macros implement early return on a failed `std::expected`. They are *statements*: each one
declares a hidden temporary, so they cannot be used inside an expression. They work with every
supported compiler.

| Macro | On success | On failure |
| --- | --- | --- |
| `Try(expr)` | continues | `return { std::unexpected { error } }` |
| `TryOr(expr, closure)` | continues | `return std::invoke(closure, error)` |
| `TryTransform(expr, closure)` | continues | `return std::unexpected { std::invoke(closure, error) }` |
| `TryAssert(expr, msg)` | continues | `stormkit::ensures(false, msg)` (aborts) |
| `TryTo(name, expr)` | `auto name = *std::move(result);` | as `Try` |
| `TryToOr(name, expr, closure)` | declares `name` | as `TryOr` |
| `TryToTransform(name, expr, closure)` | declares `name` | as `TryTransform` |
| `TryToAssert(name, expr, msg)` | declares `name` | as `TryAssert` |
| `CustomLoggedTry(expr, logger, msg)` | continues | calls `logger("{}\n    > reason: {}", msg, error)`, then returns the error |
| `CustomLoggedTryOr(expr, closure, logger, msg)` | continues | logs, then returns `closure(error)` |
| `CustomLoggedTryTo(name, expr, logger, msg)` | declares `name` | logs, then returns the error |
| `CustomLoggedTryToOr(name, expr, closure, logger, msg)` | continues | logs, then returns `closure(error)` |
| `LoggedTry(expr, msg)` | — | `CustomLoggedTry` with `elog` as the logger |
| `LoggedTryOr(expr, closure, msg)` | — | `CustomLoggedTryOr` with `elog` |
| `LoggedTryTo(name, expr, logger, msg)` | — | intended as `CustomLoggedTryTo` with `elog` |
| `LoggedTryToOr(name, expr, closure, msg)` | — | `CustomLoggedTryToOr` with `elog` |

The `Logged*` variants expect a callable named `elog` to be visible at the call site. See
[free-function shortcuts](log.md#logger-macros) in the log reference for how to declare one.

```cpp
auto load_config(const std::filesystem::path& path) noexcept -> stormkit::system_result<Config> {
    TryTo(bytes, stormkit::io::readfile(path));   // returns the system_code on failure
    Try(validate(bytes));                         // value is discarded
    return parse(bytes);
}
```

Known issues in the current sources:

- `LoggedTryTo` expands to `CustomLoggerTryTo` (typo), which does not exist. Use
  `CustomLoggedTryTo(name, expr, elog, msg)` instead.
- `CustomLoggedTryToOr` passes four arguments to the three-parameter `TryOr_impl`.
  Prefer the `TryX` family when you need "log then transform".

## TryX expression macros

`<stormkit/core/tryx_expected.hpp>`

Expression flavoured versions of the macros above: they *evaluate to the unwrapped value*.

- On Clang and GCC they are implemented with statement expressions (`({ ... })`).
- On other compilers they expand to `co_await`, which requires the function to return
  `stormkit::expected` (the coroutine-enabled subclass, see
  [errors](core-foundation.md#stormkitcoreerrors)) and to use `Return` instead of `return`.

Always write `Return` in a function that uses `TryX` if you want it to stay portable.

| Macro | Value | On failure |
| --- | --- | --- |
| `TryX(expr)` | unwrapped value | returns the error |
| `TryXOr(expr, closure)` | unwrapped value | returns `closure(error)` |
| `TryXTransform(expr, closure)` | unwrapped value | returns `std::unexpected { closure(error) }` |
| `TryXAssert(expr, msg)` | unwrapped value | `stormkit::ensures(false, msg)` |
| `TryXLift(expr)` | unwrapped value | `TryXOr(expr, monadic::identity())` |
| `Return` | `return` (Clang/GCC) or `co_return` | |

Logging variants (same message format as above):

| Macro | Equivalent |
| --- | --- |
| `CustomLoggedTryX(expr, logger, msg)` | `TryXTransform` that logs and forwards the error |
| `CustomLoggedTryXOr(expr, closure, logger, msg)` | `TryXOr` that logs first |
| `CustomLoggedTryXTransform(expr, closure, logger, msg)` | `TryXTransform` that logs first |
| `CustomLoggedTryXLift(expr, logger, msg)` | `TryXOr` that logs and returns the error itself |
| `LoggedTryX`, `LoggedTryXOr`, `LoggedTryXTransform`, `LoggedTryXLift` | the above with `elog` |

Discarding variants, for results you do not need (each declares `[[maybe_unused]] auto _`):

`DiscardTryX`, `DiscardTryXOr`, `DiscardTryXTransform`, `DiscardTryXLift`, `DiscardTryXAssert`,
`CustomLoggedDiscardTryX`, `CustomLoggedDiscardTryXOr`, `CustomLoggedDiscardTryXTransform`,
`CustomLoggedDiscardTryXLift`, `LoggedDiscardTryX`, `LoggedDiscardTryXOr`,
`LoggedDiscardTryXTransform`, `LoggedDiscardTryXLift`.

```cpp
auto make_window() noexcept -> stormkit::system_result<Size> {
    auto bytes = TryX(stormkit::io::readfile("window.cfg"));
    auto size  = TryXTransform(parse_size(bytes), to_system_code);
    Return size;
}
```

Known issue: `LoggedTryXLift(expr)` and `LoggedDiscardTryXLift(expr)` reference an undeclared `msg`
parameter. Use `CustomLoggedTryXLift(expr, elog, msg)`.

## Platform macros

`<stormkit/core/platform_macro.hpp>` (also pulls in `macro_utils.hpp`)

### Detection

Exactly one macro of each group is defined. Test them with `#ifdef` / `#if defined(...)`.

| Group | Macros |
| --- | --- |
| Compiler | `STORMKIT_COMPILER_MSVC`, `STORMKIT_COMPILER_CLANG`, `STORMKIT_COMPILER_GCC`, `STORMKIT_COMPILER_MINGW`; `STORMKIT_COMPILER` is the active one (a printable expression) |
| Standard library | `STORMKIT_COMPILER_LIBCPP`, `STORMKIT_COMPILER_LIBSTDCPP`, `STORMKIT_COMPILER_MSSTL`; `STORMKIT_COMPILER_CXXLIB` is the active one. Also `STORMKIT_LIBCXX`, `STORMKIT_LIBSTDCXX`, `STORMKIT_MSSTL`, `STORMKIT_GLIBC` |
| Operating system | `STORMKIT_OS_WINDOWS` (`STORMKIT_OS_WIN64` / `STORMKIT_OS_WIN32`), `STORMKIT_OS_LINUX` (`STORMKIT_OS_LINUX64` / `STORMKIT_OS_LINUX32`), `STORMKIT_OS_APPLE` (`STORMKIT_OS_MACOS`, `STORMKIT_OS_IOS`, `STORMKIT_OS_IOS_SIMULATOR`), `STORMKIT_OS_ANDROID`, `STORMKIT_OS_NX`; `STORMKIT_OS` is the active one |
| Word size | `STORMKIT_BITS_64`, `STORMKIT_BITS_32` |
| POSIX | `STORMKIT_POSIX` |
| Build mode | `STORMKIT_DEBUG_MODE`, `STORMKIT_RELEASE_MODE` |

### Attributes

| Macro | Meaning |
| --- | --- |
| `STORMKIT_EXPORT` / `STORMKIT_IMPORT` | shared library export / import (`__declspec` or `visibility("default")`) |
| `STORMKIT_PRIVATE` | hidden visibility where supported |
| `STORMKIT_API` | `STORMKIT_EXPORT` or `STORMKIT_IMPORT` |
| `STORMKIT_FORCE_INLINE` | currently expands to nothing; `STORMKIT_FORCE_INLINE_IMPL` is the real always-inline attribute |
| `STORMKIT_INTRINSIC` | `[[msvc::intrinsic]]` on MSVC |
| `STORMKIT_NO_UNIQUE_ADDRESS` | portable `[[no_unique_address]]` |
| `STORMKIT_RESTRICT` | `__restrict` |
| `STORMKIT_PURE`, `STORMKIT_CONST` | `[[gnu::pure]]`, `[[gnu::const]]` where supported |
| `STORMKIT_LIFETIMEBOUND` | `[[lifetimebound]]` in its compiler specific spelling |
| `STORMKIT_GUARDED_BY(x)` | `[[clang::guarded_by(x)]]` on Clang |
| `STORMKIT_OWNER`, `STORMKIT_VIEW` | `[[gsl::Owner]]`, `[[gsl::Pointer]]` |
| `STORMKIT_TRIVIALLY_RELOCATABLE` | `[[trivially_relocatable]]` / `[[clang::trivial_abi]]` |
| `STORMKIT_ARRAY_IF_MSVC` | `array` on MSVC's standard library, empty elsewhere |

### Warning control

`STORMKIT_PUSH_WARNINGS`, `STORMKIT_POP_WARNINGS`, `STORMKIT_WARNING_IGNORE_MSVC(id)`,
`STORMKIT_WARNING_IGNORE_CLANG("-Wname")`, `STORMKIT_WARNING_IGNORE_GCC("-Wname")`,
`STORMKIT_WARNING_IGNORE_GCC_CLANG("-Wname")`. The compiler specific forms expand to nothing on the
other compilers.

## Preprocessor utilities

`<stormkit/core/macro_utils.hpp>`

| Macro | Purpose |
| --- | --- |
| `STORMKIT_STRINGIFY(x)` | stringify after expansion |
| `STORMKIT_CONCAT(a, b)` | token paste after expansion |
| `STORMKIT_UNIQUE_NAME(base)` | `base` suffixed with `__COUNTER__` |
| `STORMKIT_PRAGMA_FROM_STRING(x)` | `_Pragma(STORMKIT_STRINGIFY(x))` |
| `STORMKIT_VAARGS_HEAD(...)`, `STORMKIT_VAARGS_TAIL(...)`, `STORMKIT_HAS_VAARGS(...)` | variadic argument inspection |
| `STORMKIT_TUPLE_APPEND(tuple, el)` | append to a parenthesised token tuple |
| `STORMKIT_IIF(c)`, `IIF(c)`, `STORMKIT_IF(c)`, `STORMKIT_WHEN(c)`, `STORMKIT_NOT(x)`, `STORMKIT_BOOL(x)` | conditional expansion |
| `STORMKIT_INC(x)`, `STORMKIT_DEC(x)` | single digit arithmetic |
| `STORMKIT_CHECK(...)`, `STORMKIT_PROBE(x)` | detection idiom |
| `STORMKIT_EAT(...)`, `STORMKIT_EXPAND(...)`, `STORMKIT_EMPTY()`, `STORMKIT_DEFER(id)`, `STORMKIT_OBSTRUCT(...)`, `STORMKIT_DELAY` | deferred expansion |
| `STORMKIT_EVAL(...)` | force up to 3⁵ rescans |
| `STORMKIT_REPEAT(count, macro, ...)`, `STORMKIT_WHILE(pred, op, ...)` | recursion |
| `STORMKIT_FOR_EACH_COMBINATION(fn, (a, b), (c, d), ...)` | calls `fn` with every element of the cartesian product of the tuples |

These exist for the library's own use (for instance to stamp out operator overloads); they are
stable enough to borrow but are not the reason to use StormKit.

## Configuration macros

`<stormkit/core/config.hpp>` is generated at configure time from `config.hpp.in`.

| Macro | Defined when |
| --- | --- |
| `STORMKIT_LIB_MATH_ENABLED` | the `math` option is on |
| `STORMKIT_LIB_LOG_ENABLED` | the `log` option is on |
| `STORMKIT_LIB_ENTITIES_ENABLED` | the `entities` option is on |
| `STORMKIT_LIB_IMAGE_ENABLED` | the `image` option is on |
| `STORMKIT_LIB_WSI_ENABLED` | the `wsi` option is on |
| `STORMKIT_LIB_GPU_ENABLED` | the `gpu` option is on |
| `STORMKIT_LIB_LUA_ENABLED` | the `lua` option is on |

Unless `NO_CONSTANTS` is defined before inclusion, the header also declares the version constants
documented under [config](core-foundation.md#stormkitcoreconfig). Prefer importing
`stormkit.core.config` to get those.

Other definitions set by the build system:

| Macro | Meaning |
| --- | --- |
| `STORMKIT_STATIC` | StormKit is built as static libraries |
| `STORMKIT_BUILD_DEBUG` | debug build of StormKit |
| `STORMKIT_IMPORT_<LIB>` | the umbrella `stormkit` module re-exports `stormkit.<lib>` |
| `STORMKIT_GPU_VULKAN` | the gpu backend is Vulkan (always, today) |
| `STORMKIT_ASSERT` | set to `0` before importing to compile contract checks out (defaults to `1`) |

## API macros

Each library has `<stormkit/<lib>/api.hpp>` defining `STORMKIT_<LIB>_API`
(`STORMKIT_CORE_API`, `STORMKIT_LOG_API`, `STORMKIT_ENTITIES_API`, `STORMKIT_IMAGE_API`,
`STORMKIT_WSI_API`, `STORMKIT_GPU_API`, `STORMKIT_LUA_API`). It expands to `STORMKIT_EXPORT` while
the library itself is being built (`STORMKIT_<LIB>_BUILD` defined) and `STORMKIT_IMPORT` otherwise.
You only need these when contributing to StormKit.

## Main macro

`<stormkit/main/main_macro.hpp>` contains a single line:

```cpp
#define main user_main
```

Including it renames *your* `main` to `user_main`, which the platform entry point provided by
`stormkit-main` then calls. See the [main guide](../guides/main.md).

## Test macro

`<stormkit/test/test_macro.hpp>`

```cpp
#define EXPECTS(x) test::expects(x, #x)
```

Requires `using namespace stormkit;` (or a `test` namespace alias) at the call site.
See the [test guide](../guides/test.md).

## Lua header

`<stormkit/lua/lua.hpp>` includes Luau (`lua.h`, `luacode.h`, `lualib.h`) and sol2 configured for
Luau (`SOL_USE_LUAU`, `SOL_SAFE_STACK_CHECK`, `SOL_LUA_BIT32_LIB`, `LUA_VERSION_NUM 501`), with
warnings suppressed. Include it whenever you touch `sol::` types directly.

## Vulkan header

`<stormkit/gpu/vulkan.hpp>` includes `<vulkan/vulkan.h>` (with `VK_NO_PROTOTYPES`) and `<volk.h>`.
Define `STORMKIT_DEFINE_VK_PLATFORM` first to also get the platform surface extension types
(`VK_USE_PLATFORM_WIN32_KHR`, `…_XCB_KHR`, `…_WAYLAND_KHR`, `…_MACOS_MVK`, `…_IOS_MVK`).
Only needed when you drop down to raw Vulkan handles.

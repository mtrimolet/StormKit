# Build system reference

StormKit is built with [xmake](https://xmake.io) (3.0.0 or later). This page lists everything the
build scripts define: options, targets, rules and generated files.

For a walkthrough, see [Getting started](../getting-started.md).

---

## Requirements

| | |
| --- | --- |
| Language | C++ latest (`cxxlatest`): C++23 plus a few C++26 features (`import std`, pack indexing, `= delete("reason")`, deducing `this`, static `operator()`, multi-argument `operator[]`) |
| Standard library | Must provide the `std` module. Tested: libc++, MSVC STL (through clang-cl), libstdc++ |
| Compilers exercised by CI | LLVM/Clang on Windows 2025 (`libc++` and `msstl`), Ubuntu 26.04 (`libc++`) and macOS |
| Platforms | `windows`, `mingw`, `linux`, `macosx`, `wasm` |
| Architectures | Windows: `x64`, `arm64` · Linux: `x86_64`, `aarch64` · macOS: `x86_64`, `arm64` |
| Build modes | `debug`, `release`, `releasedbg`, `profile` (plus `valgrind` outside Windows) |

Third-party packages are fetched by xmake from the `xmake-repo`, `nazara-repo`
(`github.com/NazaraEngine/xmake-repo`) and `tapzcrew-repo` (`github.com/Tapzcrew/xmake-repo`)
repositories.

| Library | Packages |
| --- | --- |
| core | `frozen`, `unordered_dense`, `nontype_functional` |
| image | `libktx`, `libpng`, `libjpeg-turbo` |
| wsi (Linux only) | `libxcb`, `xcb-util`, `xcb-util-keysyms`, `xcb-util-image`, `xcb-util-wm`, `xcb-util-errors`, `wayland`, `wayland-protocols`, `libxkbcommon` |
| gpu | `volk`, `vulkan-headers` (1.4.335), `vulkan-memory-allocator` (3.3.0) |
| lua | `luau`, `sol2_luau` |
| gpu examples | `nzsl` (shader compiler, host tool) |

The bundled [status-code](https://github.com/ned14/status-code) headers live in
`include/status-code`.

---

## Configuration

```console
> xmake f [options]
> xmake b
```

### Standard xmake options

| Option | Values |
| --- | --- |
| `-m`, `--mode` | `debug`, `release`, `releasedbg`, `profile` |
| `-k`, `--kind` | `static` (default), `shared` |
| `--toolchain` | e.g. `llvm`, `clang`, `gcc`, `msvc` |
| `--runtimes` | `c++_static`, `c++_shared`, `stdc++_static`, `stdc++_shared`, `MT`, `MD`, `MTd`, `MDd` |
| `-a`, `--arch` | see the table above |

### Library options

Menu category `modules`. Enabling a library enables nothing else automatically: turn on its
requirements too.

| Option | Default | Requires | Builds |
| --- | --- | --- | --- |
| `--log` | `y` | | `stormkit-log` |
| `--math` | `y` | | `stormkit-math` |
| `--image` | `y` | `math`, `log` | `stormkit-image` |
| `--entities` | `n` | | `stormkit-entities` |
| `--wsi` | `n` | `log` | `stormkit-wsi` |
| `--gpu` | `n` | `log`, `image`, `wsi` | `stormkit-gpu` |
| `--lua` | `n` | `log` | `stormkit-lua` |

`stormkit-core` and `stormkit-main` are always built.

### Build options

Menu category `build`.

| Option | Default | Effect |
| --- | --- | --- |
| `--examples` | `y` | Builds the examples of every enabled library (sets `examples_<lib>` for each). |
| `--examples_log`, `--examples_wsi`, `--examples_gpu`, `--examples_entities`, `--examples_lua` | follow `examples` | Per-library example switches. |
| `--tests` | `n` | Builds `stormkit-test` and the unit tests. |
| `--tools` | `n` | Builds the tools (`terra`). |
| `--sanitizers` | `n` | Address + undefined behaviour sanitizers on executables. |
| `--lto` | `n` | Link-time optimisation (thin LTO with LLVM). |
| `--mold` | `n` | Links with [mold](https://github.com/rui314/mold) on Linux. A string value selects another linker (`--mold=lld`). |
| `--rad` | `n` | Links with `radlink` on Windows. |
| `--shared_deps` | `n` | Reserved. |
| `--on_ci` | `n` | Set by the CI scripts. |

### Support options

Menu category `support`.

| Option | Effect |
| --- | --- |
| `--compile_commands` | Regenerates `build/compile_commands.json` on each build, for clangd. |
| `--vsxmake` | Keeps a Visual Studio solution in sync. |
| `--devmode` | Developer preset: turns on `tests`, `examples`, `mold` and `sanitizers`, hides module dependency scanning noise, makes warnings non-fatal, and defines `RESOURCE_DIR` / `SHADER_DIR` in the examples so they run from the source tree. |

### Typical configurations

```console
# default: core + math + log + image, static, with examples
> xmake f -m release

# everything, for working on StormKit itself
> xmake f -m debug --toolchain=llvm --runtimes=c++_static --devmode=y --wsi=y --gpu=y --entities=y --lua=y

# what CI runs
> xmake f --mode=releasedbg --kind=static --examples=y --tests=y --mold=y --toolchain=llvm --runtimes="c++_static" --yes
> xmake b -v
> xmake test -v
```

---

## Targets

All targets are declared inside the xmake namespace `stormkit`.

| Target | Kind | Output | C++ module | Depends on |
| --- | --- | --- | --- | --- |
| `stormkit::core` | `$(kind)` | `stormkit-core` | `stormkit.core` | |
| `stormkit::main` | static | `stormkit-main` | `stormkit.main` | core |
| `stormkit::math` | `$(kind)` | `stormkit-math` | `stormkit.math` | core |
| `stormkit::log` | `$(kind)` | `stormkit-log` | `stormkit.log` | core |
| `stormkit::image` | `$(kind)` | `stormkit-image` | `stormkit.image` | core, math |
| `stormkit::entities` | `$(kind)` | `stormkit-entities` | `stormkit.entities` | core |
| `stormkit::wsi` | `$(kind)` | `stormkit-wsi` | `stormkit.wsi` | core, log |
| `stormkit::gpu` | `$(kind)` | `stormkit-gpu` | `stormkit.gpu` | core, wsi, image, (log) |
| `stormkit::lua` | `$(kind)` | `stormkit-lua` | `stormkit.lua` | core, log, and image / entities / wsi / gpu when enabled |
| `stormkit::test` | static | `stormkit-test` | `stormkit.test` | core |
| `stormkit::stormkit` | static | `stormkit` | `stormkit` (umbrella) | every enabled library |
| `stormkit::examples::…` | binary | | | `stormkit::stormkit`, `stormkit::main` |
| `stormkit::tests::<lib>-<file>` | binary | | | `stormkit::test`, `stormkit::<lib>` |
| `stormkit::tools::terra` | binary | | | `stormkit::stormkit`, `stormkit::main` |

Output names get a suffix: `-static` for static builds, `-debug` in debug mode
(`stormkit-core-static-debug`). The umbrella library has no suffix.

### The umbrella module

`import stormkit;` re-exports `stormkit.core` plus every library that is both **enabled**
(`STORMKIT_LIB_<LIB>_ENABLED`, from `config.hpp`) and **requested**
(`STORMKIT_IMPORT_<LIB>`, defined publicly by the `stormkit::stormkit` target for each enabled
library). Depending on `stormkit::stormkit` is therefore enough to get everything that was built.

### Definitions exported by the targets

| Definition | Set by | When |
| --- | --- | --- |
| `STORMKIT_STATIC` | core (public) | static build |
| `STORMKIT_BUILD_DEBUG` | core (public) | debug mode |
| `ANKERL_UNORDERED_DENSE_STD_MODULE=1`, `FROZEN_STD_MODULE=1` | core (public) | always |
| `STORMKIT_GPU_VULKAN` | gpu (public) | always |
| `STORMKIT_IMPORT_<LIB>` | stormkit (public) | library enabled |
| `STORMKIT_<LIB>_BUILD` | each library (private) | while building it |

---

## Rules

### `stormkit::flags`

Applied to every StormKit target; apply it to yours to compile with the same settings.

| Area | Settings |
| --- | --- |
| Warnings | `allextra`, `pedantic`, as errors (not as errors with `--devmode`) |
| Encoding | UTF-8 source and execution charset |
| Optimisation | `release`: fastest, hidden symbols. `releasedbg`: fastest + debug symbols. `debug`: debug symbols |
| Floating point | fast model; FMA, NEON, SSE–SSE4.2, AVX, AVX2 enabled |
| Hardening (GCC/Clang) | `-fstack-protector-strong`, `-fstack-clash-protection`, `-ftrivial-auto-var-init=zero`, `-fcf-protection=full` (Linux), `-fstrict-aliasing` |
| Hardening (standard library) | libc++ hardening mode (`DEBUG` / `EXTENSIVE` / `FAST` by build mode), `_GLIBCXX_ASSERTIONS` / `_FORTIFY_SOURCE`, `_MSVC_STL_HARDENING=1` |
| Clang | `-fexperimental-library` with libc++, `-Wno-include-angled-in-module-purview` |
| MSVC / clang-cl | `/permissive-`, `/Zc:preprocessor`, `/Zc:__cplusplus`, `/bigobj`, `-fms-compatibility`, lld-link |
| Linking | `lld` with the LLVM toolchain, `mold` or `radlink` on request, `--export-dynamic` in debug on Linux (for stack traces), `dl` and `stdc++exp` where needed |
| Sanitizers | ASan + UBSan on executables when `--sanitizers=y` |

### `stormkit::example`

For executables **inside the StormKit tree** (examples, tests, tools):

- sets the kind to `binary` and the languages to `cxxlatest` / `clatest`;
- adds the dependencies `stormkit::stormkit` and `stormkit::main`;
- applies `stormkit::flags` and the Windows console subsystem;
- on Windows adds the common manifest; with `apple_bundle` adds the Xcode application rule and
  the common `info.plist`.

```lua
target("my-example", function()
    add_rules("stormkit::example")
    add_files("src/*.cpp")
end)
```

### `stormkit::application` and `stormkit::library`

For projects that consume StormKit **as an xmake package** named `stormkit`. Both read the list of
wanted libraries from the target value `stormkit.components`, add the third-party packages those
libraries need, and add `stormkit` with the matching components. `application` also adds the
`main` component.

```lua
target("my-game", function()
    set_kind("binary")
    set_languages("cxxlatest")
    add_rules("stormkit::application")
    set_values("stormkit.components", { "log", "wsi", "gpu" })
    add_files("src/*.cpp", "src/*.cppm")
end)
```

| Component | Third-party packages added |
| --- | --- |
| *(always)* | `frozen`, `unordered_dense`, `nontype_functional` |
| `image` | `libktx`, `libpng`, `libjpeg-turbo` |
| `wsi` | the xcb / wayland / xkbcommon set, on Linux |
| `gpu` | `volk`, `vulkan-headers`, `vulkan-memory-allocator` |

<a id="shader-compilation"></a>

### `compile.shaders`

Compiles [NZSL](https://github.com/NazaraEngine/ShaderLang) shaders (`.nzsl`, `.nzslb`) added to a
target with `add_files`. Each file is compiled with `nzslc` to
`$(builddir)/shaders/<name>.spv` (SPIR-V 1.3, optimised, Y flipped), before the target's sources.

```lua
add_requires("nzsl", { configs = { kind = "binary" } })

target("triangle", function()
    add_rules("stormkit::example", "compile.shaders")
    add_files("src/*.cpp", "shaders/*.nzsl")
    add_packages("nzsl")
end)
```

A file configured with `{ archive = "name.nzsla" }` is additionally packed into a shader archive
(requires the `@nzsl/archive.shaders` rule). The helper rule `find_nzsl` locates the `nzslc` and
`nzsla` executables.

### `stormkit.utils.resource2cpp`

Turns files of the `embed_resources` source batch into headers containing a comma-separated list
of `std::byte { … }` initialisers, generated in the target's autogen directory (which is added to
the include path). Include the result inside a braced initialiser:

```cpp
static constexpr auto LOGO = std::array {
    #include <logo.png.hpp>
};
```

### `wayland.protocols`

Used by `stormkit::wsi` on Linux: runs `wayland-scanner` on the protocol XML files added to the
target and compiles the generated client code.

### `platform.windows.subsystem.console`

Selects the console subsystem for Windows executables (so that `main`, not `WinMain`, is the entry
point and output appears in the launching terminal).

---

## Generated files

| File | Source | Content |
| --- | --- | --- |
| `$(builddir)/.gens/include/stormkit/core/config.hpp` | `include/stormkit/core/config.hpp.in` | `STORMKIT_LIB_*_ENABLED` macros, version / build / git constants (see [config](core-foundation.md#stormkitcoreconfig)) |
| `modules/stormkit/gpu/core/vulkan/enums.cppm` | `enums.cppm.tpl` + `mapping.json` | the gpu enumerations (checked in; regenerate with `terra`) |
| `$(builddir)/shaders/*.spv` | `*.nzsl` | compiled shaders |

The project version is `0.1.0`; the build component is the configure timestamp.

---

## Tools

### `terra`

A tiny template expander, built with `--tools=y`.

```console
> terra <template-file> [output-file]
```

It reads a template in which `{% … %}` blocks contain Lua code, and prints a **Lua script** that,
when run, writes the expanded file (`output-file`, by default the template path without its last
extension). Text outside the blocks is emitted verbatim; inside a block, call
`outfile:write(...)` to emit text.

```cpp
{% for i, name in ipairs({ "FOO", "BAR" }) do %}
inline constexpr auto {% outfile:write(name .. i) %} = "{% outfile:write(name) %}";
{% end %}
```

---

## Tests

With `--tests=y`, each `tests/<lib>/**.cpp` file is its own executable. The build script parses the
file for the suite name and the test names and registers one xmake test per test case, named
`<suite>/<test>` and grouped by suite. See the [test reference](main-test.md#stormkittest).

```console
> xmake f --tests=y && xmake b && xmake test
```

## Continuous integration

`.github/workflows` builds and tests every push and pull request to `develop` on Linux, Windows and
macOS, in `debug` and `releasedbg`, static and shared. Commits whose message contains `ci skip`
are ignored.

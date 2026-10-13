# StormKit documentation

StormKit is a modular C++ toolkit distributed as **C++ modules**: a foundation library
(`stormkit.core`) and a set of optional libraries for math, logging, images, windowing, GPU
rendering, entity-component systems and Luau scripting.

```cpp
import std;
import stormkit;

#include <stormkit/main/main_macro.hpp>

using namespace stormkit;

auto main(array_view<const string_view> args) -> int {
    auto logger = log::logger::create_logger_instance<log::console_logger>();
    log::logger::ilog("Hello from StormKit {} ({} arguments)", STORMKIT_VERSION, std::ranges::size(args));
    return 0;
}
```

## Browsing it as a website

These pages read fine on GitHub, and can also be served locally as a searchable site with
navigation, a table of contents and a dark mode, using
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/). From the repository root:

```console
> python -m pip install -r docs/requirements.txt
> python -m mkdocs serve
```

then open <http://127.0.0.1:8000>. The site reloads when a page is edited. `python -m mkdocs build`
writes a static copy to `build/docs-site`. The configuration is in `mkdocs.yml`.

## How this documentation is organised

| You want to… | Read |
| --- | --- |
| build StormKit and run a first program | [Getting started](getting-started.md) |
| understand the conventions shared by every module | [Concepts and conventions](concepts.md) |
| learn one module | a [module guide](#module-guides) |
| see several modules working together | a [tutorial](#tutorials) |
| look up a signature, a default value, an enumerator | the [reference](#reference) |

The guides explain and show; the reference lists everything, tersely. Guides link to the reference
rather than repeat it.

## The libraries

| Library | Module | Default | Purpose | Guide | Reference |
| --- | --- | --- | --- | --- | --- |
| core | `stormkit.core` | always | types, errors, casts, containers, strings, threads | [guide](guides/core.md) | [1](reference/core-foundation.md) · [2](reference/core-containers.md) · [3](reference/core-meta-string.md) · [4](reference/core-typesafe.md) |
| main | `stormkit.main` | always | portable entry point | [guide](guides/main.md) | [ref](reference/main-test.md#stormkitmain) |
| math | `stormkit.math` | on | vectors, matrices, extents, rectangles | [guide](guides/math.md) | [ref](reference/math.md) |
| log | `stormkit.log` | on | console and file logging | [guide](guides/log.md) | [ref](reference/log.md) |
| image | `stormkit.image` | on | image loading, saving, conversion | [guide](guides/image.md) | [ref](reference/image.md) |
| wsi | `stormkit.wsi` | off | windows, monitors, input | [guide](guides/wsi.md) | [ref](reference/wsi.md) |
| gpu | `stormkit.gpu` | off | Vulkan rendering | [guide](guides/gpu.md) | [ref](reference/gpu.md) · [enums](reference/gpu-enums.md) |
| entities | `stormkit.entities` | off | entity-component-system | [guide](guides/entities.md) | [ref](reference/entities.md) |
| lua | `stormkit.lua` | off | Luau scripting | [guide](guides/lua.md) | [ref](reference/lua.md) |
| test | `stormkit.test` | off | unit-test framework | [guide](guides/test.md) | [ref](reference/main-test.md#stormkittest) |

```
core ──┬── main
       ├── math ───┐
       ├── log ────┼── image ──┐
       │           └── wsi ────┴── gpu
       ├── entities
       ├── lua  (binds whichever of log / image / entities / wsi / gpu are enabled)
       └── test
```

## Module guides

One guide per library, each a guided tour with runnable-sized examples.

- [core](guides/core.md) — the foundation: vocabulary types, contracts, `expected`-based error
  handling, safe casts, strings and formatting, containers, ownership helpers, functional tools,
  threading
- [main](guides/main.md) — the entry point
- [math](guides/math.md) — linear algebra and geometry
- [log](guides/log.md) — logging
- [image](guides/image.md) — images on the CPU
- [wsi](guides/wsi.md) — windows and events
- [gpu](guides/gpu.md) — rendering with Vulkan
- [entities](guides/entities.md) — entity-component-system
- [lua](guides/lua.md) — scripting
- [test](guides/test.md) — unit tests

## Tutorials

Complete programs that combine several libraries.

| Tutorial | Libraries | What you build |
| --- | --- | --- |
| [A command-line tool](tutorials/command-line-tool.md) | main, core, log | a directory checksum tool with proper error handling and logging |
| [Batch image processing](tutorials/batch-image-processing.md) | core, math, image, log | a multi-threaded thumbnail generator |
| [Software rendering in a window](tutorials/software-rendering.md) | core, math, wsi, log | an interactive Mandelbrot viewer drawn on the CPU |
| [A simulation with the ECS](tutorials/ecs-simulation.md) | core, math, entities, wsi | a particle system stepped by systems and drawn in a window |
| [Your first triangle](tutorials/vulkan-triangle.md) | wsi, gpu, log | the Vulkan frame loop, from instance to present |
| [Textures and uniforms](tutorials/textured-quad.md) | math, image, wsi, gpu | a rotating textured quad: staging uploads, descriptor sets, uniform buffers |
| [Scripting a window](tutorials/scripting.md) | log, wsi, lua | an application whose behaviour lives in a Luau script |
| [Testing your own code](tutorials/testing.md) | core, math, test | a small library and its unit tests, wired into xmake |

## Reference

- **API**
  - `stormkit.core`: [foundation](reference/core-foundation.md) ·
    [containers, memory & parallelism](reference/core-containers.md) ·
    [meta & strings](reference/core-meta-string.md) · [type safety](reference/core-typesafe.md)
  - [`stormkit.math`](reference/math.md)
  - [`stormkit.log`](reference/log.md)
  - [`stormkit.image`](reference/image.md)
  - [`stormkit.wsi`](reference/wsi.md)
  - [`stormkit.gpu`](reference/gpu.md) · [gpu enumerations](reference/gpu-enums.md)
  - [`stormkit.entities`](reference/entities.md)
  - [`stormkit.lua`](reference/lua.md)
  - [`stormkit.main` and `stormkit.test`](reference/main-test.md)
- [Macros](reference/macros.md) — everything that needs an `#include`
- [Build system](reference/build.md) — options, targets, rules

## Project status

StormKit is at version 0.1 and is being reworked. Two things follow for readers of these pages:

1. **Naming is in transition.** `core`, `math`, `log` and `image` use `snake_case` throughout
   (`thread_pool`, `console_logger`, `image::image`). `wsi`, `gpu` and `lua` still use the earlier
   `PascalCase` (`wsi::Window`, `gpu::Device`, `lua::Engine`), and `entities` is half-way. The
   documentation always shows the names currently declared in `modules/`.
2. **The optional libraries lag behind `core`.** `wsi`, `gpu`, `entities` and `lua` (all off by
   default) still reference helpers from an earlier `core` — among them the `LOGGER` macros of the
   removed `<stormkit/log/log_macro.hpp>`. Their pages carry a *Status* note listing what is
   affected. Code in the guides for these libraries is written against the declared interfaces.

The files under `examples/` predate part of this rework; where an example and a module interface
disagree, the documentation follows the interface.

The documentation was written from the sources at commit `1c4e5dc7`. Its code samples have not
been compiled.

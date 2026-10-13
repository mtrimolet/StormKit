# Tutorial: software rendering in a window

**Libraries:** `core`, `math`, `wsi`, `log` (and `main`)

We will write an interactive Mandelbrot viewer that computes every pixel on the CPU, on all cores,
and presents the result in a window — no GPU API involved. Along the way: the window event model,
a render-on-demand loop, and splitting work across a thread pool.

| Input | Action |
| --- | --- |
| left click | centre the view on the cursor |
| `+` / `-` | zoom in / out |
| arrow keys | pan |
| `R` | reset the view |
| `F11` | toggle fullscreen |
| `Escape` | quit |

## Setting up

`wsi` is off by default:

```console
> xmake f --wsi=y
```

```lua
-- examples/wsi/mandelbrot/xmake.lua
target("mandelbrot", function()
    add_rules("stormkit::example")
    add_files("src/*.cpp")
    set_group("examples/stormkit-wsi")
end)
```

```cpp
// examples/wsi/mandelbrot/src/main.cpp
import std;
import stormkit;

#include <stormkit/main/main_macro.hpp>

using namespace stormkit;
using namespace stormkit::literals;

namespace {
    constexpr auto LOG = log::module { "mandelbrot" };
}
```

## Step 1 — a window that stays open

```cpp
auto main(array_view<const string_view> args) -> int {
    wsi::parse_args(args);
    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    auto window = wsi::Window::open("Mandelbrot", { .width = 960u, .height = 640u }, wsi::WindowFlag::RESIZEABLE);
    LOG.ilog("window system: {}", window.wm());

    window.on(wsi::KeyDownEventFunc { [&window](u8, wsi::Key key, char) noexcept {
        if (key == wsi::Key::ESCAPE) window.close();
    } });

    window.event_loop([&] noexcept { window.clear(); });
    return 0;
}
```

Build and run it (`xmake b stormkit::examples::mandelbrot`, then `xmake run …`): a black, resizable
window that closes with Escape or its close button. The [wsi guide](../guides/wsi.md) explains each
call; what matters here is the shape — **register callbacks, then loop**.

## Step 2 — the view

What part of the complex plane are we looking at? A centre and a scale are enough, and screen
↔ plane conversions are a few lines of `math`:

```cpp
struct plane_view {
    f64 center_x = -0.5;
    f64 center_y = 0.0;
    f64 scale    = 3.0 / 640.0;            // plane units per pixel

    constexpr auto to_plane(const math::ivec2& pixel, const math::uextent2& extent) const noexcept -> std::pair<f64, f64> {
        return { center_x + (as<f64>(pixel.x()) - as<f64>(extent.width) / 2.0) * scale,
                 center_y + (as<f64>(pixel.y()) - as<f64>(extent.height) / 2.0) * scale };
    }
};
```

`pixel` is a `math::ivec2` because that is what mouse events give us; `extent` is the
`math::uextent2` the window reports. Mixed signed/unsigned arithmetic is where bugs hide, so every
conversion to `f64` is an explicit `as`.

## Step 3 — colouring one pixel

```cpp
constexpr auto MAX_ITERATIONS = 256_u32;

constexpr auto iterations(f64 cx, f64 cy) noexcept -> u32 {
    auto x = 0.0, y = 0.0;
    for (auto i : range(MAX_ITERATIONS)) {
        const auto xx = x * x, yy = y * y;
        if (xx + yy > 4.0) return i;
        y = 2.0 * x * y + cy;
        x = xx - yy + cx;
    }
    return MAX_ITERATIONS;
}

constexpr auto shade(u32 count) noexcept -> ucolor_rgb {
    if (count == MAX_ITERATIONS) return colors::BLACK<u8>;

    const auto t = as<f32>(count) / as<f32>(MAX_ITERATIONS);
    return {
        .r = unchecked_narrow<u8>(9.f * (1.f - t) * t * t * t * 255.f),
        .g = unchecked_narrow<u8>(15.f * (1.f - t) * (1.f - t) * t * t * 255.f),
        .b = unchecked_narrow<u8>(8.5f * (1.f - t) * (1.f - t) * (1.f - t) * t * 255.f),
    };
}

static_assert(iterations(0.0, 0.0) == MAX_ITERATIONS);      // the origin is in the set
static_assert(iterations(2.0, 2.0) < 4);                    // far outside: escapes at once
```

- `ucolor_rgb` is the pixel type the window's framebuffer takes: three `u8`, in that order.
- The colour presets ([`colors::BLACK<u8>`](../guides/core.md#colours)) convert to any colour
  type.
- `unchecked_narrow` is the deliberate cast: we *want* the fractional part dropped, and the
  polynomial stays within `[0, 255]`. With `as<u8>` a non-integral value would be reported as
  lossy.
- Both functions are `constexpr`, so two `static_assert`s act as unit tests.

## Step 4 — rendering on every core

The image is `width × height` independent computations. We cut it into horizontal bands and give
each band to a [`thread_pool`](../guides/core.md#thread_pool) worker.

```cpp
auto render(thread_pool& pool, dynarray<ucolor_rgb>& pixels, const math::uextent2& extent, const plane_view& view) noexcept -> void {
    pixels.resize(extent.width * extent.height);
    if (std::ranges::empty(pixels)) return;                                           // zero-sized window

    const auto band_count  = math::min(pool.worker_count(), extent.height);
    const auto band_height = (extent.height + band_count - 1u) / band_count;        // rounded up

    auto pending = dynarray<std::future<void>> {};
    pending.reserve(band_count);

    for (auto band : range(band_count)) {
        const auto first = band * band_height;
        const auto last  = math::min(first + band_height, extent.height);

        pending.emplace_back(pool.post_task<void>([&pixels, &extent, &view, first, last] noexcept {
            auto image = mdarray_view { std::ranges::data(pixels), extent.height, extent.width };

            for (auto [y, x] : multi_range(numeric_range { first, last }, numeric_range { 0u, extent.width })) {
                const auto [cx, cy] = view.to_plane({ as<i32>(x), as<i32>(y) }, extent);
                image[y, x]         = shade(iterations(cx, cy));
            }
        }));
    }

    wait_all(pending);
}
```

- **Bands, not pixels.** One task per pixel would drown in scheduling overhead; one per worker is
  the right granularity. Rounding the band height up and clamping `last` covers the rows that do
  not divide evenly.
- **No locking.** Each task writes a disjoint range of rows. Sharing a buffer between threads is
  fine when no two of them touch the same element.
- **`mdarray_view`** (`std::mdspan`) gives the flat pixel array a `[row, column]` interface.
- **`multi_range`** iterates the cartesian product of two [`numeric_range`s](../guides/core.md#numeric-ranges),
  row by row.
- **`wait_all`** blocks until the image is complete, which also keeps the by-reference captures
  valid.

`render` is synchronous: when it returns, `pixels` holds a finished frame.

## Step 5 — render only when something changed

Recomputing the fractal sixty times per second would waste every core. The picture changes only
when the view or the window size does, so we keep a `dirty` flag: callbacks set it, the loop
consumes it.

```cpp
struct app_state {
    plane_view view;
    bool dirty     = true;
    bool minimized = false;
    math::ivec2 cursor = { 0, 0 };
};
```

## Step 6 — the callbacks

```cpp
auto install_callbacks(wsi::Window& window, app_state& state) noexcept -> void {
    window.on(
      wsi::ResizedEventFunc { [&state](const math::uextent2&) noexcept { state.dirty = true; } },
      wsi::MinimizedEventFunc { [&state] noexcept { state.minimized = true; } },
      wsi::RestoredEventFunc { [&state] noexcept {
          state.minimized = false;
          state.dirty     = true;
      } },
      wsi::MouseMovedEventFunc { [&state](u8, const math::ivec2& position) noexcept { state.cursor = position; } },
      wsi::MouseButtonDownEventFunc { [&window, &state](u8, wsi::MouseButton button, const math::ivec2& position) noexcept {
          if (button != wsi::MouseButton::LEFT) return;

          const auto [x, y]   = state.view.to_plane(position, window.extent());
          state.view.center_x = x;
          state.view.center_y = y;
          state.dirty         = true;
      } },
      wsi::KeyDownEventFunc { [&window, &state](u8, wsi::Key key, char) noexcept {
          auto&      view = state.view;
          const auto step = view.scale * 40.0;                     // 40 pixels

          switch (key) {
              case wsi::Key::ESCAPE: window.close(); return;
              case wsi::Key::F11: window.toggle_fullscreen(); return;      // triggers a RESIZED event
              case wsi::Key::LEFT: view.center_x -= step; break;
              case wsi::Key::RIGHT: view.center_x += step; break;
              case wsi::Key::UP: view.center_y -= step; break;
              case wsi::Key::DOWN: view.center_y += step; break;
              case wsi::Key::EQUAL:
              case wsi::Key::NUMPAD_ADD: view.scale *= 0.8; break;
              case wsi::Key::MINUS:
              case wsi::Key::NUMPAD_SUBTRACT: view.scale *= 1.25; break;
              case wsi::Key::R: view = {}; break;
              default: return;
          }
          state.dirty = true;
      } });
}
```

Points worth dwelling on:

- **Each callback type identifies its event**, so one `on(…)` call registers all six.
- **`Key` is the physical key**, not the character. `EQUAL` is the key that carries `+` on most
  layouts; we also accept the numeric keypad.
- **Callbacks capture `window` and `state` by reference.** Both are locals of `main` that outlive
  the event loop, and neither moves afterwards — the two conditions for this to be safe.
- **Key repeat is on by default**, which is what we want here: holding an arrow keeps panning.
- **No mutex anywhere.** Callbacks run inside `handle_events`, on the main thread, between two
  frames; the worker threads only exist inside `render`.

## Step 7 — the loop

```cpp
auto main(array_view<const string_view> args) -> int {
    wsi::parse_args(args);
    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    auto window = wsi::Window::open("Mandelbrot", { .width = 960u, .height = 640u }, wsi::WindowFlag::RESIZEABLE);
    auto pool   = thread_pool { std::max(1u, std::thread::hardware_concurrency()) };
    auto pixels = dynarray<ucolor_rgb> {};
    auto state  = app_state {};

    pool.set_name("render");
    install_callbacks(window, state);
    LOG.ilog("{} on {} worker(s)", window.wm(), pool.worker_count());

    window.event_loop([&] noexcept {
        if (state.minimized) {
            std::this_thread::sleep_for(std::chrono::milliseconds { 50 });
            return;
        }

        if (state.dirty) {
            const auto extent = window.extent();
            const auto start  = std::chrono::steady_clock::now();

            render(pool, pixels, extent, state.view);

            const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start);
            window.set_title(std::format("Mandelbrot — {} — {} ms", extent, elapsed.count()));
            LOG.dlog("rendered {} in {} ms", extent, elapsed.count());

            state.dirty = false;
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds { 5 });
        }

        if (std::ranges::size(pixels) == window.extent().width * window.extent().height) window.fill_framebuffer(pixels);
    });

    return 0;
}
```

Reading the loop body top to bottom:

1. **Minimised?** Nothing to show; sleep and let `event_loop` process events. Without this the
   program would spin at 100 % CPU while invisible.
2. **Dirty?** Recompute at the window's *current* size. The size is read here rather than in the
   `RESIZED` callback, so a burst of resize events costs one render, not one per event.
3. **Not dirty?** Sleep briefly instead of busy-waiting.
4. **Present.** `fill_framebuffer` expects exactly `width × height` pixels; the guard skips the one
   frame in which a resize has happened but the buffer has not yet been rebuilt.

`event_loop` then calls `handle_events`, which runs our callbacks, and starts over.

## Run it

```console
> xmake b stormkit::examples::mandelbrot
> xmake run stormkit::examples::mandelbrot --debug
```

With `--debug` the logger prints the time of each render; try resizing the window and watch the
worker count pay off.

## What to take away

| Idea | In this program |
| --- | --- |
| events are callbacks, registered once | `install_callbacks` |
| callbacks and the frame function share a thread | no locks around `app_state` |
| render on demand | the `dirty` flag |
| parallelise by partitioning the output | one band of rows per worker, no shared writes |
| `math` types are the lingua franca | `ivec2` from the mouse, `uextent2` from the window, both into `plane_view::to_plane` |

## Going further

- **Progressive refinement.** Render at a quarter of the resolution first for instant feedback,
  then at full resolution if no new input arrived.
- **Keep the UI responsive during long renders.** Do not `wait_all`; store the futures, poll them
  each frame with `wait_for(0s)`, and present the previous image meanwhile. `pixels` then needs a
  front and a back buffer.
- **Save a screenshot.** With the `image` library: build an `image::image` of format
  `RGB8_UNORM`, copy `pixels` into its `data()`, and `save_to_file(…, image_codec::PNG)`.
- **Move the drawing to the GPU**: [your first triangle](vulkan-triangle.md).

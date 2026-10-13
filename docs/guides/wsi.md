# Guide: `stormkit.wsi`

`wsi` — *window system integration* — opens windows and delivers input, on Windows, Linux (X11 and
Wayland), macOS and iOS, behind one interface.

Enable it at configure time with `--wsi=y`.

```cpp
import std;
import stormkit;

#include <stormkit/main/main_macro.hpp>

using namespace stormkit;
```

> This library still uses `PascalCase` names (`wsi::Window`, `wsi::Key`), unlike `core`. See the
> [status note](../reference/wsi.md#status).

## A window in ten lines

```cpp
auto main(array_view<const string_view> args) -> int {
    wsi::parse_args(args);
    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    auto window = wsi::Window::open("Hello", { .width = 800u, .height = 600u }, wsi::WindowFlag::RESIZEABLE);

    window.event_loop([&] noexcept { window.clear(colors::TEAL<u8>); });

    return 0;
}
```

- `Window::open` creates the window and shows it. The window is move-only and closes when
  destroyed.
- `event_loop(f)` repeats "call `f`, then process pending events" until the window is closed.
- `clear` fills the window with a colour — enough to see that it works.

`wsi::parse_args` only matters on Linux, where `--x11` and `--wayland` force a backend; calling it
everywhere keeps the program portable.

### Window flags

| Flag | Meaning |
| --- | --- |
| `WindowFlag::DEFAULT` | a decorated window of fixed size |
| `WindowFlag::RESIZEABLE` | the user can resize it |
| `WindowFlag::BORDERLESS` | no title bar, no borders |
| `WindowFlag::EXTERNAL_CONTEXT` | something else (the `gpu` library) will draw into it |

Combine them with `|`.

## Reacting to events

Events arrive through callbacks that you register on the window. There are two ways to say which
event a callback is for.

**By event type** — pass the lambda bare:

```cpp
window.on<wsi::EventType::CLOSED>([] noexcept {
    return true;                       // true: let the window close; false: refuse
});

window.on<wsi::EventType::RESIZED>([](const math::uextent2& extent) noexcept {
    log::logger::ilog("resized to {}", extent);
});
```

**By callback type** — wrap the lambda; several can be registered in one call:

```cpp
window.on(
    wsi::KeyDownEventFunc { [&window](u8 /*keyboard*/, wsi::Key key, char character) noexcept {
        if (key == wsi::Key::ESCAPE) window.close();
        if (character != '\0') log::logger::ilog("typed '{}'", character);
    } },
    wsi::MouseButtonDownEventFunc { [](u8 /*mouse*/, wsi::MouseButton button, const math::ivec2& position) noexcept {
        log::logger::ilog("{} pressed at {}", button, position);
    } },
    wsi::MouseMovedEventFunc { [](u8 /*mouse*/, const math::ivec2& position) noexcept { /* … */ } });
```

The available events:

| Event | Arguments | Notes |
| --- | --- | --- |
| `CLOSED` | — | return a `bool` |
| `RESIZED` | new client-area extent | |
| `MINIMIZED`, `RESTORED` | — | pause and resume rendering here |
| `ACTIVATE`, `DEACTIVATE` | — | focus gained / lost |
| `MONITOR_CHANGED` | the new `Monitor` | DPI may have changed |
| `KEY_DOWN`, `KEY_UP` | keyboard id, `Key`, character | |
| `MOUSE_BUTTON_DOWN`, `MOUSE_BUTTON_UP` | mouse id, `MouseButton`, position | |
| `MOUSE_MOVED` | mouse id, position | |

Rules of the road:

- **One callback per event.** Registering again replaces the previous callback.
- Callbacks run inside `handle_events()` (and so inside `event_loop`), on the thread that calls
  it. No locking is needed between a callback and your per-frame function.
- The window stores the callbacks. Whatever they capture by reference — including the window
  itself — must stay alive and must not move. If the window lives in a class, register the
  callbacks once it has reached its final address.

### Keys and characters

A key event carries two different things:

- `Key` identifies the **physical key**, independent of layout: use it for controls (`W`, `ESCAPE`,
  `F11`).
- the `char` is the **text** that key produces with the current layout and modifiers, or `'\0'`:
  use it for typing. `is_text(c)` from `core` filters out control characters.

Holding a key repeats `KEY_DOWN`. For game-style input, turn that off:
`window.set_key_repeat(false);`

## Writing your own loop

`event_loop` is a convenience. When you need control over timing, drive the window yourself:

```cpp
auto previous = std::chrono::steady_clock::now();

while (window.is_open()) {
    window.handle_events();                         // never blocks

    const auto now   = std::chrono::steady_clock::now();
    const auto delta = std::chrono::duration_cast<fsecond>(now - std::exchange(previous, now));

    update(delta);
    render(window);
}
```

When the window is minimised there is nothing to draw; use the `MINIMIZED` / `RESTORED` events to
set a flag and sleep or yield instead of spinning.

## Changing the window

```cpp
window.set_title(std::format("My game — {} fps", fps));
window.set_extent({ .width = 1280u, .height = 720u });
window.toggle_fullscreen();

const auto size = window.extent();          // client area, in pixels
```

## Mouse modes

| Call | Effect | Typical use |
| --- | --- | --- |
| `hide_mouse()` | the cursor is not drawn over the window | custom cursors |
| `confine_mouse()` | the pointer cannot leave the window | strategy games, edge scrolling |
| `lock_mouse()` | the pointer stays where it is | |
| `set_relative_mouse()` | `MOUSE_MOVED` reports *movement* instead of position | first-person cameras |

Each has an `un…` / `toggle_…` counterpart and an `is_mouse_…()` query. A first-person camera
enables relative mode, locks and hides the pointer, and gives it back when focus is lost:

```cpp
window.on(wsi::ActivateEventFunc { [&window] noexcept {
              window.set_relative_mouse(true);
              window.lock_mouse();
              window.hide_mouse();
          } },
          wsi::DeactivateEventFunc { [&window] noexcept {
              window.set_relative_mouse(false);
              window.unlock_mouse();
              window.unhide_mouse();
          } });
```

## Drawing without a GPU

`fill_framebuffer` presents an array of pixels — one `ucolor_rgb` per pixel, rows from top to
bottom:

```cpp
auto pixels = dynarray<ucolor_rgb> {};

const auto redraw = [&](const math::uextent2& extent) {
    pixels.assign(extent.width * extent.height, colors::BLACK<u8>);
    for (auto [y, x] : multi_range(extent.height, extent.width))
        pixels[y * extent.width + x] = { .r = as<u8>(x * 255u / extent.width), .g = as<u8>(y * 255u / extent.height), .b = 64 };
};

redraw(window.extent());
window.on(wsi::ResizedEventFunc { [&](const math::uextent2& extent) noexcept { redraw(extent); } });

window.event_loop([&] noexcept { window.fill_framebuffer(pixels); });
```

The buffer must match the window's current extent, which is why it is rebuilt on `RESIZED`.
This is plenty for tools, visualisations and emulators; the
[software rendering tutorial](../tutorials/software-rendering.md) builds a complete program on it.

## Monitors

```cpp
for (const auto& monitor : wsi::get_monitors()) {
    log::logger::ilog("{}{} — scale {} — {} video modes",
                      monitor.name,
                      has_flag_bit(monitor.flags, wsi::Monitor::Flags::PRIMARY) ? " (primary)" : "",
                      monitor.scale_factor,
                      std::ranges::size(monitor.extents));
}

const auto& primary = wsi::get_primary_monitor();
const auto  largest = std::ranges::max(primary.extents, {}, [](const auto& e) { return e.width * e.height; });
```

`extents` lists the resolutions a monitor supports. The list of monitors is cached; pass `true` to
`get_monitors` to refresh it after a display is plugged in. `window.current_monitor()` tells you
where a window is.

## Rendering with the GPU

Create the window with `WindowFlag::EXTERNAL_CONTEXT` and give it to `gpu::Surface`:

```cpp
auto window  = wsi::Window::open("Vulkan", { 1280u, 720u }, wsi::WindowFlag::DEFAULT | wsi::WindowFlag::EXTERNAL_CONTEXT);
auto surface = TryX(gpu::Surface::create_from_window(instance, window));
```

Everything from there is in the [gpu guide](gpu.md). `window.native_handle()` gives the platform
handle if you need to hand the window to another library.

Reference: [`stormkit.wsi`](../reference/wsi.md).

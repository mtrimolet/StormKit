# `stormkit.wsi` reference

```cpp
import stormkit.wsi;      // or: import stormkit;
```

| | |
| --- | --- |
| Library | `stormkit-wsi` |
| xmake option | `wsi` (default: **off**; requires `log`) |
| Depends on | `stormkit.core`, `stormkit.log`; on Linux: xcb, xcb-util*, wayland, wayland-protocols, libxkbcommon |
| Namespace | `stormkit::wsi` |

**W**indow **S**ystem **I**ntegration: windows, monitors and input events on top of the native
APIs (Win32, X11 through xcb, Wayland, AppKit, UIKit).

The module is split into partitions (`:core`, `:monitor`, `:window`, `:keyboard`, `:mouse`) that
cannot be imported individually; `import stormkit.wsi;` gives everything.

> **Naming.** This module has not yet been moved to the snake_case convention used by `core`,
> `math`, `log` and `image`: types are `PascalCase` (`Window`, `Monitor`, `Key`). The names below
> are the ones currently declared.

---

## Window system

```cpp
enum class WM : u8 { WIN32, WAYLAND, X11, ANDROID, MACOS, IOS, TVOS, SWITCH };

constexpr auto as_string(WM wm) noexcept -> string_view;
constexpr auto to_string(WM wm) noexcept -> string;

auto parse_args(array_view<const string_view> args) noexcept -> void;
auto wm() noexcept -> WM;
```

| Function | Description |
| --- | --- |
| `wm()` | The window system in use. Fixed per platform, except on Linux: `WAYLAND` when the `WAYLAND_DISPLAY` environment variable is set, `X11` otherwise, unless overridden by `parse_args`. |
| `parse_args(args)` | Recognises `--x11` and `--wayland` to force the Linux backend. Call it before anything else in the module. |

---

## Monitors

```cpp
struct Monitor {
    enum class Flags { NONE = 0, PRIMARY };       // flag enum

    Flags                    flags = Flags::NONE;
    string                   name;
    dynarray<math::uextent2> extents;
    u32                      scale_factor = 1;
    void*                    native_handle = nullptr;

    constexpr auto operator<=>(const Monitor& other) const noexcept -> std::strong_ordering;
    constexpr auto operator==(const Monitor& other) const noexcept -> bool;
};

constexpr auto as_string(Monitor::Flags flags) noexcept -> string_view;
constexpr auto to_string(Monitor::Flags flags) noexcept -> string;
auto to_string(const Monitor& monitor) noexcept -> string;
template<typename FormatContext> auto format_as(const Monitor& monitor, FormatContext& ctx) noexcept;

auto get_monitors(bool update = false) noexcept -> array_view<const Monitor>;
auto get_primary_monitor() noexcept -> const Monitor&;
```

| Member | Description |
| --- | --- |
| `flags` | `PRIMARY` for the main display. |
| `name` | Name reported by the system. |
| `extents` | The video modes (resolutions) the monitor supports. |
| `scale_factor` | HiDPI scale. |
| `native_handle` | Platform handle (`HMONITOR`, `wl_output*`, …). |
| ordering | By flags, then name, then extents — the primary monitor sorts apart from the others. |

| Function | Description |
| --- | --- |
| `get_monitors(update)` | The connected monitors. The list is cached; pass `true` to query the system again. The returned view stays valid until the next refresh. |
| `get_primary_monitor()` | The monitor flagged `PRIMARY`. |

---

## Input identifiers

### `Key`

```cpp
inline constexpr auto GLOBAL_KEYBOARD_ID = 0_u8;

enum class Key : u8 { /* ... */ UNKNOWN = 255 };
constexpr auto as_string(Key key) noexcept -> string_view;
constexpr auto to_string(Key key) noexcept -> string;
```

Layout-independent key identifiers.

| Group | Enumerators |
| --- | --- |
| Letters | `A` … `Z` |
| Digits (top row) | `NUM_0` … `NUM_9` |
| Arrows | `LEFT`, `RIGHT`, `UP`, `DOWN` |
| Modifiers | `L_CONTROL`, `L_SHIFT`, `L_ALT`, `L_META`, `R_CONTROL`, `R_SHIFT`, `R_ALT`, `R_META` |
| Control | `ESCAPE`, `TAB`, `MENU`, `BACK_SPACE`, `CAPS_LOCK`, `ENTER`, `SPACE`, `PRINT_SCREEN`, `INSERT`, `DELETE`, `HOME`, `END`, `PAGE_UP`, `PAGE_DOWN` |
| Punctuation | `QUOTE`, `BACK_SLASH`, `COMMA`, `EQUAL`, `GRAVE_ACCENT`, `L_BRACKET`, `R_BRACKET`, `MINUS`, `PERIOD`, `SEMI_COLON`, `SLASH`, `ISO` |
| Function | `F1` … `F20` |
| Numpad | `NUMPAD_LOCK`, `NUMPAD_ADD`, `NUMPAD_SUBTRACT`, `NUMPAD_MULTIPLY`, `NUMPAD_DIVIDE`, `NUMPAD_DECIMAL`, `NUMPAD_ENTER`, `NUMPAD_EQUAL`, `NUMPAD_0` … `NUMPAD_9` |
| | `UNKNOWN` |

### `MouseButton`

```cpp
inline constexpr auto GLOBAL_MOUSE_ID = 0_u8;

enum class MouseButton : u8 { LEFT, RIGHT, MIDDLE, BUTTON_1, /* ... */ BUTTON_12 };
constexpr auto as_string(MouseButton button) noexcept -> string_view;
constexpr auto to_string(MouseButton button) noexcept -> string;
```

`GLOBAL_KEYBOARD_ID` and `GLOBAL_MOUSE_ID` (both `0`) designate "the" keyboard / mouse on systems
that do not distinguish devices; they are the default value of every `mouse_id` / `keyboard_id`
parameter.

---

## Events

```cpp
enum class EventType : u8 {
    NONE, CLOSED, MONITOR_CHANGED, RESIZED, RESTORED, MINIMIZED,
    KEY_DOWN, KEY_UP, MOUSE_BUTTON_DOWN, MOUSE_BUTTON_UP, MOUSE_MOVED,
    ACTIVATE, DEACTIVATE,
};
constexpr auto as_string(EventType type) noexcept -> string_view;
constexpr auto to_string(EventType type) noexcept -> string;
```

Events are delivered through **callbacks**. Each event has a dedicated callback type, a thin
subclass of `std::function` whose only purpose is to be a distinct type:

| Callback type | `EventType` | Signature | Sent when |
| --- | --- | --- | --- |
| `ClosedEventFunc` | `CLOSED` | `bool()` | The user asks to close the window. Return `true` to let it close, `false` to keep it open. Default: `true`. |
| `MonitorChangedEventFunc` | `MONITOR_CHANGED` | `void(const Monitor&)` | The window moved to another monitor. |
| `ResizedEventFunc` | `RESIZED` | `void(const math::uextent2&)` | The client area changed size. |
| `RestoredEventFunc` | `RESTORED` | `void()` | The window was restored from the minimised state. |
| `MinimizedEventFunc` | `MINIMIZED` | `void()` | The window was minimised. |
| `KeyDownEventFunc` | `KEY_DOWN` | `void(u8 keyboard, Key key, char c)` | A key was pressed. `c` is the translated character, `'\0'` when there is none. |
| `KeyUpEventFunc` | `KEY_UP` | `void(u8 keyboard, Key key, char c)` | A key was released. |
| `MouseButtonDownEventFunc` | `MOUSE_BUTTON_DOWN` | `void(u8 mouse, MouseButton button, const math::ivec2& position)` | A button was pressed. |
| `MouseButtonUpEventFunc` | `MOUSE_BUTTON_UP` | `void(u8 mouse, MouseButton button, const math::ivec2& position)` | A button was released. |
| `MouseMovedEventFunc` | `MOUSE_MOVED` | `void(u8 mouse, const math::ivec2& position)` | The pointer moved. Position is relative to the client area, or a delta in relative mode. |
| `ActivateEventFunc` | `ACTIVATE` | `void()` | The window gained focus. |
| `DeactivateEventFunc` | `DEACTIVATE` | `void()` | The window lost focus. |

`EventCallbackFunc` is the concept satisfied by anything convertible to one of these types.

---

## `Window`

```cpp
enum class WindowFlag : u8 {        // flag enum
    DEFAULT          = 0b1,
    BORDERLESS       = 0b10,
    RESIZEABLE       = 0b100,
    EXTERNAL_CONTEXT = 0b1000,
};

using NativeHandle = void*;

class Window {
  public:
    static auto open(string title, const math::uextent2& size, WindowFlag flags) noexcept -> Window;
    static auto allocate_and_open(string title, const math::uextent2& size, WindowFlag flags) noexcept -> heap_ptr<Window>;

    Window(Window&&) noexcept;                      // move-only
    auto operator=(Window&&) noexcept -> Window&;
    ~Window() noexcept;

    // see the sections below
};
```

| `WindowFlag` | Effect |
| --- | --- |
| `DEFAULT` | Decorated, fixed-size window. |
| `BORDERLESS` | No title bar or borders. |
| `RESIZEABLE` | The user can resize the window. |
| `EXTERNAL_CONTEXT` | The window is driven by an externally created surface/context. |

`WindowFlag` is formattable (through `as<string_view>`).

### Lifetime and event loop

```cpp
auto close() noexcept -> void;
auto is_open() const noexcept -> bool;
auto visible() const noexcept -> bool;
auto handle_events() noexcept -> void;
auto event_loop() noexcept -> void;
auto event_loop(std::invocable<> auto&& func) noexcept -> void;
```

| Member | Description |
| --- | --- |
| `open(title, size, flags)` | Creates and shows the window. |
| `close()` | Closes it; `is_open()` becomes false. |
| `handle_events()` | Processes the pending system events and invokes the registered callbacks, **on the calling thread**. Never blocks. |
| `event_loop(func)` | `while (is_open()) { func(); handle_events(); }` — `func` is your per-frame work. |
| `event_loop()` | Same with nothing to do per frame. |

### Registering callbacks

```cpp
template<EventCallbackFunc T>                    auto on(T&& callback) noexcept -> void;
template<EventCallbackFunc... Ts>                auto on(Ts&&... callbacks) noexcept -> void;      // two or more
template<EventType TYPE, EventCallbackFunc T>    auto on(T&& callback) noexcept -> void;
```

| Form | How the event is selected |
| --- | --- |
| `window.on(wsi::ResizedEventFunc { lambda })` | From the **type** of the argument. Wrap the lambda in the callback type. |
| `window.on(a, b, c, ...)` | Several typed callbacks at once. |
| `window.on<wsi::EventType::CLOSED>(lambda)` | From the template argument; the lambda can be passed bare. |

Each event has exactly **one** slot: registering a callback replaces the previous one. Callbacks
are stored in the window, so anything they capture by reference must outlive it.

```cpp
auto window = wsi::Window::open("Hello", { .width = 800u, .height = 600u }, wsi::WindowFlag::RESIZEABLE);

window.on<wsi::EventType::CLOSED>([] noexcept { return true; });
window.on(wsi::ResizedEventFunc { [](const math::uextent2& extent) noexcept { std::println("{}", extent); } },
          wsi::KeyDownEventFunc { [&window](u8, wsi::Key key, char) noexcept {
              if (key == wsi::Key::ESCAPE) window.close();
          } });

window.event_loop([&] noexcept { window.clear(); });
```

### Properties

```cpp
auto title() const noexcept -> const string&;                 auto set_title(string title) noexcept -> void;
auto extent() const noexcept -> const math::uextent2&;        auto set_extent(const math::uextent2& extent) noexcept -> void;
auto fullscreen() const noexcept -> bool;                     auto set_fullscreen(bool fullscreen) noexcept -> void;
auto toggle_fullscreen() noexcept -> void;
auto current_monitor() const noexcept -> const Monitor&;
auto native_handle() const noexcept -> NativeHandle;
auto wm() const noexcept -> WM;
```

| Member | Description |
| --- | --- |
| `extent()` | Size of the client area, in pixels. |
| `native_handle()` | `HWND`, `xcb_window_t`, `wl_surface*`, `NSView*`… as a `void*`. What the gpu module needs to create a surface. |
| `wm()` | The backend this particular window uses. |

### Software framebuffer

```cpp
auto clear(const ucolor_rgb& color = colors::BLACK<u8>) noexcept -> void;
auto fill_framebuffer(array_view<const ucolor_rgb> colors) noexcept -> void;
```

Draw without a GPU API:

| Member | Description |
| --- | --- |
| `clear(color)` | Fills the client area with one colour. |
| `fill_framebuffer(pixels)` | Presents a full image. `pixels` holds `extent().width * extent().height` colours, row by row from the top-left. Re-create the buffer in your `RESIZED` callback. |

### Mouse

```cpp
auto confine_mouse(bool confined = true, u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto unconfine_mouse(u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto toggle_confined_mouse(u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto is_mouse_confined(u8 mouse_id = GLOBAL_MOUSE_ID) const noexcept -> bool;

auto lock_mouse(bool locked = true, u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto unlock_mouse(u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto toggle_locked_mouse(u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto is_mouse_locked(u8 mouse_id = GLOBAL_MOUSE_ID) const noexcept -> bool;

auto hide_mouse(bool hidden = true, u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto unhide_mouse(u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto toggle_hidden_mouse(u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto is_mouse_hidden(u8 mouse_id = GLOBAL_MOUSE_ID) const noexcept -> bool;

auto set_relative_mouse(bool enabled = true, u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto toggle_relative_mouse(u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
auto is_mouse_relative(u8 mouse_id = GLOBAL_MOUSE_ID) const noexcept -> bool;

auto set_mouse_position(const math::ivec2& position, u8 mouse_id = GLOBAL_MOUSE_ID) noexcept -> void;
```

| Mode | Effect |
| --- | --- |
| confined | The pointer cannot leave the window. |
| locked | The pointer is pinned in place. |
| hidden | The cursor is not drawn over the window. |
| relative | `MOUSE_MOVED` reports motion deltas instead of positions — the mode for first-person cameras, usually combined with *locked* and *hidden*. |

`set_mouse_position` warps the pointer, in client-area coordinates.

### Keyboard

```cpp
auto set_key_repeat(bool enabled = true, u8 keyboard_id = GLOBAL_KEYBOARD_ID) noexcept -> void;
auto disable_key_repeat(u8 keyboard_id = GLOBAL_KEYBOARD_ID) noexcept -> void;
auto toggle_key_repeat(u8 keyboard_id = GLOBAL_KEYBOARD_ID) noexcept -> void;
auto is_key_repeat_enabled(u8 keyboard_id = GLOBAL_KEYBOARD_ID) const noexcept -> bool;

auto show_virtual_keyboard(bool visible = true) noexcept -> void;
auto hide_virtual_keyboard() noexcept -> void;
auto toggle_virtual_keyboard() noexcept -> void;
auto is_virtual_keyboard_visible() const noexcept -> bool;
```

| Member | Description |
| --- | --- |
| key repeat | When enabled, holding a key sends repeated `KEY_DOWN` events. Disable it for game-style input. |
| virtual keyboard | The on-screen keyboard of touch platforms. |

---

## Status

- Backends present in the tree: Win32, X11, Wayland, macOS, iOS.
- The interface refers to `meta::IsConvertibleToOneOf` and `meta::IsCanonical`, and the `Monitor`
  formatter uses the pre-`tag_invoke` `format_as` / `to_string` hooks. These predate the current
  `stormkit.core` and are expected to change when the module is migrated.

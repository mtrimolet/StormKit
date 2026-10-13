# `stormkit.lua` reference

```cpp
import stormkit.lua;      // or: import stormkit;
```

| | |
| --- | --- |
| Library | `stormkit-lua` |
| xmake option | `lua` (default: **off**; requires `log`) |
| Depends on | `stormkit.core`, `stormkit.log`, plus `image` / `entities` / `wsi` / `gpu` when those options are on; [Luau](https://luau.org), [sol2](https://github.com/ThePhD/sol2) |
| Namespace | `stormkit::lua` |
| Header | `<stormkit/lua/lua.hpp>` |

Embeds a [Luau](https://luau.org) interpreter and exposes StormKit to scripts.

> The scripting language is **Luau** (Roblox's Lua 5.1 dialect with optional types), driven
> through sol2. `sol::` types appear in the C++ interface; include `<stormkit/lua/lua.hpp>` in the
> global module fragment of any file that names them.

> **Status.** Like `wsi`, this module still uses the earlier `PascalCase` naming, and parts of its
> implementation refer to names the other modules no longer export. The C++ interface below is
> the one declared in `modules/stormkit/lua.cppm`.

---

## `Modules`

```cpp
struct Modules {
    bool log      = false;
    bool image    = false;
    bool entities = false;
    bool wsi      = false;
    bool gpu      = false;
};
```

Selects which StormKit libraries are bound into the script environment. `core` bindings are always
installed. Requesting a library that was not compiled in (its xmake option is off) logs an error
and is otherwise ignored.

## `Engine`

```cpp
class Engine {
  public:
    using InitUserLibrariesClosure = std::function<void(sol::state&)>;

    static auto load_from_file(stdfs::path path, Modules modules = {},
                               InitUserLibrariesClosure init_user_libraries = /* no-op */) noexcept -> Engine;
    auto run() noexcept -> sol::state;

    static auto run(stdfs::path file, Modules modules = {},
                    InitUserLibrariesClosure init_user_libraries = /* no-op */) noexcept -> void;

    Engine(Engine&&) noexcept;                       // move-only
    auto operator=(Engine&&) noexcept -> Engine&;
    ~Engine() noexcept;
};
```

| Member | Description |
| --- | --- |
| `load_from_file(path, modules, init)` | Reads the script source into memory. A file that cannot be read is a contract violation. |
| `run()` | Creates a fresh `sol::state`, installs the [environment](#script-environment), calls `init_user_libraries(state)`, executes the script and **returns the state**, so that C++ can read globals or call functions the script defined. A script error is logged (`elog`) rather than propagated. Each call starts from a new state. |
| `Engine::run(file, modules, init)` | Shorthand for `load_from_file(...).run()` when the resulting state is not needed. |
| `init_user_libraries` | Your hook to register application functions and types before the script runs. |

```cpp
#include <stormkit/lua/lua.hpp>

import std;
import stormkit;

using namespace stormkit;

struct player { int health = 100; };

auto run_script() -> void {
    auto engine = lua::Engine::load_from_file("scripts/game.luau", { .log = true }, [](sol::state& state) {
        state.new_usertype<player>("player", "health", &player::health);
        state["spawn"] = [] { return player {}; };
    });

    auto state = engine.run();

    auto on_tick = sol::protected_function { state["on_tick"] };
    if (on_tick.valid()) lua::luacall(on_tick, 0.016);
}
```

## `luacall`

```cpp
template<typename... Ts>
auto luacall(const sol::protected_function& function, Ts&&... args) noexcept -> sol::protected_function_result;
```

Calls a Lua function and **checks the result**: a Lua runtime error fails a contract with the Lua
error message and traceback. Use it for calls that are not supposed to fail; call the
`sol::protected_function` directly when you want to handle the error yourself.

---

## Script environment

### Standard libraries

`base`, `bit32`, `debug`, `io`, `os`, `string` and `table` are opened. Three globals are replaced:

| Global | Behaviour |
| --- | --- |
| `format(fmt, ...)` | `std::format`-style: each `{}` in `fmt` is replaced by `tostring` of the next argument. The number of arguments must match the number of placeholders (contract-checked). No format specifiers. |
| `print(fmt, ...)` | `format`, then prints a line to standard output. |
| `tostring(value)` | As in Lua, except that tables are rendered recursively as `[lua_table key: value, ...]`. |

```lua
print("{} + {} = {}", 1, 2, 1 + 2)
```

### `core` (always available)

| Name | Contents |
| --- | --- |
| `fcolor`, `ucolor` | Tables holding the colour types `rgb` and `rgba` (`f32` and `u8` components respectively): `fcolor.rgb`, `ucolor.rgba`, … Each type has its component fields (`r`, `g`, `b`, `a`), `component_count`, `layout` and the preset constants `BLACK`, `GRAY`, `SILVER`, `WHITE`, `MAROON`, `RED`, `OLIVE`, `YELLOW`, `GREEN`, `LIME`, `TEAL`, `AQUA`, `NAVY`, `BLUE`, `PURPLE`, `FUSCHIA`, `TRANSPARENT` |
| `color_layout` | The layout enumeration |
| `math` | Vector and matrix types with `add`, `sub`, `mul`, `div`, `dot`, `cross`, `normalize`, `determinant`, `transpose`, `inverse`, `is_inversible`, `is_orthogonal`, `translate`, `scale`, `rotate`, `orthographique`, `perspective`, `look_at`, `identity`; extents (`rank`); rectangles (`position`, `extent`, `to_bounding_rect`, `to_rect`, `topleft`, `bottomright`, `AABB`); `math.angle.radians` |

These mirror the C++ [`color`](core-foundation.md#stormkitcorecolor) and [math](math.md) APIs.

### `log` (`Modules::log`)

| Function | C++ equivalent |
| --- | --- |
| `log.debug(fmt, ...)` | `dlog` |
| `log.info(fmt, ...)` | `ilog` |
| `log.warning(fmt, ...)` | `wlog` |
| `log.error(fmt, ...)` | `elog` |
| `log.fatal(fmt, ...)` | `flog` |

Arguments are formatted with the script-side `format`. Messages are emitted under the `lua`
log module; a [logger](log.md#logger) must exist on the C++ side.

### `wsi` (`Modules::wsi`)

| Name | Contents |
| --- | --- |
| `wsi.window_manager`, `wsi.key`, `wsi.mouse_button`, `wsi.window_flag`, `wsi.event_type`, `wsi.monitor_flag` | The corresponding enumerations |
| `wsi.monitor` | `flags`, `name`, `extents`, `scale_factor` |
| `wsi.window.open(title, width, height, flags)` | Creates a window |
| window properties | `window_manager`, `extent`, `set_extent`, `title`, `set_title`, `close`, `clear()` / `clear(color)` |
| window toggles | `fullscreen`, `toggle_fullscreen`, `is_mouse_hidden`, `toggle_hidden_mouse`, `is_mouse_locked`, `toggle_locked_mouse`, `is_mouse_confined`, `toggle_confined_mouse`, `is_mouse_relative`, `toggle_relative_mouse`, `is_key_repeat_enabled`, `toggle_key_repeat` |
| window events | `on_closed`, `on_monitor_changed`, `on_resized`, `on_restored`, `on_minimized`, `on_key_down`, `on_key_up`, `on_mouse_button_down`, `on_mouse_button_up`, `on_mouse_moved`, `on_activated`, `on_deactivated` |
| `window:event_loop(fn)` | Runs until the window closes, calling `fn` each iteration |

Callbacks receive the same arguments as their [C++ counterparts](wsi.md#events).

```lua
local window = wsi.window.open("Hello from Luau", 800, 600, wsi.window_flag.RESIZEABLE)

window:on_closed(function() return true end)
window:on_resized(function(extent) print("resized: {}", extent) end)
window:on_key_down(function(_, key, _)
  if key == wsi.key.ESCAPE then window:close() end
end)

window:event_loop(function() window:clear() end)
```

### `entities` (`Modules::entities`)

An entity `manager` type exposing `make_entity`, `destroy_entity`, `destroy_all_entities`,
`has_entity`, `entities`, `entity_count`, `add_component`, `get_component`, `has_component`,
`components_types_of`, `add_system`, `has_system`, `remove_system` and `step`.
See the [entities reference](entities.md).

### `image`, `gpu`

`Modules::image` and `Modules::gpu` are accepted, but their binding functions are currently empty:
no names are added to the environment.

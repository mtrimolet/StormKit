# Guide: `stormkit.lua`

`stormkit.lua` embeds a scripting language in your application: load a script, run it, and let it
call into StormKit — and into your own code.

The language is [**Luau**](https://luau.org): Lua 5.1 syntax and semantics, plus optional type
annotations and a faster interpreter. Files conventionally end in `.luau`.

Enable the library with `--lua=y`.

```cpp
#include <stormkit/lua/lua.hpp>             // only in files that use sol:: types

import std;
import stormkit;

#include <stormkit/main/main_macro.hpp>

using namespace stormkit;
```

> This library still uses `PascalCase` names (`lua::Engine`). See the
> [status note](../reference/lua.md).

## Running a script

```cpp
auto main(array_view<const string_view> args) -> int {
    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    lua::Engine::run("scripts/hello.luau");
    return 0;
}
```

```lua
-- scripts/hello.luau
local who = "world"
print("hello, {}!", who)
print("2 + 2 = {}", 2 + 2)
```

A logger must exist first: the engine reports script errors through it.

### `print` is not Lua's `print`

The engine replaces three globals so that scripts format text the same way the C++ side does:

| Global | Behaviour |
| --- | --- |
| `format(fmt, ...)` | replaces each `{}` with the next argument and returns the string |
| `print(fmt, ...)` | `format`, then writes a line |
| `tostring(v)` | as usual, but prints tables with their contents |

The number of `{}` must match the number of arguments. A string with no placeholder is printed
as-is, so `print("done")` still works; `print(42)` does not — write `print("{}", 42)`.

## Choosing what scripts can use

By default a script sees the Luau standard libraries and StormKit's `core` bindings (colours and
math). Other libraries are opt-in, through the second argument:

```cpp
lua::Engine::run("scripts/game.luau", { .log = true, .wsi = true });
```

| Field | Gives scripts |
| --- | --- |
| *(always)* | `math` vectors, matrices, extents and rectangles; the colour types under `fcolor` / `ucolor` |
| `.log` | `log.info`, `log.debug`, `log.warning`, `log.error`, `log.fatal` |
| `.wsi` | `wsi.window`, the key / button / event enumerations, monitors |
| `.entities` | an entity manager |
| `.image`, `.gpu` | accepted, but nothing is bound yet |

A library must also have been enabled when StormKit was built; asking for one that was not logs an
error and carries on.

```lua
log.info("starting level {}", 3)
log.warning("texture {} is missing, using the default", name)
```

## A window from a script

With `.wsi = true`, an entire interactive program fits in a script:

```lua
local window = wsi.window.open("Scripted", 800, 600, wsi.window_flag.RESIZEABLE)

window:on_closed(function()
  return true
end)

window:on_resized(function(extent)
  print("resized to {}", extent)
end)

local clicks = 0
window:on_mouse_button_down(function(_, button, position)
  clicks = clicks + 1
  window:set_title(format("{} click(s), last at {}", clicks, position))
end)

window:on_key_down(function(_, key, _)
  if key == wsi.key.ESCAPE then
    window:close()
  elseif key == wsi.key.F11 then
    window:toggle_fullscreen()
  end
end)

window:event_loop(function()
  window:clear()
end)
```

The method names and callback arguments mirror the [C++ window](wsi.md). Methods are called with
`:`; enumerations are tables (`wsi.key.ESCAPE`, `wsi.mouse_button.LEFT`).

## Exposing your own code

Scripts become useful when they can reach your application. The third argument is a function that
receives the freshly created interpreter state — a `sol::state` — before the script runs:

```cpp
struct player {
    string name;
    int    health = 100;

    auto damage(int amount) -> void { health = std::max(0, health - amount); }
};

auto spawn(const string& name) -> player { return { .name = name }; }

auto main(array_view<const string_view> args) -> int {
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    lua::Engine::run("scripts/fight.luau", { .log = true }, [](sol::state& state) {
        state.new_usertype<player>("player",
                                   "name",   &player::name,
                                   "health", &player::health,
                                   "damage", &player::damage);
        state["spawn"]     = &spawn;
        state["DIFFICULTY"] = 3;
    });
    return 0;
}
```

```lua
local hero = spawn("Aria")
hero:damage(10 * DIFFICULTY)
log.info("{} has {} HP left", hero.name, hero.health)
```

Everything sol2 offers is available here — functions, lambdas, user types, tables, enumerations.
Its [documentation](https://sol2.readthedocs.io) is the reference for this part.

## Calling back into the script

`Engine::run` (the static function) runs a script and throws the state away. To *keep* the state —
to read results, or to call script functions later — use the two-step form:

```cpp
auto engine = lua::Engine::load_from_file("scripts/ai.luau", { .log = true });
auto state  = engine.run();                        // runs the top level; returns the sol::state

auto think = sol::protected_function { state["think"] };

while (running) {
    const auto action = lua::luacall(think, enemy_distance, health);
    apply(sol::object { action }.as<string>());
}
```

```lua
-- scripts/ai.luau
function think(distance, health)
  if health < 20 then return "flee" end
  if distance < 2 then return "attack" end
  return "approach"
end
```

This is the usual shape of a scripted application: the top level of the script defines functions
and data, and the host calls them at the right moments (per frame, on events).

`lua::luacall` calls a script function and turns a script error into a contract failure, with the
Lua message and traceback. For calls where failure is acceptable, call the
`sol::protected_function` yourself and test `result.valid()`.

`engine.run()` can be called again: each call creates a new state and re-executes the script from
the top, which gives you a simple "reload" key during development.

## Errors

| Situation | What happens |
| --- | --- |
| the script file cannot be read | contract failure when loading |
| syntax or runtime error at the top level of the script | logged with `elog`; `run` returns the state as it was |
| error inside a function called through `luacall` | contract failure with the Lua traceback |
| wrong number of arguments to `format` / `print` | contract failure |

## Practical advice

- **Keep the boundary narrow.** Expose a handful of verbs (`spawn`, `play_sound`, `load_level`)
  rather than your whole object model. The script stays readable and you keep freedom to refactor.
- **Decide who owns the loop.** Either the script drives (`window:event_loop(...)`, as above) or
  the host does and calls into the script. Mixing both is confusing.
- **Scripts are data.** Ship them as files next to the executable; the examples locate them
  through a `RESOURCE_DIR` definition set by the build.
- **Type annotations are free documentation.** Luau accepts
  `function think(distance: number, health: number): string`.

The [scripting tutorial](../tutorials/scripting.md) builds a small application along these lines.

Reference: [`stormkit.lua`](../reference/lua.md).

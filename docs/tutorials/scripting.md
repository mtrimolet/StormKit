# Tutorial: scripting a window

**Libraries:** `log`, `wsi`, `lua` (and `core`, `main`)

We will build an application whose *behaviour* lives in a Luau script while the *host* stays in
C++: the script opens a window and reacts to input; the host provides services the script calls
(a counter that survives across calls, a way to quit, a pick-a-colour function) and decides which
StormKit libraries the script may touch.

It is the architecture of most scripted tools and games, at the smallest possible scale.

```
┌──────────────── host (C++) ────────────────┐        ┌────────── script (Luau) ──────────┐
│ logger, engine, exposed functions and types │ ◀────▶ │ window, callbacks, application logic │
└─────────────────────────────────────────────┘        └──────────────────────────────────────┘
```

> `lua` and `wsi` are documented from their declared interfaces and still use `PascalCase` names
> ([status](../reference/lua.md)). The script side mirrors `examples/lua/wsi/events`.

## Setting up

```console
> xmake f --wsi=y --lua=y --devmode=y
```

```lua
-- examples/lua/scripted/xmake.lua
namespace("lua", function()
    target("scripted", function()
        add_rules("stormkit::example")
        add_files("src/*.cpp")

        if get_config("devmode") then
            add_defines(format('RESOURCE_DIR="%s"', path.unix(path.join(os.projectdir(), "examples/lua/scripted"))))
        end

        set_group("examples/stormkit-lua")
    end)
end)
```

`RESOURCE_DIR` tells the program where its script is while we develop.

## Step 1 — a host that runs a script

`src/main.cpp`:

```cpp
#include <stormkit/lua/lua.hpp>

import std;
import stormkit;

#include <stormkit/main/main_macro.hpp>

#ifndef RESOURCE_DIR
    #define RESOURCE_DIR "../share/stormkit"
#endif

using namespace stormkit;

namespace {
    constexpr auto LOG    = log::module { "host" };
    const auto     SCRIPT = std::filesystem::path { RESOURCE_DIR } / "lua" / "app.luau";
}

auto main(array_view<const string_view> args) -> int {
    wsi::parse_args(args);
    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    LOG.ilog("running {}", SCRIPT.string());
    lua::Engine::run(SCRIPT, { .log = true, .wsi = true });

    return 0;
}
```

`lua/app.luau`:

```lua
log.info("hello from Luau")
print("{} + {} = {}", 20, 22, 20 + 22)
```

- `<stormkit/lua/lua.hpp>` brings in sol2; we will need its types in step 3. It must come before
  the imports.
- `Engine::run(file, modules)` loads the file, builds an interpreter, binds the requested
  libraries and executes the script.
- `{ .log = true, .wsi = true }` is the **capability list**: this script may log and open windows.
  It could not use the entity manager even if StormKit was built with it.
- A logger exists before the engine runs; the engine reports script errors through it.

Run it (`xmake b stormkit::examples::lua::scripted`, then `xmake run …`): two lines of output, the
first through the logger.

## Step 2 — the script opens a window

Replace `app.luau`:

```lua
local window = wsi.window.open("Scripted", 800, 600, wsi.window_flag.RESIZEABLE)

window:on_closed(function()
  log.info("bye")
  return true
end)

window:on_resized(function(extent)
  log.debug("resized: {}", extent)
end)

window:on_key_down(function(_, key, character)
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

No C++ changed, and the program now has a window, input handling and an event loop.

- The bindings mirror the C++ API: `wsi.window.open`, `window:on_key_down`, `window:close`.
  Methods use `:`, enumerations are tables (`wsi.key.ESCAPE`).
- Callback arguments are the same as in C++ (keyboard id, key, character).
- `log.debug` only shows when the program is started with `--debug` — the script inherits the
  host's logger configuration.
- `window:event_loop(fn)` blocks until the window closes, so the script's top level *is* the
  application's main loop here.

## Step 3 — the host offers services

A script that can only call StormKit is a toy. The third argument of `Engine::run` receives the
interpreter state before the script runs; that is where the host publishes its own API.

Add to `main.cpp`, above `main`:

```cpp
struct app_stats {
    u32 clicks = 0;
    u32 keys   = 0;

    auto summary() const -> string { return std::format("{} click(s), {} key(s)", clicks, keys); }
};

auto pick_color(u32 index) -> ucolor_rgb {
    static constexpr auto PALETTE = std::array<ucolor_rgb, 4> {
        ucolor_rgb { .r = 30, .g = 30, .b = 46 },
        ucolor_rgb { .r = 24, .g = 78, .b = 119 },
        ucolor_rgb { .r = 42, .g = 157, .b = 143 },
        ucolor_rgb { .r = 231, .g = 111, .b = 81 },
    };
    return PALETTE[index % std::ranges::size(PALETTE)];
}
```

and change the call:

```cpp
auto stats = app_stats {};

lua::Engine::run(SCRIPT, { .log = true, .wsi = true }, [&stats](sol::state& state) {
    // a C++ type, with fields and a method
    state.new_usertype<app_stats>("app_stats",
                                  "clicks",  &app_stats::clicks,
                                  "keys",    &app_stats::keys,
                                  "summary", &app_stats::summary);

    // one shared instance, owned by the host
    state["stats"] = std::ref(stats);

    // free functions
    state["pick_color"] = &pick_color;
    state["app_name"]   = [] { return "scripted demo"; };
});

LOG.ilog("session over: {}", stats.summary());
```

What each registration does:

| C++ | Seen from Luau as |
| --- | --- |
| `new_usertype<app_stats>(…)` | a type whose objects have `.clicks`, `.keys` and `:summary()` |
| `state["stats"] = std::ref(stats)` | a global `stats` that **refers to** the host's object — changes are visible on both sides |
| `state["pick_color"] = &pick_color` | a global function |
| a lambda | likewise; captures are allowed |

Passing `std::ref` matters: without it the script would get a *copy*, and the final
`stats.summary()` in C++ would report zeros.

`pick_color` returns a `ucolor_rgb`, a type the `core` bindings already know, so the script can
pass the result straight to `window:clear`.

## Step 4 — the script uses them

```lua
local window = wsi.window.open(app_name(), 800, 600, wsi.window_flag.RESIZEABLE)
local background = pick_color(0)

local function refresh_title()
  window:set_title(format("{} — {}", app_name(), stats:summary()))
end

window:on_closed(function()
  return true
end)

window:on_mouse_button_down(function(_, button, _)
  if button == wsi.mouse_button.LEFT then
    stats.clicks = stats.clicks + 1
    background = pick_color(stats.clicks)
    log.info("click #{}", stats.clicks)
    refresh_title()
  end
end)

window:on_key_down(function(_, key, _)
  stats.keys = stats.keys + 1
  refresh_title()

  if key == wsi.key.ESCAPE then
    window:close()
  end
end)

refresh_title()

window:event_loop(function()
  window:clear(background)
end)
```

Each click changes the background, bumps the counter the host owns, and updates the title through
a method implemented in C++. When the window closes, `Engine::run` returns and the host prints the
totals it accumulated *through the script*:

```
[ INFO    | lua | 04 ] click #3
[ INFO    | host | 09 ] session over: 3 click(s), 17 key(s)
```

Notice the two module names: messages logged from the script are tagged `lua`, the host's are
tagged `host`.

## Step 5 — iterate without recompiling

The script is read each time the engine runs, so changing behaviour is: edit `app.luau`, restart.
Nothing is rebuilt.

To reload *without* restarting, keep the engine and run it again when asked. `run()` (the member
function) builds a fresh interpreter each time and returns it:

```cpp
auto engine = lua::Engine::load_from_file(SCRIPT, { .log = true, .wsi = true }, register_host_api);

for (auto reload = true; reload;) {
    auto state = engine.run();                          // returns when the script's event loop ends

    reload = state["wants_reload"].get_or(false);       // a global the script may set before closing
    if (reload) engine = lua::Engine::load_from_file(SCRIPT, { .log = true, .wsi = true }, register_host_api);
}
```

```lua
wants_reload = false

window:on_key_down(function(_, key, _)
  if key == wsi.key.F5 then
    wants_reload = true
    window:close()
  end
end)
```

(`register_host_api` is the lambda from step 3, given a name.) The returned `sol::state` is how
the host reads what the script left behind: here a flag, in a real program perhaps a table of
settings.

## When things go wrong

| Mistake | What you see |
| --- | --- |
| syntax error in the script, or an error at its top level | an `ERROR` log line `lua error!` followed by the message; `Engine::run` returns |
| `print("{} {}", 1)` — placeholder / argument mismatch | a contract failure naming the expected and actual counts |
| calling a function the host did not register | a Lua error: `attempt to call a nil value` |
| asking for `{ .entities = true }` when StormKit was built without it | an `ERROR` log line, and the `entities` table is simply absent |
| the script file is missing | a contract failure at load time |

## What to take away

- **The host decides the surface.** Which libraries (`Modules`) and which of its own functions and
  objects a script can reach is explicit, in one place.
- **Objects can be shared by reference.** State owned by C++ and mutated by the script stays in
  one copy.
- **Either side can own the loop.** Here the script does (`window:event_loop`). The alternative —
  the host loops and calls script functions such as `on_update` with
  [`lua::luacall`](../guides/lua.md#calling-back-into-the-script) — is described in the guide.
- **Logging is shared.** One logger, tagged by origin.

## Going further

- Expose an entity manager (`{ .entities = true }`, with `--entities=y`) and let the script define
  the systems of the [ECS tutorial](ecs-simulation.md).
- Give the script a typed interface file: Luau understands
  `declare function pick_color(index: number): ucolor`, and its analyzer will then check your
  scripts before you run them.
- Load several scripts as "mods": one `Engine` each, each with its own capability list.

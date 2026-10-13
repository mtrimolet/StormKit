# Tutorial: a simulation with the ECS

**Libraries:** `core`, `math`, `entities`, `wsi` (and `log`, `main`)

We will build a particle fountain: particles are **entities**, their properties are
**components**, and their behaviour comes from three **systems**. A window shows the result,
drawn pixel by pixel, and a mouse click sets off a burst.

The goal is to see how a simulation is *structured* with the ECS, and how it sits next to a window
loop.

> The `entities` library is mid-migration (see its [status note](../reference/entities.md)); this
> tutorial is written against the interface declared in `modules/stormkit/entities.cppm`.

## Setting up

```console
> xmake f --wsi=y --entities=y
```

```lua
-- examples/entities/fountain/xmake.lua
target("fountain", function()
    add_rules("stormkit::example")
    add_files("src/*.cpp")
    set_group("examples/stormkit-entities")
end)
```

```cpp
// examples/entities/fountain/src/main.cpp
import std;
import stormkit;

#include <stormkit/main/main_macro.hpp>

using namespace stormkit;
using namespace stormkit::literals;

namespace {
    constexpr auto LOG = log::module { "fountain" };
}
```

## Step 1 — the data

Decide what a particle *is* before deciding what it *does*. Four small components:

```cpp
struct position {
    static constexpr auto type() noexcept -> ecs::component_id { return as<underlying>("position"_hash32); }
    math::fvec2 value;
};

struct velocity {
    static constexpr auto type() noexcept -> ecs::component_id { return as<underlying>("velocity"_hash32); }
    math::fvec2 value;
};

struct lifetime {
    static constexpr auto type() noexcept -> ecs::component_id { return as<underlying>("lifetime"_hash32); }
    f32 remaining;
    f32 total;
};

struct tint {
    static constexpr auto type() noexcept -> ecs::component_id { return as<underlying>("tint"_hash32); }
    ucolor_rgb color;
};
```

- Each has a static `type()` returning its identifier; we derive it from a
  [compile-time string hash](../guides/core.md#hashing-strings).
- All four are trivially copyable — a requirement, since the manager stores components as raw
  bytes.
- They are deliberately separate. A system that only moves things needs `position` and `velocity`
  and never loads a colour.

## Step 2 — spawning

```cpp
auto spawn(ecs::entity_manager& world, const math::fvec2& origin, f32 spread, f32 speed) noexcept -> void {
    const auto e     = world.make_entity();
    const auto angle = rand(-spread, spread) - std::numbers::pi_v<f32> / 2.f;       // around "up"
    const auto v     = rand(speed * 0.6f, speed);
    const auto life  = rand(1.5f, 3.5f);

    world.add_component(e, position { origin });
    world.add_component(e, velocity { { std::cos(angle) * v, std::sin(angle) * v } });
    world.add_component(e, lifetime { .remaining = life, .total = life });
    world.add_component(e, tint { { .r = as<u8>(rand(180, 255)), .g = as<u8>(rand(120, 220)), .b = as<u8>(rand(20, 90)) } });
}
```

`rand(min, max)` is `core`'s thread-local random generator; the overload is chosen by the argument
type, floating-point or integer. For the colour we draw `int`s and convert with `as<u8>`, which
checks that the value fits.

An entity is nothing more than the identifier `e`; what makes it a particle is the set of
components we attach.

## Step 3 — the behaviour

Three systems, each a few lines, each concerned with one thing.

```cpp
constexpr auto GRAVITY = math::fvec2 { 0.f, 220.f };          // pixels / s², +Y is down on screen

auto install_systems(ecs::entity_manager& world) noexcept -> void {
    using entities = array_view<const ecs::entity>;

    world.add_system("gravity", { velocity::type() }, {
        .update = [](ecs::entity_manager& world, fsecond delta, entities all) {
            for (const auto e : all) {
                auto& v = world.get_component<velocity>(e);
                v.value = add(v.value, mul(GRAVITY, delta.count()));
            }
        },
    });

    world.add_system("movement", { position::type(), velocity::type() }, {
        .update = [](ecs::entity_manager& world, fsecond delta, entities all) {
            for (const auto e : all) {
                auto&       p = world.get_component<position>(e);
                const auto& v = world.get_component<velocity>(e);
                p.value = add(p.value, mul(v.value, delta.count()));
            }
        },
    });

    world.add_system("expiry", { lifetime::type() }, {
        .update = [](ecs::entity_manager& world, fsecond delta, entities all) {
            for (const auto e : all) {
                auto& life = world.get_component<lifetime>(e);
                life.remaining -= delta.count();
                if (life.remaining <= 0.f) world.destroy_entity(e);
            }
        },
    });
}
```

- A system declares the components it **requires**. The manager keeps, for each system, the list
  of entities that have all of them, and passes it as the last argument.
- `fsecond` is a floating-point duration in seconds; `delta.count()` is the `f32` inside.
- Vector arithmetic uses `math`'s free functions: `add(a, b)`, `mul(v, scalar)`.
- Systems run **in the order they are added**: gravity updates the velocity that movement then
  integrates.
- "expiry" destroys entities while iterating over them. That is safe: destruction is *deferred*
  until the start of the next step.

Nothing here knows about windows or pixels. You could run this world headless, or in a test.

## Step 4 — drawing

Rendering does not need to be a system. After stepping the world we simply query it:

```cpp
auto draw(const ecs::entity_manager& world, dynarray<ucolor_rgb>& pixels, const math::uextent2& extent) noexcept -> void {
    pixels.assign(extent.width * extent.height, ucolor_rgb { .r = 12, .g = 12, .b = 24 });

    const auto bounds = math::frect { .x = 0.f, .y = 0.f, .width = as<f32>(extent.width), .height = as<f32>(extent.height) };

    for (const auto e : world.entities_with_component(position::type())) {
        const auto& p = world.get_component<position>(e).value;
        if (not math::AABB(p, bounds)) continue;                        // off-screen

        const auto& life  = world.get_component<lifetime>(e);
        const auto& color = world.get_component<tint>(e).color;
        const auto  fade  = life.remaining / life.total;                // 1 -> 0

        const auto x = math::min(as<u32>(math::floor(p.x())), extent.width - 1u);
        const auto y = math::min(as<u32>(math::floor(p.y())), extent.height - 1u);

        pixels[y * extent.width + x] = {
            .r = unchecked_narrow<u8>(as<f32>(color.r) * fade),
            .g = unchecked_narrow<u8>(as<f32>(color.g) * fade),
            .b = unchecked_narrow<u8>(as<f32>(color.b) * fade),
        };
    }
}
```

- `entities_with_component` returns every entity carrying a component — a one-off query, with no
  system involved.
- `math::AABB(point, rect)` is the point-in-rectangle test; it spares us four comparisons and the
  bugs that come with them.
- Through a `const entity_manager&`, `get_component` returns `const` references: the drawing code
  cannot alter the simulation.
- The colour is faded by the fraction of life remaining. The multiplication produces a fractional
  value on purpose, hence `unchecked_narrow`.

## Step 5 — the loop

```cpp
auto main(array_view<const string_view> args) -> int {
    wsi::parse_args(args);
    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    auto window = wsi::Window::open("Fountain", { .width = 800u, .height = 600u }, wsi::WindowFlag::RESIZEABLE);
    auto world  = ecs::entity_manager {};
    auto pixels = dynarray<ucolor_rgb> {};
    auto burst  = std::optional<math::fvec2> {};

    install_systems(world);

    window.on(wsi::KeyDownEventFunc { [&window](u8, wsi::Key key, char) noexcept {
                  if (key == wsi::Key::ESCAPE) window.close();
              } },
              wsi::MouseButtonDownEventFunc { [&burst](u8, wsi::MouseButton button, const math::ivec2& position) noexcept {
                  if (button == wsi::MouseButton::LEFT) burst = math::fvec2 { as<f32>(position.x()), as<f32>(position.y()) };
              } });

    auto previous   = std::chrono::steady_clock::now();
    auto since_log  = fsecond { 0.f };

    window.event_loop([&] noexcept {
        const auto now   = std::chrono::steady_clock::now();
        const auto delta = std::min(std::chrono::duration_cast<fsecond>(now - std::exchange(previous, now)), fsecond { 0.05f });

        const auto extent = window.extent();
        if (extent.width == 0u or extent.height == 0u) return;                       // minimised

        // 1. input -> new entities
        const auto fountain = math::fvec2 { as<f32>(extent.width) / 2.f, as<f32>(extent.height) - 10.f };
        for (auto _ : range(8)) spawn(world, fountain, 0.35f, 420.f);

        if (burst) {
            for (auto _ : range(400)) spawn(world, *burst, std::numbers::pi_v<f32>, 260.f);
            burst.reset();
        }

        // 2. simulate
        world.step(delta);

        // 3. draw
        draw(world, pixels, extent);
        window.fill_framebuffer(pixels);

        since_log += delta;
        if (since_log >= fsecond { 1.f }) {
            LOG.dlog("{} particles", world.entity_count());
            since_log = fsecond { 0.f };
        }
    });

    return 0;
}
```

The frame has three clearly separated phases:

1. **Input becomes entities.** The mouse callback does not touch the world; it records a request
   (`burst`) that the frame function turns into `spawn` calls. Keeping structural changes in one
   place makes the program easy to reason about.
2. **`world.step(delta)`.** Applies pending creations and destructions, then runs the systems.
3. **Draw.** A read-only pass over the result.

Two details:

- The delta time is **clamped** to 50 ms. If the program is paused in a debugger or the window is
  dragged, the next frame would otherwise simulate a huge time step and fling every particle off
  screen.
- Particles spawned this frame take part in the systems from this frame's `step` on, because
  `step` begins by flushing pending changes.

## Run it

```console
> xmake b stormkit::examples::fountain
> xmake run stormkit::examples::fountain --debug
```

Click anywhere for a burst; `--debug` prints the live particle count every second.

## What to take away

| ECS idea | Here |
| --- | --- |
| entities are identifiers | `world.make_entity()` |
| data lives in small components | `position`, `velocity`, `lifetime`, `tint` |
| behaviour lives in systems that declare their needs | `gravity`, `movement`, `expiry` |
| membership is automatic | an entity with `velocity` is affected by gravity; one without is not |
| structural changes are deferred | `destroy_entity` inside a system; `spawn` before `step` |
| not everything is a system | `draw` is a plain function querying the world |

Adding behaviour means adding a system, not editing a class. Want particles to bounce on the
floor? One more system requiring `position` and `velocity`. Want *some* particles to ignore
gravity? Give gravity a `weight` component to require, and do not attach it to those.

## Going further

- **A bounce system**: when `position.y` passes the bottom edge, mirror it and multiply the
  vertical velocity by `-0.5f`.
- **Tag components**: add an empty-ish `sparkle` component to one particle in ten, and a system
  requiring it that spawns short-lived children.
- **A system with state**: turn "gravity" into a class holding a wind vector that changes over
  time, registered with `world.add_system("wind", { velocity::type() }, wind_object)`.
- **React to messages**: use `on_message_received` and `REMOVED_ENTITY_MESSAGE_ID` to count how
  many particles died each second.
- **Draw with the GPU** once the count gets large: upload positions to a vertex buffer each frame
  ([gpu guide](../guides/gpu.md#buffers)).

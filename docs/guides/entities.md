# Guide: `stormkit.entities`

An entity-component-system (ECS) organises a simulation around data instead of class hierarchies:

- an **entity** is just an identifier;
- a **component** is a piece of plain data attached to an entity (`position`, `velocity`,
  `health`);
- a **system** is logic that runs over every entity owning a given set of components.

"What an object is" becomes "which components it has", which can change at run time.

Enable the library with `--entities=y`. Its namespace is `stormkit::ecs`.

```cpp
import std;
import stormkit;

using namespace stormkit;
```

> The library is mid-migration: this guide follows the interface declared in
> `modules/stormkit/entities.cppm`. See the [status note](../reference/entities.md).

## Components

A component is a struct with a `type()` function returning its identifier. Make that function
`static` and the manager can find components from the type alone:

```cpp
using namespace stormkit::literals;

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
};
```

Hashing a name is a convenient way to get identifiers that are unique and stable without keeping a
central list. Any scheme works, as long as two component types never share an identifier.

Two constraints come from how components are stored — packed, as bytes, in one pool per type:

- components must be **trivially copyable**. Vectors, numbers, enums, fixed-size arrays and
  entity identifiers are fine; `std::string`, `dynarray` and owning pointers are not. Store an
  index or a handle to such data instead;
- keep them small and focused. A system only declares the components it reads; narrow components
  mean less data pulled through the cache.

## Entities

```cpp
auto world = ecs::entity_manager {};

const auto spark = world.make_entity();
world.add_component(spark, position { { 400.f, 300.f } });
world.add_component(spark, velocity { { 12.f, -40.f } });
world.add_component(spark, lifetime { 2.f });
```

`add_component` copies the component into the manager and returns a reference to the stored copy.

Querying and editing:

```cpp
if (world.has_component<velocity>(spark)) {
    auto& v = world.get_component<velocity>(spark);
    v.value = mul(v.value, 0.5f);
}

world.destroy_component(spark, lifetime::type());
world.destroy_entity(spark);
```

Do not hold on to references returned by `add_component` / `get_component`: they point into a
pool that moves when components of that type are added or removed. Fetch, use, let go.

## Systems

A system is a name, the components it needs, and an `update` callback. The manager works out which
entities qualify and hands the callback that list:

```cpp
world.add_system("movement", { position::type(), velocity::type() }, {
    .update = [](ecs::entity_manager& world, fsecond delta, array_view<const ecs::entity> entities) {
        for (const auto e : entities) {
            auto&       p = world.get_component<position>(e);
            const auto& v = world.get_component<velocity>(e);
            p.value = add(p.value, mul(v.value, delta.count()));
        }
    },
});

world.add_system("expiry", { lifetime::type() }, {
    .update = [](ecs::entity_manager& world, fsecond delta, array_view<const ecs::entity> entities) {
        for (const auto e : entities) {
            auto& life = world.get_component<lifetime>(e);
            life.remaining -= delta.count();
            if (life.remaining <= 0.f) world.destroy_entity(e);
        }
    },
});
```

An entity belongs to a system as soon as it has **all** the listed components — the spark above
is in both. Remove its `velocity` and it silently drops out of "movement".

### Systems as classes

When a system has state of its own, write a class. Only `update` is required; `pre_update`,
`post_update` and `on_message_received` are picked up when present:

```cpp
class gravity_system {
  public:
    explicit gravity_system(math::fvec2 gravity) noexcept : m_gravity { gravity } {}

    auto update(ecs::entity_manager& world, fsecond delta, array_view<const ecs::entity> entities) -> void {
        for (const auto e : entities) {
            auto& v = world.get_component<velocity>(e);
            v.value = add(v.value, mul(m_gravity, delta.count()));
        }
    }

    auto post_update(ecs::entity_manager&, array_view<const ecs::entity> entities) -> void {
        m_last_count = std::ranges::size(entities);
    }

  private:
    math::fvec2 m_gravity;
    usize       m_last_count = 0;
};

auto gravity = gravity_system { { 0.f, 98.f } };
world.add_system("gravity", { velocity::type() }, gravity);
```

The manager keeps a pointer to `gravity`: the object must outlive the manager and must not move.

## Stepping the world

```cpp
auto previous = std::chrono::steady_clock::now();

while (running) {
    const auto now   = std::chrono::steady_clock::now();
    const auto delta = std::chrono::duration_cast<fsecond>(now - std::exchange(previous, now));

    world.step(delta);
}
```

One `step` does, in order:

1. **flush** — applies everything that was requested since the last step: created entities join
   their systems, destroyed entities lose their components and free their identifiers, entities
   whose components changed are re-matched;
2. every system's `pre_update`;
3. every system's `update`;
4. every system's `post_update`.

Systems run in the order they were added, so register "gravity" before "movement" if movement
should see this frame's velocity.

### Changes are deferred

Creating or destroying entities does not take effect immediately; it is queued until the next
flush. That is what makes it safe to do from inside a system — as "expiry" does above — without
invalidating the list being iterated. The flip side: an entity created in a system is first
visited on the **next** step.

Call `world.flush()` yourself when you need the changes applied outside of `step`, for instance
after populating the world and before counting entities.

## Messages

The manager announces structural changes on an internal message bus, and systems can listen:

```cpp
world.add_system("audio", { emitter::type() }, {
    .update              = [](auto&, fsecond, auto) {},
    .on_message_received = [](ecs::entity_manager&, const ecs::message& message, array_view<const ecs::entity>) {
        if (message.id == ecs::entity_manager::REMOVED_ENTITY_MESSAGE_ID)
            for (const auto e : message.entities) stop_sounds_of(e);
    },
});
```

`ADDED_ENTITY_MESSAGE_ID` and `REMOVED_ENTITY_MESSAGE_ID` are the two built-in messages.

## Working outside systems

Not everything is a system. For one-off queries — a debug overlay, a save file — ask the manager
directly:

```cpp
for (const auto e : world.entities_with_component(position::type())) draw_marker(world.get_component<position>(e).value);

std::println("{} entities, spark has {} components", world.entity_count(), std::ranges::size(world.components_types_of(spark)));
```

Rendering is commonly done this way: a plain function that reads the components it needs after
`step`, rather than a system that would have to own a renderer.

## Design notes

- **Prefer many small systems** over one that does everything. Each is easy to test with a
  hand-built manager.
- **Use components as tags.** An empty-ish component (`struct frozen { static … type(); u8 _; };`)
  is how you say "this entity is in that state"; adding and removing it moves the entity in and
  out of the systems that require it.
- **Keep heavy data elsewhere.** A mesh, a sound, a string belong in a resource container;
  components hold the index.

The [ECS tutorial](../tutorials/ecs-simulation.md) builds a particle simulation with these pieces
and draws it in a window.

Reference: [`stormkit.entities`](../reference/entities.md).

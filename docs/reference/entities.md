# `stormkit.entities` reference

```cpp
import stormkit.entities;      // or: import stormkit;
```

| | |
| --- | --- |
| Library | `stormkit-entities` |
| xmake option | `entities` (default: **off**) |
| Depends on | `stormkit.core` |
| Namespace | `stormkit::ecs` |

A small entity-component-system: entities are integers, components are plain data stored in
per-type byte pools, systems are sets of callbacks run over the entities that own a given set of
component types.

> **Status.** This module is mid-migration. The interface below (namespace `ecs`, snake_case) is
> what `modules/stormkit/entities.cppm` declares; the implementation files under `src/entities`
> still use the previous names (`stormkit::entities::EntityManager`), and the interface refers to
> a few helpers the current core no longer exports (`ref<T>`, `monadic::as_ref`, `hash(name)`).
> Treat this page as the description of the intended API.

---

## Basic types

```cpp
using component_id = u32;
using entity       = u32;
inline constexpr auto INVALID_ENTITY = entity { 0 };
```

Entity identifiers start at `1`; identifiers of destroyed entities are recycled.

## Components

```cpp
namespace meta {
    template<typename T> concept is_component = requires(T&& c) { { c.type() } -> /* component_id */; };
    template<typename T> concept component_with_static_type = is_component<T> and requires { { T::type() } -> same_as<component_id>; };
}
```

A component is any type exposing its identifier through `type()`. Make it `static` whenever the
identifier is known at compile time, which enables the shorter, type-only overloads of the manager:

```cpp
struct position {
    static constexpr auto type() noexcept -> ecs::component_id { return 1; }
    math::fvec2 value;
};
```

Constraints:

- Components are stored by **byte copy** (`std::bit_cast` on insertion). They must be trivially
  copyable: no `std::string`, no owning pointers.
- All components sharing an identifier must have the same size (checked by contract).
- Identifiers only need to be unique within one `entity_manager`. Deriving them from a string hash
  (`"position"_hash32`) is a convenient way to get stable values.

---

## Messages

```cpp
struct message {
    u32              id;
    dynarray<entity> entities;
};

class message_bus {
  public:
    message_bus();                                  // move-only
    auto push(message&& message) -> void;
    auto top() const -> const message&;
    auto pop() -> void;
    auto empty() const noexcept -> bool;
};
```

A FIFO queue of notifications. The manager owns one and uses it to announce entity creation and
destruction, with the identifiers `entity_manager::ADDED_ENTITY_MESSAGE_ID` (`1`) and
`entity_manager::REMOVED_ENTITY_MESSAGE_ID` (`2`). Systems receive messages through their
`on_message_received` callback.

---

## `system`

```cpp
class system {
  public:
    using component_ids = dynarray<component_id>;

    using pre_update_cb          = std::function<void(entity_manager&, array_view<const entity>)>;
    using update_cb              = std::function<void(entity_manager&, fsecond, array_view<const entity>)>;
    using post_update_cb         = std::function<void(entity_manager&, array_view<const entity>)>;
    using on_message_received_cb = std::function<void(entity_manager&, const message&, array_view<const entity>)>;

    struct Closures {
        pre_update_cb          pre_update          = /* no-op */;
        update_cb              update;
        post_update_cb         post_update         = /* no-op */;
        on_message_received_cb on_message_received = /* no-op */;
    };

    system(string name, component_ids components, Closures&& closures) noexcept;     // move-only

    auto name() const noexcept -> const string&;
    auto components_used() const noexcept -> const component_ids&;
};
```

A system is a name, the list of component types it requires, and callbacks. The manager maintains,
for each system, the list of entities that own **all** the required components, and passes it to
every callback.

| Callback | Called | Receives |
| --- | --- | --- |
| `pre_update` | at the start of `step`, for every system | the matching entities |
| `update` | after all `pre_update`s | the frame delta (`fsecond`) and the matching entities |
| `post_update` | after all `update`s | the matching entities |
| `on_message_received` | when a message is dispatched | the message and the matching entities |

Only `update` is mandatory. Systems are normally created through
[`entity_manager::add_system`](#systems) rather than constructed directly.

```cpp
namespace meta {
    template<typename T> concept system_type = /* T has update(entity_manager&, fsecond, entities) */;
}
```

---

## `entity_manager`

```cpp
class entity_manager {
  public:
    using delete_cb = std::function<void(byte*)>;
    static constexpr auto ADDED_ENTITY_MESSAGE_ID   = 1;
    static constexpr auto REMOVED_ENTITY_MESSAGE_ID = 2;

    entity_manager() noexcept;                      // move-only
    // sections below
};
```

### Entities

```cpp
auto make_entity() noexcept -> entity;
auto destroy_entity(entity entity) noexcept -> void;
auto destroy_all_entities() noexcept -> void;
auto has_entity(entity entity) const noexcept -> bool;
auto entities() const noexcept -> const dynarray<entity>&;
auto entity_count() const noexcept -> usize;
```

| Member | Description |
| --- | --- |
| `make_entity()` | Allocates an identifier (recycling a free one when possible) and queues an *added* message. The entity becomes part of `entities()` and of the systems at the next [`flush`](#stepping). |
| `destroy_entity(e)` | Marks the entity for destruction and queues a *removed* message. Its components are destroyed and its identifier released at the next `flush`. |
| `destroy_all_entities()` | Marks every entity. |
| `has_entity(e)` | True for live entities, including ones created since the last flush. |

### Components

```cpp
template<meta::is_component T> auto add_component(entity entity, T&& component) noexcept -> T&;

template<meta::component_with_static_type T> auto has_component(entity entity) const noexcept -> bool;
auto has_component(entity entity, component_id type) const noexcept -> bool;
auto has_component(entity entity, string_view name) const noexcept -> bool;

template<meta::component_with_static_type T> auto get_component(entity entity) noexcept -> T&;
template<meta::is_component T>               auto get_component(entity entity, component_id type) noexcept -> T&;
template<meta::is_component T>               auto get_component(entity entity, string_view name) noexcept -> T&;

auto destroy_component(entity entity, component_id type) noexcept -> void;
auto destroy_component(entity entity, string_view name) noexcept -> void;

auto components_types_of(entity entity) const noexcept -> dynarray<component_id>;
auto entities_with_component(component_id type) const noexcept -> dynarray<entity>;
auto entities_with_component(string_view name) const noexcept -> dynarray<entity>;

template<meta::component_with_static_type T> auto components_of_type() noexcept;                       // references to every T
template<meta::is_component T>               auto components_of_type(component_id type) noexcept;
template<meta::is_component T>               auto components_of_type(string_view name) noexcept;
```

`get_component` and `components_of_type` are const-propagating.

| Member | Description |
| --- | --- |
| `add_component(e, c)` | Copies `c` into the pool of its type and returns a reference to the stored copy. Pre-conditions: the entity exists and does not already have a component of that type. The entity is re-evaluated against the systems at the next flush. |
| `has_component` | By static type, by identifier, or by name (the name is hashed to an identifier). |
| `get_component<T>(e)` | Reference to the stored component. Pre-condition: it exists. |
| `destroy_component` | Removes one component from one entity. |
| `components_types_of(e)` | The identifiers of every component the entity owns. |
| `entities_with_component(type)` | Every entity owning that component. |
| `components_of_type<T>()` | References to every stored `T`. |

References returned by `add_component` / `get_component` point into a growable pool: **they are
invalidated by adding or destroying a component of the same type**. Do not keep them across such
calls.

Low-level access, for bindings and type-erased code:

```cpp
auto add_raw_component(entity entity, component_id type, array_view<const byte> component,
                       delete_cb delete_func) noexcept -> array_view<byte>;
auto get_raw_component(entity entity, component_id type) noexcept -> array_view<byte>;     // const-propagating
```

`delete_func` is invoked with the address of each stored component when it is destroyed.

### Systems

```cpp
template<meta::system_type T>
auto add_system(string name, system::component_ids types, T& system) noexcept -> system&;
auto add_system(string name, system::component_ids types, system::Closures&& closures) noexcept -> system&;

auto has_system(string_view name) const noexcept -> bool;
auto remove_system(string_view name) noexcept -> void;
auto get_system(string_view name) noexcept -> system&;        // const-propagating
auto systems() noexcept -> /* the registered systems */;      // const-propagating
```

| Member | Description |
| --- | --- |
| `add_system(name, types, closures)` | Registers callbacks. Existing entities that match `types` are attached immediately. |
| `add_system(name, types, object)` | Registers an **object**: its `update` member is bound, and `pre_update`, `post_update` and `on_message_received` too when the class defines them. The object is captured by address and must outlive the manager. |
| `get_system(name)` | Pre-condition: `has_system(name)`. |

```cpp
auto manager = ecs::entity_manager {};

manager.add_system("movement", { position::type(), velocity::type() }, {
    .update = [](auto& manager, fsecond delta, auto entities) {
        for (auto e : entities) {
            auto&       pos = manager.template get_component<position>(e);
            const auto& vel = manager.template get_component<velocity>(e);
            pos.value = add(pos.value, mul(vel.value, delta.count()));
        }
    },
});

const auto e = manager.make_entity();
manager.add_component(e, position { { 0.f, 0.f } });
manager.add_component(e, velocity { { 1.f, 0.f } });
```

### Stepping

```cpp
auto flush() noexcept -> void;
auto step(fsecond delta) noexcept -> void;
```

| Member | Description |
| --- | --- |
| `flush()` | Applies the deferred structural changes: destroys the components of removed entities and recycles their identifiers, inserts created entities, re-evaluates which systems each modified entity belongs to, and dispatches the pending messages. |
| `step(delta)` | One simulation tick: `flush()`, then every system's `pre_update`, then every `update(delta)`, then every `post_update`. Systems run in registration order. |

Because changes are deferred, it is safe to create and destroy entities from inside a system
callback; they take effect at the beginning of the next `step`.

```cpp
auto clock = std::chrono::steady_clock::now();
while (running) {
    const auto now   = std::chrono::steady_clock::now();
    const auto delta = std::chrono::duration_cast<fsecond>(now - std::exchange(clock, now));
    manager.step(delta);
}
```

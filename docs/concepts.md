# Concepts and conventions

StormKit has a recognisable style. The same handful of ideas appear in every library; knowing them
once saves re-learning them per module.

## Modules, not headers

Every library is a named C++ module with sub-modules that follow the directory layout:

```
stormkit                      umbrella: core + every enabled library
stormkit.core                 all of core
stormkit.core.typesafe          a group
stormkit.core.typesafe.flags      one file
```

Names live in `namespace stormkit`, with one nested namespace per library (`stormkit::math`,
`stormkit::log`, `stormkit::image`, `stormkit::wsi`, `stormkit::gpu`, `stormkit::ecs`,
`stormkit::lua`). `core` is the exception: it is an **inline** namespace, so its names are used
unqualified after `using namespace stormkit;` — `u32`, not `core::u32`.

Sub-namespaces with a fixed meaning:

| Namespace | Contents |
| --- | --- |
| `stormkit::meta` (and `math::meta`, …) | concepts and type aliases |
| `stormkit::monadic` | small closures for `.transform(…)`, `.or_else(…)`, range pipelines |
| `stormkit::literals` | user-defined literals (`42_u8`, `4_kib`, `"x"_hash32`) |
| `stormkit::io` | file access |
| `stormkit::colors` | colour presets |

## Code style

The whole code base, and therefore every signature in the reference, uses:

- **trailing return types** — `auto size() const noexcept -> usize;`
- **`auto` and braces for variables** — `auto window = wsi::Window::open(…);`,
  `const auto count = 3_u32;`
- **alternative operator tokens** — `not`, `and`, `or`
- **`noexcept` nearly everywhere** — errors travel in return values, not exceptions
- **deducing `this`** for const-propagating accessors — written in the reference as "const-propagating"
- **`UPPER_CASE` enumerators and constants**, `snake_case` everything else in the migrated libraries

## Vocabulary types

`core` renames the standard vocabulary to a compact, uniform set and uses it in every signature:

| StormKit | Standard |
| --- | --- |
| `u8` … `u64`, `i8` … `i64`, `f32`, `f64`, `usize`, `isize` | fixed-width arithmetic types |
| `array<T, N>`, `dynarray<T>` | `std::array`, `std::vector` |
| `array_view<T>` | `std::span` |
| `string`, `string_view` | the `std` types |
| `heap_ptr<T>`, `shared_heap_ptr<T>` | `std::unique_ptr`, `std::shared_ptr` |
| `ref_ptr<T>` | *(none)* — a non-owning, non-null, rebindable reference |
| `expected<T, E>` | `std::expected` |
| `hash_map<K, V>`, `hash_set<K>` | `ankerl::unordered_dense` tables |

These are aliases, not new types: a `dynarray<int>` **is** a `std::vector<int>` and works with
every standard algorithm.

Parameter conventions:

| You see | It means |
| --- | --- |
| `array_view<const T>` | "a contiguous sequence I only read" — pass a `dynarray`, an `array`, a C array, a single-element `std::array { x }` |
| `string_view` | "text I only read" |
| `meta::in<T>` | `T` by value if small and trivially copyable, `const T&` otherwise |
| `ref_ptr<T>`, `view::X` | "I will keep referring to this; keep it alive" |
| `T&&` / by value | "I take ownership" |

## Errors are values

There are three channels, and each has one job.

**1. Recoverable failures → `expected`.** Anything that can legitimately fail at run time returns
a `std::expected`:

| Alias | Error type | Used by |
| --- | --- | --- |
| `system_result<T>` | `system_code` (any OS error) | `core` file, library and shared-memory functions |
| `image::image::result<T>` | `system_code` carrying an `image_status_code` | `image` |
| `gpu::expected<T>` | `gpu::Result` (≈ `VkResult`) | `gpu` |

Handle them with the standard monadic members or with the early-return macros:

```cpp
auto load(const std::filesystem::path& path) noexcept -> system_result<Config> {
    auto bytes = TryX(io::readfile(path));          // returns the error to our caller on failure
    Return parse(bytes);
}

auto config = load("app.cfg")
                .transform_error(monadic::assert("configuration is mandatory"))   // or: abort with a message
                .value();
```

**2. Programming errors → contracts.** A violated pre-condition is a bug, not a situation to
recover from. `expects`, `ensures` and `assert` print a report with the source location and
terminate — in *every* build mode. Functions document their pre-conditions; out-of-range access,
lossy casts and null handles are all contract-checked.

**3. Exceptions → not used.** StormKit functions are `noexcept`. An exception escaping your own
code reaches `std::terminate`, where the handler installed by `stormkit-main` prints a stack trace.

## Fallible construction: `create` and `allocate`

Constructors cannot return errors, so types whose construction can fail have none that you can
call. They offer static factories instead:

```cpp
static auto T::create(args…)   -> expected<T, E>;             // by value
static auto T::allocate(args…) -> expected<heap_ptr<T>, E>;   // on the heap
```

The variants are named after what they do — `open` / `allocate_and_open`, `load` /
`allocate_and_load`, `load_from_file` — but always come in that value / heap pair. Use the value
form by default; use the heap form when the object needs a stable address or must be stored where
it cannot be default-constructed.

When you need such an object as a data member initialised later, `defer_init<T>` provides
in-place storage without the heap:

```cpp
class app {
    defer_init<wsi::Window> m_window;
  public:
    auto init() -> void { m_window = wsi::Window::open("app", { 800u, 600u }, wsi::WindowFlag::DEFAULT); }
};
```

## Ownership is in the type

| Type | Owns? | Null? | Copy |
| --- | --- | --- | --- |
| `T` (value) | yes | — | as `T` allows; most resource types are move-only |
| `heap_ptr<T>` | yes | yes | move-only |
| `ref_ptr<T>` | no | no (built from a reference) | cheap |
| `array_view<T>`, `string_view` | no | may be empty | cheap |
| `gpu::view::X` | no | no | cheap |

A function that takes a view or a `ref_ptr` and stores it is telling you the referent must outlive
the object. Nothing in StormKit extends lifetimes behind your back.

## Conversions are explicit and checked

Implicit narrowing is the classic silent bug. StormKit code converts through five named
operations instead of `static_cast`:

| Operation | Use |
| --- | --- |
| `as<To>(x)` | a conversion you assert is valid; a lossy one is a contract violation |
| `to<To>(x)` | a conversion that may fail; returns an `expected` |
| `is<T>(x)` / `is(a, b)` | "does it hold a `T`?" / robust equality (floats, mixed signedness) |
| `into<Container>({…})` | build a container from a braced list, moving the elements |
| `view_of(x)` | non-owning view (span, `ref_ptr`, bytes) |

`as` covers arithmetic types, enums, bytes, polymorphic downcasts, `variant` / `optional` /
`expected` access and string conversions — one spelling for all of them. See the
[type safety reference](reference/core-typesafe.md#safe-casts).

## Customisation through `tag_invoke`

StormKit never asks you to specialise a template in its namespace or to inherit from an
interface. To teach it about your type you write a free function called `tag_invoke`, next to your
type, whose first parameter says which operation you are customising:

```cpp
namespace game {
    struct health { int points; };

    // formatting: std::format("{}", health { 3 }), logging, …
    template<typename CharT, typename FormatContext>
    constexpr auto tag_invoke(stormkit::format_as_fn<CharT>, const health& h, FormatContext& ctx) -> decltype(ctx.out()) {
        return std::format_to(ctx.out(), "{} HP", h.points);
    }

    // hashing: hash_of(health { 3 }), usable as a hash_map key
    template<typename Ret>
    constexpr auto tag_invoke(stormkit::hash_fn<Ret>, const health& h) noexcept -> Ret {
        return stormkit::hash_of<Ret>(h.points);
    }

    // casting: as<int>(health { 3 })
    constexpr auto tag_invoke(stormkit::as_fn<int>, const health& h,
                              stormkit::source_location_arg = std::source_location::current()) noexcept -> int {
        return h.points;
    }
}
```

The complete list of customisable operations is in the
[meta reference](reference/core-meta-string.md#tag_invoke).

Two shortcuts follow from this design:

- an **enum** only needs `as<string_view>` to become formattable *and* loggable;
- a **trivially copyable, padding-free struct** is hashable with no code at all.

## Flags are scoped enums

Bit masks are `enum class` types opted in to bitwise operators, so they stay type-safe:

```cpp
auto style = wsi::WindowFlag::RESIZEABLE | wsi::WindowFlag::BORDERLESS;
if (has_flag_bit(style, wsi::WindowFlag::BORDERLESS)) { /* … */ }
```

Mixing two different flag types does not compile. Enable it for your own enums by specialising
`stormkit::meta::FLAG_TRAIT`.

## Reading the documentation

- Signatures in the reference drop `[[nodiscard]]` (assume it everywhere) and, in summary tables,
  `noexcept`.
- "Pre-condition" means *contract-checked*: violating it terminates with a diagnostic.
- "Const-propagating" means the member returns `const T&` through a const object and `T&`
  otherwise.
- Pages for libraries that have not finished the move to the current conventions start with a
  **Status** note. See [project status](README.md#project-status).

# `stormkit.core` reference — type safety

Part 4 of 4 of the `stormkit.core` reference
([1. Foundation](core-foundation.md) · [2. Containers, memory & parallelism](core-containers.md) ·
[3. Meta & strings](core-meta-string.md) · **4. Type safety**).

`import stormkit.core.typesafe;` re-exports `typesafe.safecasts`, `typesafe.ref_ptr`,
`typesafe.flags`, `typesafe.strong_type` and `typesafe.checked_value`.

---

## Safe casts

`stormkit.core.typesafe.safecasts`

Five families of conversion, each a customisation point resolved through
[`tag_invoke`](core-meta-string.md#tag_invoke):

| Spelling | Meaning | On failure |
| --- | --- | --- |
| [`as<To>(value)`](#as) | "this conversion is valid, do it" | contract violation |
| [`to<To>(value)`](#to) | "try this conversion" | returns an `expected` |
| [`is<T>(value)`](#is), `is(a, b)` | "does this hold a `T`?" / "are these equal?" | returns `false` |
| [`into<To>({...})`](#into) | build a container from a braced list | — |
| [`view_of(value)`](#view_of) | get a non-owning view | — |

Marker types used as the template argument of some of them:

```cpp
struct underlying;   // as<underlying>(enum_value)
struct empty;        // is<empty>(optional / expected / variant)
struct error;        // is<error>(expected)
struct equal;        // is_fn<equal>, the tag behind is(a, b)
inline constexpr struct as_bytes_type {} as_bytes;   // view_of(as_bytes, x), into<...>(as_bytes, {...})
```

### `as`

```cpp
template<typename To> struct as_fn;
template<typename To> inline constexpr auto as = as_fn<To> {};

template<typename To, typename From>
constexpr auto unchecked_narrow(From from) noexcept -> To;
```

`as<To>(value)` selects the `tag_invoke(as_fn<To>, value, std::source_location)` overload. If none
exists the call is deleted with *"As caster not defined for these types!"*. The source location of
the call site is forwarded so that a failed check reports **your** line.

Built-in conversions:

| From → To | Behaviour |
| --- | --- |
| `T` → `T` | Identity (forwards). |
| arithmetic → arithmetic | `static_cast`. When the conversion [`is_narrowing`](core-meta-string.md#concepts--arithmetic-and-enums), the value is first checked to survive the round trip; otherwise `expects` fails with *"Lossy narrowing detected, use unchecked_narrow() to explicitly force the conversion…"*. |
| arithmetic ↔ `byte`, enum ↔ `byte` | Same rule. |
| enum → arithmetic, arithmetic → enum | Same rule, on the underlying type. |
| enum → `underlying` | `std::to_underlying(value)`; the result type is deduced. |
| polymorphic reference → `Derived` | `dynamic_cast`, returns `Derived&`. Fails a contract if the dynamic type does not match. |
| polymorphic pointer (raw or smart) → `Derived` | Returns a [`ref_ptr<Derived>`](#stormkitcoretypesaferef_ptr). Same check. |
| `std::variant` → alternative `T` | Reference to the alternative; *"Bad variant access!"* otherwise. |
| `std::optional<T>` → `T` | Reference to the value; *"Bad optional access!"* when empty. |
| `std::expected<T, E>` → `T` | Reference to the value; *"Bad expected access!"* on error. |
| `std::expected<T, E>` → `std::unexpected<E>` | Reference to the error. |
| `string_view` → `string` | Copy. |
| anything with `as<string_view>` → `string` | Copy of the view. |
| integer → `string` | `as<string>(value, base = 10)` |
| floating point → `string` | `as<string>(value, fmt = std::chars_format::general)` |
| `string_view` → integer | `as<i32>(text, base = 10)`; contract violation on malformed input |
| `string_view` → floating point | `as<f32>(text, fmt = general)` |
| any formattable type → `string` | `std::format("{}", value)` (from `string.format`) |
| `color<A, T>` → `color<B, U>`, `color_layout` → `string_view` | see [color](core-foundation.md#stormkitcorecolor) |

`unchecked_narrow<To>(value)` is a bare `static_cast` for when truncation is the intent
(`unchecked_narrow<u8>(0x1FF)` is `0xFF`).

```cpp
using namespace stormkit;

const auto count  = as<u32>(std::ranges::size(items));   // checked: aborts if it does not fit
const auto ratio  = as<f32>(width) / as<f32>(height);
const auto raw    = as<underlying>(key::ESCAPE);
auto&      circle = as<Circle>(shape);                   // checked downcast
```

Making your own type convertible:

```cpp
struct celsius { float degrees; };

template<stormkit::meta::floating_point To>
constexpr auto tag_invoke(stormkit::as_fn<To>, celsius value,
                          stormkit::source_location_arg = std::source_location::current()) noexcept -> To {
    return static_cast<To>(value.degrees);
}

constexpr auto tag_invoke(stormkit::as_fn<stormkit::string_view>, color_space value,
                          stormkit::source_location_arg = std::source_location::current()) noexcept
  -> stormkit::string_view;   // also makes color_space formattable, see string.format
```

The overload is found by ADL, so declare it in the namespace of your type.

### `to`

```cpp
template<typename To> struct to_fn;
template<typename To> inline constexpr auto to_cpo = to_fn<To> {};

template<typename To, typename... Ts>
constexpr auto to(Ts&&... args) noexcept -> decltype(auto);
template<template<class> typename To, stdr::input_range T>
constexpr auto to(T&& range) noexcept -> To<range_value>;
```

The fallible sibling of `as`. `to<To>(args...)` calls `tag_invoke(to_fn<To>, args...)` when one
exists and otherwise falls back to the `as` conversion.

| Conversion | Result |
| --- | --- |
| `to<string>(integer, base = 10)` | `system_result<string>` |
| `to<string>(floating, fmt = general)` | `system_result<string>` |
| `to<Integer>(string_view, base = 10)` | `system_result<Integer>` — `std::from_chars`, error on malformed or out-of-range input |
| `to<Floating>(string_view, fmt = general)` | `system_result<Floating>` |

```cpp
if (auto port = stormkit::to<stormkit::u16>(argv[1]); port) listen(*port);
else std::println("invalid port: {}", port.error());
```

### `is`

```cpp
template<typename T> struct is_fn;
template<typename T> inline constexpr auto is_cpo = is_fn<T> {};

template<typename T, typename U>          constexpr auto is(const U& value) noexcept -> bool;                       // is<T>(value)
template<typename First, typename Second> constexpr auto is(const First& first, const Second& second) noexcept -> bool;
```

**Type query — `is<T>(value)`**

| `value` | `is<T>(value)` is true when |
| --- | --- |
| polymorphic reference or pointer | the dynamic type is `T` (or derives from it) |
| `std::variant` | the active alternative is exactly `T`; `is<empty>` tests for `std::monostate` |
| `std::optional<V>` | it holds a value and `V` is `T`; `is<empty>` when disengaged |
| `std::expected<V, E>` | `is<V>` → has a value; `is<std::unexpected<E>>`, `is<error>` or `is<empty>` → holds an error |

**Comparison — `is(a, b)`**

| Operands | Behaviour |
| --- | --- |
| two floating point values | relative epsilon comparison |
| integer and floating point | the integer is converted, then epsilon comparison |
| two integers | compared in the wider type — **no sign-compare surprises** (`is(-1, 4294967295u)` is false) |
| value and unary predicate | `predicate(value)` |
| anything else | a user `tag_invoke(is_fn<equal>, a, b)` if present, else `a == b` |

```cpp
if (stormkit::is<wsi::resized_event>(event)) { /* ... */ }
if (stormkit::is(angle, 0.3f))               { /* robust float comparison */ }
```

### `into`

```cpp
template<typename To> struct into_fn;

into<To>({ a, b, c })              // To is a complete type
into<Container>({ a, b, c })       // Container is a template: element type deduced
into<array>({ a, b, c })           // size deduced too
into<Container>(as_bytes, { ... }) // each element converted with as<byte>
```

Builds a container from a braced list **without `std::initializer_list`**: elements are moved, so
move-only types work, and the element type is deduced.

```cpp
constexpr auto primes  = stormkit::into<stormkit::array>({ 2, 3, 5, 7 });            // array<int, 4>
auto           buffers = stormkit::into<stormkit::dynarray>({ make_buffer(), make_buffer() });
auto           magic   = stormkit::into<stormkit::array>(stormkit::as_bytes, { 0x89, 0x50, 0x4E, 0x47 });   // array<byte, 4>
```

### `view_of`

```cpp
template<bool MUTABLE> struct view_of_fn;
inline constexpr auto view_of         = view_of_fn<false> {};
inline constexpr auto mutable_view_of = view_of_fn<true> {};

template<typename From> constexpr auto bytes_of(From& value) noexcept;                // view_of(as_bytes, value)
template<typename From> constexpr auto mutable_bytes_of(const From& value) noexcept;  // mutable_view_of(as_bytes, value)

views_of(a, b, c)                 mutable_views_of(a, b, c)                 // -> array<View, 3>
views_of<Container>(a, b, c)      mutable_views_of<Container>(a, b, c)      // -> Container<View>
views_of<Container>(range)        mutable_views_of<Container>(range)        // one view per element
```

| Argument | `view_of(x)` | `mutable_view_of(x)` |
| --- | --- | --- |
| contiguous range (`dynarray`, `array`, C array, `string`) | `array_view<const T, N>` | `array_view<T, N>` |
| pointer or smart pointer | `ref_ptr` to the pointee | same |
| any other object | `ref_ptr<const T>` | `ref_ptr<T>` |
| `(as_bytes, contiguous_range)` | `array_view<const byte, N * sizeof(T)>` | `array_view<byte, …>` |
| `(as_bytes, standard_layout_object)` | `array_view<const byte, sizeof(T)>` | `array_view<byte, sizeof(T)>` |

The extent is static whenever the source size is a compile-time constant (`array`, C arrays,
fixed-extent spans) and `std::dynamic_extent` otherwise.

```cpp
device.upload(stormkit::view_of(stormkit::as_bytes, vertices));   // dynarray<vertex> -> array_view<const byte>
file.write(stormkit::bytes_of(header));                           // any standard-layout struct
```

### String conversion concepts

```cpp
namespace meta {
    template<typename T, typename CharT = char> concept has_as_string_view = /* as<basic_string_view<CharT>>(v) is valid */;
    template<typename T, typename CharT = char> concept has_as_string      = /* as<basic_string<CharT>>(v) is valid */;
    namespace plain { /* cv-ref insensitive versions */ }
}
```

---

## `stormkit.core.typesafe.ref_ptr`

```cpp
template<typename T> using owned_raw_ptr = T*;          // documents that a raw pointer is owning

template<meta::negate<meta::reference> T>
class ref_ptr {
  public:
    using element_type = T;   using pointer = T*;   using const_pointer = const T*;

    constexpr ref_ptr(T& pointed) noexcept;                               // from a reference
    template<typename U> constexpr ref_ptr(U&& pointed) noexcept;         // from a raw pointer / ref_ptr / reference_wrapper
    template<typename U> constexpr ref_ptr(U& pointed) noexcept;          // from an lvalue unique_ptr / shared_ptr
    constexpr ref_ptr(const ref_ptr<U>&) noexcept;                        // U is T or derives from it

    constexpr auto operator->(this Self& self) noexcept -> /* const-propagating */ T*;
    constexpr auto operator*(this Self& self)  noexcept -> /* const-propagating */ T&;
    constexpr auto get(this Self& self)        noexcept -> /* const-propagating */ T*;

    constexpr operator pointer() noexcept;
    constexpr operator const_pointer() const noexcept;
    constexpr operator ref_ptr<const T>() const noexcept;
    constexpr operator std::reference_wrapper<const T>() const noexcept;

    constexpr explicit operator bool() const noexcept;
    // ==, <, <=, >, >=, <=> against nullptr and against any ref_ptr<U>
};
```

A **non-owning, rebindable reference** — StormKit's vocabulary type for "I refer to this object but
do not own it" (the role of `std::observer_ptr` / `T*`, with fewer ways to misuse it).

- One pointer in size, trivially copyable and trivially relocatable.
- Built from a reference, so it is normally non-null; there is no default constructor.
- Cannot be built from an **rvalue** smart pointer (the pointee would die immediately).
- Const propagates: a `const ref_ptr<T>` only gives `const T&`.
- Converts implicitly to `T*`, to `ref_ptr<const T>` and to `std::reference_wrapper`.
- Hashable (by address) and formattable; `std::pointer_traits` is specialised.

Use it for data members and containers of references (`dynarray<ref_ptr<const entity>>`), where a
C++ reference cannot be used.

### Factories

```cpp
template<typename T>       constexpr auto ref_of(const T& of) noexcept -> ref_ptr<const T>;
template<meta::pointer T>  constexpr auto ref_of(const T& of) noexcept -> ref_ptr<const pointee>;
template<typename T>       constexpr auto mutable_ref_of(T& of) noexcept -> ref_ptr<T>;
template<meta::pointer T>  constexpr auto mutable_ref_of(T& of) noexcept -> ref_ptr<pointee>;

refs_of(a, b, c)                mutable_refs_of(a, b, c)                 // -> array<ref_ptr, 3>
refs_of<Container>(a, b, c)     mutable_refs_of<Container>(a, b, c)      // -> Container<ref_ptr>
refs_of<Container>(range)       mutable_refs_of<Container>(range)        // one ref per element
```

| Function | Description |
| --- | --- |
| `ref_of(x)` | Const reference to `x`; when `x` is itself a pointer or smart pointer, to its pointee. |
| `mutable_ref_of(x)` | The mutable version. |
| `refs_of(...)` | References to several objects at once. Arguments may freely mix objects, raw pointers and smart pointers; all are unwrapped to the same pointee type. |

```cpp
auto images = stormkit::dynarray<gpu::image> { /* ... */ };
auto views  = stormkit::refs_of<stormkit::dynarray>(images);   // dynarray<ref_ptr<const gpu::image>>

const auto set_layouts = stormkit::refs_of(camera_layout, material_layout);   // array<ref_ptr<...>, 2>
```

---

## `stormkit.core.typesafe.flags`

```cpp
namespace meta {
    template<enumeration T> inline constexpr auto FLAG_TRAIT = false;     // specialise to opt in
    template<typename T>    concept is_flag = FLAG_TRAIT<T>;
}

template<meta::is_flag T> constexpr auto has_flag_bit(T value, T flag) noexcept -> bool;

// global namespace, for every T satisfying meta::is_flag
constexpr auto operator|(T, T) -> T;     constexpr auto operator|=(T&, T) -> T&;
constexpr auto operator&(T, T) -> T;     constexpr auto operator&=(T&, T) -> T&;
constexpr auto operator^(T, T) -> T;     constexpr auto operator^=(T&, T) -> T&;
constexpr auto operator~(T)    -> T;
```

Turns an enumeration into a bit-flag type **by opt-in**:

```cpp
enum class buffer_usage : stormkit::u8 { VERTEX = 1, INDEX = 2, UNIFORM = 4 };

template<>
inline constexpr auto stormkit::meta::FLAG_TRAIT<buffer_usage> = true;

auto usage = buffer_usage::VERTEX | buffer_usage::INDEX;
if (stormkit::has_flag_bit(usage, buffer_usage::INDEX)) { /* ... */ }
```

| Name | Description |
| --- | --- |
| `FLAG_TRAIT<E>` | Specialise to `true` (at namespace scope, spelled with the full `stormkit::meta::` qualification) to enable the operators for `E`. |
| `has_flag_bit(value, flag)` | `(value & flag) == flag` — true when **all** bits of `flag` are set. |
| operators | Work on the underlying type; the result is still `E`, so type safety is kept. Both scoped and unscoped enums are supported. |

### `generate_substitution_strings_for`

```cpp
template<meta::enumeration T, usize N, T DEFAULT_VALUE, usize BUF_LEN = 50>
consteval auto generate_substitution_strings_for(string_view prefix,
                                                 array_view<const std::pair<T, string_view>, N> mapping,
                                                 char separator = '|') noexcept;
template<meta::enumeration T, usize N, usize BUF_LEN = 50>
consteval auto generate_substitution_strings_for(string_view prefix,
                                                 array_view<const std::pair<T, string_view>, N> mapping,
                                                 char separator = '|') noexcept;
```

Given the name of each individual flag, computes **at compile time** the name of *every
combination* of flags, as an `array<std::pair<T, static_string<BUF_LEN>>, K>`.

- A single flag is rendered as `prefix + name`.
- A combination is rendered as `prefix + "(" + "A | B" + ")"`, using `separator`.
- The first overload takes a `DEFAULT_VALUE` (typically the zero "none" enumerator), which is listed
  once and never combined.

This is how the gpu module produces `as<string_view>` (and therefore formatting) for its flag
enums. `BUF_LEN` must be large enough for the longest combination.

---

## `stormkit.core.typesafe.strong_type`

```cpp
template<meta::is_decayed T, typename Tag, static_string NAME, template<class> typename... Capabilities>
class strong_type final : public Capabilities<T>... {
  public:
    using value_type = T;
    static constexpr std::string_view NAME;

    constexpr explicit strong_type(/* T or T&& */ value);
    template<class... Ts> constexpr strong_type(std::in_place_t, Ts&&... args);
    // copy / move as supported by T

    constexpr auto value(this Self&& self) noexcept -> /* T forwarded like Self */;
    constexpr explicit(/* unless implicit_convertion */) operator /* T forwarded like Self */ () noexcept;
};

namespace capabilities {
    template<typename T> struct arithmetic;            // + - * / and compound assignment
    template<typename T> struct implicit_convertion;   // makes the conversion to T implicit
}

namespace meta {
    template<typename T>                      concept is_strong_type = /* a strong_type specialisation */;
    template<typename T, typename Capability> concept has_capability = derived_from<T, Capability>;
}
```

A zero-overhead wrapper that makes two values of the same representation **different types**.

| Parameter | Role |
| --- | --- |
| `T` | The wrapped type. |
| `Tag` | Any type, usually declared inline (`struct meter_tag`); it is what makes the type unique. |
| `NAME` | A string literal, exposed as `NAME` and used when formatting. |
| `Capabilities...` | Mix-ins granting operations. Without any, a strong type can only be constructed, copied and unwrapped. |

| Capability | Grants |
| --- | --- |
| `capabilities::arithmetic` | `+ - * /` and `+= -= *= /=` with another value of the same strong type or with a raw `T`. |
| `capabilities::implicit_convertion` | Implicit conversion back to `T` (explicit otherwise). |

```cpp
using meter  = stormkit::strong_type<float, struct meter_tag,  "meter",  stormkit::capabilities::arithmetic>;
using second = stormkit::strong_type<float, struct second_tag, "second", stormkit::capabilities::arithmetic>;

auto travel(meter distance, second duration) -> void;

travel(meter { 10.f }, second { 2.f });      // OK
// travel(second { 2.f }, meter { 10.f });   // error: no conversion between second and meter
// travel(10.f, 2.f);                        // error: the constructor is explicit

const auto total = meter { 1.f } + meter { 2.f };
std::println("{}", total.value());
```

Strong types are formattable. The math module's
[`radian` and `euler`](math.md#stormkitmathlinearangle) are strong types.

---

## `stormkit.core.typesafe.checked_value`

```cpp
template<meta::is_decayed T, meta::is_decayed Tag, auto CHECK_FN>
struct checked_value final {
    using value_type = T;

    constexpr checked_value();                          // if T is default constructible
    constexpr checked_value(/* const T& or T */ value);
    constexpr checked_value(T&& value);
    // copy / move / assignment from T and from checked_value

    constexpr operator T&() noexcept;
    constexpr operator const T&() const noexcept;

    // when T is arithmetic: + - * / and += -= *= /= with T and with checked_value

    value_type value;
};

template<meta::arithmetic T> using positive = checked_value<T, struct positive_tag, /* value >= 0 */>;
template<meta::arithmetic T> using negative = checked_value<T, struct negative_tag, /* value <  0 */>;

namespace meta { template<typename T> concept is_checked_value = /* a checked_value specialisation */; }
```

A value that carries an **invariant**. `CHECK_FN` is a unary predicate (a captureless lambda)
evaluated with `expects` on every construction, assignment and arithmetic operation; a violation
reports *"Checked value predicated violation!"*.

Unlike `strong_type`, a `checked_value` converts implicitly to and from `T`, so it drops into
existing code and only adds the check.

```cpp
using percentage = stormkit::checked_value<float, struct percentage_tag,
                                           [](float v) static noexcept { return v >= 0.f and v <= 100.f; }>;

auto set_volume(percentage volume) -> void;

set_volume(50.f);      // OK
set_volume(150.f);     // contract violation at run time (compile error in a constant expression)
```

| Alias | Invariant |
| --- | --- |
| `positive<T>` | `value >= 0` (always true for unsigned `T`) |
| `negative<T>` | `value < 0` (always false for unsigned `T`) |

`math::rect`'s `width` and `height` are `positive<T>`. Checked values are formattable.

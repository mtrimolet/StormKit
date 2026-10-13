# `stormkit.core` reference — meta-programming & strings

Part 3 of 4 of the `stormkit.core` reference
([1. Foundation](core-foundation.md) · [2. Containers, memory & parallelism](core-containers.md) ·
**3. Meta & strings** · [4. Type safety](core-typesafe.md)).

---

## `stormkit.core.meta`

`namespace stormkit::meta`. Concepts and type aliases used throughout the library's own
signatures. `import stormkit.core.meta;` re-exports the sub-modules `meta.concepts`,
`meta.algorithms`, `meta.type_query`, `meta.type_manipulation`, `meta.tag_invoke`,
`meta.priority_tag` and `meta.type_traits` (the last one is currently empty).

### The `plain::` and `decayed::` mirrors

Most concepts test the type *exactly as given*, so `meta::integral<const int&>` is false.
Two nested namespaces re-declare (almost) every concept with a transformation applied first:

| Namespace | Transformation | Example |
| --- | --- | --- |
| `meta::plain::` | `std::remove_cvref_t` | `meta::plain::integral<const int&>` is true |
| `meta::decayed::` | `std::decay_t` | `meta::decayed::is<int[3], int*>` is true |

Use the `plain::` form to constrain forwarding references:
`template<meta::plain::is<Config> T> auto set(T&& config)`.

The generic building blocks behind them are also available:

```cpp
template<template<typename> typename Modifier, template<typename...> concept C, typename... Ts>
concept apply = C<Modifier<Ts>...>;
namespace plain   { template<typename First, template<typename...> concept C, typename... Ts> concept apply_to = ...; }
namespace decayed { template<typename First, template<typename...> concept C, typename... Ts> concept apply_to = ...; }
```

### Concepts — identity and conversion

| Concept | Satisfied when |
| --- | --- |
| `same_as<T, U>` | `std::same_as` |
| `is<T, U>` | `same_as`, **or** both are polymorphic and `T` derives from `U` |
| `is_any_of<T, Us...>` | `is<T, U>` for at least one `U` |
| `same_as_any_of<T, Us...>` | `same_as<T, U>` for at least one `U` |
| `same_types_as<T, Ts...>` | `same_as<T, U>` for every `U` |
| `derived_from<T, U>` | `std::derived_from` |
| `convertible_to<From, To>` | `std::convertible_to` |
| `explicitly_convertible_to<From, To>` | convertible, or `static_cast<To>(from)` is valid |
| `brace_initializable_to<From, To>` | `To { from }` is valid |
| `is_decayed<T>` | `T` is its own decayed type |
| `boolean_testable<T>` | convertible to `bool` |
| `standard_layout<T>` | `std::is_standard_layout_v` |
| `structural_type<T>` | usable as a non-type template parameter |
| `has_unique_object_representations<T>` | the `std` trait |
| `negate<T, C, Ts...>` | `not C<T, Ts...>` — e.g. `template<meta::negate<meta::reference> T>` |
| `all_of<T, Cs...>`, `any_of<T, Cs...>` | conjunction / disjunction of unary concepts |

### Concepts — template specialisations

| Concept | Matches |
| --- | --- |
| `specialization_of<S, Template>` | `Template<Ts...>` with type parameters only |
| `specialization_of_nttp_v<S, Template>` | `Template<auto...>` |
| `specialization_of_nttp_tv<S, Template>` | `Template<T, auto...>` (e.g. `std::array`, `std::span`) |
| `specialization_of_nttp_ttv<S, Template>` | `Template<T, U, auto...>` |
| `specialization_of_nttp_tvc<S, Template>` | `Template<T, auto, template...>` |
| `specialization_of_nttp_ttvc<S, Template>` | `Template<T, U, auto, template...>` (e.g. `strong_type`) |
| `std_optional<T>`, `std_expected<T>`, `std_variant<T>`, `std_span<T>`, `std_mdspan<T>`, `std_array<T>`, `std_reference_wrapper<T>` | the named standard template |

### Concepts — references, pointers and wrappers

| Concept | Satisfied when |
| --- | --- |
| `lvalue_ref<T>`, `rvalue_ref<T>`, `reference<T>` | the reference categories |
| `reference_to<T, U>` | a reference whose referred type `is` `U` |
| `raw_pointer<T>` | `std::is_pointer_v` |
| `owning_pointer<T>` | smart pointer shape with `reset()` (`unique_ptr`, `shared_ptr`) |
| `view_pointer<T>` | raw pointer, non-owning pointer-like (`ref_ptr`) or `std::reference_wrapper` |
| `pointer<T>` | `view_pointer` or `owning_pointer` |
| `owning_pointer_to<T, U>`, `view_pointer_to<T, U>`, `pointer_to<T, U>` | same, with element type `U` |
| `indirection<T>`, `indirection_to<T, U>` | a reference or a pointer |
| `view_indirection<T>` | a view pointer or an lvalue reference |
| `raw_indirection<T>`, `raw_indirection_to<T, U>` | a reference or a raw pointer |
| `wrapped_value<T>` | has `value_type`, `.value()`, `*` and `->` (`optional`, `expected`, …) |
| `wrapped_value_of<T, U>` | same, with `value_type` `U` |
| `polymorphic_type<T>`, `polymorphic_pointer<T>`, `polymorphic_reference<T>`, `polymorphic_indirection<T>` | involving a polymorphic class |
| `has_element_type<T>`, `has_value_type<T>`, `has_size_type<T>`, `has_error_type<T>`, `has_expected_type<T>`, `has_ordering_type<T>` | the nested alias exists |

### Concepts — arithmetic and enums

| Concept | Satisfied when |
| --- | --- |
| `integral<T>` | an integer type **excluding `bool` and `byte`**, including `i128` / `u128` |
| `floating_point<T>` | `std::floating_point` |
| `arithmetic<T>` | `integral` or `floating_point` |
| `scalar<T>` | `arithmetic`, raw pointer or enumeration |
| `signed_type<T>`, `unsigned_type<T>` | signedness (128-bit aware) |
| `has_same_signeness<T, U>` | both signed or both unsigned |
| `enumeration<T>` | any enum except `std::byte` |
| `scoped_enum<T>`, `c_enum<T>` | `enum class` / unscoped enum |
| `char_type<T>`, `char_types<Ts...>` | `char`, `wchar_t`, `char8_t`, `char16_t`, `char32_t` |
| `is_narrowing<To, From>` | converting `From` to `To` may lose information (float→int, wider→narrower, sign change, int→float, pointer→bool, arithmetic→byte) |
| `is_sign_narrowing<To, From>`, `is_byte_narrowing<To, From>` | the corresponding sub-cases |
| `hash_type<T>` | `hash32` or `hash64` |

### Concepts — object model

| Concept | Meaning |
| --- | --- |
| `default_constructible`, `constructible_from<T, Args...>`, `destructible`, `copyable`, `movable`, `assignable_from<T, U>`, `copy_assignable`, `move_assignable` | the usual requirements |
| `trivially_copyable`, `trivially_movable`, `trivially_destructible`, `trivially_relocatable`, `trivially_assignable_from<T, U>`, `trivially_copy_assignable`, `trivially_move_assignable` | their trivial versions |
| `noexcept_default_constructible`, `noexcept_constructible_from<T, Args...>`, `noexcept_copyable`, `noexcept_movable`, `noexcept_copy_assignable`, `noexcept_move_assignable`, `noexcept_assignable_from<T, U>`, `noexcept_destructible` | their non-throwing versions (used in `noexcept(...)` clauses) |
| `prefer_pass_by_value<T>` | trivially copyable and no larger than two pointers |
| `prefer_pass_by_ref<T>` | the opposite |
| `const_type<T>`, `const_types<Ts...>`, `volatile_type<T>`, `volatile_types<Ts...>` | cv-qualification |
| `has_equality_operator<T, U>` | `t == u` is valid |
| `predicate<F, Args...>` | `std::predicate` |
| `unary_predicate<F, T>`, `binary_predicate<F, T>` | predicate over `const T&` (twice) |
| `constant_iterator<T>`, `constant_range<T>` | iteration yields const references |

### Type aliases

`meta.type_manipulation`:

| Alias | Result |
| --- | --- |
| `to_plain_type<T>` | `std::remove_cvref_t<T>` |
| `to_decayed_type<T>` | `std::decay_t<T>` |
| `add_const_to<T>`, `add_volatile_to<T>`, `add_lvalue_ref_to<T>`, `add_rvalue_ref_to<T>` | the `std::add_*` traits |
| `remove_const_of<T>`, `remove_refs_of<T>`, `remove_pointer_of<T>` | the `std::remove_*` traits |
| `remove_indirections_of<T>` | removes the reference, then one pointer level |
| `forward_const_to<T, U>` | `const U` when `T` is const, else `U` |
| `forward_ref_to<T, U>` | `U` with the reference category of `T` |
| `forward_like<T, U>` | both of the above — the type `std::forward_like<T>(u)` returns |
| `replace_first<T, C<A, ...>>` | `C<T, ...>` |

`meta.type_query`:

| Alias | Result |
| --- | --- |
| `underlying_type<E>` | `std::underlying_type_t<E>` |
| `pointer_type<P>`, `pointed_type<P>` | the pointer / pointee type of any pointer-like |
| `indirection_target_type<T>` | the type behind a reference or pointer |
| `return_type<F>` | return type of a callable |
| `value_type<T>`, `element_type<T>`, `size_type<T>`, `error_type<T>`, `expected_type<T>`, `ordering_type<T>` | the nested alias |
| `iterator_type<R>`, `sentinel_type<R>`, `range_value_type<R>`, `range_value_type_ref<R>` | range traits |
| `in<T>` | `T` when `prefer_pass_by_value<T>`, otherwise `const T&` — **the canonical input parameter type** |
| `take<T>` | `T` when `prefer_pass_by_value<T>`, otherwise `T&&` — the canonical sink parameter type |
| `safe_narrow_type<T, V>`, `safe_narrow_other_type<T, V>` | the wider / narrower of two arithmetic types |
| `arithmetic_ordering_type<T>` | `std::strong_ordering` for integers, `std::partial_ordering` for floats |

`meta.algorithms`:

| Alias | Result |
| --- | --- |
| `conditional<C, Then, Else>` | `std::conditional_t` |
| `lazy_conditional<C, Then, Else>` | same, but only instantiates the selected branch |
| `identity<T>` | `T` in a non-deduced context |
| `nth_type<N, Ts...>`, `first_type<Ts...>`, `last_type<Ts...>` | pack indexing |

### Functions

```cpp
template<arithmetic T, arithmetic V> constexpr auto is_greater() noexcept;      // max(T) > max(V)
template<typename T> consteval auto name_of() noexcept -> std::string_view;     // spelled type name
template<enumeration E> constexpr auto enumerate() noexcept = delete;           // customisation point

template<typename Predicate, template<typename...> class Variant, typename... Ts>
constexpr auto variant_type_find_if(const Variant<Ts...>&, Predicate&& predicate) noexcept -> usize;
template<typename T, template<typename...> class Variant, typename... Ts>
constexpr auto variant_contains_type(const Variant<Ts...>&) noexcept -> bool;
```

| Function | Description |
| --- | --- |
| `name_of<T>()` | Compile-time name of `T`, extracted from the compiler's pretty function string. The exact spelling is compiler dependent. |
| `enumerate<E>()` | Deleted primary template; specialise it for your enum to expose its enumerators to generic code. |
| `variant_contains_type<T>(variant)` | Whether `T` is one of the alternatives. |
| `variant_type_find_if(variant, pred)` | Index of the first alternative for which the predicate holds, or `std::variant_npos`. |

### `tag_invoke`

`meta.tag_invoke` implements the `tag_invoke` customisation protocol (P1895) that every StormKit
customisation point is built on.

```cpp
inline constexpr /* function object */ tag_invoke;

template<typename Tag, typename... Ts> concept tag_invocable          = /* tag_invoke(tag, args...) is valid */;
template<typename Tag, typename... Ts> concept noexcept_tag_invocable = /* ... and noexcept */;
template<typename Tag, typename... Ts> using   tag_invoke_result      = /* its result type */;
template<auto& cpo>                    using   tag                    = /* plain type of a CPO object */;
```

To customise a StormKit operation for your type, declare a free function named `tag_invoke` in
your type's namespace, taking the operation's tag as first parameter:

| Operation | Tag type | See |
| --- | --- | --- |
| `as<To>(value)` | `as_fn<To>` (or `meta::tag<as<To>>`) | [casts](core-typesafe.md#as) |
| `to<To>(value)` | `to_fn<To>` | [casts](core-typesafe.md#to) |
| `is<T>(value)`, `is(a, b)` | `is_fn<T>`, `is_fn<equal>` | [casts](core-typesafe.md#is) |
| `into<To>(...)` | `into_fn<To>` | [casts](core-typesafe.md#into) |
| `view_of(value)`, `mutable_view_of(value)` | `meta::tag<view_of>`, `meta::tag<mutable_view_of>` | [casts](core-typesafe.md#view_of) |
| `hash_of(value)` | `hash_fn<Ret>` | [hash](core-containers.md#stormkitcorehash) |
| `std::format("{}", value)` | `format_as_fn<CharT>` | [format](#stormkitcorestringformat) |

### `priority_tag`

```cpp
template<usize I> struct priority_tag : priority_tag<I - 1> {};
template<>        struct priority_tag<0> {};
```

The overload-ranking idiom: an overload taking `priority_tag<2>` is preferred over one taking
`priority_tag<1>` when called with `priority_tag<2> {}`.

---

## `stormkit.core.string`

Umbrella for the sub-modules below.

### `stormkit.core.string.algorithms`

```cpp
constexpr auto split(string_view str, string_view delim) noexcept -> dynarray<string_view>;
constexpr auto to_lower(string_view str) noexcept -> string;
constexpr auto to_upper(string_view str) noexcept -> string;
auto to_lower(string_view str, const std::locale& locale) noexcept -> string;
auto to_upper(string_view str, const std::locale& locale) noexcept -> string;
constexpr auto replace(string_view in, string_view pattern, string_view replacement) noexcept -> string;
template<meta::char_type T> constexpr auto is_text(T c) noexcept -> bool;
```

| Function | Description |
| --- | --- |
| `split(str, delim)` | Views into `str` between occurrences of `delim`. The views are only valid while `str`'s storage lives. |
| `to_lower`, `to_upper` | ASCII case mapping (`constexpr`), or locale-aware with the second overload. |
| `replace(in, pattern, replacement)` | A copy of `in` with every occurrence of `pattern` replaced. |
| `is_text(c)` | True for printable ASCII (32–126) and any code unit ≥ 128. Used to filter text input events. |

### `stormkit.core.string.encodings`

```cpp
auto ascii_to_utf16(string_view) -> u16string;      auto utf16_to_ascii(u16string_view) -> string;
auto ascii_to_wide(string_view)  -> wstring;        auto wide_to_ascii(wstring_view)    -> string;
auto ascii_to_utf8(string_view)  -> u8string;       auto utf8_to_ascii(u8string_view)   -> string;
auto to_native_encoding(string_view) -> /* u16string with MSVC, u8string otherwise */;
```

Conversions between narrow strings and the UTF-8 / UTF-16 / wide encodings.
`to_native_encoding` returns what the platform's native APIs expect.

### `stormkit.core.string.format`

Hooks StormKit types into `std::format` through `tag_invoke`.

```cpp
template<typename CharT> struct format_as_fn;       // the customisation tag

namespace meta {
    template<typename T> concept format_context = /* behaves like std::format_context */;
    template<typename T, typename CharT> concept has_format_as = /* a format_as_fn overload exists */;
    template<typename T> inline constexpr auto DISABLE_AS_STRING_VIEW_FORMATTER = false;
    template<typename T> concept format_as_string_view_enabled = has_as_string_view<T> and not DISABLE_AS_STRING_VIEW_FORMATTER<T>;
}

template<typename... Args>
constexpr auto format_to(meta::format_context auto& ctx, std::format_string<Args...> fmt, Args&&... args) -> void;
```

The module partially specialises `std::formatter<T, CharT>` (deriving from the `string_view`
formatter, so width, fill and alignment specifiers work) for every `T` that satisfies one of:

1. **`meta::has_format_as<T, CharT>`** — a `tag_invoke(format_as_fn<CharT>, const T&, FormatContext&)`
   overload exists;
2. **`meta::format_as_string_view_enabled<T>`** — `as<string_view>(value)` is defined for `T`
   (typical for enums). Opt out by specialising `DISABLE_AS_STRING_VIEW_FORMATTER<T>` to `true`.

```cpp
struct version { int major, minor; };

template<typename CharT, typename FormatContext>
constexpr auto tag_invoke(stormkit::format_as_fn<CharT>, const version& v, FormatContext& ctx) -> decltype(ctx.out()) {
    return std::format_to(ctx.out(), "{}.{}", v.major, v.minor);
}

std::println("{:>8}", version { 1, 2 });   // "     1.2"
```

Formatters provided by this module: `byte`, `ref_ptr<T>`, `system_code` and `allocation_error`.
It also defines `as<basic_string<CharT>>(value)` for any formattable type that has no
`as<string_view>`.

`format_to(ctx, fmt, args...)` is `std::format_to(ctx.out(), ...)` followed by `ctx.advance_to`,
for use inside your own `tag_invoke` when you emit several pieces.

### `stormkit.core.string.hash`

```cpp
struct string_hash_fn {                              // transparent, avalanching
    template<typename T = u64> static constexpr auto operator()(string_view value, T seed = 0) noexcept -> T;
};

template<class Value, class Key = string>            using string_hash_map        = hash_map<Key, Value, string_hash_fn, std::equal_to<>>;
template<class Value = string>                       using string_hash_set        = hash_set<Value, string_hash_fn, std::equal_to<>>;
template<class Value, usize SIZE, class Key = string> using static_string_hash_map = static_hash_map<Key, Value, SIZE, string_hash_fn, std::equal_to<>>;
template<usize SIZE, class Value = string>           using static_string_hash_set = static_hash_set<Value, SIZE, string_hash_fn, std::equal_to<>>;

template<meta::hash_type Ret> constexpr auto tag_invoke(hash_fn<Ret>, string_view value) noexcept -> Ret;

namespace literals {
    constexpr auto operator""_hash32(czstring str, usize size) -> hash32;
    constexpr auto operator""_hash64(czstring str, usize size) -> hash64;
}
```

| Name | Description |
| --- | --- |
| `string_hash_fn` | `constexpr` string hasher. Being *transparent*, maps keyed by `string` can be queried with a `string_view` or a literal without allocating. |
| `string_hash_map<V>`, `string_hash_set` | Heterogeneous-lookup string tables. |
| `static_string_hash_map<V, N>`, `static_string_hash_set<N>` | Their compile-time, immutable counterparts. |
| `hash_of(string_view)` | Strings are hashable through the general [`hash_of`](core-containers.md#stormkitcorehash). |
| `"..."_hash32`, `"..."_hash64` | Compile-time string hashes, e.g. for `switch` on strings. |

### `stormkit.core.string.static_string`

```cpp
template<usize N, typename CharT = char>
struct static_string {
    using value_type = CharT;                      using storage_type = array<CharT, N>;
    using string_view_type = basic_string_view<CharT>;
    static constexpr auto SIZE = N - 1;            static constexpr auto npos = SIZE + 1;

    consteval static_string() noexcept;
    consteval static_string(const value_type (&str)[N]) noexcept;

    // iteration
    begin() end() cbegin() cend() rbegin() rend() crbegin() crend()
    // element access (const-propagating)
    operator[](size_type)  at(size_type)  front()  back()  data()
    // capacity
    size()  length()  max_size()  empty()
    // operations — same overload sets as std::string_view
    copy(dest, count, pos)   substr(pos, count = npos)   subview(pos, count = npos)   compare(...)
    starts_with(...)  ends_with(...)  contains(...)
    find(...)  rfind(...)  find_first_of(...)  find_last_of(...)  find_first_not_of(...)  find_last_not_of(...)

    constexpr operator string_view_type() const noexcept;
    storage_type m_data = {};
};
```

A fixed-capacity string whose storage is part of the object, making it a **structural type**: it
can be a non-type template parameter.

```cpp
template<stormkit::static_string NAME>
struct named_tag { static constexpr auto name = std::string_view { NAME }; };

using position = named_tag<"position">;
```

- `N` includes the terminating null, as deduced from a string literal; `SIZE` is `N - 1`.
- `substr` and `subview` both return a `string_view_type` into the object.
- Search and comparison members take a `string_view`, a single character or a `ref_ptr<const CharT>`
  (C string) and mirror `std::string_view`.
- `m_data` is public only because structural types require it; do not rely on it.

`static_string` is what gives [`strong_type`](core-typesafe.md#stormkitcoretypesafestrong_type) and
the [log module](log.md) their compile-time names.

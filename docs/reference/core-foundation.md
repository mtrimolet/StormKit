# `stormkit.core` reference — foundation

Part 1 of 4 of the `stormkit.core` reference.

| Part | Sub-modules |
| --- | --- |
| **1. Foundation (this page)** | `types`, `byte`, `config`, `contract`, `errors`, `status_code`, `at_scope_exit`, `defer_init`, `functional`, `function_ref`, `filesystem`, `dynamic_loader`, `console`, `color`, `coroutines` |
| [2. Containers, memory & parallelism](core-containers.md) | `containers`, `heap`, `pimpl`, `singleton`, `private_tag`, `overload_set`, `hash`, `random`, `ranges`, `parallelism`, `stacktrace`, `signal_handler` |
| [3. Meta & strings](core-meta-string.md) | `meta`, `string` |
| [4. Type safety](core-typesafe.md) | `typesafe` (casts, `ref`, flags, strong types, checked values) |

Everything lives in `namespace stormkit::core`, which is an **inline** namespace: write
`stormkit::u32`, not `stormkit::core::u32`. `import stormkit.core;` (or `import stormkit;`) brings
in every sub-module; each sub-module can also be imported on its own under the name given in its
heading.

Conventions used in the synopses: `[[nodiscard]]`, `noexcept` and inlining attributes are omitted
when they add nothing; `stdfs` is `std::filesystem`, `stdr` is `std::ranges`.

---

## `stormkit.core.types`

Fixed-width aliases, vocabulary type aliases and literals.

### Global aliases

Declared in the global namespace:

```cpp
using uchar = unsigned char;      using ushort = unsigned short;
using uint  = unsigned int;       using ulong  = unsigned long;
using ulonglong = unsigned long long;
using schar = signed char;        using longlong = signed long long;
using longdouble = long double;
```

### Arithmetic aliases

| Alias | Type | Alias | Type |
| --- | --- | --- | --- |
| `u8` `u16` `u32` `u64` | `std::uintN_t` | `i8` `i16` `i32` `i64` | `std::intN_t` |
| `u128` | `unsigned __int128` / `std::_Unsigned128` | `i128` | `__int128` / `std::_Signed128` |
| `usize` | `std::size_t` | `isize`, `ioffset` | `std::ptrdiff_t` |
| `uptr` | `std::uintptr_t` | `iptr` | `std::intptr_t` |
| `f16` | `std::float16_t` or `_Float16` (not on Windows) | `f32` | `std::float32_t`, `_Float32` or `float` |
| `f64` | `std::float64_t`, `_Float64` or `double` | `f128` | `std::float128_t` or `long double` |
| `c8` `c16` `c32` | `char8_t` `char16_t` `char32_t` | `wchar` | `wchar_t` |
| `byte` | `std::byte` | `fsecond` | `std::chrono::duration<f32>` (seconds) |

> `f32` is a distinct type from `float` when the compiler provides `std::float32_t`. Use the
> [cast functions](core-typesafe.md#safe-casts) rather than relying on implicit conversions.

### Hash value types

```cpp
enum class hash32 : u32 {};
enum class hash64 : u64 {};
```

Opaque strong enums used as the result type of the [hashing functions](core-containers.md#stormkitcorehash).

### Vocabulary aliases

| Alias | Type |
| --- | --- |
| `raw_ptr<T>` | `T*` |
| `array<T, N>` | `std::array<T, N>` |
| `dynarray<T, Alloc>` | `std::vector<T, Alloc>` |
| `array_view<T, Extent>` | `std::span<T, Extent>` |
| `mdarray_view<T, Extents, Layout, Accessor>` | `std::mdspan<...>` |
| `string`, `string_view`, `u8string(_view)`, `u16string(_view)`, `u32string(_view)`, `wstring(_view)`, `basic_string(_view)` | the `std` types |
| `czstring`, `zstring` | `const char*`, `char*` |
| `cwzstring`, `wzstring` | `const wchar_t*`, `wchar_t*` |
| `pmr::dynarray<T>`, `pmr::string`, `pmr::u8string`, `pmr::u16string`, `pmr::u32string`, `pmr::wstring` | the `std::pmr` equivalents |
| `source_location_arg` | `const std::source_location` or `const std::source_location&`, whichever is cheaper to pass |

### Literals

`namespace stormkit::literals` (reachable through `using namespace stormkit::literals;`).

| Literal | Result | Literal | Result |
| --- | --- | --- | --- |
| `_i8` `_i16` `_i32` `_i64` `_i128` | the signed type | `_u8` `_u16` `_u32` `_u64` `_u128` | the unsigned type |
| `_usize` `_isize` `_ioffset` | size types | `_uptr` `_iptr` | pointer-sized integers |
| `_b` | `byte` | | |
| `_kb` `_mb` `_gb` | `u64`, powers of 1000 | `_kib` `_mib` `_gib` | `u64`, powers of 1024 |

All of them are plain `static_cast`s of the literal: `300_u8` silently wraps.

---

## `stormkit.core.byte`

```cpp
template<typename T> constexpr auto zero_bytes(T& value) noexcept -> void;
template<typename T> constexpr auto zeroed() noexcept -> T;
template<typename T> constexpr auto byte_swap(const T& value) noexcept -> T;
```

| Function | Effect |
| --- | --- |
| `zero_bytes(value)` | Overwrites the object representation of `value` with zero bytes. |
| `zeroed<T>()` | Returns a value-initialised `T` whose bytes were then zeroed. Typical use: C structs. |
| `byte_swap(value)` | Reverses the byte order. `std::byteswap` for integers, a `bit_cast` round trip otherwise. |

To *view* an object as bytes see `bytes_of` / `as_bytes` in
[containers.utils](core-containers.md#stormkitcorecontainersutils).

---

## `stormkit.core.config`

Build-time constants, generated from `config.hpp.in`.

| Constant | Type | Meaning |
| --- | --- | --- |
| `STORMKIT_MAJOR_VERSION`, `STORMKIT_MINOR_VERSION`, `STORMKIT_PATCH_VERSION` | `int` | semantic version |
| `STORMKIT_BUILD_VERSION` | `std::string_view` | build timestamp (`%Y%m%d%H%M`) |
| `STORMKIT_VERSION` | `std::string_view` | `"<version>-<build>"` |
| `STORMKIT_BUILD_TYPE` | `std::string_view` | xmake mode (`debug`, `release`, …) |
| `STORMKIT_GIT_COMMIT_HASH`, `STORMKIT_GIT_BRANCH` | `std::string_view` | source revision |

The `STORMKIT_LIB_*_ENABLED` feature macros are documented in the
[macro reference](macros.md#configuration-macros).

---

## `stormkit.core.contract`

Runtime and compile-time contract checks.

```cpp
enum class assert_type { ASSERTION, PRE_CONDITION, POST_CONDITION };

auto assert_base(bool cond, assert_type type, string_view message,
                 const std::source_location& location = std::source_location::current()) noexcept -> void;
consteval auto consteval_assert_base(bool cond, assert_type type, string_view message) noexcept -> void;

constexpr auto assert (bool cond, string_view message, const std::source_location& = current()) noexcept -> void;
constexpr auto assert (bool cond,                      const std::source_location& = current()) noexcept -> void;
constexpr auto expects(bool cond, string_view message, const std::source_location& = current()) noexcept -> void;
constexpr auto expects(bool cond,                      const std::source_location& = current()) noexcept -> void;
constexpr auto ensures(bool cond, string_view message, const std::source_location& = current()) noexcept -> void;
constexpr auto ensures(bool cond,                      const std::source_location& = current()) noexcept -> void;
```

| Function | Semantic role | Failure label |
| --- | --- | --- |
| `expects` | pre-condition | `Pre condition check` |
| `ensures` | post-condition | `Post condition check` |
| `assert` | invariant | `Contract check` |

Behaviour on failure:

- **During constant evaluation** the check calls an undefined function, which makes the program
  ill-formed; the diagnostic carries `[ASSERTION]<label>: <message>`.
- **At run time** the check prints a coloured report to `stderr` (label, `file:line:column`,
  function, message), flushes, breaks into the debugger when one is attached and the standard
  library supports `std::breakpoint`, then calls `std::terminate()`. Reports are serialised by a
  global mutex.

Contracts are active in every build mode. They compile to nothing only when the library was built
with `STORMKIT_ASSERT` defined to `0`.

`stormkit::assert` is a function, not the `<cassert>` macro. Including `<cassert>` (directly or
through a C header) after it will break calls to it; `#undef assert` if you must.

Macro spellings that capture the expression text: [`EXPECTS`, `ENSURES`, `ASSERT`](macros.md#contract-macros).

---

## `stormkit.core.errors`

Re-exports [`stormkit.core.status_code`](#stormkitcorestatus_code).

```cpp
template<typename Val, typename Err> using expected = std::expected<Val, Err>;   // see note
using system_code = system_error2::system_code;
template<typename T> using system_result = expected<T, system_code>;

namespace error_code {
    auto from_errno() noexcept -> system_code;
    auto from_stderrc(std::errc code) noexcept -> system_code;
    auto from_win32() noexcept -> system_code;               // Windows only
    auto from_ntstatus(long code) noexcept -> system_code;   // Windows only
}
```

| Name | Description |
| --- | --- |
| `expected<V, E>` | Alias of `std::expected`. On compilers without statement expressions, and when `STORMKIT_TRYX_COROUTINES` is set, it is instead a subclass that is also an awaitable with a `promise_type`, which is what lets [`TryX`](macros.md#tryx-expression-macros) be spelled `co_await`. |
| `system_code` | Type-erased status code able to hold any OS error (POSIX `errno`, Win32 `GetLastError`, NT status…). Exposes `.message()`, `.value()`, `.success()`, `.failure()`. Formattable. |
| `system_result<T>` | The return type of every StormKit function that wraps an OS call. |
| `error_code::from_errno()` | Captures the current `errno`. |
| `error_code::from_stderrc(c)` | Wraps a `std::errc`. |
| `error_code::from_win32()` | Captures `GetLastError()`. |
| `error_code::from_ntstatus(s)` | Wraps an `NTSTATUS`. |

## `stormkit.core.status_code`

Re-exports the bundled [status-code](https://github.com/ned14/status-code) library (the reference
implementation of the proposed `std::error`) in `namespace system_error2`. The exported names are
`status_code`, `system_code`, `posix_code`, `errc`, `quick_status_code_from_enum`,
`quick_status_code_from_enum_code`, `quick_status_code_from_enum_defaults` and, on Windows,
`win32_code` and `nt_code`. Refer to the upstream documentation for their API.

---

## `stormkit.core.at_scope_exit`

```cpp
template<auto DO>                     constexpr auto at_scope_exit_do() noexcept -> /* guard */;
template<std::regular_invocable<> F>  constexpr auto at_scope_exit_do(F&& do_at_exit) noexcept -> /* guard */;
```

Returns a guard object whose destructor invokes the callable. The first form takes the callable as
a template argument (zero-size guard), the second stores it.

```cpp
auto file  = std::fopen("data.bin", "rb");
auto close = stormkit::at_scope_exit_do([&] noexcept { std::fclose(file); });
```

The guard must be bound to a named variable; a discarded temporary runs immediately.

---

## `stormkit.core.deferinit`

> The module name has no underscore: `import stormkit.core.deferinit;`.

```cpp
template<typename T> using defer_init_default_storage = array<byte, sizeof(T)>;

template<typename T, typename Storage = defer_init_default_storage<T>>
class defer_init {
  public:
    using value_type = T;
    using reference = T&;            using const_reference = const T&;
    using pointer   = T*;            using const_pointer   = const T*;

    constexpr defer_init();
    constexpr ~defer_init();
    defer_init(const defer_init&) = delete;
    constexpr defer_init(defer_init&&) noexcept(/* T is nothrow movable */);
    constexpr auto operator=(defer_init&&) noexcept(...) -> defer_init&;

    template<typename... Ts> constexpr auto construct(Ts&&... args) -> void;                 // T { args... }
    template<typename... Ts> constexpr auto construct_with_narrowing(Ts&&... args) -> void;  // T ( args... )
    constexpr auto operator=(value_type&& value) -> void;

    constexpr auto value(this Self&& self) noexcept -> /* T forwarded like Self */;
    constexpr auto operator*(this Self&& self) noexcept -> /* same */;
    constexpr auto operator->(this Self& self) noexcept -> /* pointer or const_pointer */;
    constexpr operator reference() noexcept;
    constexpr operator const_reference() const noexcept;

    constexpr explicit operator bool() const noexcept;
    constexpr auto has_value() const noexcept -> bool;
};
```

In-place storage for an object that cannot be built in the constructor of its owner (no default
constructor, needs data that only exists later). No heap allocation; move-only.

| Member | Notes |
| --- | --- |
| `construct(args...)` | Destroys the current value, if any, then brace-initialises a new one. |
| `construct_with_narrowing(args...)` | Same with parentheses, for constructors that brace initialisation would reject or redirect to `std::initializer_list`. |
| `operator=(T&&)` | Destroys then move-constructs. |
| `value()`, `*`, `->`, conversions | Pre-condition: `has_value()` (checked with `expects`). |

Compared to `std::optional<T>`: no `reset`/`emplace` vocabulary, implicit conversion to `T&`, and
access is contract-checked rather than throwing.

---

## `stormkit.core.functional`

Umbrella for `functional.utils`, `functional.monadic` and `functional.error_handling`.

### `stormkit.core.functional.utils`

```cpp
inline constexpr /* function object */ either;

either(bool condition,      auto&& on_true,          auto&& on_false) -> decltype(on_false());
either(Pointer value,       auto&& on_true /*(T&)*/, auto&& on_false) -> decltype(on_false());
either(WrappedValue&& value, auto&& on_true /*(T)*/, auto&& on_false) -> decltype(on_false());

using std::bind_front;
using std::bind_back;        // polyfilled as bind_back<FUNC>(args...) when the standard library lacks it

template<typename T, typename Func, typename... Ts>
constexpr auto init_by(Func&& func, Ts&&... args) noexcept -> T;
```

| Name | Description |
| --- | --- |
| `either(cond, t, f)` | Expression-level `if`/`else`: returns `t()` when `cond` is true, `f()` otherwise. Both must return the same type. |
| `either(ptr, t, f)` | For raw and smart pointers: calls `t(*ptr)` when the pointer is non-null. |
| `either(wrapper, t, f)` | For boolean-testable types satisfying [`meta::wrapped_value`](core-meta-string.md#concepts--references-pointers-and-wrappers): calls `t(*wrapper)`, forwarding the value category of `wrapper`. |
| `init_by<T>(func, args...)` | Value-initialises a `T`, calls `func(out, args...)` (which must return `void`), returns it. Handy for filling C structs in an initialiser. |

### `stormkit.core.functional.monadic`

`namespace stormkit::monadic`. Every function here is a *factory* returning a small closure meant
to be passed to `.transform`, `.and_then`, `.or_else`, `.transform_error`, a range adaptor or
`std::visit`.

```cpp
struct anything { /* implicitly converts to any T& / T&& */ };

constexpr auto identity(auto&& value) noexcept;          constexpr auto consume(auto&& value) noexcept;
constexpr auto noop() noexcept;                          constexpr auto discard() noexcept;
constexpr auto set(auto& output) noexcept;
constexpr auto emplace_to(stdr::range auto& container) noexcept;
constexpr auto append_to(stdr::range auto& range) noexcept;
constexpr auto wrap(auto&& func) noexcept;               template<auto Func> constexpr auto wrap() noexcept;
constexpr auto unwrap() noexcept;                        constexpr auto unwrap_error() noexcept;
constexpr auto unpack_tuple_to(auto&& func) noexcept;
constexpr auto map(auto&& first, auto&& second) noexcept;
constexpr auto either(std::regular_invocable<anything> auto&&... visitors) noexcept;
template<typename T> constexpr auto either(auto&& predicate, auto&& true_, auto&& false_) noexcept;
template<auto Index> constexpr auto get() noexcept;
constexpr auto is() noexcept;
template<typename T> constexpr auto is() noexcept;
template<typename T> constexpr auto is(const T& value) noexcept;
template<typename T> constexpr auto as() noexcept;
template<typename T> constexpr auto unchecked_narrow() noexcept;
constexpr auto clone() noexcept;                         constexpr auto unref() noexcept;
template<typename T> constexpr auto init() noexcept;
template<typename T> constexpr auto init(auto&&... args) noexcept;
template<typename T, auto Initializer> constexpr auto init_by() noexcept;
template<typename T> constexpr auto forward_like() noexcept;
template<typename T> constexpr auto value() noexcept;
```

| Factory | The returned closure… |
| --- | --- |
| `identity(v)` | takes nothing, returns the captured `v`. Use as an `or_else` fallback. |
| `consume(v)` | ignores its arguments, returns the captured `v` by move. |
| `noop()`, `discard()` | ignore their arguments, return `void`. |
| `set(out)` | assigns its argument to `out`. |
| `emplace_to(c)` | calls `c.emplace_back(arg)`. |
| `append_to(r)` | calls `r.emplace(cend(r), arg)`. |
| `wrap(f)`, `wrap<F>()` | forwards to `std::invoke(f, args...)`; turns member pointers and overload-set-free functions into closures. |
| `unwrap()` | returns `arg.value()` by move. |
| `unwrap_error()` | returns `arg.error()` by move. |
| `unpack_tuple_to(f)` | calls `std::apply(f, tuple)`. |
| `map(first, second)` | composition: `second(first(args...))`. |
| `either(visitors...)` | calls `std::visit` on a variant with the visitors merged into an [`overload_set`](core-containers.md#stormkitcoreoverload_set). |
| `get<I>()` | returns `std::get<I>(arg)` (index or type). |
| `is()` | binary: `core::is(a, b)`. |
| `is<T>()` | unary: `core::is<T>(arg)` — type test, see [safe casts](core-typesafe.md#is). |
| `is(value)` | unary: `core::is(value, arg)` — equality-style test against `value`. |
| `as<T>()` | returns `core::as<T>(arg)`. |
| `unchecked_narrow<T>()` | returns `core::unchecked_narrow<T>(arg)`. |
| `clone()` | returns a decayed copy (`auto(arg)`). |
| `unref()` | returns `*arg`. |
| `init<T>()` | returns `T { args... }` built from the call arguments. |
| `init<T>(args...)` | takes nothing, returns `T { captured... }`. |
| `init_by<T, F>()` | returns `stormkit::init_by<T>(F, args...)`. |
| `forward_like<T>()` | returns `std::forward_like<T>(arg)`. |

```cpp
namespace m = stormkit::monadic;

auto names = std::vector<std::string> {};
find_user(id).transform(&User::name).transform(m::emplace_to(names));

auto text = std::visit(/*...*/);                       // or:
auto text = m::either([](int i)                { return std::to_string(i); },
                      [](const std::string& s) { return s; })(variant);
```

Known issues in the current sources: the predicate overload `either<T>(predicate, true_, false_)`
does not return its closure and cannot be used; `value<T>()` is declared as a template but
implemented without one.

### `stormkit.core.functional.error_handling`

Also in `namespace stormkit::monadic`; closures intended for `.or_else` / `.transform_error`.

```cpp
constexpr auto assert(std::optional<string> message = std::nullopt,
                      std::source_location location = std::source_location::current()) noexcept;
template<typename T>
constexpr auto assert(std::optional<string> message = std::nullopt,
                      std::source_location location = std::source_location::current()) noexcept;
constexpr auto log(std::invocable auto&& logger, string&& message) noexcept;
constexpr auto throw_as_exception() noexcept;
```

| Factory | The returned closure… |
| --- | --- |
| `assert(msg)` | takes the error and fails a contract check with `"<msg> (<error>)"` (or just the formatted error). Never returns. Declared as returning the error type, for `transform_error`. |
| `assert<T>(msg)` | same, but declared as returning `T`, for `or_else` on an `expected<T, E>`-shaped call chain. |
| `log(logger, msg)` | calls `logger(msg, error)` and returns an empty `std::expected<void, E>`. |
| `throw_as_exception()` | throws the error object. |

```cpp
auto window = wsi::window::open(/*...*/)
                .transform_error(stormkit::monadic::assert("Failed to open window"))
                .value();
```

---

## `stormkit.core.function_ref`

Re-exports two types from [nontype_functional](https://github.com/zhihaoy/nontype_functional) in
`namespace std23`:

| Type | Description |
| --- | --- |
| `std23::function_ref<Sig>` | Non-owning, trivially copyable reference to a callable (P0792). Use for callback *parameters*. |
| `std23::move_only_function<Sig>` | Owning, move-only type-erased callable (P0288). Use to *store* callbacks. |

---

## `stormkit.core.filesystem`

`namespace stormkit::io`. Unbuffered, `expected`-returning file access on top of native handles.
Also declares `namespace stormkit::stdfs = std::filesystem`.

```cpp
namespace io {
    enum class open_mode { BINARY, AINSI, UTF8, WIDE };
    enum class access    { READ, WRITE };          // flag enum: READ | WRITE

    template<open_mode MODE>
    class file_descriptor final {
      public:
        using native_handle_type = /* HANDLE on Windows, i32 elsewhere */;
        static const native_handle_type INVALID_HANDLE;

        static auto open(const stdfs::path& path, access access) noexcept -> system_result<file_descriptor>;
        static auto allocate_and_open(const stdfs::path& path, access access) noexcept
          -> system_result<heap_ptr<file_descriptor>>;

        file_descriptor(file_descriptor&&) noexcept;              // move-only
        auto operator=(file_descriptor&&) noexcept -> file_descriptor&;
        ~file_descriptor() noexcept;                              // closes

        auto close() noexcept;
        auto read_to(array_view<byte>  out) noexcept -> system_result<usize>;
        auto read_to(array_view<char>  out) noexcept -> system_result<usize>;   // UTF8 / AINSI
        auto read_to(array_view<wchar> out) noexcept -> system_result<usize>;   // WIDE
        auto write(array_view<byte>        bytes) noexcept -> system_result<usize>;
        auto write(array_view<const char>  bytes) noexcept -> system_result<usize>;  // UTF8 / AINSI
        auto write(array_view<const wchar> bytes) noexcept -> system_result<usize>;  // WIDE
        auto flush() noexcept -> void;
        auto position() const noexcept -> usize;
        auto size() const noexcept -> usize;
        auto native_descriptor() const noexcept -> native_handle_type;
    };

    using binary_file = file_descriptor<open_mode::BINARY>;
    template<open_mode MODE = open_mode::UTF8> using text_file = file_descriptor<MODE>;   // MODE != BINARY

    auto readfile(const stdfs::path& path) noexcept -> system_result<dynarray<byte>>;
    auto readfile_to(const stdfs::path& path, array_view<byte> output) noexcept -> system_result<usize>;
    auto writefile(const stdfs::path& path, array_view<byte> data) noexcept -> system_result<usize>;

    template<open_mode MODE = open_mode::UTF8>
    auto readfile(const stdfs::path& path) noexcept -> system_result<dynarray<CharT>>;
    template<open_mode MODE = open_mode::UTF8>
    auto readfile_to(const stdfs::path& path, array_view<CharT> output) noexcept -> system_result<usize>;
    template<open_mode MODE = open_mode::UTF8>
    auto writefile(const stdfs::path& path, array_view<const CharT> data) noexcept -> system_result<usize>;
}
```

`CharT` is `wchar` for `open_mode::WIDE` and `char` for the other text modes.

| Name | Description |
| --- | --- |
| `open_mode` | Selects the element type and translation mode. `AINSI` is the spelling used in the sources (ANSI code page). |
| `access` | Flag enum; combine with `\|` for read/write. |
| `file_descriptor::open` | Opens the file and returns the descriptor by value. |
| `file_descriptor::allocate_and_open` | Same, on the heap (see [`heap_ptr`](core-containers.md#stormkitcoreheap)). |
| `read_to(out)` | Reads at most `out.size()` elements, returns the count read. |
| `write(data)` | Returns the count written. |
| `size()` | File size in bytes (cached). |
| `readfile(path)` | Opens, reads the whole file, closes. The non-template overload returns bytes; `readfile<open_mode::UTF8>(path)` returns characters. |
| `readfile_to(path, out)` | Reads into caller storage. |
| `writefile(path, data)` | Creates/truncates and writes. |

Every failure is reported as the native OS error in a `system_code`.

---

## `stormkit.core.dynamic_loader`

```cpp
class dynamic_loader {
  public:
    static auto load(const stdfs::path& filepath) noexcept -> system_result<dynamic_loader>;
    static auto allocate_and_load(const stdfs::path& filepath) noexcept -> system_result<heap_ptr<dynamic_loader>>;

    dynamic_loader(dynamic_loader&&) noexcept;                 // move-only
    auto operator=(dynamic_loader&&) noexcept -> dynamic_loader&;
    ~dynamic_loader();                                         // unloads

    template<class Signature> auto func(string_view name)   const noexcept -> system_result<std23::function_ref<Signature>>;
    template<class Signature> auto c_func(string_view name) const noexcept -> system_result<Signature*>;
    auto filepath() const noexcept -> const stdfs::path&;
};
```

Loads a shared library (`LoadLibrary` / `dlopen`) and resolves symbols.

| Member | Description |
| --- | --- |
| `load(path)` | Loads the library; the error is the OS error. |
| `func<R(Args...)>(name)` | Looks up `name` and returns it as a `function_ref`. |
| `c_func<R(Args...)>(name)` | Same, as a plain function pointer. |

Symbols obtained from a loader must not outlive it.

---

## `stormkit.core.console`

Umbrella for `console.io` and `console.style`.

### `stormkit.core.console.io`

```cpp
auto get_stdout() noexcept -> std::FILE*;
auto get_stderr() noexcept -> std::FILE*;
```

Function forms of the `stdout` / `stderr` macros, usable from module code:
`std::println(stormkit::get_stderr(), "…")`.

### `stormkit.core.console.style`

```cpp
enum class console_color {
    RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, BLACK,
    BRIGHT_RED, BRIGHT_GREEN, BRIGHT_YELLOW, BRIGHT_BLUE,
    BRIGHT_MAGENTA, BRIGHT_CYAN, BRIGHT_WHITE, BRIGHT_BLACK,
};

enum class style_modifier {            // flag enum
    NONE = 0x0, BOLD = 0x1, FAINT = 0x2, ITALIC = 0x4, INVERSE = 0x8, UNDERLINE = 0xA,
};

struct console_style {
    template<typename T> constexpr auto operator|(T&& value) const noexcept -> stylized<T>;
    std::optional<console_color> fg        = std::nullopt;
    std::optional<console_color> bg        = std::nullopt;
    style_modifier               modifiers = style_modifier::NONE;
};

template<typename T>
struct stylized {
    constexpr auto render() const noexcept -> string;
    constexpr auto render_into(stdr::output_range<char> auto& out) const noexcept -> void;
    T value;
    std::optional<console_color> fg, bg;
    style_modifier modifiers = style_modifier::NONE;
};

inline constexpr console_style RED_TEXT_STYLE, GREEN_TEXT_STYLE, YELLOW_TEXT_STYLE, BLUE_TEXT_STYLE,
                               MAGENTA_TEXT_STYLE, CYAN_TEXT_STYLE, WHITE_TEXT_STYLE, BLACK_TEXT_STYLE;
```

| Name | Description |
| --- | --- |
| `console_style` | A foreground, a background and modifiers. Formatting a bare `console_style` emits only the opening escape sequences. |
| `style \| value` | Produces a `stylized<T>`; formatting it emits the escapes, the formatted value, then a reset. |
| `stylized::render()` | Same as formatting, returned as a `string`. |
| `*_TEXT_STYLE` | Presets with only the foreground set. |

`namespace ecma48` exposes the raw sequences: the `FOREGROUND` and `BACKGROUND` maps
(`console_color` → `string_view`) and `RESET`, `BOLD`, `FAINT`, `ITALIC`, `UNDERLINE`, `INVERSE`.

```cpp
using namespace stormkit;
std::println("{}", console_style { .fg = console_color::RED, .modifiers = style_modifier::BOLD } | "error");
std::println("{} items", GREEN_TEXT_STYLE | 42);
```

Note that `UNDERLINE` is `0xA`, which overlaps the `FAINT` and `INVERSE` bits: requesting
`UNDERLINE` also applies those two.

---

## `stormkit.core.color`

```cpp
namespace meta { template<typename T> concept color_component_type = is_any_of<T, u8, f32, f64>; }

enum class color_layout { R, RG, RGB, BGR, RGBA, ARGB, BGRA, ABGR };

template<meta::color_component_type T> inline constexpr auto COLOR_COMPONENT_MAX = T { 1 };
template<>                             inline constexpr auto COLOR_COMPONENT_MAX<u8> = 0xFF;

template<color_layout LAYOUT, meta::color_component_type T> struct color;
```

`color<LAYOUT, T>` is an aggregate whose data members are declared **in the order of the layout**,
so its memory matches the pixel format it names:

| Specialisation | Members (in order) | `COMPONENTS_COUNT` |
| --- | --- | --- |
| `color<R, T>` | `r` | 1 |
| `color<RG, T>` | `r, g` | 2 |
| `color<RGB, T>` | `r, g, b` | 3 |
| `color<BGR, T>` | `b, g, r` | 3 |
| `color<RGBA, T>` | `r, g, b, a` | 4 |
| `color<ARGB, T>` | `a, r, g, b` | 4 |
| `color<BGRA, T>` | `b, g, r, a` | 4 |
| `color<ABGR, T>` | `a, b, g, r` | 4 |

Each specialisation also provides `component_type`, `param_type`, `static constexpr LAYOUT`,
`static constexpr COMPONENTS_COUNT` and `operator==`.

### Aliases

| Template alias | `f32` alias | `u8` alias |
| --- | --- | --- |
| `color_r<T>` | `fcolor_r` | `ucolor_r` |
| `color_rg<T>` | `fcolor_rg` | `ucolor_rg` |
| `color_rgb<T>` | `fcolor_rgb` | `ucolor_rgb` |
| `color_rgba<T>` | `fcolor_rgba` | `ucolor_rgba` |
| `color_argb<T>` | `fcolor_argb` | `ucolor_argb` |
| `color_bgr<T>` | `fcolor_bgr` | `ucolor_bgr` |
| `color_bgra<T>` | `fcolor_bgra` | `ucolor_bgra` |
| `color_abgr<T>` | `fcolor_abgr` | `ucolor_abgr` |

### Conversions and formatting

| Expression | Result |
| --- | --- |
| `as<color<TO, T>>(c)` | Converts between any two layouts and component types. Components are rescaled between the `[0, 255]` and `[0, 1]` ranges; missing alpha becomes `COLOR_COMPONENT_MAX`. |
| `as<string_view>(layout)` | Name of a `color_layout`. |
| `as<string>(c)` | Textual form of a colour. |
| `std::format("{}", c)` | Colours are formattable. |

### Presets

`namespace stormkit::colors` holds the HTML 4.01 named colours as variable templates:
`BLACK`, `GRAY`, `SILVER`, `WHITE`, `MAROON`, `RED`, `OLIVE`, `YELLOW`, `GREEN`, `LIME`, `TEAL`,
`AQUA`, `NAVY`, `BLUE`, `PURPLE`, `FUSCHIA`, `TRANSPARENT`.

Each preset is `colors::NAME<T>` (default `T = u8`) and **converts implicitly to any
`color<LAYOUT, U>`**:

```cpp
const stormkit::fcolor_rgba clear = stormkit::colors::SILVER<stormkit::f32>;
const stormkit::ucolor_bgr  pixel = stormkit::colors::RED<>;
```

| Preset | r | g | b | a | Preset | r | g | b | a |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `BLACK` | 0 | 0 | 0 | max | `GREEN` | 0 | ½ | 0 | max |
| `GRAY` | ½ | ½ | ½ | max | `LIME` | 0 | max | 0 | max |
| `SILVER` | ¾ | ¾ | ¾ | max | `TEAL` | 0 | ½ | ½ | max |
| `WHITE` | max | max | max | max | `AQUA` | 0 | max | max | max |
| `MAROON` | ½ | 0 | 0 | max | `NAVY` | 0 | 0 | ½ | max |
| `RED` | max | 0 | 0 | max | `BLUE` | 0 | 0 | max | max |
| `OLIVE` | ½ | ½ | 0 | max | `PURPLE` | ½ | 0 | ½ | max |
| `YELLOW` | max | max | 0 | max | `FUSCHIA` | max | 0 | max | max |
| `TRANSPARENT` | 0 | 0 | 0 | 0 | | | | | |

("max" is `COLOR_COMPONENT_MAX<T>`; ½ and ¾ are fractions of it.)

---

## `stormkit.core.coroutines`

A polyfill. When the standard library does not ship a conforming `std::generator`
(`__cpp_lib_generator < 202207L`), this module **defines `std::generator`** (and, on Clang < 22,
`std::ranges::elements_of`) from the reference implementation, so that the same user code compiles
everywhere:

```cpp
auto fibonacci() -> std::generator<stormkit::u64> {
    auto a = 0_u64, b = 1_u64;
    for (;;) { co_yield a; a = std::exchange(b, a + b); }
}
```

When the standard library already provides it, the module exports nothing.

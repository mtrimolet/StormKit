# Guide: `stormkit.core`

`core` is the foundation every other library is built on. It is large, but it is not a framework:
it is a collection of small, independent tools. This guide walks through them in the order you
are likely to need them.

- [Vocabulary types and literals](#vocabulary-types-and-literals)
- [Contracts](#contracts)
- [Error handling with `expected`](#error-handling-with-expected)
- [Safe conversions](#safe-conversions)
- [Strings and formatting](#strings-and-formatting)
- [Files, libraries and the console](#files-libraries-and-the-console)
- [Containers](#containers)
- [Owning and referring](#owning-and-referring)
- [Stronger types](#stronger-types)
- [Functional helpers and ranges](#functional-helpers-and-ranges)
- [Threads](#threads)
- [Colours](#colours)
- [Meta-programming](#meta-programming)

Every sample assumes:

```cpp
import std;
import stormkit.core;

using namespace stormkit;
using namespace stormkit::literals;
```

Exhaustive listings are in the reference:
[foundation](../reference/core-foundation.md) ·
[containers, memory & parallelism](../reference/core-containers.md) ·
[meta & strings](../reference/core-meta-string.md) ·
[type safety](../reference/core-typesafe.md).

---

## Vocabulary types and literals

StormKit code never spells `std::uint32_t` or `std::vector`. It uses short aliases:

```cpp
auto count   = 12_u32;                       // u32
auto ratio   = f32 { 0.5f };
auto buffer  = dynarray<byte> {};            // std::vector<std::byte>
auto lookup  = array<u8, 256> {};            // std::array
auto budget  = 64_mib;                       // u64: 64 * 1024 * 1024
auto elapsed = fsecond { 0.016f };           // std::chrono::duration<f32>

auto sum(array_view<const i32> values) noexcept -> i64;     // std::span<const int>
```

They are plain aliases, so they interoperate with any standard or third-party code. One thing to
keep in mind: on compilers that provide `std::float32_t`, `f32` is that type and **not** `float`.
Convert with `as<f32>(x)` rather than relying on implicit conversions.

The literals are in `stormkit::literals`: `_u8` … `_u64`, `_i8` … `_i64`, `_usize`, `_isize`,
`_b` (a `byte`), and the sizes `_kb` / `_mb` / `_gb` (decimal) and `_kib` / `_mib` / `_gib`
(binary).

---

## Contracts

A contract states something that must be true. If it is not, the program has a bug, and StormKit
stops it at once with a precise report instead of letting it limp on.

```cpp
auto average(array_view<const f32> samples) noexcept -> f32 {
    expects(not std::ranges::empty(samples), "average of an empty range");      // pre-condition

    const auto result = std::ranges::fold_left(samples, 0.f, std::plus {}) / as<f32>(std::ranges::size(samples));

    ensures(not std::isnan(result));                                             // post-condition
    return result;
}
```

| Function | Use it for |
| --- | --- |
| `expects(cond, message)` | what the *caller* must guarantee |
| `ensures(cond, message)` | what the *function* guarantees on exit |
| `assert(cond, message)` | an invariant in the middle |

A failure prints the kind of check, the file, line, column and function of **the call site**, and
your message, then calls `std::terminate` (breaking into the debugger first when one is attached):

```
[Assertion] Pre condition check failed in
    > file:     src/stats.cpp:12:5
      function: f32 average(std::span<const f32>)
      reason:   average of an empty range
```

Three properties make contracts worth using liberally:

- they are active in release builds too — a contract is a statement about correctness, not a
  debugging aid;
- they work in **constant expressions**: a violated contract inside a `constexpr` evaluation is a
  compile error;
- they are functions, so they have no macro pitfalls.

If you prefer the condition itself as the message, include
`<stormkit/core/contract_macro.hpp>` and write `EXPECTS(index < size);`.

Contracts are for bugs. For things that can legitimately go wrong at run time, read on.

---

## Error handling with `expected`

A function that can fail returns a `std::expected<T, E>`. For anything that wraps an operating
system call, `E` is `system_code` and the alias is `system_result<T>`:

```cpp
auto data = io::readfile("settings.json");          // system_result<dynarray<byte>>

if (not data) {
    std::println(get_stderr(), "cannot read settings: {}", data.error());
    return -1;
}
use(*data);
```

`system_code` holds whichever native error the platform produced (an `errno`, a Win32 error, an NT
status) and formats to its message.

### Propagating

Most of the time a function that calls a failing function simply wants to pass the error up.
The `TryX` macros do that in one word:

```cpp
#include <stormkit/core/tryx_expected.hpp>

auto count_lines(const std::filesystem::path& path) noexcept -> system_result<usize> {
    const auto text = TryX(io::readfile<io::open_mode::UTF8>(path));     // dynarray<char>, or early return
    Return as<usize>(std::ranges::count(text, '\n'));
}
```

`TryX(expr)` evaluates to the value when there is one and returns the error from the enclosing
function otherwise. Write `Return` rather than `return` in such functions: on compilers without
statement expressions the macros are implemented with coroutines and `Return` becomes `co_return`.

Variations (all in the [macro reference](../reference/macros.md)):

| Macro | On failure |
| --- | --- |
| `TryX(expr)` | return the error |
| `TryXTransform(expr, f)` | return `f(error)` as the new error — to translate between error types |
| `TryXOr(expr, f)` | return `f(error)` as the function's result — to recover |
| `TryXAssert(expr, "msg")` | fail a contract — for errors that cannot be handled |
| `DiscardTryX(expr)` | same as `TryX` when you do not need the value |

There is also a statement family that needs no compiler extension:
`TryTo(text, io::readfile(path));` declares `text` or returns.

### Chaining

`std::expected` has monadic members; `stormkit::monadic` supplies ready-made closures for them:

```cpp
auto names = dynarray<string> {};

load_user(id)
    .transform(&User::name)                                   // expected<string, E>
    .transform(monadic::emplace_to(names))                    // push it
    .transform_error(monadic::assert("user database is corrupt"));
```

| Closure | Purpose |
| --- | --- |
| `monadic::assert("msg")` | turn an error into a contract failure |
| `monadic::log(logger, "msg")` | log the error and carry on |
| `monadic::throw_as_exception()` | throw the error |
| `monadic::identity(v)`, `monadic::consume(v)` | supply a fallback value |
| `monadic::set(out)`, `monadic::emplace_to(c)` | store the value |
| `monadic::discard()` | ignore it |

### Producing errors

To report an OS failure from your own code, capture it right after the failing call:

```cpp
auto open_device(czstring path) noexcept -> system_result<int> {
    const auto fd = ::open(path, O_RDWR);
    if (fd < 0) return std::unexpected { error_code::from_errno() };
    return fd;
}
```

`error_code::from_win32()` and `error_code::from_stderrc(std::errc::invalid_argument)` are the
other common sources. For errors of your own domain, any enum or struct works as `E`; make it
formattable (see [below](#making-your-types-formattable)) so that it logs nicely.

### Cleaning up

`at_scope_exit_do` runs a callable when the enclosing scope ends, however it ends:

```cpp
auto handle  = acquire();
auto cleanup = at_scope_exit_do([&] noexcept { release(handle); });

Try(step_one(handle));       // early returns still release
Try(step_two(handle));
```

---

## Safe conversions

`static_cast` says "trust me". StormKit's casts say what you mean, and check it.

### `as` — a conversion that must be valid

```cpp
const auto n      = as<u32>(std::ranges::size(items));     // usize -> u32, checked
const auto scale  = as<f32>(width) / as<f32>(height);
const auto raw    = as<underlying>(color_layout::RGBA);    // enum -> its underlying type
const auto level  = as<log_level>(2);                      // integer -> enum
```

When the destination cannot represent the value, `as` fails a contract — at compile time if the
value is a constant. If truncation is what you want, say so: `unchecked_narrow<u8>(value)`.

The same spelling accesses sum types and downcasts, with the same check:

```cpp
auto&      circle = as<Circle>(shape);                     // Shape& -> Circle&, checked dynamic_cast
const auto text   = as<string>(variant_value);             // the active alternative must be string
const auto value  = as<i32>(optional_int);                 // must not be empty
const auto number = as<string>(255, 16);                   // "ff"
```

### `is` — asking first

```cpp
if (is<Circle>(shape))           { /* dynamic type test */ }
if (is<string>(variant_value))   { /* active alternative */ }
if (is<empty>(optional_int))     { /* disengaged */ }

if (is(a, 0.1f + 0.2f))          { /* epsilon comparison of floats */ }
if (is(-1, 4'000'000'000u))      { /* false: no signed/unsigned surprise */ }
```

### `to` — a conversion that may fail

```cpp
if (auto port = to<u16>(text); port) listen(*port);
else std::println("'{}' is not a port number: {}", text, port.error());
```

### `into` and `view_of`

```cpp
constexpr auto primes = into<array>({ 2, 3, 5, 7 });                 // array<int, 4>
auto workers          = into<dynarray>({ make_worker(), make_worker() });   // moves, works with move-only types

auto bytes  = view_of(as_bytes, vertices);        // array_view<const byte> over a dynarray<vertex>
auto header = bytes_of(file_header);              // any standard-layout struct as bytes
auto span   = mutable_view_of(pixels);            // array_view<pixel>
```

### Teaching `as` about your types

Declare a `tag_invoke` overload in your type's namespace:

```cpp
enum class direction { NORTH, EAST, SOUTH, WEST };

constexpr auto tag_invoke(as_fn<string_view>, direction value,
                          source_location_arg = std::source_location::current()) noexcept -> string_view {
    switch (value) {
        case direction::NORTH: return "north";
        case direction::EAST:  return "east";
        case direction::SOUTH: return "south";
        case direction::WEST:  return "west";
    }
    std::unreachable();
}

const auto name = as<string_view>(direction::EAST);
std::println("{}", direction::WEST);                 // also formattable now
```

---

## Strings and formatting

### Algorithms

```cpp
const auto parts = split("width=800;height=600", ";");      // dynarray<string_view>: views into the input
const auto upper = to_upper("hello");                        // "HELLO" (constexpr, ASCII)
const auto path  = replace("a/b/c", "/", "\\");              // "a\\b\\c"
```

`split` returns views: keep the original string alive.

### Making your types formattable

One function makes a type work with `std::format`, `std::println` and the logger:

```cpp
struct vec2i { i32 x, y; };

template<typename CharT, typename FormatContext>
constexpr auto tag_invoke(format_as_fn<CharT>, const vec2i& v, FormatContext& ctx) -> decltype(ctx.out()) {
    return std::format_to(ctx.out(), "({}, {})", v.x, v.y);
}

std::println("position: {:>12}", vec2i { 3, 4 });     // width and alignment work
```

As seen above, a type with an `as<string_view>` conversion is formattable for free. Most StormKit
types are formattable out of the box: colours, extents, vectors, matrices, `system_code`,
`ref_ptr`, strong types, flag enums.

### Compile-time strings

`static_string<N>` is a string that can be a template argument:

```cpp
template<static_string NAME>
struct setting {
    static constexpr auto name = string_view { NAME };
    i32 value;
};

auto volume = setting<"audio.volume"> { 80 };
```

### Hashing strings

```cpp
using namespace stormkit::literals;

switch (hash_of<hash32>(command)) {
    case "start"_hash32: start(); break;
    case "stop"_hash32:  stop();  break;
}

auto registry = string_hash_map<i32> {};      // keys are std::string…
registry.emplace("answer", 42);
registry.find("answer"sv);                    // …but lookups by string_view do not allocate
```

### Encodings

`ascii_to_utf16`, `ascii_to_wide`, `ascii_to_utf8` and their inverses convert between narrow
strings and the other encodings; `to_native_encoding` gives what the platform's APIs expect.

---

## Files, libraries and the console

### Reading and writing files

```cpp
auto bytes = io::readfile("model.bin");                                // system_result<dynarray<byte>>
auto text  = io::readfile<io::open_mode::UTF8>("notes.txt");           // system_result<dynarray<char>>

io::writefile("copy.bin", *bytes);
```

For incremental access, open a descriptor:

```cpp
auto file = TryX(io::binary_file::open("big.dat", io::access::READ));

auto chunk = array<byte, 4096> {};
while (file.position() < file.size()) {
    const auto read = TryX(file.read_to(chunk));
    consume(std::span { chunk }.first(read));
}
```

`io::text_file<io::open_mode::UTF8>` is the text equivalent. Descriptors are move-only and close
themselves.

### Loading shared libraries

```cpp
auto plugin = TryX(dynamic_loader::load("plugins/effects.dll"));
auto create = TryX(plugin.func<Effect*()>("create_effect"));

auto* effect = create();
```

Keep the loader alive for as long as you use what it resolved.

### Styled console output

```cpp
std::println("{}", console_style { .fg = console_color::RED, .modifiers = style_modifier::BOLD } | "error:");
std::println("{} tests passed", GREEN_TEXT_STYLE | passed);
std::println(get_stderr(), "{}", YELLOW_TEXT_STYLE | "warning: disk almost full");
```

`style | value` wraps any formattable value; the escape sequences and the reset are emitted for
you. `get_stdout()` / `get_stderr()` are the function forms of the C stream macros, which modules
cannot export.

### Crash diagnostics

`setup_signal_handler()` installs handlers that print a stack trace on `std::terminate` and on a
segmentation fault. `stormkit-main` calls it for you. `print_stacktrace()` prints one on demand.

---

## Containers

### Hash tables

`hash_map` and `hash_set` are fast open-addressing tables with contiguous storage:

```cpp
auto scores = hash_map<string, u32> {};
scores.emplace("alice", 12);
scores["bob"] += 3;

for (const auto& [name, score] : scores) std::println("{}: {}", name, score);
```

Iteration is as fast as over a vector; in exchange, inserting or erasing invalidates references
and iterators. Your own types work as keys as soon as they are [hashable](#hashing).

For tables known at compile time, use the frozen variants:

```cpp
inline constexpr auto DEFAULT_EXTENSION = make_static_hash_map<file_kind, string_view>({
    { file_kind::IMAGE, ".png" },
    { file_kind::SOUND, ".ogg" },
});

constexpr auto extension = DEFAULT_EXTENSION.at(file_kind::IMAGE);
```

### Hashing

`hash_of(a, b, …)` hashes and combines any number of values. A type is hashable when it is
trivially copyable without padding, or when it has a `tag_invoke(hash_fn<Ret>, …)`:

```cpp
struct tile { i32 x, y; u8 layer; };       // has padding: needs an explicit hasher

template<typename Ret>
constexpr auto tag_invoke(hash_fn<Ret>, const tile& t) noexcept -> Ret {
    return hash_of<Ret>(t.x, t.y, t.layer);
}

auto visited = hash_set<tile> {};
```

### Building and combining sequences

```cpp
auto zeros   = filled_with(1024_usize, 0.f);              // dynarray<f32>
auto mask    = filled_with<8>(true);                      // array<bool, 8>
auto all     = concat(first, second, third);              // new dynarray
merge(all, extra);                                        // append in place
auto joined  = move_and_concat(std::move(a), std::move(b));
```

### Ring buffer

A fixed-capacity buffer that overwrites its oldest element — frame-time history, recent log lines:

```cpp
auto history = ring_buffer<f32> { 120 };
history.emplace(frame_time);
if (history.full()) plot(history.data());
```

### Directed acyclic graph

`dag<T>` stores vertices and edges and answers ordering questions — build steps, render passes,
module dependencies:

```cpp
auto tasks = dag<string> {};
const auto fetch   = tasks.emplace_vertex("fetch");
const auto compile = tasks.emplace_vertex("compile");
const auto link    = tasks.emplace_vertex("link");
tasks.add_edge(fetch, compile);
tasks.add_edge(compile, link);

if (auto order = tasks.topological_sort(); order) {
    for (auto id : *order) run(tasks.get_vertex_value(id));
} else {
    std::println("dependency cycle through {}", order.error());      // the ids on the cycle
}

const auto dot = tasks.dump();                                       // Graphviz, for debugging
io::writefile<io::open_mode::UTF8>("tasks.dot", dot);
```

### Tree

`tree<Node>` is an index-linked hierarchy in one contiguous array, with dirty-flag propagation —
the shape of a scene graph. See the
[reference](../reference/core-containers.md#stormkitcorecontainerstree).

---

## Owning and referring

### `heap_ptr` and `allocate`

`heap_ptr<T>` is `std::unique_ptr<T>`. `allocate<T>(args…)` creates one without throwing:

```cpp
auto cache = allocate<texture_cache>(256_mib);        // expected<heap_ptr<texture_cache>, allocation_error>
if (not cache) return std::unexpected { cache.error() };
```

`allocate_unsafe<T>` skips the check and returns the pointer directly.

### `ref_ptr` — a reference you can store

A C++ reference cannot be reseated, stored in a container or defaulted. A raw pointer can be null
and says nothing about ownership. `ref_ptr<T>` is the middle ground: non-owning, built from an
object, copyable.

```cpp
class sprite {
  public:
    explicit sprite(const texture& texture) noexcept : m_texture { texture } {}
    auto set_texture(const texture& texture) noexcept -> void { m_texture = texture; }
    auto draw() const -> void { blit(*m_texture); }
  private:
    ref_ptr<const texture> m_texture;
};

auto visible = dynarray<ref_ptr<const sprite>> {};
for (const auto& s : sprites) if (on_screen(s)) visible.emplace_back(s);
```

Helpers build several at once, unwrapping pointers and smart pointers along the way:

```cpp
auto refs = refs_of(camera, light, *mesh_ptr);              // array<ref_ptr<const node>, 3>
auto all  = refs_of<dynarray>(meshes);                      // one per element
```

### `defer_init` — construct later, in place

For members that cannot be built in the constructor's initialiser list:

```cpp
class renderer {
  public:
    auto init(const config& cfg) -> system_result<void> {
        m_device = TryX(device::create(cfg));       // move-assigns into the storage
        Return {};
    }
    auto draw() -> void { m_device->submit(); }      // contract-checked access
  private:
    defer_init<device> m_device;
};
```

Unlike `std::optional`, it is meant to be initialised exactly once and then used as if it were the
object (`->`, `*`, implicit conversion to `T&`).

### `pimpl`

```cpp
// widget.cppm
class widget {
  public:
    widget();
    ~widget();
    widget(widget&&) noexcept;
    auto operator=(widget&&) noexcept -> widget&;
    auto draw() const -> void;
  private:
    struct impl;
    pimpl<impl> m_impl;
};

// widget.cpp
struct widget::impl { /* heavy members */ };
widget::widget() : m_impl {} {}
widget::~widget()                                    = default;
widget::widget(widget&&) noexcept                    = default;
auto widget::operator=(widget&&) noexcept -> widget& = default;
auto widget::draw() const -> void { m_impl->render(); }       // const widget -> const impl
```

`pimpl<T, true>` defers construction to an explicit `init(args…)`.

### `raii_capsule` — owning a C handle

```cpp
struct socket_tag;
using unique_socket = raii_capsule<int, ::socket, ::close, socket_tag, -1>;

auto sock = unique_socket::create(AF_INET, SOCK_STREAM, 0);
::connect(sock, address, length);            // converts to the raw handle
```

The handle type, how to create it, how to destroy it and its "empty" value are all template
arguments; the result is a move-only owner with no overhead.

### `singleton` and the private tag

`class registry : public singleton<registry>` gives `registry::instance()`, created on first use
and thread-safe. `private_tag<T>` implements the passkey idiom behind the `create` factories:
[reference](../reference/core-containers.md#stormkitcoreprivate_tag).

---

## Stronger types

### Flags

```cpp
enum class permission : u8 { READ = 1, WRITE = 2, EXECUTE = 4 };

template<>
inline constexpr auto stormkit::meta::FLAG_TRAIT<permission> = true;       // at namespace scope

auto perms = permission::READ | permission::WRITE;
perms &= ~permission::WRITE;
if (has_flag_bit(perms, permission::READ)) { /* … */ }
```

### Strong types

Give meaning to primitive values so that the compiler rejects mix-ups:

```cpp
using user_id  = strong_type<u64, struct user_id_tag,  "user_id">;
using order_id = strong_type<u64, struct order_id_tag, "order_id">;

auto find_order(user_id user, order_id order) -> order_view;

find_order(user_id { 7 }, order_id { 1042 });        // OK
// find_order(order_id { 1042 }, user_id { 7 });     // does not compile
```

Add `capabilities::arithmetic` when the quantity supports `+ - * /`
(`using meters = strong_type<f32, struct meters_tag, "meters", capabilities::arithmetic>;`).
Read the value back with `.value()`.

### Checked values

Attach an invariant to a type; it is verified on every construction and assignment:

```cpp
using normalized = checked_value<f32, struct normalized_tag, [](f32 v) static noexcept { return v >= 0.f and v <= 1.f; }>;

auto set_opacity(normalized opacity) -> void;

set_opacity(0.5f);       // OK
set_opacity(1.5f);       // contract violation
```

`positive<T>` and `negative<T>` are predefined.

---

## Functional helpers and ranges

### Numeric ranges

```cpp
for (auto i : range(10)) { /* 0 … 9 */ }
for (auto i : range(2, 20, 3)) { /* 2, 5, 8, … */ }
for (auto [y, x] : multi_range(height, width)) { image[y, x] = shade(x, y); }
```

### `either`

An expression-level conditional, usable where a statement is not (initialising a `const`,
inside a larger expression). Given a pointer it also unwraps it:

```cpp
const auto mode  = either(fullscreen, [] { return "fullscreen"sv; }, [] { return "windowed"sv; });

const auto label = either(find_user(id),                                  // a User* or smart pointer
                          [](const User& user) { return user.name; },
                          [] { return string { "anonymous" }; });
```

### `init_by`

Initialise a `const` object that needs several statements, without a mutable temporary leaking
into scope:

```cpp
const auto info = init_by<VkApplicationInfo>([&](auto& info) noexcept {
    zero_bytes(info);
    info.sType            = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    info.pApplicationName = name;
});
```

### `overload_set` and `monadic::either`

```cpp
std::visit(overload_set {
    [](const circle& c) { draw_circle(c); },
    [](const rect& r)   { draw_rect(r); },
}, shape);

auto areas = shapes | std::views::transform(monadic::either(
    [](const circle& c) { return 3.14159f * c.radius * c.radius; },
    [](const rect& r)   { return r.width * r.height; }));
```

### Eager range algorithms

`transform`, `copy_if` and `transform_if` are the "give me a vector" versions of the standard
views:

```cpp
auto names  = transform(users, &User::name);                                   // dynarray<string>
auto adults = copy_if(users, [](const auto& u) { return u.age >= 18; });
```

### Callbacks

Take callbacks as `std23::function_ref<Sig>` (a non-owning, two-pointer reference to any callable)
and store them as `std23::move_only_function<Sig>`.

---

## Threads

### `locked` — data that cannot be touched without its lock

```cpp
auto queue = locked<dynarray<job>> {};

// producer
queue.write([&](auto& jobs) noexcept { jobs.emplace_back(std::move(job)); });

// consumer
auto next = queue.write([](auto& jobs) noexcept -> std::optional<job> {
    if (std::ranges::empty(jobs)) return std::nullopt;
    auto out = std::move(jobs.back());
    jobs.pop_back();
    return out;
});

const auto pending = queue.read([](const auto& jobs) noexcept { return std::ranges::size(jobs); });
```

There is no way to obtain the value without holding the mutex (short of the explicitly named
`unsafe()`), so "forgot to lock" is not a bug you can write. `read()` / `write()` without a
closure return a guard object for longer critical sections.

For real reader/writer locking, choose the mutex type, and the lock type on the guard form:

```cpp
auto config = locked<settings, std::shared_mutex> {};

{
    const auto guard = config.read<std::shared_lock>();      // several readers may hold this at once
    apply(guard->volume, guard->brightness);
}
config.write([](auto& s) noexcept { s.volume = 11; });       // exclusive
```

### `thread_pool`

```cpp
auto pool = thread_pool {};                      // half the hardware threads by default
pool.set_name("worker");                         // visible in debuggers

auto answer = pool.post_task<int>([] { return expensive(); });      // std::future<int>
pool.post_task<void>([] { warm_cache(); }, no_future);              // fire and forget

std::println("{}", answer.get());
```

`parallel_for` applies a function to every element of a random-access range, split across the
workers, and returns when all are done:

```cpp
parallel_for(pool, pixels, [](auto& pixel) noexcept { pixel = tone_map(pixel); });
```

The destructor waits for running tasks and joins the workers.

### Thread names

`set_current_thread_name("audio")` names the calling thread for debuggers and profilers.

---

## Colours

`color<LAYOUT, T>` is a small aggregate whose members are laid out in the order of its name, so a
`ucolor_bgra` *is* a BGRA8 pixel in memory:

```cpp
auto pixel = ucolor_rgba { .r = 255, .g = 128, .b = 0, .a = 255 };
const fcolor_rgba clear = colors::SILVER<f32>;             // presets convert to any layout and component type

const auto swapped = as<ucolor_bgra>(pixel);               // reorders components
const auto linear  = as<fcolor_rgb>(pixel);                // 0-255 -> 0-1, drops alpha
```

Presets are the HTML 4.01 colours (`colors::RED<>`, `colors::TEAL<f32>`, …).

---

## Meta-programming

`stormkit::meta` is where the concepts used in all the signatures above live. A few are worth
knowing even if you never write a template library:

| Concept / alias | Why you would use it |
| --- | --- |
| `meta::arithmetic<T>`, `meta::integral<T>`, `meta::floating_point<T>` | numeric constraints that exclude `bool` and `byte` |
| `meta::enumeration<T>` | any enum |
| `meta::plain::is<T, U>` | constrain a forwarding reference: `template<meta::plain::is<Config> T> auto set(T&&)` |
| `meta::specialization_of<T, std::vector>` | "is some `vector`" |
| `meta::in<T>` | the cheapest way to take a read-only `T` parameter |
| `meta::forward_like<Self, T>` | return type of a deducing-`this` accessor |
| `meta::name_of<T>()` | the type's name, at compile time |

```cpp
template<meta::arithmetic T>
constexpr auto lerp(T a, T b, meta::in<f32> t) noexcept -> T {
    return as<T>(as<f32>(a) + (as<f32>(b) - as<f32>(a)) * t);
}
```

The full catalogue, including the `tag_invoke` machinery, is in the
[meta reference](../reference/core-meta-string.md#stormkitcoremeta).

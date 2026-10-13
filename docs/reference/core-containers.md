# `stormkit.core` reference — containers, memory & parallelism

Part 2 of 4 of the `stormkit.core` reference
([1. Foundation](core-foundation.md) · **2. Containers, memory & parallelism** ·
[3. Meta & strings](core-meta-string.md) · [4. Type safety](core-typesafe.md)).

All names are in `namespace stormkit` unless stated otherwise.

---

## `stormkit.core.heap`

```cpp
struct allocation_error { string_view type; usize size; };

template<typename T> using heap_ptr        = std::unique_ptr<T>;
template<typename T> using shared_heap_ptr = std::shared_ptr<T>;
using std::weak_ptr;

template<typename T, class... Ts> auto allocate(Ts&&... args)               -> std::expected<heap_ptr<T>, allocation_error>;
template<typename T, class... Ts> auto allocate_unsafe(Ts&&... args)        -> heap_ptr<T>;
template<typename T, class... Ts> auto allocate_shared(Ts&&... args)        -> std::expected<shared_heap_ptr<T>, allocation_error>;
template<typename T, class... Ts> auto allocate_shared_unsafe(Ts&&... args) -> shared_heap_ptr<T>;
```

| Function | Description |
| --- | --- |
| `allocate<T>(args...)` | `new (std::nothrow) T(args...)`. On failure returns an `allocation_error` holding the type name and `sizeof(T)`. |
| `allocate_unsafe<T>(args...)` | Same without the check; the pointer is null when allocation failed. |
| `allocate_shared*` | The `shared_ptr` equivalents. |

Construction uses parentheses, so aggregates need C++20 parenthesised aggregate initialisation.

Most StormKit classes follow the convention `static T::create(...)` (by value) and
`static T::allocate(...)` (returns `heap_ptr<T>`), built on these helpers.

---

## `stormkit.core.pimpl`

```cpp
template<typename T, bool DEFER = false>
class pimpl {
  public:
    using element_type = T;
    using pointer      = T*;

    constexpr pimpl() noexcept requires(DEFER);
    template<typename... Ts> constexpr pimpl(Ts&&... args) requires(not DEFER);
    constexpr pimpl(pimpl&&) noexcept;                       // move-only
    constexpr auto operator=(pimpl&&) noexcept -> pimpl&;

    template<typename... Ts> constexpr auto init(Ts&&... args) -> void;

    constexpr auto operator->(this Self& self) noexcept -> /* const-propagating */ T*;
    constexpr auto operator*(this Self& self)  noexcept -> /* const-propagating */ T&;
    constexpr auto get(this Self& self)        noexcept -> ref_ptr</* const-propagating */ T>;
    constexpr auto operator==(std::nullptr_t) const noexcept -> bool;
    constexpr explicit operator bool() const noexcept;
};
```

Heap-allocated implementation pointer with **const propagation**: through a `const pimpl<T>` you
only reach a `const T`.

| Mode | Behaviour |
| --- | --- |
| `pimpl<T>` | The constructor forwards its arguments to `T` and allocates immediately. |
| `pimpl<T, true>` | Default constructible and empty; call `init(args...)` later. |

Because `T` may be incomplete where the `pimpl` member is declared, the owning class must define
its destructor and move operations in the source file where `T` is complete.

---

## `stormkit.core.singleton`

```cpp
template<typename T>
class singleton {
  public:
    template<typename... Ts> static auto instance(Ts&&... args) -> T&;
  protected:
    singleton() noexcept;
    ~singleton() noexcept;
};
```

CRTP-free singleton base: `class registry : public stormkit::singleton<registry> { ... };`.
The first call to `registry::instance(args...)` constructs the object (thread-safe through
`std::call_once`); arguments of later calls are ignored. Non-copyable, non-movable.

---

## `stormkit.core.private_tag`

```cpp
template<typename T> using private_tag = /* a type only T can construct */;
template<typename T> inline constexpr auto PRIVATE = /* the unique value of private_tag<T> */;
```

The passkey idiom. A class takes a `private_tag<Self>` in a **public** constructor so that
`std::make_unique`, `allocate` and friends can call it, while only the class itself can obtain the
tag value:

```cpp
class device {
    using private_tag = stormkit::private_tag<device>;
  public:
    explicit device(private_tag) noexcept;                  // callable by anyone, constructible by no one else
    static auto create() noexcept -> expected<device, error> {
        auto out = device { stormkit::PRIVATE<device> };
        /* fallible initialisation */
        return out;
    }
};
```

This is why StormKit objects are created with `T::create(...)` / `T::allocate(...)` rather than
with a constructor.

---

## `stormkit.core.overload_set`

```cpp
template<class... Ts> struct overload_set : Ts... { using Ts::operator()...; };
template<class... Ts> overload_set(Ts...) -> overload_set<Ts...>;
```

The classic "overloaded" helper for `std::visit`:

```cpp
std::visit(stormkit::overload_set {
    [](const wsi::closed_event&)    { /* ... */ },
    [](const wsi::resized_event& e) { /* ... */ },
    [](auto&&)                      {},
}, event);
```

---

## `stormkit.core.containers`

Umbrella for the sub-modules below.

### `stormkit.core.containers.hash_map`

| Alias | Underlying type |
| --- | --- |
| `hash_map<Key, T, Hash, KeyEqual, AllocatorOrContainer>` | [`ankerl::unordered_dense::map`](https://github.com/martinus/unordered_dense) |
| `hash_set<Key, Hash, KeyEqual, AllocatorOrContainer>` | `ankerl::unordered_dense::set` |
| `static_hash_map<Key, Value, N, Hash, KeyEqual>` | [`frozen::unordered_map`](https://github.com/serge-sans-paille/frozen) |
| `static_hash_set<Key, N, Hash, KeyEqual>` | `frozen::unordered_set` |

```cpp
template<typename Key, typename Value, usize N>
constexpr auto make_static_hash_map(std::pair<Key, Value> (&pairs)[N])  noexcept -> static_hash_map<Key, Value, N>;
template<typename Key, typename Value, usize N>
constexpr auto make_static_hash_map(std::pair<Key, Value> (&&pairs)[N]) noexcept -> static_hash_map<Key, Value, N>;
```

- `hash_map` / `hash_set` are open-addressing, contiguous-storage tables: fast iteration, but
  **references and iterators are invalidated by insertion and erasure**.
- `static_hash_map` / `static_hash_set` are immutable, perfect-hashed and usable in constant
  expressions.
- Any type that satisfies [`meta::has_hasher`](#stormkitcorehash) is automatically usable as a
  `hash_map` key: the module specialises `ankerl::unordered_dense::hash` to call `hash_of`.

```cpp
inline constexpr auto NAMES = stormkit::make_static_hash_map<level, std::string_view>({
    { level::LOW,  "low"  },
    { level::HIGH, "high" },
});
```

### `stormkit.core.containers.utils`

```cpp
template<template<class> typename Container = dynarray, typename T>
constexpr auto filled_with(usize size, T value) noexcept -> Container<T>;
template<usize N, typename T>
constexpr auto filled_with(T value) noexcept -> array<T, N>;

template<stdr::range Out, stdr::input_range... Inputs>
constexpr auto merge(Out& output, const Inputs&... ranges) noexcept -> void;
template<template<class...> typename Out = dynarray, stdr::input_range... Inputs>
constexpr auto concat(const Inputs&... inputs) noexcept -> Out<Value>;

template<stdr::range Out, stdr::input_range... Inputs>
constexpr auto move_and_merge(Out& output, Inputs&&... ranges) noexcept -> void;
template<template<class...> typename Out = dynarray, stdr::input_range... Inputs>
constexpr auto move_and_concat(Inputs&&... inputs) noexcept -> Out<Value>;

namespace meta { template<stdr::input_range... Inputs> using common_range_value_type = /* value type of the first range */; }
```

| Function | Description |
| --- | --- |
| `filled_with(n, v)` | A `dynarray<T>` (or other container) of `n` copies of `v`. |
| `filled_with<N>(v)` | An `array<T, N>` of copies of `v`. |
| `merge(out, a, b, ...)` | Appends every range to `out`, reserving once. |
| `concat(a, b, ...)` | Returns a new container holding the concatenation. |
| `move_and_merge`, `move_and_concat` | Same, moving the elements out of the inputs. |

`Value` is the value type of the *first* input; the others must be convertible to it.

Helpers to build arrays from values (`into<array>`, `to<dynarray>`) and to view objects as bytes
live in the [typesafe casts](core-typesafe.md#safe-casts).

### `stormkit.core.containers.ringbuffer`

```cpp
template<typename T>
class ring_buffer {
  public:
    using value_type = T;   using size_type = usize;

    ring_buffer(size_type capacity);                // copyable and movable

    auto clear() noexcept -> void;
    auto empty() const noexcept -> bool;            auto full() const noexcept -> bool;
    auto size() const noexcept -> size_type;        auto capacity() const noexcept -> size_type;

    template<meta::plain::is<T> U> auto push(U&& value) -> void;
    template<typename... Ts>       auto emplace(Ts&&... values) -> void;
    auto next() noexcept -> void;
    auto pop() noexcept -> void;
    auto get(this Self& self) noexcept -> /* T& or const T& */;
    auto data() const noexcept -> array_view<const value_type>;
};
```

Fixed-capacity circular buffer; inserting into a full buffer overwrites the oldest slot.

| Member | Description |
| --- | --- |
| `emplace(args...)` / `push(v)` | Constructs at the write cursor; when `full()`, an element is destroyed first. |
| `get()` | The element at the read cursor. Pre-condition: not empty. |
| `next()` | Advances the read cursor (does not destroy). |
| `pop()` | Destroys one element and decrements `size()`. Pre-condition: not empty. |
| `data()` | View over the whole storage, `capacity()` elements long. |

### `stormkit.core.containers.tree`

```cpp
class tree_node {
  public:
    using index_type = u32;   using bitfield_type = u32;
    static constexpr auto INVALID_INDEX = std::numeric_limits<index_type>::max();

    auto name() const noexcept -> const string&;            auto set_name(string name) noexcept -> void;
    auto parent() const noexcept -> index_type;             auto set_parent(index_type) noexcept -> void;
    auto next_sibling() const noexcept -> index_type;       auto set_next_sibling(index_type) noexcept -> void;
    auto first_child() const noexcept -> index_type;        auto set_first_child(index_type) noexcept -> void;
    auto dirty_bits() const noexcept -> const bitfield_type&;
    auto set_dirty_bits(bitfield_type bits) noexcept -> void;
    auto invalidate() noexcept -> void;
};

template<typename T = tree_node>
class tree {
  public:
    static constexpr auto DEFAULT_PREALLOCATED_TREE_SIZE = usize { 10 };
    using tree_node_type = T;
    using tree_node_index_type    = typename T::index_type;
    using tree_node_bitfield_type = typename T::bitfield_type;

    auto get_free_node() -> tree_node_index_type;
    auto insert(tree_node_type&& node, tree_node_index_type parent_index,
                tree_node_index_type previous_sibling) -> tree_node_index_type;
    auto remove(tree_node_index_type index) -> void;
    auto mark_dirty(tree_node_index_type index, tree_node_bitfield_type bits) -> void;

    auto operator[](tree_node_index_type index) noexcept -> tree_node_type&;        // and const
    auto size() const noexcept -> usize;
    auto begin(); auto end(); auto cbegin() const; auto cend() const;               // and const begin/end

    auto clear_dirties() noexcept -> void;
    auto dirties() const noexcept -> array_view<const tree_node_index_type>;

    auto gen_dot_file(stdfs::path filepath,
                      std23::function_ref<string_view(string_view)> colorize_node) const noexcept -> system_result<usize>;
    auto gen_dot_file(stdfs::path filepath, u32 highlight,
                      std23::function_ref<string_view(string_view)> colorize_node) const noexcept -> system_result<usize>;
};
```

An index-linked tree stored in one contiguous array ("first child / next sibling"), designed for
scene-graph style hierarchies with dirty tracking.

| Member | Description |
| --- | --- |
| `tree_node` | Link record. Derive from it (or provide the same interface) to attach a payload. |
| `get_free_node()` | Returns the index of an unused slot, growing the storage when needed. |
| `insert(node, parent, previous_sibling)` | Links `node` under `parent`; pass `INVALID_INDEX` for "no parent" / "first child". |
| `remove(index)` | Unlinks the node and its subtree, returning the slots to the free list. |
| `mark_dirty(index, bits)` | ORs `bits` into the node and its descendants and records them in `dirties()`. |
| `gen_dot_file(...)` | Writes a Graphviz description; `colorize_node` maps a node name to a colour name. Returns the byte count written. |

### `stormkit.core.containers.dag`

```cpp
template<typename T>
class dag {
  public:
    using value_type = T;   using index_type = u32;
    struct edge   { index_type from; index_type to; };
    struct vertex { index_type id;   value_type value; };

    using colorize_closure     = std23::move_only_function<string(const value_type&)>;
    using format_value_closure = std23::move_only_function<string(const value_type&)>;
    struct closures {
        std::optional<colorize_closure>     colorize     = std::nullopt;
        std::optional<format_value_closure> format_value = /* std::format("{}", v) when T is formattable */;
    };

    constexpr explicit dag(std::optional<usize> reserve = std::nullopt) noexcept;   // move-only

    constexpr auto directed() const noexcept -> bool;
    constexpr auto clear() -> void;
    constexpr auto empty() const noexcept -> bool;

    constexpr auto add_vertex(const value_type& value) -> index_type;
    constexpr auto add_vertex(value_type&& value)      -> index_type;
    template<typename... Ts> constexpr auto emplace_vertex(Ts&&... args) -> index_type;
    constexpr auto get_vertex_value(this Self&& self, index_type id) noexcept -> /* forwarded value_type */;
    constexpr auto has_vertex(const value_type& value) const noexcept -> bool;
    constexpr auto has_vertex(index_type id) const noexcept -> bool;
    constexpr auto remove_vertex(const value_type& value) -> void;
    constexpr auto remove_vertex(index_type id) -> void;

    constexpr auto add_edge(index_type from, index_type to) noexcept -> void;
    constexpr auto has_edge(index_type from, index_type to) const noexcept -> bool;
    constexpr auto remove_edge(index_type from, index_type to) noexcept -> void;
    constexpr auto adjacent_edges(index_type vert) const noexcept -> const dynarray<edge>&;

    constexpr auto vertices() const noexcept -> const dynarray<vertex>&;
    constexpr auto vertices_count() const noexcept -> usize;
    constexpr auto edges() const noexcept -> const dynarray<edge>&;
    constexpr auto edges_count() const noexcept -> usize;

    constexpr auto topological_sort() const noexcept -> expected<dynarray<index_type>, dynarray<index_type>>;
    constexpr auto find_cycle() const noexcept -> std::optional<dynarray<index_type>>;
    constexpr auto reverse_view() const noexcept -> dag<ref_ptr<const value_type>>;
    constexpr auto reverse_clone() const noexcept -> dag<value_type>;
    constexpr auto dump(closures closures_ = {}) const noexcept -> string;
};
```

A directed graph intended to stay acyclic (dependency graphs, frame graphs, task ordering).

| Member | Description |
| --- | --- |
| `add_vertex` / `emplace_vertex` | Returns the new vertex id. Ids are allocated sequentially and never reused. |
| `remove_vertex` | Also removes every edge touching the vertex. |
| `adjacent_edges(id)` | Outgoing edges of `id`. |
| `topological_sort()` | On success, the vertex ids ordered so that every edge goes forward. On failure, the **error holds the ids forming a cycle**. |
| `find_cycle()` | The ids of one cycle, or `nullopt`. |
| `reverse_view()` | A graph with every edge flipped whose values are `ref_ptr`s into this graph (must not outlive it). |
| `reverse_clone()` | Same with copied values. |
| `dump(closures)` | Graphviz `dot` text. `colorize` and `format_value` customise node colour and label. |

`dag<T>::edge` and `dag<T>::vertex` are formattable. `dag` is usable in constant expressions.

```cpp
auto graph = stormkit::dag<std::string> {};
const auto compile = graph.emplace_vertex("compile");
const auto link    = graph.emplace_vertex("link");
graph.add_edge(compile, link);

if (auto order = graph.topological_sort(); order)
    for (auto id : *order) std::println("{}", graph.get_vertex_value(id));
```

### `stormkit.core.containers.raii_capsule`

```cpp
template<typename T, auto CONSTRUCTOR, auto DELETER, typename Tag, auto RELEASE_VALUE = T {}>
class raii_capsule {
  public:
    using value_type = T;   using reference_type = T&;

    template<typename... Ts> static constexpr auto create(Ts&&... args) noexcept;   // see below
    static constexpr auto take(value_type&& value) noexcept -> raii_capsule;
    static constexpr auto empty() noexcept -> raii_capsule;

    constexpr raii_capsule(raii_capsule&&) noexcept;                                 // move-only
    constexpr auto operator=(raii_capsule&&) noexcept -> raii_capsule&;
    constexpr ~raii_capsule() noexcept;

    constexpr operator value_type() const noexcept;
    constexpr auto handle() noexcept -> reference_type;
    constexpr auto handle() const noexcept -> value_type;
    constexpr auto release() noexcept -> value_type;
    constexpr auto reset(value_type handle = RELEASE_VALUE) noexcept -> void;
};
```

A `unique_ptr`-like owner for **C handles** (file descriptors, `xcb_*`, `wl_*`, `HANDLE`, …).

| Parameter | Role |
| --- | --- |
| `T` | The handle type. |
| `CONSTRUCTOR` | Callable used by `create(args...)`. May return `T` or a `std::expected<T, E>`; in the latter case `create` returns `std::expected<raii_capsule, E>`. |
| `DELETER` | Callable invoked with the handle on destruction and `reset`. |
| `Tag` | Any type; makes two capsules over the same `T` distinct types. |
| `RELEASE_VALUE` | The "empty" handle value (default `T {}`); the deleter is not called for it. |

```cpp
struct fd_tag;
using unique_fd = stormkit::raii_capsule<int, ::open, ::close, fd_tag, -1>;

auto fd = unique_fd::create("/dev/null", O_RDONLY);
::read(fd, buffer, size);              // implicit conversion to int
```

### `stormkit.core.containers.shmbuffer`

```cpp
class shm_buffer final {
  public:
    using value_type = byte;

    static auto create(usize size, string name,
                       io::access access = io::access::READ | io::access::WRITE) noexcept -> system_result<shm_buffer>;
    static auto allocate(usize size, string name,
                         io::access access = io::access::READ | io::access::WRITE) noexcept
      -> system_result<heap_ptr<shm_buffer>>;

    shm_buffer(shm_buffer&&) noexcept;                    // move-only
    auto operator=(shm_buffer&&) noexcept -> shm_buffer&;
    ~shm_buffer();

    auto begin(); auto end(); auto cbegin() const; auto cend() const;
    auto operator[](usize index) noexcept -> byte&;       // const-propagating
    auto at(usize index) noexcept -> byte&;               // const-propagating
    auto size() const noexcept -> usize;
    auto data() noexcept -> array_view<byte>;             // const-propagating
    auto native_handle() noexcept -> void*;               // const-propagating
    auto name() const noexcept -> string_view;
    auto access() const noexcept -> io::access;
};
```

A named shared-memory region mapped into the process (`shm_open` + `mmap` on POSIX,
`CreateFileMapping` + `MapViewOfFile` on Windows), exposed as a contiguous range of bytes.
Element access is contract-checked. Used by the Wayland backend for software framebuffers.

---

## `stormkit.core.hash`

```cpp
template<meta::hash_type Ret> struct hash_fn;                       // the customisation point
template<meta::hash_type Ret> inline constexpr auto hash_cpo = hash_fn<Ret> {};

template<meta::hash_type Ret = hash64, typename... Ts>
constexpr auto hash_of(const Ts&... values) noexcept -> Ret;        // at least one value
template<meta::hash_type Ret = hash64, typename... Ts>
constexpr auto hash_combine(Ret hash, const Ts&... args) noexcept -> Ret;

namespace meta { template<typename T> concept has_hasher = /* hash_of<hash64>(value) is valid */; }
```

`Ret` is [`hash32` or `hash64`](core-foundation.md#hash-value-types).

How a value is hashed, in order of preference:

1. a `tag_invoke(hash_fn<Ret>, const T&)` overload found by ADL — **the way to make your own type
   hashable**;
2. otherwise, if `T` has unique object representations (integers, enums, padding-free trivially
   copyable structs), the CRC of its bytes;
3. otherwise the call is deleted with the message *"No hasher defined for this type"*.

`hash_combine` folds each argument in with the usual `0x9e3779b9` mix; ranges other than `string` /
`string_view` are hashed element by element. `hash_of(a, b, c)` is `hash_combine` starting from
zero. A hasher for `ref_ptr<T>` (hashing the address) is provided.

```cpp
struct vertex { vec3 position; vec2 uv; };

template<typename Ret>
constexpr auto tag_invoke(stormkit::hash_fn<Ret>, const vertex& v) noexcept -> Ret {
    return stormkit::hash_of<Ret>(v.position, v.uv);
}

auto cache = stormkit::hash_map<vertex, stormkit::u32> {};   // works out of the box
```

String hashing lives in [`stormkit.core.string.hash`](core-meta-string.md#stormkitcorestringhash).

### `stormkit.core.hash.crc`

```cpp
namespace hash {
    constexpr auto crc32(array_view<const byte>, u32 seed = 0) -> hash32;
    constexpr auto crc64(array_view<const byte>, u64 seed = 0) -> hash64;
}
namespace literals {
    constexpr auto operator""_crc32(unsigned long long) -> hash32;   constexpr auto operator""_crc32(long double) -> hash32;
    constexpr auto operator""_crc64(unsigned long long) -> hash64;   constexpr auto operator""_crc64(long double) -> hash64;
}
```

Table-driven CRC-32 and CRC-64, both `constexpr`. The literals hash the bytes of a numeric literal.

---

## `stormkit.core.random`

```cpp
auto seed(u32 seed) noexcept -> void;
template<meta::floating_point T> auto rand(T min, T max) noexcept -> T;   // uniform in [min, max)
template<meta::integral T>       auto rand(T min, T max) noexcept -> T;   // uniform in [min, max]
```

A `thread_local` `std::default_random_engine` behind a two-function interface. `seed` only affects
the calling thread. Not suitable for cryptography.

---

## `stormkit.core.ranges`

### `stormkit.core.ranges.numeric_range`

```cpp
template<typename T> struct numeric_range { T begin = 0; T end; T step = 1; };

template<meta::arithmetic T> constexpr auto range(T end) noexcept;
template<meta::arithmetic T> constexpr auto range(T begin, T end) noexcept;
template<meta::arithmetic T> constexpr auto range(T begin, T end, T step) noexcept;
template<meta::arithmetic T> constexpr auto range(const numeric_range<T>& nrange) noexcept;

template<meta::arithmetic... Ts> constexpr auto multi_range(Ts... ends) noexcept;
template<meta::arithmetic... Ts> constexpr auto multi_range(const numeric_range<Ts>&... ranges) noexcept;
```

| Function | Yields |
| --- | --- |
| `range(end)` | `0, 1, …, end - 1` (`std::views::iota`) |
| `range(begin, end)` | `begin, …, end - 1` |
| `range(begin, end, step)` | every `step`-th value (`iota \| stride`) |
| `multi_range(a, b, ...)` | tuples of the cartesian product `range(a) × range(b) × …`, last index varying fastest |

```cpp
for (auto i : stormkit::range(10)) { /* ... */ }
for (auto [y, x] : stormkit::multi_range(height, width)) { /* ... */ }
for (auto [y, x] : stormkit::multi_range(numeric_range { 1u, h - 1u }, numeric_range { 1u, w - 1u })) { /* ... */ }
```

`std::views::cartesian_product` is polyfilled when the standard library lacks it.

### `stormkit.core.ranges.algorithms`

```cpp
template<stdr::input_range Range, meta::range_predicate<Range> Predicate>
constexpr auto copy_if(const Range& input, const Predicate& predicate) noexcept;
template<stdr::input_range Range, meta::range_unary_op<Range> Operation>
constexpr auto transform(const Range& input, const Operation& op) noexcept;
template<stdr::input_range Range, meta::range_predicate<Range> Predicate, meta::range_unary_op<Range> Operation>
constexpr auto transform_if(const Range& input, const Predicate& predicate, const Operation& op) noexcept;
template<...>
constexpr auto transform_if(const Range& input, const Iterator& it, const Predicate& predicate, const Operation& op) noexcept -> void;
```

Eager shorthands that **return a `dynarray`**:

| Function | Equivalent |
| --- | --- |
| `copy_if(r, pred)` | `r \| filter(pred) \| to<dynarray>` |
| `transform(r, op)` | `r \| transform(op) \| to<dynarray>` |
| `transform_if(r, pred, op)` | `r \| filter(pred) \| transform(op) \| to<dynarray>` |
| `transform_if(r, out_it, pred, op)` | writes through an output iterator instead |

Concepts: `meta::range_predicate<P, Range>` (unary predicate on the range's value type) and
`meta::range_unary_op<F, Range>`, plus their `meta::plain::` variants that ignore cv-ref
qualifiers.

---

## `stormkit.core.parallelism`

### `stormkit.core.parallelism.locked`

```cpp
enum class lock_access_mode : u8 { READ_ONLY, READ_WRITE };

template<meta::is_decayed T, class Mutex = std::mutex>
class locked {
  public:
    using stored_type = T;
    using value_type  = /* T, or the pointee / wrapped type when T is a pointer, optional, ... */;
    using mutex_type  = Mutex;

    locked();
    locked(const T& value);                    locked(T&& value);
    template<typename... Ts> locked(std::in_place_t, Ts&&... args);
    locked(locked&&) noexcept;                 // move-only
    auto operator=(locked&&) noexcept -> locked&;

    template<template<class> typename Lock = std::unique_lock, typename... LockTs>
    auto read(LockTs&&... lock_args) const noexcept -> read_access<Lock>;
    template<std::invocable<const value_type&> Closure, template<class> typename Lock = std::unique_lock, typename... LockTs>
    auto read(Closure&& closure, LockTs&&... lock_args) const noexcept -> /* closure result */;

    template<template<class> typename Lock = std::unique_lock, typename... LockTs>
    auto write(LockTs&&... lock_args) noexcept -> write_access<Lock>;
    template<std::invocable<value_type&> Closure, template<class> typename Lock = std::unique_lock, typename... LockTs>
    auto write(Closure&& closure, LockTs&&... lock_args) noexcept -> /* closure result */;

    template<lock_access_mode MODE, template<class> typename Lock, typename... LockTs>
    auto access(LockTs&&... lock_args) noexcept -> accessor<Lock, MODE>;
    template<lock_access_mode MODE, Closure, template<class> typename Lock, typename... LockTs>
    auto access(Closure&& closure, LockTs&&... lock_args) noexcept -> /* closure result */;

    template<template<class> typename Lock = std::unique_lock, typename... LockTs>
    auto copy(LockTs&&... lock_args) const noexcept -> value_type;
    template<template<class> typename Lock = std::unique_lock, typename... LockTs>
    auto assign(const T& value, LockTs&&... lock_args) -> void;
    template<template<class> typename Lock = std::unique_lock, typename... LockTs>
    auto assign(T&& value, LockTs&&... lock_args) -> void;

    auto unsafe() noexcept -> value_type&;      // const-propagating, no locking
    auto mutex() const noexcept -> const mutex_type&;
};
template<typename T> locked(T) -> locked<T>;
```

A value fused with the mutex that protects it: the only way to reach the value is through an
access that holds the lock.

| Member | Description |
| --- | --- |
| `read()` / `write()` | Return an **accessor**: a guard holding the lock and exposing the value through `*` and `->`. `read` gives const access. The public `lock` data member of the accessor is the underlying lock (usable with a condition variable). |
| `read(closure)` / `write(closure)` | Lock, call the closure with a reference to the value, unlock, return its result. Prefer this form: the critical section is the closure body. |
| `Lock` template argument | The lock class template (`std::unique_lock` by default; pass `std::shared_lock` with a `std::shared_mutex` for real reader/writer locking). `lock_args` are forwarded to its constructor after the mutex (`std::try_to_lock`, `std::defer_lock`, …). On the closure overloads `Lock` comes *after* the deduced closure type, so in practice it is only selectable on the accessor overloads: `value.read<std::shared_lock>()`. |
| `copy()` | Locks and returns a copy. |
| `assign(v)` | Locks and assigns. |
| `unsafe()` | Bypasses the lock. For single-threaded phases (initialisation, tests) only. |

When `T` is a pointer or a wrapper (`std::optional`, smart pointers…), accessors look *through* it:
`value_type` is the pointee.

```cpp
auto counter = stormkit::locked { 0 };

counter.write([](auto& value) noexcept { value += 1; });   // closure form

{
    auto value = counter.write();                          // accessor form
    *value += 1;
}                                                          // unlocked here

auto shared = stormkit::locked<Config, std::shared_mutex> {};
{
    const auto config = shared.read<std::shared_lock>();   // shared (reader) lock
    use(config->name);
}
```

### `stormkit.core.parallelism.threadpool`

```cpp
inline constexpr struct no_future_type {} no_future;

class thread_pool {
  public:
    template<typename T> using closure_type = std23::move_only_function<T()>;

    explicit thread_pool(u32 worker_count = std::thread::hardware_concurrency() / 2);
    thread_pool(thread_pool&&) noexcept;                    // move-only
    ~thread_pool();                                         // wait_idle() then join_all()

    auto worker_count() const noexcept -> u32;
    template<typename T> auto post_task(closure_type<T>&& task) noexcept -> std::future<T>;
    template<typename T> auto post_task(closure_type<T>&& task, no_future_type) noexcept -> void;
    auto join_all() noexcept -> void;
    auto wait_idle(bool cancel_tasks = false) noexcept -> void;
    auto set_name(string_view name) noexcept -> void;
};

template<Range, F> auto parallel_for(thread_pool& pool, Range&& range, F&& f) noexcept -> void;
template<Range, F> auto parallel_for_async(thread_pool& pool, Range& range, F&& f) noexcept -> dynarray<std::future<void>>;
```

| Member | Description |
| --- | --- |
| `post_task<T>(task)` | Queues the task and returns a `std::future<T>`. The return type must be given explicitly: `pool.post_task<int>([] { return 42; })`. |
| `post_task<T>(task, no_future)` | Fire-and-forget; avoids the `packaged_task` allocation. |
| `wait_idle(cancel)` | Blocks until no task is running; with `cancel_tasks = true` the pending queue is dropped first. |
| `join_all()` | Stops and joins the workers. |
| `set_name(name)` | Names the worker threads `name:0`, `name:1`, … for debuggers. |
| `parallel_for(pool, range, f)` | Splits `range` into chunks of `size / worker_count()` elements, calls `f(element)` for each element and waits for completion. The range needs a size and random-access iterators and must hold at least `worker_count()` elements. **Known issue:** when the size is not a multiple of the chunk size, the trailing `size % chunk_size` elements are not visited; make the size a multiple of the worker count, or post the tasks yourself. |
| `parallel_for_async` | Same without waiting; returns the futures. `range` and `f` must outlive them. |

### `stormkit.core.parallelism.threadutils`

```cpp
auto set_current_thread_name(string_view name) noexcept -> void;
auto set_thread_name(std::thread& thread,  string_view name) noexcept -> void;
auto set_thread_name(std::jthread& thread, string_view name) noexcept -> void;
auto get_current_thread_name() noexcept -> string;
auto get_thread_name(const std::thread& thread)  noexcept -> string;
auto get_thread_name(const std::jthread& thread) noexcept -> string;

template<Range> auto wait_all(Range&& futures) noexcept;   // range of std::future
```

Thread names are set through the native API of each platform (`SetThreadDescription`,
`pthread_setname_np`, `NSThread`) and appear in debuggers and profilers. Linux truncates names to
15 characters. `wait_all` calls `.wait()` on every future.

---

## `stormkit.core.stacktrace`

```cpp
auto print_stacktrace(u32 ignore_count = 0) noexcept -> void;
```

Prints the current call stack to `stderr`, skipping the `ignore_count` innermost frames.

## `stormkit.core.signal_handler`

```cpp
auto setup_signal_handler() noexcept -> void;
```

Installs a `std::terminate` handler and a `SIGSEGV` handler that both print a stack trace before
the process dies. Call it first thing in `main`.

# `stormkit.math` reference

```cpp
import stormkit.math;      // or: import stormkit;
```

| | |
| --- | --- |
| Library | `stormkit-math` |
| xmake option | `math` (default: on) |
| Depends on | `stormkit.core` |
| Namespace | `stormkit::math` |

`import stormkit.math;` re-exports `math.arithmetic`, `math.combinatoric`, `math.extent`,
`math.geometry` and `math.linear` (`linear.tensor`, `linear.vector`, `linear.matrix`,
`linear.angle`). The sub-modules `math.trigonometry`, `math.hypercomplex` and
`math.linear.quaternion` exist but are empty placeholders.

Everything is `constexpr`. Synopses omit `noexcept` and `[[nodiscard]]`; `cmeta` stands for
`stormkit::core::meta`.

---

## `stormkit.math.arithmetic`

```cpp
template<arithmetic T> constexpr auto floor(T v) -> T;
template<arithmetic T> constexpr auto log2(T v) -> T;
template<arithmetic T> constexpr auto min(T a, T b) -> T;
template<arithmetic T> constexpr auto max(T a, T b) -> T;
template<arithmetic T> constexpr auto abs(T n) -> T;
template<arithmetic T> constexpr auto is_positive(T value) -> bool;
template<arithmetic T> constexpr auto is_negative(T value) -> bool;

template<arithmetic T, arithmetic U> constexpr auto scale(U x, U rmin, U rmax, T tmin, T tmax) -> T;
template<integral T>                 constexpr auto scale(T x, T rmin, T rmax, T tmin, T tmax) -> T;
template<floating_point T>           constexpr auto scale(T x, T rmin, T rmax, T tmin, T tmax) -> T;
```

| Function | Description |
| --- | --- |
| `floor(v)` | Largest integral value not greater than `v`, in type `T`. |
| `log2(v)` | Base-2 logarithm. An approximation is used during constant evaluation, `std::log2` at run time. |
| `min`, `max` | Of two values of the same type (no reference-to-temporary pitfalls: returned by value). |
| `abs(n)` | Absolute value; identity for unsigned types. |
| `is_positive(v)` | `v >= 0`; always true for unsigned types. |
| `is_negative(v)` | `v < 0`; always false for unsigned types. |
| `scale(x, rmin, rmax, tmin, tmax)` | Linearly remaps `x` from `[rmin, rmax]` to `[tmin, tmax]`. The mixed-type overload converts `x` and the source range to `T` first. The floating-point overload returns `rmin` / `rmax` when `x` is outside the source range. |

## `stormkit.math.combinatoric`

```cpp
template<arithmetic T> constexpr auto factoriel(T n) -> T;
```

`n!`. Table-driven for small integers; a contract check guards against overflow of narrow types.

---

## `stormkit.math.extent`

```cpp
template<arithmetic T, usize N> struct extent;          // N is 2 or 3

template<arithmetic T>
struct extent<T, 2> {
    using value_type = T;   using size_type = usize;
    using ordering_type = /* strong_ordering for integers, partial_ordering for floats */;
    static constexpr auto RANK = size_type { 2 };
    value_type width  = 0;
    value_type height = 0;
    constexpr auto operator[](size_type index) -> value_type&;     // const-propagating
};

template<arithmetic T>
struct extent<T, 3> {
    static constexpr auto RANK = size_type { 3 };
    value_type width  = 0;
    value_type height = 0;
    value_type depth  = 1;
    constexpr auto operator[](size_type index) -> value_type&;
};

extent(T, T)    -> extent<T, 2>;
extent(T, T, T) -> extent<T, 3>;
```

A size in two or three dimensions. Aggregates: `math::uextent2 { 800u, 600u }`,
`math::extent { .width = 800u, .height = 600u }`.

| Alias | Type | Alias | Type |
| --- | --- | --- | --- |
| `extent2<T>` | `extent<T, 2>` | `extent3<T>` | `extent<T, 3>` |
| `fextent2` | `extent2<f32>` | `fextent3` | `extent3<f32>` |
| `uextent2` | `extent2<u32>` | `uextent3` | `extent3<u32>` |
| `iextent2` | `extent2<i32>` | `iextent3` | `extent3<i32>` |

| Operation | Description |
| --- | --- |
| `e[i]` | `0` → width, `1` → height, `2` → depth. |
| `a == b`, `a <=> b` | Lexicographic, component by component. |
| `e * k`, `e / k`, `e *= k`, `e /= k` | Scales every component by a scalar. |
| `as<To>(e)` | Converts between any two extents: components go through the checked arithmetic [`as`](core-typesafe.md#as); going from 3 to 2 dimensions drops `depth`, from 2 to 3 keeps the default `depth = 1`. |
| `std::format("{}", e)` | Extents are formattable. |

Concepts in `stormkit::math::meta`: `is_extent<T>`, `is_extent2<T>`, `is_extent3<T>`.

```cpp
const auto window_size = math::uextent2 { 1280u, 720u };
const auto viewport    = as<math::fextent2>(window_size);
const auto volume      = as<math::uextent3>(window_size);      // { 1280, 720, 1 }
```

---

## `stormkit.math.geometry`

```cpp
template<arithmetic T>
struct rect {
    using value_type = T;
    value_type           x = 0, y = 0;
    positive<value_type> width = 0, height = 0;

    constexpr auto position() const -> vec2<value_type>;
    constexpr auto extent() const   -> extent2<value_type>;
    template<arithmetic U> constexpr auto to() const -> rect<U>;
};
rect(T, T, T, T) -> rect<T>;

template<arithmetic T>
struct bounding_rect {
    using value_type = T;
    value_type left = 0, top = 0, right = 0, bottom = 0;

    constexpr auto topleft() const     -> vec2<value_type>;
    constexpr auto bottomright() const -> vec2<value_type>;
    template<arithmetic U> constexpr auto to() const -> rect<U>;
};

template<typename T> constexpr auto to_bounding_rect(const rect<T>& value) -> bounding_rect<T>;
template<typename T> constexpr auto to_rect(const bounding_rect<T>& value) -> rect<T>;

template<typename T> constexpr auto AABB(const rect<T>& a, const rect<T>& b) -> bool;
template<typename T> constexpr auto AABB(const vec2<T>& pos, const rect<T>& rect) -> bool;
template<typename T> constexpr auto AABB(const vec2<T>& pos, const bounding_rect<T>& rect) -> bool;

template<arithmetic T> auto to_string(const rect<T>& value) -> string;
template<arithmetic T> auto to_string(const bounding_rect<T>& value) -> string;
template<hash_type Ret = hash32, arithmetic T> constexpr auto hasher(const rect<T>& value) -> Ret;
template<hash_type Ret = hash32, arithmetic T> constexpr auto hasher(const bounding_rect<T>& value) -> Ret;
template<arithmetic T, typename FormatContext> auto format_as(const rect<T>& value, FormatContext& ctx);
template<arithmetic T, typename FormatContext> auto format_as(const bounding_rect<T>& value, FormatContext& ctx);
```

| Alias | Type | Alias | Type |
| --- | --- | --- | --- |
| `irect` | `rect<i32>` | `ibounding_rect` | `bounding_rect<i32>` |
| `urect` | `rect<u32>` | `ubounding_rect` | `bounding_rect<u32>` |
| `frect` | `rect<f32>` | `fbounding_rect` | `bounding_rect<f32>` |

| Name | Description |
| --- | --- |
| `rect` | Position + size. `width` and `height` are [`positive<T>`](core-typesafe.md#stormkitcoretypesafechecked_value): a negative size is a contract violation. |
| `bounding_rect` | The same area as four edges. |
| `rect::to<U>()` | Component-wise checked conversion. |
| `to_bounding_rect`, `to_rect` | Convert between the two representations. |
| `AABB(a, b)` | Whether two rectangles overlap (strict: touching edges do not count). |
| `AABB(point, rect)` | Whether a point lies inside a rectangle (inclusive). |

`to_string`, `hasher` and `format_as` are legacy free functions; they are not connected to
`std::format` / `hash_of` in the current sources, so do not rely on `std::format("{}", rect)`.

---

## `stormkit.math.linear`

### `stormkit.math.linear.angle`

```cpp
template<floating_point T> using radian = strong_type<T, struct radian_tag, "radian", capabilities::arithmetic>;
template<floating_point T> using euler  = strong_type<T, struct euler_tag,  "euler",  capabilities::arithmetic>;

template<floating_point T> constexpr auto radians(T degrees) -> radian<T>;
```

Angles are [strong types](core-typesafe.md#stormkitcoretypesafestrong_type): a function taking a
`radian<f32>` cannot be handed degrees by mistake.

| Name | Description |
| --- | --- |
| `radian<T>` | An angle in radians. Supports `+ - * /` with itself and with `T`; unwrap with `.value()`. |
| `euler<T>` | An angle in degrees. |
| `radians(degrees)` | Converts degrees to a `radian<T>`. |

### `stormkit.math.linear.tensor`

The storage and element-wise arithmetic shared by vectors and matrices.

```cpp
template<arithmetic T, usize... EXTENTS>
using tensor_view = mdarray_view<T, std::extents<usize, EXTENTS...>>;      // std::mdspan

template<arithmetic T, usize... EXTENTS>
struct tensor_base {
    using value_type = T;   using size_type = usize;   using rank_type = usize;
    using storage_type = array<T, (EXTENTS * ...)>;
    static constexpr array<size_type, sizeof...(EXTENTS)> EXTENTS;
    storage_type storage;

    constexpr auto operator[](size_type i) -> T&;                  // linear index, const-propagating
    constexpr auto operator[](auto... indices) -> T&;              // one index per dimension (rank 2)
    constexpr auto begin(); end(); cbegin() const; cend() const;
    constexpr auto data() -> T*;
    constexpr auto size() const -> size_type;
    static consteval auto max_size() -> size_type;
    static consteval auto order() -> size_type;                    // number of dimensions
    constexpr auto extent(rank_type rank) const -> size_type;
    static constexpr auto static_extent(rank_type rank) -> size_type;
};

template<arithmetic T, typename Interface, usize... EXTENTS>
struct tensor : tensor_base<T, EXTENTS...>, Interface {
    constexpr operator tensor_view<T, EXTENTS...>();               // const-propagating
    constexpr operator array_view<T, (EXTENTS * ...)>();           // const-propagating
};

inline constexpr struct as_linear_type {} as_linear;
```

- A `tensor` is an **aggregate** over a flat `std::array`, in **row-major** order. Initialise it
  with a flat list of values; missing trailing values are zero.
- `Interface` is a mix-in that adds the named accessors (`x()`, `row()`, …) — this is what
  distinguishes a `vec` from a `mat`.
- `alignas` matches the underlying array; a tensor is trivially copyable and can be uploaded to
  the GPU as-is.
- Tensors opt out of range formatting and have their own formatter.

**Views**

| Expression | Result |
| --- | --- |
| `view_of(t)` | `tensor_view<const T, EXTENTS...>` — a multi-dimensional `std::mdspan` |
| `mutable_view_of(t)` | `tensor_view<T, EXTENTS...>` |
| `view_of(as_linear, t)` | `array_view<const T, N>` — the flat storage |
| `mutable_view_of(as_linear, t)` | `array_view<T, N>` |

The same four forms accept a `tensor_view` instead of a tensor.

**Element-wise arithmetic**

Every operation comes in two forms: one returning a new tensor, one writing into an output view
(which must not alias the inputs — checked by contract).

```cpp
template<is_tensor T> constexpr auto add(const T& a, const T& b) -> T;
template<is_tensor T> constexpr auto sub(const T& a, const T& b) -> T;
template<is_tensor T> constexpr auto mul(const T& a, value_type<T> scalar) -> T;
template<is_tensor T> constexpr auto div(const T& a, value_type<T> scalar) -> T;     // scalar != 0, checked

constexpr auto add(tensor_view<const T, E...> a, tensor_view<const T, E...> b, tensor_view<T, E...> out) -> void;
constexpr auto sub(tensor_view<const T, E...> a, tensor_view<const T, E...> b, tensor_view<T, E...> out) -> void;
constexpr auto mul(tensor_view<const T, E...> a, T scalar, tensor_view<T, E...> out) -> void;
constexpr auto div(tensor_view<const T, E...> a, T scalar, tensor_view<T, E...> out) -> void;
```

There are **no overloaded arithmetic operators** on tensors: write `add(a, b)`, not `a + b`.
The functions are found by ADL, so no `math::` qualification is needed.

Concepts in `stormkit::math::meta`: `is_tensor<T>`, `is_tensor_view<T>`, `is_tensor_or_view<T>`.

### `stormkit.math.linear.vector`

```cpp
template<arithmetic T, usize N> using vec      = tensor<T, vec_interface<T, N>, N>;
template<typename T, usize N>   using vec_view = tensor_view<T, N>;
```

| Alias | Type | `f32` | `i32` | `u32` |
| --- | --- | --- | --- | --- |
| `vec1<T>` | `vec<T, 1>` | `fvec1` | `ivec1` | `uvec1` |
| `vec2<T>` | `vec<T, 2>` | `fvec2` | `ivec2` | `uvec2` |
| `vec3<T>` | `vec<T, 3>` | `fvec3` | `ivec3` | `uvec3` |
| `vec4<T>` | `vec<T, 4>` | `fvec4` | `ivec4` | `uvec4` |

**Accessors** (member functions, from `vec_interface`)

| Size | Component accessors | Swizzles |
| --- | --- | --- |
| 1 | `x()` | — |
| 2 | `x()`, `y()` | `xx()`, `xy()`, `yx()`, `yy()` |
| 3 | `x()`, `y()`, `z()` | all 27 three-letter combinations: `xyz()`, `zyx()`, `xxz()`, … |
| 4 | `x()`, `y()`, `z()`, `w()` | all 256 four-letter combinations: `xyzw()`, `wzyx()`, … |

Component accessors return a reference (const-propagating) and can be assigned through:
`v.x() = 1.f`. Swizzles return a new vector **of the same size**. Indexing with `v[i]` also works.

**Functions**

```cpp
template<arithmetic T, usize N> constexpr auto normalize(const vec<T, N>& v) -> vec<T, N>;
template<arithmetic T, usize N> constexpr auto normalize(vec_view<const T, N> a, vec_view<T, N> out) -> void;
template<is_vec_or_view T>      constexpr auto dot(const T& a, const T& b) -> value_type<T>;
template<arithmetic T>          constexpr auto cross(const vec<T, 3>& a, const vec<T, 3>& b) -> vec<T, 3>;
template<arithmetic T>          constexpr auto cross(vec_view<const T, 3> a, vec_view<const T, 3> b, vec_view<T, 3> out) -> void;
template<arithmetic T>          constexpr auto cross(const vec<T, 4>& a, const vec<T, 4>& b) -> vec<T, 4>;
template<arithmetic T>          constexpr auto cross(vec_view<const T, 4> a, vec_view<const T, 4> b, vec_view<T, 4> out) -> void;
```

| Function | Description |
| --- | --- |
| `normalize(v)` | `v` scaled to unit length. |
| `dot(a, b)` | Scalar product. |
| `cross(a, b)` | Vector product. The 4-component version operates on `xyz`. |
| `add`, `sub`, `mul`, `div` | Inherited from [tensor](#stormkitmathlineartensor). |

Vectors are formattable. Concepts: `meta::is_vec`, `is_vec_view`, `is_vec_2`, `is_vec_3`,
`is_vec_4`, `is_vec_or_view`.

```cpp
auto a = math::fvec3 { 1.f, 0.f, 0.f };
auto b = math::fvec3 { 0.f, 1.f, 0.f };

const auto n   = cross(a, b);                 // { 0, 0, 1 }
const auto sum = add(a, mul(b, 2.f));         // { 1, 2, 0 }
a.x() = 3.f;
std::println("{} · {} = {}", a, b, dot(a, b));
```

### `stormkit.math.linear.matrix`

```cpp
template<arithmetic T, usize M, usize N> using mat             = tensor<T, mat_interface<T, M, N>, M, N>;   // M rows, N columns
template<typename T, usize M, usize N>   using mat_view        = tensor_view<T, M, N>;
template<typename T, usize N>            using square_mat_view = mat_view<T, N, N>;
```

| Template alias | `f32` | `i32` | `u32` |
| --- | --- | --- | --- |
| `mat2x2<T>` | `fmat2` | `imat2` | `umat2` |
| `mat3x3<T>` | `fmat3` | `imat3` | `umat3` |
| `mat4x4<T>` | `fmat4` | `imat4` | `umat4` |
| `mat2x3<T>` | `fmat2x3` | `imat2x3` | `umat2x3` |
| `mat3x2<T>` | `fmat3x2` | `imat3x2` | `umat3x2` |
| `mat4x3<T>` | `fmat4x3` | `imat4x3` | `umat4x3` |
| `mat3x4<T>` | `fmat3x4` | `imat3x4` | `umat3x4` |
| `mat4x2<T>` | `fmat4x2` | `imat4x2` | `umat4x2` |
| `mat2x4<T>` | `fmat2x4` | `imat2x4` | `umat2x4` |

**Members** (from `mat_interface`, in addition to the tensor ones)

| Member | Description |
| --- | --- |
| `static identity()` | The identity matrix (square matrices only): `math::fmat4::identity()`. |
| `row(i)` | An `array_view` over row `i`. |
| `m[row, column]` | Element access with the C++23 multi-argument subscript. |
| `m[i]` | Linear (row-major) element access. |

**General functions**

```cpp
constexpr auto determinant(const SquareMatOrView& m) -> value_type;
constexpr auto transpose(const mat<T, M, N>& m) -> mat<T, N, M>;
constexpr auto cofactor(const mat<T, M, M>& m) -> mat<T, M, M>;
constexpr auto inverse(const mat<T, M, M>& m) -> mat<T, M, M>;
constexpr auto is_inversible(const MatOrView& m) -> bool;
constexpr auto is_orthogonal(const MatOrView& m) -> bool;
constexpr auto mul(const mat<T, M, N>& a, const mat<T, N, K>& b) -> mat<T, M, K>;
constexpr auto div(const mat<T, M, N>& a, const mat<T, N, N>& b) -> mat<T, N, N>;
```

| Function | Description |
| --- | --- |
| `determinant(m)` | Determinant of a square matrix. |
| `transpose(m)` | Rows and columns swapped. |
| `cofactor(m)` | Cofactor matrix. |
| `inverse(m)` | Inverse of a square matrix. Check `is_inversible` first. |
| `is_inversible(m)` | Square and non-zero determinant. |
| `is_orthogonal(m)` | `m · mᵀ` is the identity. |
| `mul(a, b)` | Matrix product (dimensions checked at compile time). |
| `div(a, b)` | `a · b⁻¹`. |
| `add`, `sub`, `mul(m, scalar)`, `div(m, scalar)` | Inherited from [tensor](#stormkitmathlineartensor). |

**3D transforms** (4×4, signed element types only)

```cpp
constexpr auto translate(const mat<T, 4, 4>& m, const vec<T, 3>& translation) -> mat<T, 4, 4>;
constexpr auto scale(const mat<T, 4, 4>& m, const vec<T, 3>& factors) -> mat<T, 4, 4>;
constexpr auto rotate(const mat<T, 4, 4>& m, radian<T> angle, const vec<T, 3>& axis) -> mat<T, 4, 4>;

constexpr auto orthographique(T left, T right, T bottom, T top) -> mat<T, 4, 4>;                 // near = 0.1, far = 100
constexpr auto orthographique(T left, T right, T bottom, T top, T near, T far) -> mat<T, 4, 4>;
constexpr auto perspective(radian<T> fov_y, T aspect, T near, T far) -> mat<T, 4, 4>;
constexpr auto look_at(const vec<T, 3>& eye, const vec<T, 3>& center, const vec<T, 3>& up) -> mat<T, 4, 4>;
```

| Function | Description |
| --- | --- |
| `translate(m, t)` | `m` combined with a translation by `t`. |
| `scale(m, s)` | `m` combined with a per-axis scale. |
| `rotate(m, angle, axis)` | `m` combined with a rotation of `angle` around `axis` (normalised internally). |
| `orthographique(...)` | Orthographic projection (French spelling in the API). |
| `perspective(fov_y, aspect, near, far)` | Perspective projection with a vertical field of view. Depth maps to `[0, 1]` and **Y is flipped**, matching Vulkan clip space. `aspect != 0` and `near != far` are checked. |
| `look_at(eye, center, up)` | View matrix looking from `eye` towards `center`. |

Every function above also has an overload that takes views and writes into a trailing `out` view
instead of returning (`transpose(view_of(m), mutable_view_of(out))`, …), for use in hot loops and
on memory you do not own, such as a mapped uniform buffer.

Matrices are formattable (one row per line). Concepts in `stormkit::math::meta`: `is_mat`,
`is_mat_view`, `is_square_mat`, `is_square_mat_view`, `is_mat_2`, `is_mat_3`, `is_mat_4`,
`is_mat_or_view`, `is_square_mat_or_view` and `plain::` variants of the last two.

```cpp
struct camera { math::fmat4 proj, view, model; };

auto cam = camera {
    .proj  = math::perspective(math::radians(45.f), 16.f / 9.f, 0.1f, 100.f),
    .view  = math::look_at(math::fvec3 { 0.f, 3.f, 5.f }, { 0.f, 0.f, 0.f }, { 0.f, 1.f, 0.f }),
    .model = math::fmat4::identity(),
};
cam.model = math::rotate(math::fmat4::identity(), math::radians(90.f), math::fvec3 { 0.f, 1.f, 0.f });
```

> **Storage order.** Matrices are stored row-major. Shader languages default to column-major, so
> either `transpose` before uploading (as the `textured_cube` example does) or declare the matrix
> `row_major` in the shader.

---

## Status

The module is under active development. At the time of writing:

- `math.trigonometry`, `math.hypercomplex` and `math.linear.quaternion` are empty;
- the value-returning `rotate` is declared (and exported) with a raw `T angle` but defined with
  `radian<T>`; the table above documents the definition. As a result the exported declaration has
  no definition;
- the bodies of `rotate` and `perspective` read their angle with `angle.get()`, which
  [`strong_type`](core-typesafe.md#stormkitcoretypesafestrong_type) does not provide (the accessor
  is `value()`), so both fail to compile when instantiated;
- `orthographique` never writes element `[3, 3]`, which therefore stays `0` instead of `1`;
- the transform helpers do not share one layout convention: `perspective` places its terms where a
  column-major shader reads them when the matrix is uploaded as is, whereas the `textured_cube`
  example transposes the result of `rotate` before uploading. Check a helper's output against
  your shader's convention before relying on it;
- `geometry`'s `to_string`, `hasher` and `format_as` predate the `tag_invoke` hooks and are not
  wired to `std::format` / `hash_of`;
- the multi-index `operator[]` is implemented for rank 2 only.

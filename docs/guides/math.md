# Guide: `stormkit.math`

Fixed-size linear algebra and a few geometric types, all `constexpr`.

```cpp
import std;
import stormkit;

using namespace stormkit;
```

The design in one paragraph: vectors and matrices are thin aggregates over a flat `std::array`.
Operations are **free functions** (`add(a, b)`, `dot(a, b)`, `mul(m, n)`), not operators, and each
exists in two forms — one that returns a result, one that writes into an output view.

## Vectors

```cpp
auto position = math::fvec3 { 1.f, 2.f, 3.f };
auto offset   = math::fvec3 { 0.f, 1.f, 0.f };

position.x() += 0.5f;                  // named accessors are functions
const auto y = position[1];            // indexing works too
```

The aliases combine a prefix and a size: `f` (`f32`), `i` (`i32`), `u` (`u32`) × 1–4 →
`fvec2`, `ivec3`, `uvec4`… For another element type, write `math::vec3<f64>`.

Vectors are aggregates: brace-initialise them with their components. Omitted trailing components
are zero.

### Arithmetic

```cpp
const auto moved  = add(position, offset);            // component-wise
const auto delta  = sub(position, offset);
const auto scaled = mul(position, 2.f);               // by a scalar
const auto half   = div(position, 2.f);

const auto length_squared = dot(position, position);
const auto unit           = normalize(position);
const auto normal         = cross(math::fvec3 { 1.f, 0.f, 0.f }, math::fvec3 { 0.f, 1.f, 0.f });
```

The functions are found by argument-dependent lookup, so they need no `math::` prefix.

Why functions rather than `a + b`? Because the same function has an allocation-free twin that
writes where you tell it, which matters in inner loops and when the destination is memory you do
not own (see [views](#views-working-in-place)).

### Swizzles

```cpp
const auto flipped = position.zyx();       // fvec3 { 3, 2, 1 }

const auto uv = math::fvec2 { 4.f, 5.f };
const auto vv = uv.yy();                   // fvec2 { 5, 5 }
```

Every combination of a vector's own components exists, and returns a vector of the *same* size.
Accessors and swizzles are called on named objects (lvalues), not on temporaries.

## Matrices

`mat<T, M, N>` has `M` rows and `N` columns, stored **row-major**.

```cpp
auto m = math::fmat3 {
    1.f, 0.f, 0.f,
    0.f, 1.f, 0.f,
    0.f, 0.f, 1.f,
};

m[0, 2] = 5.f;                         // row 0, column 2 (C++23 multi-argument subscript)
const auto first_row = m.row(0);       // array_view<f32, 3>
const auto identity  = math::fmat4::identity();
```

### Operations

```cpp
const auto product     = mul(a, b);            // matrix product; dimensions checked at compile time
const auto transposed  = transpose(a);
const auto det         = determinant(a);

if (is_inversible(a)) {
    const auto inv = inverse(a);
}
```

### Transforms

```cpp
auto model = math::fmat4::identity();
model = math::translate(model, math::fvec3 { 0.f, 1.f, 0.f });
model = math::rotate(model, math::radians(45.f), math::fvec3 { 0.f, 1.f, 0.f });
model = math::scale(model, math::fvec3 { 2.f, 2.f, 2.f });

const auto view = math::look_at(math::fvec3 { 0.f, 3.f, 5.f },      // eye
                                math::fvec3 { 0.f, 0.f, 0.f },      // target
                                math::fvec3 { 0.f, 1.f, 0.f });     // up
const auto proj = math::perspective(math::radians(60.f), 16.f / 9.f, 0.1f, 100.f);
const auto ui   = math::orthographique(0.f, 1280.f, 720.f, 0.f);
```

Qualify these with `math::`: `scale` in particular also exists as a scalar function.

`perspective` produces Vulkan-style clip space (depth in `[0, 1]`, Y pointing down).

> **Heads-up.** In the current sources `rotate` and `perspective` do not compile when
> instantiated (they read their angle with a member the angle type no longer has), and the
> value-returning `rotate` is declared with a different signature than its definition. The code
> above shows the intended usage; `translate`, `scale`, `look_at` and `orthographique` are not
> affected. Details in the [reference](../reference/math.md#status).

### Angles are typed

`perspective` and `rotate` take a `math::radian<T>`, not a bare number, so degrees cannot slip in
unnoticed:

```cpp
const auto fov  = math::radians(60.f);                 // degrees -> radian<f32>
const auto half = fov / 2.f;                           // still a radian
const auto raw  = half.value();                        // the underlying f32
// math::perspective(60.f, …);                         // does not compile
```

### Sending matrices to a shader

Matrices are row-major; GLSL, HLSL and NZSL default to column-major. Either transpose on the way
out, or mark the matrices `row_major` in the shader:

```cpp
struct camera_data { math::fmat4 proj, view, model; };

camera.model = math::transpose(math::rotate(math::fmat4::identity(), angle, axis));
buffer.upload(camera);                                 // a tensor is trivially copyable
```

## Views: working in place

Every operation has a second overload that takes views and an output view:

```cpp
auto result = math::fvec3 {};
add(view_of(a), view_of(b), mutable_view_of(result));

auto out = math::fmat4 {};
math::translate(view_of(model), view_of(offset), mutable_view_of(out));
```

- `view_of(v)` is a read-only multi-dimensional view (`std::mdspan`) of a vector or matrix;
  `mutable_view_of(v)` a writable one.
- `view_of(math::as_linear, v)` is the flat `array_view` of the storage — what you hand to an API
  that wants `N` floats.

The output must not alias an input; this is contract-checked.

Views are also how you run the math on memory that is not a `vec` or a `mat` — a mapped GPU
buffer, a row of a larger array:

```cpp
auto* floats = buffer.data_as<f32>();                                // 16 floats somewhere
auto  target = math::mat_view<f32, 4, 4> { floats };
math::perspective(math::radians(70.f), aspect, 0.1f, 500.f, target);  // computed straight into it
```

## Extents

An `extent` is a size: `width`, `height`, and for the 3D version `depth` (default `1`).

```cpp
const auto window  = math::uextent2 { 1280u, 720u };
const auto half    = window / 2u;
const auto aspect  = as<f32>(window.width) / as<f32>(window.height);

const auto as_float = as<math::fextent2>(window);          // checked component conversion
const auto volume   = as<math::uextent3>(window);          // { 1280, 720, 1 }

std::println("{}", window);
```

Extents compare (`==`, `<=>`), scale by a scalar, index (`e[0]` is the width) and format. They are
the type every size parameter in `image`, `wsi` and `gpu` uses.

## Rectangles

```cpp
const auto button = math::irect { .x = 10, .y = 10, .width = 120, .height = 32 };
const auto cursor = math::ivec2 { 50, 20 };

if (math::AABB(cursor, button)) { /* the cursor is over the button */ }
if (math::AABB(button, other))  { /* the rectangles overlap */ }

const auto bounds = math::to_bounding_rect(button);        // { left, top, right, bottom }
```

`rect` stores a position and a size — and the size members are `positive<T>`, so a negative width
is caught at construction. `bounding_rect` stores the four edges.

## Scalar helpers

```cpp
const auto t      = math::scale(value, 0.f, 255.f, 0.f, 1.f);     // remap a range
const auto levels = as<u32>(math::floor(math::log2(as<f32>(size)))) + 1u;
const auto clamped = math::max(0, math::min(x, limit));
```

`math::is(a, b)` does not exist — floating-point comparison is the core
[`is(a, b)`](core.md#is--asking-first).

## Everything is `constexpr`

```cpp
constexpr auto OFFSET = math::translate(math::fmat4::identity(), math::fvec3 { 0.f, 0.f, 1.f });
static_assert(math::determinant(math::imat2 { 1, 2, 3, 4 }) == -2);
```

Tables of transforms, test expectations and lookup data can all be computed at compile time.

## What is not there yet

Quaternions, the trigonometry module and the hypercomplex module are empty placeholders, and there
are no arithmetic operators on tensors. See the
[status section of the reference](../reference/math.md#status).

Reference: [`stormkit.math`](../reference/math.md).

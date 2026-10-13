# Guide: `stormkit.image`

Load an image file, look at its pixels, transform it, save it. `stormkit.image` works entirely on
the CPU; it is what you use before handing pixels to the GPU, or when there is no GPU involved at
all.

```cpp
import std;
import stormkit;

using namespace stormkit;
```

The class is `stormkit::image::image` — namespace and class share a name. With
`using namespace stormkit;` in effect you write `image::image`.

## Loading

```cpp
auto picture = image::image {};

if (const auto result = picture.load_from_file("assets/hero.png"); not result) {
    std::println(get_stderr(), "cannot load hero.png: {}", result.error());
    return -1;
}

std::println("{} — {} channel(s), {} byte(s) each", picture.extent(), picture.channel_count(), picture.bytes_per_channel());
```

The codec is deduced from the file extension:

| Extension | Format |
| --- | --- |
| `.png` | PNG |
| `.jpg`, `.jpeg` | JPEG |
| `.tga`, `.targa` | Targa |
| `.ppm` | PPM |
| `.hdr` | Radiance HDR |
| `.ktx` | Khronos texture |
| `.qoi` | Quite OK Image |

To override the deduction, pass the codec: `picture.load_from_file(path, image::image_codec::PNG)`.

Images that are already in memory — downloaded, embedded in the executable, extracted from an
archive — load the same way, the codec being recognised from the first bytes:

```cpp
auto bytes   = TryX(io::readfile("assets/hero.png"));
auto picture = image::image {};
DiscardTryX(picture.load_from_memory(bytes));
```

There are also constructors that load directly (`image::image { "hero.png" }`). They are
convenient in tests and tools, but a constructor has no way to tell you it failed: prefer the
`load_from_…` functions for anything that comes from outside.

### What went wrong?

The error is a `system_code` whose domain is the image library's own status enumeration:

```cpp
using image::image_status_code;

if (result.error() == image_status_code::FILE_NOT_FOUND) { /* … */ }
if (result.error() == image_status_code::FAILED_TO_PARSE) { /* corrupt or not the format we thought */ }
```

## What an image contains

```cpp
picture.extent();              // math::uextent3 { width, height, depth }
picture.format();              // image::image_format::RGBA8_UNORM, …
picture.channel_count();       // 1 to 4
picture.bytes_per_channel();   // 1, 2 or 4
picture.size();                // total bytes
picture.data();                // array_view<byte> over all of them
```

The format name reads left to right: channels, bits per channel, interpretation. `RGB8_UNORM` is
three 8-bit channels meaning 0–1; `RGBA32F` is four 32-bit floats; `SRGBA8` is 8-bit sRGB with
alpha.

For ordinary files that is the whole story. Texture containers such as KTX can also hold several
**layers** (array textures), **faces** (cube maps) and **mip levels**; the accessors take them as
optional trailing arguments:

```cpp
for (auto level : range(picture.mip_levels())) {
    const auto bytes = picture.data(0, 0, level);          // layer, face, level
    std::println("level {}: {} ({} bytes)", level, picture.extent(level), std::ranges::size(bytes));
}
```

## Reading and writing pixels

`pixel` returns the bytes of one pixel, by coordinates or by linear index:

```cpp
auto first = picture.pixel(0);                             // array_view<byte>, channel_count * bytes_per_channel long
auto here  = picture.pixel(math::uvec3 { 10u, 20u, 0u });
```

To work with typed colours, make sure the format is the one you expect, then view the buffer as
the matching [`color`](core.md#colours) type:

```cpp
auto rgba = picture.convert_to(image::image_format::RGBA8_UNORM);

const auto [width, height, _] = rgba.extent();
auto pixels = std::span { std::bit_cast<ucolor_rgba*>(std::ranges::data(rgba.data())), width * height };

for (auto& pixel : pixels) {
    const auto gray = as<u8>((as<u32>(pixel.r) + pixel.g + pixel.b) / 3u);
    pixel = { .r = gray, .g = gray, .b = gray, .a = pixel.a };
}
```

`ucolor_rgba` is four `u8` laid out as r, g, b, a — exactly an `RGBA8_UNORM` pixel — which is why
the reinterpretation is sound. Pick `ucolor_rgb` for `RGB8_UNORM`, `ucolor_bgra` for
`BGRA8_UNORM`, `fcolor_rgba` for `RGBA32F`.

## Creating an image from nothing

```cpp
auto canvas = image::image { { .width = 256u, .height = 256u }, image::image_format::RGBA8_UNORM };

auto pixels = std::span { std::bit_cast<ucolor_rgba*>(std::ranges::data(canvas.data())), 256uz * 256uz };
for (auto [y, x] : multi_range(256u, 256u))
    pixels[y * 256u + x] = { .r = as<u8>(x), .g = as<u8>(y), .b = 128, .a = 255 };
```

The buffer starts zero-filled. If you already own a buffer, adopt it without copying:

```cpp
auto adopted = image::image { image::image::image_data_t {
    .extent            = { .width = w, .height = h },
    .channel_count     = 4,
    .bytes_per_channel = 1,
    .format            = image::image_format::RGBA8_UNORM,
    .data              = std::move(my_bytes),
} };
```

## Transforming

Every transformation is `const` and returns a **new** image; chain them freely:

```cpp
const auto thumbnail = picture
                         .convert_to(image::image_format::RGB8_UNORM)
                         .scale({ .width = 128u, .height = 128u })
                         .flip_y();
```

| Call | Effect |
| --- | --- |
| `convert_to(format)` | changes the channel count and/or component type |
| `scale(extent)` | resizes |
| `flip_x()`, `flip_y()`, `flip_z()` | mirrors along one axis |
| `rotate_90()`, `rotate_180()`, `rotate_270()` | rotates in the image plane |

`flip_y()` is the usual fix when an image comes out upside-down because two APIs disagree about
where row zero is.

## Saving

```cpp
DiscardTryX(thumbnail.save_to_file("out/hero-thumb.jpg", image::image_codec::JPEG));

auto encoded = TryX(thumbnail.save_to_memory(image::image_codec::PNG));     // dynarray<byte>
```

The codec must be given explicitly when saving. Not every codec stores every format — JPEG has no
alpha channel, for instance — so convert first, and check the result: an unsupported combination
is reported as `INVALID_FORMAT` or `NOT_IMPLEMENTED`.

PPM has a text variant: `save_to_file(path, image::image_codec::PPM, image::image_codec_format::ASCII)`.

## Handing pixels to someone else

`image_data()` exposes the buffer together with its description. Called on an rvalue it **moves**
the buffer out, leaving nothing to copy:

```cpp
auto description = std::move(picture).image_data();

upload_texture(description.extent, description.format, std::move(description.data));
```

For the GPU, the usual path is `data()` into a staging buffer; the
[textures tutorial](../tutorials/textured-quad.md) shows it end to end.

## Things to remember

- An `image` owns its pixels and is copyable: copies are deep. Pass `const image::image&` or move.
- Transformations allocate a new buffer each. For a pipeline over many files, do the work on a
  [`thread_pool`](core.md#thread_pool) — see the
  [batch processing tutorial](../tutorials/batch-image-processing.md).
- Coordinates start at the top-left of the image as stored in the file.

Reference: [`stormkit.image`](../reference/image.md).

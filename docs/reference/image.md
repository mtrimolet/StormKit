# `stormkit.image` reference

```cpp
import stormkit.image;      // or: import stormkit;
```

| | |
| --- | --- |
| Library | `stormkit-image` |
| xmake option | `image` (default: on; requires `math` and `log`) |
| Depends on | `stormkit.core`, `stormkit.math`; libpng, libjpeg-turbo, libktx |
| Namespace | `stormkit::image` |

Loading, saving and basic manipulation of CPU-side images.

> The class and its namespace share a name: the type is `stormkit::image::image`.

---

## Enumerations

### `image_format`

The pixel layout of the stored data.

| Family | Enumerators |
| --- | --- |
| 8-bit signed normalised | `R8_SNORM`, `RG8_SNORM`, `RGB8_SNORM`, `RGBA8_SNORM` |
| 8-bit unsigned normalised | `R8_UNORM`, `RG8_UNORM`, `RGB8_UNORM`, `RGBA8_UNORM`, `BGR8_UNORM`, `BGRA8_UNORM` |
| 16-bit signed normalised | `R16_SNORM`, `RG16_SNORM`, `RGB16_SNORM`, `RGBA16_SNORM` |
| 16-bit unsigned normalised | `R16_UNORM`, `RG16_UNORM`, `RGB16_UNORM`, `RGBA16_UNORM` |
| packed | `RGBA4_UNORM` |
| 8-bit integer | `R8I`, `RG8I`, `RGB8I`, `RGBA8I`, `R8U`, `RG8U`, `RGB8U`, `RGBA8U` |
| 16-bit integer | `R16I`, `RG16I`, `RGB16I`, `RGBA16I`, `R16U`, `RG16U`, `RGB16U`, `RGBA16U` |
| 32-bit integer | `R32I`, `RG32I`, `RGB32I`, `RGBA32I`, `R32U`, `RG32U`, `RGB32U`, `RGBA32U` |
| floating point | `R16F`, `RG16F`, `RGB16F`, `RGBA16F`, `R32F`, `RG32F`, `RGB32F`, `RGBA32F` |
| sRGB | `SRGB8`, `SRGBA8`, `SBGR8`, `SBGRA8` |
| | `UNDEFINED` |

Naming: channels, bits per channel, then interpretation (`UNORM` → `[0, 1]`, `SNORM` → `[-1, 1]`,
`I` / `U` → raw signed / unsigned integers, `F` → float).

```cpp
constexpr auto get_format_channel_count(image_format format) noexcept -> u8;    // 1 to 4
constexpr auto get_format_component_size(image_format format) noexcept -> u8;   // bytes per channel
```

### `image_codec`

| Enumerator | File extensions (auto-detection) | Backend |
| --- | --- | --- |
| `AUTODETECT` | — | from the extension (files) or the header bytes (memory) |
| `JPEG` | `.jpg`, `.jpeg` | libjpeg-turbo |
| `PNG` | `.png` | libpng |
| `TARGA` | `.tga`, `.targa` | built-in |
| `PPM` | `.ppm` | built-in |
| `HDR` | `.hdr` | built-in |
| `KTX` | `.ktx` | libktx |
| `QOI` | `.qoi` | built-in |
| `UNKNOWN` | | |

### `image_codec_format`

`BINARY` (default) or `ASCII`. Only meaningful for codecs that have a text variant (PPM).

### `image_status_code`

| Enumerator | Meaning |
| --- | --- |
| `NOT_IMPLEMENTED` | The codec does not support this operation. |
| `FAILED_TO_PARSE` | The data is not a valid image for the codec. |
| `FAILED_TO_SAVE` | Encoding or writing failed. |
| `FILE_NOT_FOUND` | The file could not be opened. |
| `INVALID_FORMAT` | The image's pixel format cannot be handled by the codec. |
| `UNKNOWN` | |

These are the errors carried by `image::result<T>`. The enum is registered as a
[status-code](core-foundation.md#stormkitcorestatus_code) domain named `"stormkit Image"`, which
is what lets it travel inside a generic `system_code`:

```cpp
constexpr auto status_code(image_status_code) noexcept;    // wraps the enum into a status code
```

Compare an error against a specific value with `result.error() == image::image_status_code::FILE_NOT_FOUND`.

---

## `image`

```cpp
class image {
  public:
    template<typename T> using result = core::system_result<T>;

    struct image_data_t {
        math::uextent3 extent            = { .width = 0u, .height = 0u };
        u32            channel_count     = 0u;
        u32            bytes_per_channel = 0u;
        u32            layers            = 1u;
        u32            faces             = 1u;
        u32            mip_levels        = 1u;
        image_format   format            = image_format::UNDEFINED;
        dynarray<byte> data              = {};
    };

    image() noexcept;
    explicit image(image_data_t&& data) noexcept;
    image(const math::uextent3& extent, image_format format) noexcept;
    image(const stdfs::path& filepath, image_codec codec = image_codec::AUTODETECT) noexcept;
    image(array_view<const byte> data, image_codec codec = image_codec::AUTODETECT) noexcept;
    // copyable and movable

    auto load_from_file(const stdfs::path& filepath, image_codec codec = image_codec::AUTODETECT) noexcept -> result<void>;
    auto load_from_memory(array_view<const byte> data, image_codec codec = image_codec::AUTODETECT) noexcept -> result<void>;
    auto save_to_file(const stdfs::path& filename, image_codec codec,
                      image_codec_format args = image_codec_format::BINARY) const noexcept -> result<void>;
    auto save_to_memory(image_codec codec,
                        image_codec_format args = image_codec_format::BINARY) const noexcept -> result<dynarray<byte>>;

    auto create(const math::uextent3& extent, image_format format) noexcept -> void;

    auto convert_to(image_format format) const noexcept -> image;
    auto scale(const math::uextent3& scale_to) const noexcept -> image;
    auto flip_x() const noexcept -> image;        auto flip_y() const noexcept -> image;        auto flip_z() const noexcept -> image;
    auto rotate_90() const noexcept -> image;     auto rotate_180() const noexcept -> image;    auto rotate_270() const noexcept -> image;

    auto pixel(usize id, u32 layer = 0u, u32 face = 0u, u32 level = 0u) noexcept -> array_view<byte>;
    auto pixel(const math::uvec3& position, u32 layer = 0u, u32 face = 0u, u32 level = 0u) noexcept -> array_view<byte>;

    auto extent(u32 level = 0u) const noexcept -> math::uextent3;
    auto channel_count() const noexcept -> u32;
    auto bytes_per_channel() const noexcept -> u32;
    auto layers() const noexcept -> u32;
    auto faces() const noexcept -> u32;
    auto mip_levels() const noexcept -> u32;
    auto format() const noexcept -> image_format;

    auto size() const noexcept -> usize;
    auto size(u32 layer) const noexcept -> usize;
    auto size(u32 layer, u32 face) const noexcept -> usize;
    auto size(u32 layer, u32 face, u32 level) const noexcept -> usize;

    auto data() noexcept -> array_view<byte>;
    auto data(u32 layer, u32 face, u32 level) noexcept -> array_view<byte>;

    auto image_data() const & noexcept -> const image_data_t&;
    auto image_data() && noexcept -> image_data_t;
};
```

`pixel` and `data` are const-propagating: on a `const image` they return `array_view<const byte>`.

### Data model

An image is a single contiguous byte buffer plus a description of how to slice it:

```
layers  ×  faces  ×  mip levels  ×  (depth × height × width)  ×  channels  ×  bytes per channel
```

| Term | Meaning |
| --- | --- |
| extent | width, height and depth of mip level 0. A 2D image has `depth == 1`. |
| layers | array elements (texture arrays). |
| faces | 6 for cube maps, 1 otherwise. |
| mip levels | number of stored levels. `extent(level)` gives the size of each. |

Ordinary PNG / JPEG / TGA / QOI files produce `layers == faces == mip_levels == 1`; KTX files can
populate all of them.

### Construction and I/O

| Member | Description |
| --- | --- |
| `image()` | Empty image (`format() == UNDEFINED`). |
| `image(extent, format)` / `create(extent, format)` | Allocates a zero-filled image. |
| `image(image_data_t&&)` | Adopts an existing buffer and its description. |
| `image(path, codec)` / `image(bytes, codec)` | Convenience constructors that load immediately. **They cannot report failure**; prefer the default constructor followed by `load_from_file` / `load_from_memory` when the input is not trusted. |
| `load_from_file(path, codec)` | With `AUTODETECT`, the codec is chosen from the file extension (case-insensitive; a path without extension is a contract violation). |
| `load_from_memory(bytes, codec)` | With `AUTODETECT`, the codec is chosen from the header bytes. |
| `save_to_file(path, codec, format)` | `codec` must be explicit (not `AUTODETECT`). |
| `save_to_memory(codec, format)` | Returns the encoded bytes. |

```cpp
auto img = image::image {};
if (auto result = img.load_from_file("textures/cube.png"); not result) {
    std::println(stderr, "failed to load image: {}", result.error());
    return -1;
}
std::println("{} — {} channels, {} bytes", img.extent(), img.channel_count(), img.size());
```

### Transformations

All transformations are `const` and **return a new image**.

| Member | Description |
| --- | --- |
| `convert_to(format)` | Converts the pixel format (channel count and/or component type), e.g. `RGB8_UNORM` → `RGBA8_UNORM` before a GPU upload. |
| `scale(extent)` | Resizes to `extent`. |
| `flip_x()`, `flip_y()`, `flip_z()` | Mirror along an axis. `flip_y` converts between top-left and bottom-left origins. |
| `rotate_90()`, `rotate_180()`, `rotate_270()` | Rotate in the XY plane. |

### Pixel access

| Member | Description |
| --- | --- |
| `pixel(index, layer, face, level)` | The bytes of one pixel, by linear index within the sub-image. |
| `pixel({ x, y, z }, layer, face, level)` | By coordinates. |
| `data()` | The whole buffer. |
| `data(layer, face, level)` | The bytes of one sub-image. |
| `size(...)` | Byte size of the whole image, a layer, a face or a single level. |

A pixel view is `channel_count() * bytes_per_channel()` bytes long. To read it as a typed colour,
copy the bytes: `std::memcpy(&color, std::ranges::data(img.pixel(i)), sizeof(color))`, choosing a
[`color`](core-foundation.md#stormkitcorecolor) alias whose layout matches `format()`
(`ucolor_rgba` for `RGBA8_UNORM`, …).

### Raw description

`image_data()` exposes the underlying `image_data_t`. The rvalue overload **moves it out**, which
is the zero-copy way to hand the pixels to another owner:

```cpp
auto description = std::move(img).image_data();
upload(description.data, description.extent, description.format);
```

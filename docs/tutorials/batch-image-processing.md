# Tutorial: batch image processing

**Libraries:** `core`, `math`, `image`, `log` (and `main`)

We will write `thumbs`, a tool that turns every image in a directory into a thumbnail: resized to
fit a box while keeping its proportions, converted to RGB, saved as JPEG — several images at a
time.

```console
> thumbs photos out --size=256
[ INFO    | thumbs | 00 ] 4 image(s) -> out (max 256 px, 6 workers)
[ INFO    | thumbs | 00 ] beach.png: [extent2 .width = 4000, .height = 3000, .depth = 1] -> 256x192
[ INFO    | thumbs | 00 ] icon.tga: [extent2 .width = 64, .height = 64, .depth = 1] -> 64x64
[ WARNING | thumbs | 01 ] notes.png: not a valid image, skipped
[ INFO    | thumbs | 01 ] done: 3 converted, 1 skipped, 11.4 MiB read, 0.1 MiB written
```

The interesting parts are how the four libraries hand data to each other: `math` extents describe
sizes everywhere, `image` returns `expected`s that `core`'s macros propagate, and `core`'s
`locked` lets worker threads share a result safely.

## Setting up

The default configuration builds everything we need. Add a target as in the
[previous tutorial](command-line-tool.md#setting-up), named `thumbs`.

```cpp
import std;
import stormkit;

#include <stormkit/core/tryx_expected.hpp>
#include <stormkit/main/main_macro.hpp>

using namespace stormkit;
using namespace stormkit::literals;
using namespace std::literals;

namespace stdfs = std::filesystem;

namespace {
    constexpr auto LOG = log::module { "thumbs" };
}
```

## Step 1 — the size computation

Given an image size and a maximum side, what is the thumbnail size? This is pure arithmetic on
[`math` extents](../guides/math.md#extents), so we can make it `constexpr` and test it at compile
time.

```cpp
constexpr auto fit(const math::uextent3& source, u32 max_side) noexcept -> math::uextent3 {
    expects(source.width > 0 and source.height > 0, "empty image");
    expects(max_side > 0, "empty target");

    const auto longest = math::max(source.width, source.height);
    if (longest <= max_side) return source;                          // never enlarge

    const auto shrink = [longest, max_side](u32 side) noexcept {
        const auto scaled = as<u64>(side) * max_side / longest;      // 64-bit: the product may exceed u32
        return math::max(1u, as<u32>(scaled));
    };

    return { .width = shrink(source.width), .height = shrink(source.height), .depth = 1u };
}

static_assert(fit({ 4000u, 3000u, 1u }, 256u) == math::uextent3 { 256u, 192u, 1u });
static_assert(fit({ 64u, 64u, 1u }, 256u) == math::uextent3 { 64u, 64u, 1u });
static_assert(fit({ 5000u, 10u, 1u }, 100u) == math::uextent3 { 100u, 1u, 1u });
```

Things to notice:

- `expects` documents and enforces the pre-conditions; in a constant expression a violation is a
  compile error.
- The conversions are [`as`](../guides/core.md#safe-conversions) casts: widening to `u64` so that
  the multiplication cannot overflow, then back to `u32` — a narrowing that `as` checks. The
  result always fits here, and if a future change broke that assumption we would be told.
- Extents compare with `==`, which makes the `static_assert`s one-liners. Three test cases run
  every time the file is compiled.
- `math::max(1u, …)` keeps a very elongated image from collapsing to zero pixels.

## Step 2 — processing one image

```cpp
struct outcome {
    math::uextent3 from;
    math::uextent3 to;
    usize          bytes_read    = 0;
    usize          bytes_written = 0;
};

auto make_thumbnail(const stdfs::path& input, const stdfs::path& output, u32 max_side) noexcept
  -> system_result<outcome> {
    auto source = image::image {};
    Try(source.load_from_file(input));

    const auto target = fit(source.extent(), max_side);

    const auto thumbnail = source
                             .convert_to(image::image_format::RGB8_UNORM)      // JPEG has no alpha
                             .scale(target);

    Try(thumbnail.save_to_file(output, image::image_codec::JPEG));

    auto ec = std::error_code {};
    return outcome {
        .from          = source.extent(),
        .to            = target,
        .bytes_read    = source.size(),
        .bytes_written = as<usize>(stdfs::file_size(output, ec)),
    };
}
```

- `load_from_file` picks the decoder from the file extension and returns
  `image::image::result<void>`, which is a `system_result<void>`. [`Try`](../reference/macros.md#try-statement-macros)
  returns its error from our function if it failed; our own return type is a `system_result` too,
  so the error passes through unchanged.
- The [transformations](../guides/image.md#transforming) return new images, which lets us chain
  them and keep `thumbnail` `const`.
- We convert **before** scaling: resizing three channels is less work than resizing four.
- `source.extent()` is a `math::uextent3` — the same type `fit` takes and `scale` wants. No glue
  code.

## Step 3 — which files?

```cpp
constexpr auto EXTENSIONS = std::array { ".png"sv, ".jpg"sv, ".jpeg"sv, ".tga"sv, ".ppm"sv, ".qoi"sv, ".hdr"sv, ".ktx"sv };

auto find_images(const stdfs::path& directory) noexcept -> dynarray<stdfs::path> {
    auto ec  = std::error_code {};
    auto out = dynarray<stdfs::path> {};

    for (const auto& item : stdfs::directory_iterator { directory, ec }) {
        if (not item.is_regular_file(ec)) continue;

        const auto extension = to_lower(item.path().extension().string());
        if (std::ranges::contains(EXTENSIONS, extension)) out.emplace_back(item.path());
    }

    std::ranges::sort(out);
    return out;
}
```

`to_lower` is `core`'s [string algorithm](../guides/core.md#algorithms); it makes `PHOTO.PNG`
match.

## Step 4 — sharing a total between threads

Each worker will add to a running total. A plain struct updated from several threads is a data
race; [`locked<T>`](../guides/core.md#locked--data-that-cannot-be-touched-without-its-lock) makes
the race impossible to write, because the only way to reach the value is through a function that
holds the mutex.

```cpp
struct totals {
    u32   converted     = 0;
    u32   skipped       = 0;
    usize bytes_read    = 0;
    usize bytes_written = 0;
};
```

## Step 5 — the parallel loop

```cpp
auto run(const stdfs::path& input_dir, const stdfs::path& output_dir, u32 max_side) noexcept -> totals {
    const auto files = find_images(input_dir);

    auto pool   = thread_pool {};
    auto shared = locked<totals> {};

    pool.set_name("thumbs");
    LOG.ilog("{} image(s) -> {} (max {} px, {} workers)",
             std::ranges::size(files), output_dir.string(), max_side, pool.worker_count());

    auto pending = dynarray<std::future<void>> {};
    pending.reserve(std::ranges::size(files));

    for (const auto& file : files) {
        pending.emplace_back(pool.post_task<void>([&shared, &output_dir, file, max_side] noexcept {
            const auto name   = file.filename().string();
            const auto output = (output_dir / file.stem()).replace_extension(".jpg");

            const auto result = make_thumbnail(file, output, max_side);

            if (not result) {
                if (result.error() == image::image_status_code::FAILED_TO_PARSE) LOG.wlog("{}: not a valid image, skipped", name);
                else
                    LOG.elog("{}: {}", name, result.error());

                shared.write([](auto& t) noexcept { ++t.skipped; });
                return;
            }

            LOG.ilog("{}: {} -> {}x{}", name, result->from, result->to.width, result->to.height);

            shared.write([&result](auto& t) noexcept {
                ++t.converted;
                t.bytes_read    += result->bytes_read;
                t.bytes_written += result->bytes_written;
            });
        }));
    }

    wait_all(pending);
    return shared.copy();
}
```

Walking through it:

- **One task per image.** Decoding and resizing are CPU-bound and independent, so they scale with
  the number of workers.
- **Captures.** `file` and `max_side` are captured by value; `shared` and `output_dir` by
  reference, which is safe because `wait_all(pending)` blocks until every task has finished,
  before either goes out of scope.
- **Classifying errors.** A `system_code` compares against an enumerator of the error domain it
  came from; a corrupt file is a warning, anything else (a full disk, a missing directory) an
  error.
- **`shared.write(closure)`** locks, runs the closure on the value, unlocks. The critical section
  is exactly the closure body — short, and with no I/O inside it. The logging and the image work
  happen *outside* the lock.
- **Logging from threads is safe**; lines from different workers interleave but never mix.
- **`result->from`** is an extent and prints as one; the logger formats it like `std::format`
  would.
- **`shared.copy()`** takes the lock one last time and returns the totals by value.

## Step 6 — `main`

```cpp
auto main(array_view<const string_view> args) -> int {
    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    auto positional = dynarray<string_view> {};
    auto max_side   = 256_u32;

    for (const auto arg : args.subspan(1)) {
        if (arg.starts_with("--size=")) {
            const auto value = to<u32>(arg.substr(7));
            if (not value or *value == 0) {
                LOG.elog("invalid size '{}'", arg.substr(7));
                return 2;
            }
            max_side = *value;
        } else if (not arg.starts_with("--"))
            positional.emplace_back(arg);
    }

    if (std::ranges::size(positional) != 2) {
        LOG.elog("usage: thumbs <input-dir> <output-dir> [--size=N]");
        return 2;
    }

    const auto input  = stdfs::path { positional[0] };
    const auto output = stdfs::path { positional[1] };

    auto ec = std::error_code {};
    stdfs::create_directories(output, ec);
    if (ec) {
        LOG.elog("cannot create {}: {}", output.string(), ec.message());
        return 1;
    }

    const auto result = run(input, output, max_side);

    constexpr auto MIB = as<f64>(1_mib);
    LOG.ilog("done: {} converted, {} skipped, {:.1f} MiB read, {:.1f} MiB written",
             result.converted, result.skipped, as<f64>(result.bytes_read) / MIB, as<f64>(result.bytes_written) / MIB);

    return result.skipped == 0 ? 0 : 1;
}
```

`1_mib` is one of `core`'s [size literals](../guides/core.md#vocabulary-types-and-literals).

## Build and run

```console
> xmake f && xmake b stormkit::examples::thumbs
> xmake run stormkit::examples::thumbs ~/Pictures out --size=320
```

## What to take away

| Hand-off | How it works |
| --- | --- |
| `image` → `math` | every size is a `math::extent`; arithmetic and comparison come for free |
| `image` → `core` errors | `result<T>` *is* `system_result<T>`; `Try` / `TryX` forward it; status enumerators compare against it |
| threads → shared state | `locked<T>::write(closure)`; no mutex to forget |
| threads → logger | call it from anywhere |
| compile time | `constexpr` + `expects` + `static_assert` test the arithmetic without running anything |

## Going further

- Replace the per-file tasks with `parallel_for(pool, files, …)` when you do not need a future per
  item.
- Add a `--format=png|jpg|qoi` option mapping to `image::image_codec`, converting to
  `RGBA8_UNORM` for the formats that keep alpha.
- Generate several sizes per image from a single decode: load once, then `scale` repeatedly from
  the same source.
- Keep a `hash_map<hash64, stdfs::path>` of `hash::crc64(source.data())` to detect duplicate
  images.

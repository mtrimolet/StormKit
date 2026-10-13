# Tutorial: textures and uniforms

**Libraries:** `math`, `image`, `wsi`, `gpu` (and `core`, `log`, `main`)

The triangle of the [previous tutorial](vulkan-triangle.md) drew three vertices invented by the
shader. Real rendering feeds the GPU with **data**. This tutorial adds the three kinds you will
use in every program:

| Data | Changes | Travels through |
| --- | --- | --- |
| geometry | rarely | a **vertex buffer** |
| pixels | rarely | an **image**, filled from a staging buffer, read through a **sampler** |
| transforms | every frame | a **uniform buffer** |

and the mechanism that tells shaders where to find the last two: **descriptor sets**.

The result is a textured square that spins in the middle of the window.

> Same caveat as before: `gpu` and `wsi` are documented from their declared interfaces
> ([status](../reference/gpu.md)).

## Starting point

Take the finished program from [your first triangle](vulkan-triangle.md), in a new target
`textured-quad`. `init_gpu`, `run` and `main` are unchanged. We will:

1. replace the shader;
2. add members for the new resources;
3. extend `init_resources`;
4. update the uniform data and bind everything in `render_frame`.

Configure with the image library too (it is on by default):

```console
> xmake f --wsi=y --gpu=y --devmode=y
```

## The shader

We reuse the shader of the in-tree `textured_cube` example unchanged
(`examples/gpu/textured_cube/shaders/textured_cube.nzsl`). Its interface is what the C++ side has
to match:

```rust
struct VertIn {
    [location(0)] position: vec3[f32],
    [location(1)] uv: vec2[f32]
}

[layout(std140)]
struct ViewerData {
    proj: mat4[f32],
    view: mat4[f32],
    model: mat4[f32]
}

external {
    [binding(0)] viewer: uniform[ViewerData]
}

external {
    [binding(1)] texture: sampler2D[f32]
}

// vertex:   output.position = viewer.proj * viewer.view * viewer.model * vec4[f32](input.position, 1.);
// fragment: output.color    = texture.Sample(input.uv);
```

Three contracts follow from it:

| Shader | C++ |
| --- | --- |
| vertex inputs at locations 0 and 1 | a vertex struct and its attribute descriptions |
| uniform block at binding 0 | a struct with the same layout, in a uniform buffer |
| sampler at binding 1 | an image view and a sampler |

## Step 1 — the data types

```cpp
struct vertex {
    math::fvec3 position;
    math::fvec2 uv;
};

struct viewer_data {
    math::fmat4 proj;
    math::fmat4 view;
    math::fmat4 model;
};

static_assert(sizeof(viewer_data) == 3 * 16 * sizeof(f32));          // matches the std140 block

constexpr auto QUAD = std::array {
    vertex { { -0.5f, -0.5f, 0.f }, { 0.f, 0.f } },
    vertex { { 0.5f, -0.5f, 0.f }, { 1.f, 0.f } },
    vertex { { 0.5f, 0.5f, 0.f }, { 1.f, 1.f } },
    vertex { { -0.5f, -0.5f, 0.f }, { 0.f, 0.f } },
    vertex { { 0.5f, 0.5f, 0.f }, { 1.f, 1.f } },
    vertex { { -0.5f, 0.5f, 0.f }, { 0.f, 1.f } },
};
```

`math` vectors and matrices are plain aggregates over arrays of floats, with no padding and no
hidden members, so structs made of them have exactly the memory layout the GPU expects. The
`static_assert` documents — and checks — that `viewer_data` is three 4×4 float matrices, like the
shader's block.

Two triangles make the square; the `uv` coordinates map the texture's corners onto it.

## Step 2 — new members

```cpp
struct frame_resources {
    gpu::Fence         in_flight;
    gpu::Semaphore     image_available;
    gpu::CommandBuffer commands;
    gpu::Buffer        viewer_buffer;        // new: this frame's uniform data
    gpu::DescriptorSet descriptor_set;       // new: points at viewer_buffer and the texture
};

class application {
    // … as before, plus:
    defer_init<gpu::Buffer>              m_vertex_buffer;
    defer_init<gpu::Image>               m_texture;
    defer_init<gpu::ImageView>           m_texture_view;
    defer_init<gpu::Sampler>             m_sampler;
    defer_init<gpu::DescriptorSetLayout> m_descriptor_set_layout;
    defer_init<gpu::DescriptorPool>      m_descriptor_pool;

    std::chrono::steady_clock::time_point m_start = std::chrono::steady_clock::now();
};
```

Declare the new members **before** `m_frames`, and `m_descriptor_set_layout` before
`m_pipeline_layout`: members are destroyed in reverse order, and descriptor sets must go before
the pool and the resources they refer to.

The uniform buffer and the descriptor set are **per frame**. The CPU writes next frame's matrix
while the GPU may still be reading the previous one; giving each in-flight frame its own copy
removes the conflict.

## Step 3 — the vertex buffer

At the top of `init_resources`:

```cpp
m_vertex_buffer = TryXAssert(gpu::Buffer::create(m_device, { .usages = gpu::BufferUsageFlag::VERTEX, .size = sizeof(QUAD) }),
                             "vertex buffer");
DiscardTryXAssert(m_vertex_buffer->upload(view_of(as_bytes, QUAD)), "vertex upload");
```

- By default a buffer is allocated in memory the CPU can write, so `upload` copies straight into
  it.
- [`view_of(as_bytes, QUAD)`](../guides/core.md#into-and-view_of) views the array of vertices as
  bytes, with no copy and no `reinterpret_cast`.

## Step 4 — the texture

### Getting pixels

We load an image if a path was given on the command line, and fall back to a generated
checkerboard so that the program runs without any asset:

```cpp
auto make_checkerboard() -> image::image {
    constexpr auto SIZE = 256_u32;
    constexpr auto CELL = 32_u32;

    constexpr ucolor_rgba LIGHT = colors::WHITE<u8>;        // presets convert to any colour type
    constexpr ucolor_rgba DARK  = colors::TEAL<u8>;

    auto out    = image::image { { .width = SIZE, .height = SIZE }, image::image_format::RGBA8_UNORM };
    auto pixels = std::span { std::bit_cast<ucolor_rgba*>(std::ranges::data(out.data())), as<usize>(SIZE) * SIZE };

    for (auto [y, x] : multi_range(SIZE, SIZE))
        pixels[y * SIZE + x] = ((x / CELL + y / CELL) % 2u == 0u) ? LIGHT : DARK;

    return out;
}

auto load_pixels(std::optional<std::filesystem::path> path) -> image::image {
    if (path) {
        auto loaded = image::image {};
        if (const auto result = loaded.load_from_file(*path); result) return loaded.convert_to(image::image_format::RGBA8_UNORM);
        else
            LOG.wlog("cannot load {} ({}), using a checkerboard", path->string(), result.error());
    }
    return make_checkerboard();
}
```

- `convert_to(RGBA8_UNORM)` normalises whatever the file contained (RGB, greyscale, 16-bit…) to
  the one format we will create the GPU image with.
- A `ucolor_rgba` is four bytes in r, g, b, a order — the memory layout of an `RGBA8_UNORM`
  pixel — so the image's byte buffer can be viewed as an array of them.
- Loading can fail for ordinary reasons (wrong path, unsupported file); we log and carry on rather
  than abort.

### Uploading

```cpp
const auto pixels = load_pixels(m_texture_path);

m_texture = TryXAssert(gpu::Image::create(m_device,
                                          { .extent = pixels.extent(),
                                            .format = gpu::PixelFormat::RGBA8_UNORM,
                                            .usages = gpu::ImageUsageFlag::SAMPLED | gpu::ImageUsageFlag::TRANSFER_DST }),
                       "texture");
{
    auto staging = TryXAssert(gpu::Buffer::create(m_device, { .usages = gpu::BufferUsageFlag::TRANSFER_SRC, .size = pixels.size() }),
                              "staging buffer");
    DiscardTryXAssert(staging.upload(pixels.data()), "staging upload");

    auto done = TryXAssert(gpu::Fence::create(m_device), "fence");
    auto copy = TryXAssert(m_command_pool->create_command_buffer(), "command buffer");

    DiscardTryXAssert(copy.record([&](auto cmb) noexcept {
        const auto region = std::array {
            gpu::BufferImageCopy { .buffer_offset = 0, .buffer_row_length = 0, .buffer_image_height = 0,
                                   .subresource_layers = {}, .offset = {}, .extent = pixels.extent() }
        };

        cmb.begin_debug_region("upload texture")
           .transition_image_layout(m_texture, gpu::ImageLayout::UNDEFINED, gpu::ImageLayout::TRANSFER_DST_OPTIMAL)
           .copy_buffer_to_image(staging, m_texture, region)
           .transition_image_layout(m_texture, gpu::ImageLayout::TRANSFER_DST_OPTIMAL, gpu::ImageLayout::SHADER_READ_ONLY_OPTIMAL)
           .end_debug_region();
    }), "record upload");

    DiscardTryXAssert(copy.submit(m_queue, {}, {}, {}, done), "submit upload");
    DiscardTryXAssert(done.wait(), "wait upload");
}

m_texture_view = TryXAssert(gpu::ImageView::create(m_device, { m_texture }), "texture view");
m_sampler      = TryXAssert(gpu::Sampler::create(m_device, {}), "sampler");
```

(`m_texture_path` is a `std::optional<std::filesystem::path>` member set from `args` in `main`.)

Why the detour through a **staging buffer**? The texture lives in the GPU's own memory, which the
CPU cannot write. So:

1. put the pixels in a CPU-visible buffer;
2. record a command that copies the buffer into the image — after moving the image to the layout
   that allows it (`TRANSFER_DST_OPTIMAL`), and before moving it to the one shaders read from
   (`SHADER_READ_ONLY_OPTIMAL`);
3. submit, and **wait** on the fence: the staging buffer is destroyed at the closing brace, and it
   must not disappear while the copy is in progress.

`pixels.extent()` is a `math::uextent3`, which is what both `gpu::Image::create` and the copy
region want: the two libraries share `math`'s types and nothing needs converting.

The image view is how the image is bound; the **sampler** says how it is read — here the default:
linear filtering, repeat addressing.

## Step 5 — descriptors

The shader says "binding 0 is a uniform block, binding 1 is a sampler". Four objects turn that
into something concrete.

**The layout** restates the shader's declaration:

```cpp
m_descriptor_set_layout = TryXAssert(gpu::DescriptorSetLayout::create(m_device, {
    { .binding = 0, .type = gpu::DescriptorType::UNIFORM_BUFFER,         .stages = gpu::ShaderStageFlag::VERTEX,   .descriptor_count = 1 },
    { .binding = 1, .type = gpu::DescriptorType::COMBINED_IMAGE_SAMPLER, .stages = gpu::ShaderStageFlag::FRAGMENT, .descriptor_count = 1 },
}), "descriptor set layout");
```

**The pipeline layout** now references it (it was empty for the triangle):

```cpp
m_pipeline_layout = TryXAssert(gpu::PipelineLayout::create(m_device,
                                                           gpu::RasterPipelineLayout {
                                                             .descriptor_set_layouts = gpu::to_views(m_descriptor_set_layout) }),
                               "pipeline layout");
```

**The pool** is sized for what we will allocate — one set per in-flight frame, each with one
descriptor of each type:

```cpp
static constexpr auto POOL_SIZES = std::array {
    gpu::DescriptorPool::Size { .type = gpu::DescriptorType::UNIFORM_BUFFER,         .descriptor_count = as<u32>(FRAMES_IN_FLIGHT) },
    gpu::DescriptorPool::Size { .type = gpu::DescriptorType::COMBINED_IMAGE_SAMPLER, .descriptor_count = as<u32>(FRAMES_IN_FLIGHT) },
};
m_descriptor_pool = TryXAssert(gpu::DescriptorPool::create(m_device, POOL_SIZES, as<u32>(FRAMES_IN_FLIGHT)), "descriptor pool");
```

**The sets** are created with the per-frame resources, and pointed at the real objects:

```cpp
for (auto _ : range(FRAMES_IN_FLIGHT)) {
    m_frames.push_back({
      .in_flight       = TryXAssert(gpu::Fence::create_signaled(m_device), "fence"),
      .image_available = TryXAssert(gpu::Semaphore::create(m_device), "semaphore"),
      .commands        = TryXAssert(m_command_pool->create_command_buffer(), "command buffer"),
      .viewer_buffer   = TryXAssert(gpu::Buffer::create(m_device,
                                                        { .usages              = gpu::BufferUsageFlag::UNIFORM,
                                                          .size                = sizeof(viewer_data),
                                                          .persistently_mapped = true }),
                                    "viewer buffer"),
      .descriptor_set  = TryXAssert(m_descriptor_pool->create_descriptor_set(m_descriptor_set_layout), "descriptor set"),
    });

    auto& frame = m_frames.back();
    frame.descriptor_set.update(std::array<gpu::Descriptor, 2> {
        gpu::BufferDescriptor { .binding = 0, .buffer = frame.viewer_buffer, .range = sizeof(viewer_data) },
        gpu::ImageDescriptor  { .binding    = 1,
                                .layout     = gpu::ImageLayout::SHADER_READ_ONLY_OPTIMAL,
                                .image_view = m_texture_view,
                                .sampler    = m_sampler },
    });
}
```

- The uniform buffer is **persistently mapped**: it stays mapped for its whole life, so writing to
  it each frame is a plain memory write.
- `update` is called once. The set keeps pointing at the same buffer; only the buffer's *contents*
  change per frame.
- Both sets share the one texture: resources that do not change need no per-frame copy.

## Step 6 — the pipeline

Two additions to the pipeline state: the vertex layout, and alpha blending for textures with
transparency.

```cpp
const auto state = gpu::RasterPipelineState {
    .input_assembly_state = { .topology = gpu::PrimitiveTopology::TRIANGLE_LIST },
    .viewport_state       = { .viewports = { { .position = { 0.f, 0.f }, .extent = as<math::fextent2>(extent), .depth = { 0.f, 1.f } } },
                              .scissors  = { { .offset = { 0, 0 }, .extent = extent } } },
    .rasterization_state  = { .cull_mode = gpu::CullModeFlag::NONE },
    .color_blend_state    = { .attachments = { { .blend_enable           = true,
                                                 .src_color_blend_factor = gpu::BlendFactor::SRC_ALPHA,
                                                 .dst_color_blend_factor = gpu::BlendFactor::ONE_MINUS_SRC_ALPHA,
                                                 .src_alpha_blend_factor = gpu::BlendFactor::SRC_ALPHA,
                                                 .dst_alpha_blend_factor = gpu::BlendFactor::ONE_MINUS_SRC_ALPHA,
                                                 .alpha_blend_operation  = gpu::BlendOperation::ADD } } },
    .shader_state         = gpu::to_views(m_vertex_shader, m_fragment_shader),
    .vertex_input_state   = {
        .binding_descriptions         = { { .binding = 0, .stride = sizeof(vertex) } },
        .input_attribute_descriptions = {
            { .location = 0, .binding = 0, .format = gpu::PixelFormat::RGB32F, .offset = offsetof(vertex, position) },
            { .location = 1, .binding = 0, .format = gpu::PixelFormat::RG32F,  .offset = offsetof(vertex, uv) },
        },
    },
};
```

- One **binding** describes the buffer: where one vertex ends and the next begins (`stride`).
- One **attribute** per shader input: its location in the shader, its type (as a pixel format:
  `RGB32F` is three floats, `RG32F` two) and its offset inside the vertex struct.

`offsetof` and `sizeof` keep the description tied to the struct: reorder the members and the
pipeline follows.

## Step 7 — per-frame work

In `render_frame`, after acquiring the image and before recording, compute this frame's matrices
and write them to **this frame's** buffer:

```cpp
const auto time   = std::chrono::duration_cast<fsecond>(std::chrono::steady_clock::now() - m_start).count();
const auto size   = as<math::fextent2>(m_window->extent());
const auto angle  = time * 1.5f;                              // radians
const auto cosine = std::cos(angle);
const auto sine   = std::sin(angle);

auto viewer = viewer_data {
    .proj  = math::fmat4::identity(),
    .view  = math::fmat4::identity(),
    .model = math::fmat4::identity(),
};

viewer.proj[0, 0] = size.height / size.width;                 // keep the square square in a non-square window

viewer.model[0, 0] = cosine;                                  // rotation around Z
viewer.model[0, 1] = -sine;
viewer.model[1, 0] = sine;
viewer.model[1, 1] = cosine;

*frame.viewer_buffer.data_as<viewer_data>() = viewer;
```

We build the matrices element by element with `m[row, column]`, starting from
`math::fmat4::identity()`:

- the "projection" only compensates for the window's aspect ratio;
- the model matrix is a rotation in the plane of the screen.

In a 3D scene these come from `math::perspective`, `math::look_at` and `math::rotate` instead — see
the [math guide](../guides/math.md#transforms), including its note about the current state of
those helpers and about matrix layout when uploading. The matrices used here were chosen so that
they are valid whichever convention the shader uses.

Then bind the new objects when recording:

```cpp
static constexpr auto OFFSETS = std::array { 0_u64 };

cmb.transition_image_layout(target.image, gpu::ImageLayout::PRESENT_SRC, gpu::ImageLayout::ATTACHMENT_OPTIMAL)
   .begin_rendering(rendering_info)
   .bind_pipeline(m_pipeline)
   .bind_vertex_buffers(gpu::as_views(m_vertex_buffer), OFFSETS)
   .bind_descriptor_sets(m_pipeline, m_pipeline_layout, gpu::as_views(frame.descriptor_set))
   .draw(as<u32>(std::ranges::size(QUAD)))
   .end_rendering()
   .transition_image_layout(target.image, gpu::ImageLayout::ATTACHMENT_OPTIMAL, gpu::ImageLayout::PRESENT_SRC);
```

Compared to the triangle: a vertex buffer and a descriptor set are bound, and `draw` is told how
many vertices the buffer holds.

## Run it

```console
> xmake b stormkit::examples::textured-quad
> xmake run stormkit::examples::textured-quad                       # checkerboard
> xmake run stormkit::examples::textured-quad path/to/picture.png   # your image
```

## The whole picture

```
                       ┌───────────────┐
 QUAD ─upload────────▶ │ vertex buffer │ ──bind_vertex_buffers──┐
                       └───────────────┘                        │
 image::image ─upload▶ staging ─copy▶ texture ─▶ view ┐         │
                                              sampler ┤         ▼
                                                      ├─▶ descriptor set ──bind_descriptor_sets──▶ draw
 viewer_data ─write──▶ uniform buffer (per frame) ────┘         ▲
                                                                │
 shaders + vertex layout + blend state ─▶ pipeline ──bind_pipeline
```

| Data | Created | Updated | Bound with |
| --- | --- | --- | --- |
| vertices | once, `Buffer` + `upload` | never | `bind_vertex_buffers` |
| texture | once, staging `Buffer` → `Image` | never | a descriptor (`ImageDescriptor`) |
| matrices | one `Buffer` per frame, mapped | every frame, by writing memory | a descriptor (`BufferDescriptor`) |

## Going further

- **Indexed drawing**: four vertices and an index buffer (`BufferUsageFlag::INDEX`,
  `bind_index_buffer`, `draw_indexed`) instead of six vertices.
- **Mipmaps**: create the image with `mip_levels = gpu::compute_mip_level(extent)` and generate
  the levels with `blit_image`.
- **A device-local vertex buffer**: allocate it with `MemoryPropertyFlag::DEVICE_LOCAL` and
  `BufferUsageFlag::VERTEX | TRANSFER_DST`, and fill it through a staging buffer and
  `copy_buffer`, like the texture.
- **Depth**: turn the square into a cube ([guide](../guides/gpu.md#depth-testing)); the in-tree
  `textured_cube` example is that program.

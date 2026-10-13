# Guide: `stormkit.gpu`

`stormkit.gpu` is Vulkan with the sharp edges filed off: the same objects and the same mental
model, but handles that clean up after themselves, aggregates instead of `Vk…CreateInfo` chains,
scoped enums instead of integer constants, and `expected` instead of result codes you can forget
to check.

It is not an engine. If you know Vulkan you will recognise every step; if you do not, this guide
explains each object as it appears, but a Vulkan introduction alongside will help.

Enable it with `--wsi=y --gpu=y`.

```cpp
module;
#include <stormkit/core/tryx_expected.hpp>
export module app;

import std;
import stormkit;

using namespace stormkit;
```

> This library still uses `PascalCase` names and has not yet been ported to the current `core`.
> See the [status note](../reference/gpu.md). Samples follow the declared interfaces.

- [Objects and views](#objects-and-views)
- [Start-up: instance, device, queue](#start-up-instance-device-queue)
- [Presenting: surface and swapchain](#presenting-surface-and-swapchain)
- [Shaders and pipelines](#shaders-and-pipelines)
- [Command buffers](#command-buffers)
- [The frame loop](#the-frame-loop)
- [Buffers](#buffers)
- [Textures](#textures)
- [Descriptors: connecting data to shaders](#descriptors-connecting-data-to-shaders)
- [Depth testing](#depth-testing)
- [Resizing](#resizing)
- [Debugging](#debugging)

---

## Objects and views

Two rules explain most signatures.

**Every GPU object exists as an owner and as a view.** `gpu::Buffer` owns a Vulkan buffer and
destroys it when it goes out of scope. `gpu::view::Buffer` is a cheap, copyable, non-owning
reference to one. Functions accept views; owners convert to views implicitly:

```cpp
auto upload(gpu::view::Device device, gpu::view::Buffer destination) -> gpu::expected<void>;

upload(device, vertex_buffer);        // both are owners; both convert
```

When a function wants *several* views, build the sequence with `as_views` (a `std::array`) or
`to_views` (a `dynarray`):

```cpp
queue.submit({ .command_buffers = gpu::as_views(command_buffer) });
```

**Creation is a static function returning `expected`.**

```cpp
auto sampler = gpu::Sampler::create(device, {});                 // gpu::expected<gpu::Sampler>
```

The first argument is the object's parent (an instance, a physical device or a device); the rest
describe what to create, usually as one aggregate you fill with designated initialisers. Throughout
this guide, `TryX(...)` unwraps the result or returns the error to the caller; in a `main`-level
function you would rather use `TryXAssert(..., "message")`.

Because owners are move-only and often created after their container, the examples store them in
[`defer_init<T>`](core.md#defer_init--construct-later-in-place) members.

---

## Start-up: instance, device, queue

```cpp
DiscardTryX(gpu::initialize_backend());                                              // 1

auto instance = TryX(gpu::Instance::create({ .application_name = "my-app" }));       // 2

const auto devices  = instance.physical_devices();                                   // 3
const auto best     = std::ranges::max_element(devices, {}, gpu::score_physical_device);
auto       physical = gpu::view::PhysicalDevice { *best };

auto device = TryX(gpu::Device::create(physical, {}));                               // 4

const auto entries = device.queue_entries();                                         // 5
const auto entry   = std::ranges::find_if(entries, gpu::monadic::find_queue<gpu::QueueFlag::GRAPHICS>());
ensures(entry != std::ranges::cend(entries), "no graphics queue");
auto queue = gpu::Queue::create(device, *entry);

auto pool = TryX(gpu::CommandPool::create(device, { .queue = queue }));              // 6
```

1. **Backend** — loads the Vulkan library. Once per process.
2. **Instance** — your connection to Vulkan. Validation layers are on by default in debug builds
   (`enable_validation_layers`).
3. **Physical device** — an actual GPU. `score_physical_device` ranks them; `info()` and
   `capabilities()` let you apply your own criteria.
4. **Device** — the logical device everything else is created from. It also owns the memory
   allocator.
5. **Queue** — where work is submitted. `find_queue<WANTED, UNWANTED…>` builds a predicate over the
   device's queue entries.
6. **Command pool** — the allocator for command buffers, tied to a queue.

Declare these in this order and they are destroyed in the right (reverse) order.

---

## Presenting: surface and swapchain

To draw into a window you need a **surface** (the window, as Vulkan sees it) and a **swapchain**
(the images that get shown).

```cpp
auto window = wsi::Window::open("my-app", { 1280u, 720u },
                                wsi::WindowFlag::DEFAULT | wsi::WindowFlag::EXTERNAL_CONTEXT);

auto surface   = TryX(gpu::Surface::create_from_window(instance, window));
auto swapchain = TryX(gpu::SwapChain::create(device, { .surface = surface, .extent = window.extent() }));
```

The swapchain owns a handful of images. To render into one you need an **image view** of it:

```cpp
auto views = dynarray<gpu::ImageView> {};
for (const auto& image : swapchain.images()) views.push_back(TryX(gpu::ImageView::create(device, { image })));
```

`swapchain.pixel_format()` is the format the surface settled on; pipelines that render to the
swapchain must be created for that format.

---

## Shaders and pipelines

### Shaders

A `gpu::Shader` is a SPIR-V module for one stage:

```cpp
auto vertex   = TryXAssert(gpu::Shader::load_from_file(device, "shaders/triangle.spv", gpu::ShaderStageFlag::VERTEX),   "vertex shader");
auto fragment = TryXAssert(gpu::Shader::load_from_file(device, "shaders/triangle.spv", gpu::ShaderStageFlag::FRAGMENT), "fragment shader");
```

The examples write shaders in NZSL and let the build compile them (the `compile.shaders` rule, see
the [build reference](../reference/build.md#shader-compilation)). One NZSL file holding a vertex
and a fragment entry point compiles to one `.spv`, loaded once per stage as above.
`load_from_bytes` loads SPIR-V that is already in memory.

### Pipeline layout

The layout lists what the shaders expect from the outside: descriptor sets and push constants.
A shader with neither has an empty one:

```cpp
auto layout = TryX(gpu::PipelineLayout::create(device, gpu::RasterPipelineLayout {}));
```

### Pipeline

A pipeline is the complete, immutable description of how primitives become pixels. Its state is
one aggregate, `RasterPipelineState`, where **every field has a sensible default** — you only
write what differs:

```cpp
const auto extent = window.extent();

const auto state = gpu::RasterPipelineState {
    .input_assembly_state = { .topology = gpu::PrimitiveTopology::TRIANGLE_LIST },
    .viewport_state       = { .viewports = { { .position = { 0.f, 0.f }, .extent = as<math::fextent2>(extent), .depth = { 0.f, 1.f } } },
                              .scissors  = { { .offset = { 0, 0 }, .extent = extent } } },
    .color_blend_state    = { .attachments = { {} } },              // one colour attachment, no blending
    .shader_state         = gpu::to_views(vertex, fragment),
};

auto pipeline = TryX(gpu::Pipeline::create(device, gpu::Pipeline::RasterizationCreateInfo {
    .state          = state,                 // held by reference: `state` must outlive this call
    .layout         = layout,
    .rendering_info = { .color_attachment_formats = { swapchain.pixel_format() } },
}));
```

(The in-tree examples spell the first member `as_ref(state)`, using a helper from the earlier
`core`.)

| State | You touch it to… |
| --- | --- |
| `input_assembly_state` | draw lines or points instead of triangles |
| `viewport_state` | set the drawing area (or leave empty and use dynamic state) |
| `rasterization_state` | change culling (`cull_mode`, `front_face`), draw wireframe (`polygon_mode`) |
| `multisample_state` | enable MSAA |
| `color_blend_state` | enable blending — one `attachments` entry per colour target |
| `depth_stencil_state` | enable depth testing |
| `vertex_input_state` | describe vertex buffers |
| `dynamic_state` | list state that is set at draw time (`DynamicState::VIEWPORT`, `SCISSOR`, …) |
| `shader_state` | the shader stages |

For alpha blending, set the factors explicitly — including `alpha_blend_operation`, whose default
is `SUBTRACT`:

```cpp
.color_blend_state = { .attachments = { { .blend_enable           = true,
                                         .src_color_blend_factor = gpu::BlendFactor::SRC_ALPHA,
                                         .dst_color_blend_factor = gpu::BlendFactor::ONE_MINUS_SRC_ALPHA,
                                         .src_alpha_blend_factor = gpu::BlendFactor::SRC_ALPHA,
                                         .dst_alpha_blend_factor = gpu::BlendFactor::ONE_MINUS_SRC_ALPHA,
                                         .alpha_blend_operation  = gpu::BlendOperation::ADD } } },
```

`rendering_info` names the formats of the attachments the pipeline will draw to. This is the
*dynamic rendering* path, which needs no render pass object. The classic path
(`RenderPass` + `FrameBuffer` + `LegacyRasterizationCreateInfo`) is also available:
[reference](../reference/gpu.md#render-passes-and-framebuffers).

---

## Command buffers

Nothing is drawn by calling a function. You **record** commands into a command buffer, then
**submit** the buffer to a queue.

```cpp
auto commands = TryX(pool.create_command_buffer());

DiscardTryX(commands.record([&](auto cmb) noexcept {
    cmb.begin_debug_region("frame")
       .begin_rendering(rendering_info)
       .bind_pipeline(pipeline)
       .draw(3)
       .end_rendering()
       .end_debug_region();
}));
```

`record` begins the buffer, runs your closure and ends it. Inside, every command returns the
buffer, so they chain. The closure receives a view; capture what you need by reference.

A command buffer is reusable: `reset()` empties it for the next frame.

### Where to render

`begin_rendering` takes a `RenderingInfo` naming the attachments:

```cpp
const auto extent = as<math::iextent2>(window.extent());

const auto rendering_info = gpu::RenderingInfo {
    .render_area       = { .x = 0, .y = 0, .width = extent.width, .height = extent.height },
    .color_attachments = { { .image_view  = views[image_index],
                             .clear_value = gpu::ClearColor { .color = colors::SILVER<f32> } } },
};
```

By default an attachment is cleared at the start (`load_op = CLEAR`) and kept at the end
(`store_op = STORE`).

### Image layouts

A Vulkan image is always in a *layout* that says what it may be used for, and you must move it
between layouts explicitly. A swapchain image is rendered to in `ATTACHMENT_OPTIMAL` and presented
in `PRESENT_SRC`:

```cpp
cmb.transition_image_layout(image, gpu::ImageLayout::PRESENT_SRC, gpu::ImageLayout::ATTACHMENT_OPTIMAL)
   .begin_rendering(rendering_info)
   /* draw */
   .end_rendering()
   .transition_image_layout(image, gpu::ImageLayout::ATTACHMENT_OPTIMAL, gpu::ImageLayout::PRESENT_SRC);
```

`transition_image_layout` works out the access masks and pipeline stages from the two layouts.
New images start in `UNDEFINED`.

---

## The frame loop

Rendering a frame is a relay between the CPU and the GPU:

1. **acquire** an image from the swapchain — signals a semaphore when the image is free;
2. **record and submit** commands that wait on that semaphore, and signal a second one when done;
3. **present** the image, waiting on the second semaphore.

A fence lets the CPU know when a submission has finished, so that it does not reuse a command
buffer the GPU is still reading.

```cpp
struct frame {
    gpu::Fence         in_flight;            // created signaled
    gpu::Semaphore     image_available;
    gpu::CommandBuffer commands;
};

auto render(frame& frame) -> gpu::expected<void> {
    TryX(frame.in_flight.wait());                                              // previous use finished?
    TryX(frame.in_flight.reset());

    const auto [status, index] = TryX(swapchain.acquire_next_image(100ms, frame.image_available));

    TryX(frame.commands.reset());
    TryX(frame.commands.record([&](auto cmb) noexcept { record_frame(cmb, index); }));

    static constexpr auto WAIT_STAGES = std::array { gpu::PipelineStageFlag::COLOR_ATTACHMENT_OUTPUT };
    TryX(frame.commands.submit(queue,
                               gpu::as_views(frame.image_available),           // wait for the image…
                               WAIT_STAGES,                                    // …before writing colour
                               gpu::as_views(render_finished[index]),          // signal when done
                               frame.in_flight));                              // and tell the CPU

    TryX(queue.present(gpu::as_views(swapchain), gpu::as_views(render_finished[index]), std::array { index }));
    Return {};
}
```

Keep two or three `frame` objects and alternate between them: the CPU can then prepare frame *N+1*
while the GPU still draws frame *N*. The "render finished" semaphores are per swapchain image.

The complete program is the [first triangle tutorial](../tutorials/vulkan-triangle.md).

At shutdown, let the GPU finish before objects are destroyed:

```cpp
DiscardTryX(queue.wait_idle());
DiscardTryX(device.wait_idle());
```

---

## Buffers

A `gpu::Buffer` is a block of memory the GPU can read: vertices, indices, uniform data, or a
staging area for uploads.

```cpp
struct vertex {
    math::fvec3 position;
    math::fvec2 uv;
};

auto vertices = TryX(gpu::Buffer::create(device, {
    .usages = gpu::BufferUsageFlag::VERTEX,
    .size   = sizeof(vertex) * std::ranges::size(mesh),
}));
TryX(vertices.upload(view_of(as_bytes, mesh)));
```

By default a buffer lives in memory the CPU can write to directly, and `upload` maps, copies and
unmaps in one go.

### Telling the pipeline about vertices

```cpp
.vertex_input_state = {
    .binding_descriptions         = { { .binding = 0, .stride = sizeof(vertex) } },
    .input_attribute_descriptions = {
        { .location = 0, .binding = 0, .format = gpu::PixelFormat::RGB32F, .offset = offsetof(vertex, position) },
        { .location = 1, .binding = 0, .format = gpu::PixelFormat::RG32F,  .offset = offsetof(vertex, uv) },
    },
},
```

One binding per buffer, one attribute per shader input; the format describes the attribute's type
(`RGB32F` is three floats).

### Drawing with them

```cpp
static constexpr auto OFFSETS = std::array { 0_u64 };

cmb.bind_pipeline(pipeline)
   .bind_vertex_buffers(gpu::as_views(vertices), OFFSETS)
   .draw(as<u32>(std::ranges::size(mesh)));

// indexed
cmb.bind_index_buffer(indices)                 // 16-bit indices; pass large_indices = true for 32-bit
   .draw_indexed(index_count);
```

### Data that changes every frame

For a uniform buffer rewritten each frame, map it once and keep the pointer:

```cpp
auto camera_buffer = TryX(gpu::Buffer::create(device, {
    .usages              = gpu::BufferUsageFlag::UNIFORM,
    .size                = sizeof(camera_data),
    .persistently_mapped = true,
}));

*camera_buffer.data_as<camera_data>() = camera;        // every frame, no map/unmap
```

Use one such buffer **per in-flight frame**, so that you never overwrite data the GPU is still
reading.

---

## Textures

Pixels reach the GPU in three steps: put them in a staging buffer, copy the buffer into an image,
and bring the image into the layout shaders read from.

```cpp
auto pixels = image::image {};
TryXAssert(pixels.load_from_file("textures/crate.png"), "texture file");
pixels = pixels.convert_to(image::image_format::RGBA8_UNORM);

auto texture = TryX(gpu::Image::create(device, {
    .extent = pixels.extent(),
    .format = gpu::PixelFormat::RGBA8_UNORM,
    .usages = gpu::ImageUsageFlag::SAMPLED | gpu::ImageUsageFlag::TRANSFER_DST,
}));

{
    auto staging = TryX(gpu::Buffer::create(device, { .usages = gpu::BufferUsageFlag::TRANSFER_SRC, .size = pixels.size() }));
    TryX(staging.upload(pixels.data()));

    auto done = TryX(gpu::Fence::create(device));
    auto copy = TryX(pool.create_command_buffer());

    TryX(copy.record([&](auto cmb) noexcept {
        const auto region = std::array { gpu::BufferImageCopy { .buffer_offset = 0, .buffer_row_length = 0, .buffer_image_height = 0,
                                                                .subresource_layers = {}, .offset = {}, .extent = pixels.extent() } };
        cmb.transition_image_layout(texture, gpu::ImageLayout::UNDEFINED, gpu::ImageLayout::TRANSFER_DST_OPTIMAL)
           .copy_buffer_to_image(staging, texture, region)
           .transition_image_layout(texture, gpu::ImageLayout::TRANSFER_DST_OPTIMAL, gpu::ImageLayout::SHADER_READ_ONLY_OPTIMAL);
    }));
    TryX(copy.submit(queue, {}, {}, {}, done));
    TryX(done.wait());                                   // the staging buffer may now be destroyed
}

auto texture_view = TryX(gpu::ImageView::create(device, { texture }));
auto sampler      = TryX(gpu::Sampler::create(device, {}));
```

- The image lives in GPU memory (`DEVICE_LOCAL` by default), which the CPU cannot write to —
  hence the staging buffer.
- A **sampler** says how the texture is read: filtering, wrapping, anisotropy. The default is
  linear filtering with repeat.
- `gpu::from_image(format)` maps a `stormkit.image` format to the matching `PixelFormat`.

---

## Descriptors: connecting data to shaders

A shader refers to its uniform buffers and textures by *binding number*. Descriptors are how you
say which actual buffer or image is behind each number.

```cpp
// 1. the shape: binding 0 is a uniform buffer for the vertex stage, binding 1 a texture for the fragment stage
auto set_layout = TryX(gpu::DescriptorSetLayout::create(device, {
    { .binding = 0, .type = gpu::DescriptorType::UNIFORM_BUFFER,         .stages = gpu::ShaderStageFlag::VERTEX,   .descriptor_count = 1 },
    { .binding = 1, .type = gpu::DescriptorType::COMBINED_IMAGE_SAMPLER, .stages = gpu::ShaderStageFlag::FRAGMENT, .descriptor_count = 1 },
}));

// 2. the pipeline layout references the shape
auto layout = TryX(gpu::PipelineLayout::create(device, { .descriptor_set_layouts = gpu::to_views(set_layout) }));

// 3. a pool to allocate sets from: how many descriptors of each type, how many sets in total
static constexpr auto POOL_SIZES = std::array {
    gpu::DescriptorPool::Size { .type = gpu::DescriptorType::UNIFORM_BUFFER,         .descriptor_count = 2 },
    gpu::DescriptorPool::Size { .type = gpu::DescriptorType::COMBINED_IMAGE_SAMPLER, .descriptor_count = 2 },
};
auto descriptor_pool = TryX(gpu::DescriptorPool::create(device, POOL_SIZES, 2));

// 4. a set, pointed at real resources
auto set = TryX(descriptor_pool.create_descriptor_set(set_layout));
set.update(std::array<gpu::Descriptor, 2> {
    gpu::BufferDescriptor { .binding = 0, .buffer = camera_buffer, .range = sizeof(camera_data) },
    gpu::ImageDescriptor  { .binding = 1, .layout = gpu::ImageLayout::SHADER_READ_ONLY_OPTIMAL, .image_view = texture_view, .sampler = sampler },
});

// 5. bound when drawing
cmb.bind_pipeline(pipeline)
   .bind_descriptor_sets(pipeline, layout, gpu::as_views(set))
   .draw(vertex_count);
```

As with uniform buffers, keep one set per in-flight frame when the data behind it changes per
frame.

For a few bytes that change per draw call (a model matrix, a colour), **push constants** avoid
descriptors altogether: declare a `PushConstantRange` in the pipeline layout and call
`cmb.push_constants(layout, stage, bytes_of(value))`.

---

## Depth testing

Add a depth image next to the colour attachment:

```cpp
auto depth = TryX(gpu::Image::create(device, {
    .extent = as<math::uextent3>(window.extent()),
    .format = gpu::PixelFormat::DEPTH32F,
    .usages = gpu::ImageUsageFlag::DEPTH_STENCIL_ATTACHMENT,
}));
auto depth_view = TryX(gpu::ImageView::create(device, {
    .image             = depth,
    .subresource_range = { .aspect_mask = gpu::ImageAspectFlag::DEPTH },
}));
```

then enable it in three places:

```cpp
// pipeline state
.depth_stencil_state = { .depth_test_enable = true, .depth_write_enable = true },

// pipeline rendering info
.rendering_info = { .color_attachment_formats = { swapchain.pixel_format() }, .depth_attachment_format = gpu::PixelFormat::DEPTH32F },

// per-frame rendering info
.depth_attachment = gpu::RenderingInfo::Attachment { .image_view = depth_view, .clear_value = gpu::ClearDepthStencil {} },
```

Not every GPU supports every depth format. `physical_device.formats_properties()` lists what is
available; look for `FormatFeatureFlag::DEPTH_STENCIL_ATTACHMENT` in `optimal_tiling_features`.

---

## Resizing

A swapchain has a fixed size. When the window is resized (or `present` / `acquire_next_image`
report `ERROR_OUT_OF_DATE` or `SUBOPTIMAL`), rebuild it:

```cpp
DiscardTryX(device.wait_idle());

views.clear();
swapchain = TryX(gpu::SwapChain::create(device, {
    .surface = surface,
    .extent  = window.extent(),
    .old     = swapchain.native_handle(),          // lets the driver recycle resources
}));
/* recreate the image views, and the depth image if any */
```

Pipelines that set their viewport statically must be rebuilt too. Listing
`DynamicState::VIEWPORT` and `DynamicState::SCISSOR` in `dynamic_state` and calling
`set_viewport` / `set_scissor` each frame avoids that.

Skip rendering entirely while the window is minimised: its extent is then zero.

---

## Debugging

**Validation layers** catch API misuse. Enable them on the instance and route their messages to
your logger:

```cpp
auto on_message(VkDebugUtilsMessageSeverityFlagBitsEXT severity, VkDebugUtilsMessageTypeFlagsEXT,
                const VkDebugUtilsMessengerCallbackDataEXT* data, void*) noexcept -> VkBool32 {
    if (severity >= VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT) log::logger::elog("{}", data->pMessage);
    else if (severity >= VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT) log::logger::wlog("{}", data->pMessage);
    else log::logger::dlog("{}", data->pMessage);
    return VK_FALSE;
}

auto instance = TryX(gpu::Instance::create({ .application_name = "my-app", .enable_validation_layers = true }));
auto debug    = TryX(gpu::DebugCallback::create(instance, { .messenger_closure = on_message }));
```

(The callback signature is Vulkan's, so this file needs `<stormkit/gpu/vulkan.hpp>` in its global
module fragment.)

**Names and regions** make captures in RenderDoc and validation messages readable:

```cpp
DiscardTryX(device.set_object_name(vertices, "terrain vertices"));

cmb.begin_debug_region("shadow pass").  /* … */  .end_debug_region();
```

**Raw Vulkan** is always within reach: every object has `native_handle()`, the device exposes its
function table (`device_table()`) and allocator (`allocator()`), and `gpu::vk` has helpers for
calling Vulkan functions with StormKit's error conventions.

Reference: [`stormkit.gpu`](../reference/gpu.md) · [enumerations](../reference/gpu-enums.md).

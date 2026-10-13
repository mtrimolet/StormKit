# Tutorial: your first triangle

**Libraries:** `wsi`, `gpu`, `log` (and `core`, `main`)

The traditional first GPU program: a window, and a coloured triangle in it. With Vulkan this is
famously long; with `stormkit.gpu` it is about two hundred lines, and every one of them maps to a
concept you need to know anyway.

The program is organised as one class with three functions, called in this order:

| Function | Does | Runs |
| --- | --- | --- |
| `init_gpu` | instance, device, queue, surface, swapchain | once |
| `init_resources` | shaders, pipeline, per-frame objects | once |
| `render_frame` | acquire → record → submit → present | every frame |

> `gpu` and `wsi` still use `PascalCase` names and have not yet been ported to the current `core`
> (see the [status note](../reference/gpu.md)). This tutorial is written against the declared
> interfaces and mirrors `examples/gpu/triangle`.

## Setting up

```console
> xmake f --wsi=y --gpu=y --devmode=y
```

`--devmode=y` makes the build define `SHADER_DIR`, the directory compiled shaders are written to,
so that the program can find them when run from the build tree.

```lua
-- examples/gpu/first-triangle/xmake.lua
add_requires("nzsl", { configs = { kind = "binary", fs_watcher = false } })

target("first-triangle", function()
    add_rules("stormkit::example", "compile.shaders")
    add_files("src/*.cpp", "shaders/*.nzsl")

    if get_config("devmode") then
        add_defines(format('SHADER_DIR="%s"', path.unix("$(builddir)/shaders")))
    end

    add_packages("nzsl")
    set_group("examples/stormkit-gpu")
end)
```

The `compile.shaders` rule compiles each `.nzsl` file to SPIR-V before the C++ sources
([build reference](../reference/build.md#shader-compilation)).

## The shader

`shaders/triangle.nzsl` — the shader of the in-tree `triangle` example, reused as is. The vertex
stage produces three hard-coded corners from the vertex index, and the fragment stage outputs
their interpolated colours. No vertex buffer is needed.

```rust
[nzsl_version("1.0")]

module Shader;

struct VertIn {
    [builtin(vertex_index)]
    vertex_id: i32
}

struct VertOut {
    [builtin(position)]
    position: vec4[f32],
    [location(0)]
    color: vec3[f32]
}

[entry(vert)]
fn vert_main(input: VertIn) -> VertOut {
    let output: VertOut;

    let position: vec2[f32];
    let color: vec3[f32];

    if (input.vertex_id == 0) {
        position = vec2[f32](1., 1.);
        color    = vec3[f32](1., 0., 0.);
    } else if (input.vertex_id == 1) {
        position = vec2[f32](-1., 1.);
        color    = vec3[f32](0., 1., 0.);
    } else if (input.vertex_id == 2) {
        position = vec2[f32](0., -1.);
        color    = vec3[f32](0., 0., 1.);
    }

    output.position = vec4[f32](position, 0., 1.);
    output.color    = color;

    return output;
}

struct FragOut {
    [location(0)]
    color: vec4[f32]
}

[entry(frag)]
fn frag_main(input: VertOut) -> FragOut {
    let output: FragOut;
    output.color = vec4[f32](input.color, 1.);

    return output;
}
```

Both entry points end up in one file, `triangle.spv`.

## The program

`src/main.cpp`. The `TryXAssert(expr, "message")` macro unwraps an `expected`, or stops the program
with the message and the error — appropriate here, where any failure is fatal.

```cpp
#include <stormkit/core/tryx_expected.hpp>

import std;
import stormkit;

#include <stormkit/main/main_macro.hpp>

using namespace stormkit;
using namespace stormkit::literals;
using namespace std::literals;

namespace {
    constexpr auto LOG             = log::module { "triangle" };
    constexpr auto FRAMES_IN_FLIGHT = 2_usize;
    const auto     SHADER          = std::filesystem::path { SHADER_DIR } / "triangle.spv";
}
```

### State

```cpp
struct frame_resources {                 // one per frame "in flight"
    gpu::Fence         in_flight;
    gpu::Semaphore     image_available;
    gpu::CommandBuffer commands;
};

struct swapchain_image {                 // one per swapchain image
    gpu::view::Image image;
    gpu::ImageView   view;
    gpu::Semaphore   render_finished;
};

class application {
  public:
    auto run() -> void;

  private:
    auto init_gpu() -> void;
    auto init_resources() -> void;
    auto render_frame() -> void;

    defer_init<wsi::Window>               m_window;
    defer_init<gpu::Instance>             m_instance;
    defer_init<gpu::Surface>              m_surface;
    defer_init<gpu::view::PhysicalDevice> m_physical_device;
    defer_init<gpu::Device>               m_device;
    defer_init<gpu::SwapChain>            m_swapchain;
    defer_init<gpu::Queue>                m_queue;
    defer_init<gpu::CommandPool>          m_command_pool;

    defer_init<gpu::Shader>         m_vertex_shader;
    defer_init<gpu::Shader>         m_fragment_shader;
    defer_init<gpu::PipelineLayout> m_pipeline_layout;
    defer_init<gpu::Pipeline>       m_pipeline;

    dynarray<frame_resources> m_frames;
    dynarray<swapchain_image> m_images;
    usize                     m_current_frame = 0;
};
```

Two things are doing quiet work here:

- **[`defer_init<T>`](../guides/core.md#defer_init--construct-later-in-place)** holds objects that
  have no default constructor and are created later, without a heap allocation. Access goes
  through `->` and `*`, and a `defer_init<gpu::X>` can be passed wherever a `gpu::view::X` is
  expected.
- **Declaration order is destruction order, reversed.** Members are listed in the order they are
  created, so the pipeline is destroyed before the device, the device before the instance, the
  surface before the window. No explicit teardown code is needed.

### `init_gpu` — the plumbing

```cpp
auto application::init_gpu() -> void {
    m_window = wsi::Window::open("First triangle", { 800_u32, 600_u32 },
                                 wsi::WindowFlag::DEFAULT | wsi::WindowFlag::EXTERNAL_CONTEXT);

    m_window->on<wsi::EventType::KEY_DOWN>([this](u8, wsi::Key key, char) noexcept {
        if (key == wsi::Key::ESCAPE) m_window->close();
    });

    DiscardTryXAssert(gpu::initialize_backend(), "failed to load Vulkan");

    m_instance = TryXAssert(gpu::Instance::create({ .application_name = "first-triangle" }), "failed to create the instance");
    m_surface  = TryXAssert(gpu::Surface::create_from_window(m_instance, m_window), "failed to create the surface");

    // pick the best GPU
    const auto devices = m_instance->physical_devices();
    ensures(not std::ranges::empty(devices), "no GPU found");

    const auto best   = std::ranges::max_element(devices, {}, [](const auto& d) { return gpu::score_physical_device(d); });
    m_physical_device = *best;
    LOG.ilog("using {}", *m_physical_device);

    m_device    = TryXAssert(gpu::Device::create(m_physical_device, {}), "failed to create the device");
    m_swapchain = TryXAssert(gpu::SwapChain::create(m_device, { gpu::as_view(m_surface), m_window->extent() }),
                             "failed to create the swapchain");

    const auto entries = m_device->queue_entries();
    const auto entry   = std::ranges::find_if(entries, gpu::monadic::find_queue<gpu::QueueFlag::GRAPHICS>());
    ensures(entry != std::ranges::cend(entries), "no graphics queue");

    m_queue        = gpu::Queue::create(m_device, *entry);
    m_command_pool = TryXAssert(gpu::CommandPool::create(m_device, { .queue = m_queue }), "failed to create the command pool");
}
```

This is the sequence from the [gpu guide](../guides/gpu.md#start-up-instance-device-queue):
backend → instance → (surface) → physical device → device → (swapchain) → queue → command pool.

- The window is created with `EXTERNAL_CONTEXT` because the GPU, not the window system, will draw
  into it.
- `score_physical_device` prefers discrete GPUs; on a laptop with two GPUs this picks the fast one.
- The swapchain is created at the window's size. This tutorial uses a fixed-size window; resizing
  is covered in the [guide](../guides/gpu.md#resizing).

### `init_resources` — what we draw with

```cpp
auto application::init_resources() -> void {
    m_vertex_shader   = TryXAssert(gpu::Shader::load_from_file(m_device, SHADER, gpu::ShaderStageFlag::VERTEX), "vertex shader");
    m_fragment_shader = TryXAssert(gpu::Shader::load_from_file(m_device, SHADER, gpu::ShaderStageFlag::FRAGMENT), "fragment shader");

    m_pipeline_layout = TryXAssert(gpu::PipelineLayout::create(m_device, gpu::RasterPipelineLayout {}), "pipeline layout");

    const auto extent = m_window->extent();
    const auto state  = gpu::RasterPipelineState {
        .input_assembly_state = { .topology = gpu::PrimitiveTopology::TRIANGLE_LIST },
        .viewport_state       = { .viewports = { { .position = { 0.f, 0.f }, .extent = as<math::fextent2>(extent), .depth = { 0.f, 1.f } } },
                                  .scissors  = { { .offset = { 0, 0 }, .extent = extent } } },
        .rasterization_state  = { .cull_mode = gpu::CullModeFlag::NONE },
        .color_blend_state    = { .attachments = { {} } },
        .shader_state         = gpu::to_views(m_vertex_shader, m_fragment_shader),
    };

    m_pipeline = TryXAssert(gpu::Pipeline::create(m_device,
                                                  gpu::Pipeline::RasterizationCreateInfo {
                                                    .state          = state,
                                                    .layout         = m_pipeline_layout,
                                                    .rendering_info = { .color_attachment_formats = { m_swapchain->pixel_format() } } }),
                            "pipeline");
```

The pipeline is where most of Vulkan's verbosity usually lives. Here it is a single aggregate in
which we set only what differs from the defaults:

- the **viewport and scissor** cover the window;
- **culling is off**, so the triangle shows whichever way its vertices are wound;
- there is **one colour attachment**, with default (opaque) blending — the `{}` inside
  `attachments`;
- the **two shader stages** are passed as views;
- `rendering_info` tells the pipeline the format it will render to: the swapchain's.

Next, the objects needed to submit frames:

```cpp
    for (auto _ : range(FRAMES_IN_FLIGHT)) {
        m_frames.push_back({
          .in_flight       = TryXAssert(gpu::Fence::create_signaled(m_device), "fence"),
          .image_available = TryXAssert(gpu::Semaphore::create(m_device), "semaphore"),
          .commands        = TryXAssert(m_command_pool->create_command_buffer(), "command buffer"),
        });
    }
```

- A **fence** per frame tells the CPU when the GPU has finished with that frame's command buffer.
  They are created *signaled* so that the very first wait returns at once.
- A **semaphore** per frame is signaled when the swapchain image we asked for is ready.
- A **command buffer** per frame, so that we can record frame *N+1* while frame *N* is still being
  executed.

And one view and one semaphore per swapchain image:

```cpp
    const auto images = m_swapchain->images();
    auto       setup  = TryXAssert(m_command_pool->create_command_buffers(std::ranges::size(images)), "setup command buffers");

    for (auto i : range(std::ranges::size(images))) {
        const auto& image = images[i];

        m_images.push_back({
          .image           = image,
          .view            = TryXAssert(gpu::ImageView::create(m_device, { image }), "image view"),
          .render_finished = TryXAssert(gpu::Semaphore::create(m_device), "semaphore"),
        });

        DiscardTryXAssert(setup[i].record([&](auto cmb) noexcept {
            cmb.transition_image_layout(image, gpu::ImageLayout::UNDEFINED, gpu::ImageLayout::PRESENT_SRC);
        }), "record");
    }

    const auto done = TryXAssert(gpu::Fence::create(m_device), "fence");
    const auto cmbs = gpu::to_views(setup);
    DiscardTryXAssert(m_queue->submit({ .command_buffers = cmbs }, done), "submit");
    DiscardTryXAssert(done.wait(), "wait");
}
```

Swapchain images start in the `UNDEFINED` layout. We move them all to `PRESENT_SRC` once, up
front, so that the frame loop can always assume "the image is in `PRESENT_SRC` when I get it". This
is also our first complete record → submit → wait cycle, in miniature.

### `render_frame` — sixty times a second

```cpp
auto application::render_frame() -> void {
    auto& frame = m_frames[m_current_frame];

    // 1. wait until the GPU is done with this frame's previous use
    DiscardTryXAssert(frame.in_flight.wait(), "wait");
    DiscardTryXAssert(frame.in_flight.reset(), "reset");

    // 2. which swapchain image do we draw into?
    const auto [status, index] = TryXAssert(m_swapchain->acquire_next_image(100ms, frame.image_available), "acquire");
    const auto& target         = m_images[index];

    // 3. record
    const auto extent         = as<math::iextent2>(m_window->extent());
    const auto rendering_info = gpu::RenderingInfo {
        .render_area       = { .x = 0, .y = 0, .width = extent.width, .height = extent.height },
        .color_attachments = { { .image_view = target.view, .clear_value = gpu::ClearColor { .color = colors::SILVER<f32> } } },
    };

    DiscardTryXAssert(frame.commands.reset(), "reset");
    DiscardTryXAssert(frame.commands.record([&](auto cmb) noexcept {
        cmb.transition_image_layout(target.image, gpu::ImageLayout::PRESENT_SRC, gpu::ImageLayout::ATTACHMENT_OPTIMAL)
           .begin_debug_region("triangle")
           .begin_rendering(rendering_info)
           .bind_pipeline(m_pipeline)
           .draw(3)
           .end_rendering()
           .end_debug_region()
           .transition_image_layout(target.image, gpu::ImageLayout::ATTACHMENT_OPTIMAL, gpu::ImageLayout::PRESENT_SRC);
    }), "record");

    // 4. submit: wait for the image, signal when rendered, signal the fence when done
    static constexpr auto WAIT_STAGES = std::array { gpu::PipelineStageFlag::COLOR_ATTACHMENT_OUTPUT };
    DiscardTryXAssert(frame.commands.submit(m_queue,
                                            gpu::as_views(frame.image_available),
                                            WAIT_STAGES,
                                            gpu::as_views(target.render_finished),
                                            frame.in_flight),
                      "submit");

    // 5. present once rendering has finished
    DiscardTryXAssert(m_queue->present(gpu::as_views(m_swapchain), gpu::as_views(target.render_finished), std::array { index }),
                      "present");

    m_current_frame = (m_current_frame + 1) % FRAMES_IN_FLIGHT;
}
```

The five steps, and how they are tied together:

```
 acquire ──signals──▶ image_available ──waited by──▶ submit ──signals──▶ render_finished ──waited by──▶ present
                                                        │
                                                        └──signals──▶ in_flight (fence) ──waited by──▶ next use of this frame
```

- **Semaphores** order GPU work against other GPU work, with no CPU involvement.
- The **fence** is the only point where the CPU waits, and it waits for the frame submitted *two
  frames ago*, not the one it just sent.
- Recording reads as a sentence: make the image a render target, clear it and start rendering,
  bind the pipeline, draw three vertices, stop, make the image presentable again.
- `draw(3)` with no vertex buffer bound works because the shader generates positions from the
  vertex index.

### `run` and `main`

```cpp
auto application::run() -> void {
    init_gpu();
    init_resources();

    m_window->event_loop([this] noexcept { render_frame(); });

    DiscardTryXAssert(m_queue->wait_idle(), "wait idle");
    DiscardTryXAssert(m_device->wait_idle(), "wait idle");
}

auto main(array_view<const string_view> args) -> int {
    wsi::parse_args(args);
    log::parse_args(args);
    auto logger = log::logger::create_logger_instance<log::console_logger>();

    auto app = application {};
    app.run();
    return 0;
}
```

`event_loop` calls `render_frame`, then processes window events, until the window closes. Before
returning we wait for the GPU to go idle: `app` is about to be destroyed, and destroying objects
the GPU is still using is an error.

## Build and run

```console
> xmake b stormkit::examples::first-triangle
> xmake run stormkit::examples::first-triangle
```

A window with a red, green and blue triangle on a silver background. Press Escape to quit.

## If something goes wrong

- **Nothing appears / validation errors.** Create the instance with
  `.enable_validation_layers = true` and register a `gpu::DebugCallback` that forwards messages to
  the logger ([guide](../guides/gpu.md#debugging)). Validation messages name the exact rule that
  was broken.
- **"failed to load Vulkan".** No Vulkan driver or loader is installed.
- **The shader is not found.** Check that the target was configured with `--devmode=y` (which
  defines `SHADER_DIR`), or load the `.spv` from wherever you install it.

## What to take away

| Concept | Object | Lifetime |
| --- | --- | --- |
| connection to Vulkan | `Instance` | program |
| the GPU and its logical handle | `PhysicalDevice`, `Device` | program |
| where work goes | `Queue`, `CommandPool` | program |
| where pixels go | `Surface`, `SwapChain`, `ImageView` | until resize |
| how to draw | `Shader`, `PipelineLayout`, `Pipeline` | program |
| what to do this frame | `CommandBuffer` | re-recorded every frame |
| ordering | `Semaphore` (GPU↔GPU), `Fence` (GPU→CPU) | reused every frame |

## Going further

- Put the vertices in a `gpu::Buffer` and describe them with `vertex_input_state`
  ([guide](../guides/gpu.md#buffers)).
- Handle resizing: recreate the swapchain and its views on `RESIZED`, and make the viewport dynamic.
- Continue with [textures and uniforms](textured-quad.md).

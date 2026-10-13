# `stormkit.gpu` reference

```cpp
import stormkit.gpu;      // or: import stormkit;
```

| | |
| --- | --- |
| Library | `stormkit-gpu` |
| xmake option | `gpu` (default: **off**; requires `log`, `image`, `wsi`) |
| Depends on | `stormkit.core`, `stormkit.log`, `stormkit.image`, `stormkit.wsi`; Vulkan headers 1.4, [volk](https://github.com/zeux/volk), [VulkanMemoryAllocator](https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator) |
| Namespace | `stormkit::gpu` |
| Header | `<stormkit/gpu/vulkan.hpp>` (only when touching raw Vulkan types) |

A typed, RAII, `expected`-returning layer over **Vulkan**. It keeps Vulkan's concepts and
vocabulary one-to-one; it removes handle lifetime management, `sType`/`pNext` boilerplate and
unchecked result codes.

`import stormkit.gpu;` re-exports three sub-modules:

| Sub-module | Contents |
| --- | --- |
| `stormkit.gpu.core` | backend initialisation, `Instance`, `PhysicalDevice`, `Device`, `Surface`, `DebugCallback`, `Fence`, `Semaphore`, plain structs, [enumerations](gpu-enums.md), Vulkan helpers |
| `stormkit.gpu.resource` | `Buffer`, `Image`, `ImageView`, `Sampler`, `Shader` |
| `stormkit.gpu.execution` | `Queue`, `CommandPool`, `CommandBuffer`, descriptors, pipelines, render passes, `SwapChain` |

> **Status.** This module still uses the `PascalCase` convention and is built on helpers from an
> earlier `stormkit.core` (`core::NamedConstructor`, `ref<T>`, `as_ref`, `DecoratedError`,
> `FLAG_ENUM`, the `LOGGER` macros) that the current core no longer provides. This page documents
> the interface declared under `modules/stormkit/gpu`. Expect names to change when it is migrated.

---

## Object model

Every Vulkan handle is wrapped twice:

| Form | Example | Semantics |
| --- | --- | --- |
| **Object** | `gpu::Buffer` | Owns the handle. Move-only. Destroys the handle in its destructor. |
| **View** | `gpu::view::Buffer` | Non-owning, cheap to copy. Refers to an object that must outlive it. |

Objects and views expose **the same member functions**. Functions *take* views and *return*
objects, so passing an object where a view is expected just works (implicit conversion), including
through `defer_init<T>`, `heap_ptr<T>` and other pointer-likes.

### Common interface

Every object and view provides:

| Member | Description |
| --- | --- |
| `native_handle()` | The raw Vulkan handle (`VkBuffer`, `VkDevice`, …). Also available through an implicit conversion. |
| `owner()` | View of the parent object (not on `Instance`). |
| `instance()` | For anything created from an instance or below. |
| `physical_device()` | For anything created from a physical device or below. |
| `device()` | For anything created from a device. |

### Creation

```cpp
static auto T::create(view::Owner owner, const T::CreateInfo& info) noexcept -> gpu::expected<T>;
static auto T::allocate(view::Owner owner, const T::CreateInfo& info) noexcept -> gpu::expected<heap_ptr<T>>;
```

- `create` returns the object by value; `allocate` returns it on the heap, for when a stable
  address is needed.
- The first argument is a view of the owner (an `Instance`, a `PhysicalDevice` or a `Device`).
- The remaining arguments are listed per type below; most take a single aggregate that you can
  write with designated initialisers.

Some types use different factory names (`Shader::load_from_file`, `Surface::create_from_window`,
`CommandPool::create_command_buffer`, …); they follow the same `create…` / `allocate…` pairing.

### Errors

```cpp
template<typename T> using expected = std::expected<T, Result>;      // gpu::expected
```

[`Result`](gpu-enums.md#result) mirrors `VkResult`. Failures are returned, never thrown. Functions
that can also report non-error statuses (`SUBOPTIMAL`, `TIMEOUT`, `NOT_READY`) return
`expected<Result>`.

Combine with the [`TryX` macros](macros.md#tryx-expression-macros):

```cpp
auto buffer = TryX(gpu::Buffer::create(device, { .usages = gpu::BufferUsageFlag::VERTEX, .size = size }));
```

### Views of several objects

```cpp
auto as_view(const T& value) noexcept;        // object, view, pointer-like or container element -> view
auto as_views(Ts&&... args) noexcept;         // -> array<View, N>
auto to_views(Ts&&... args) noexcept;         // -> dynarray<View>
auto to_views(const Range& range) noexcept;   // one view per element
```

Used to build the `array_view<const view::X>` parameters that many functions take:

```cpp
queue.present(gpu::as_views(swapchain), gpu::as_views(render_finished), std::array { image_index });
state.shader_state = gpu::to_views(vertex_shader, fragment_shader);
```

---

## `stormkit.gpu.core`

### Backend

```cpp
auto initialize_backend() -> expected<void>;
```

Loads the Vulkan loader library and its global entry points. **Call it once, before anything
else** in the module.

### `Instance`

```cpp
struct Instance::CreateInfo {
    string_view application_name;
    u32         application_version      = vk::make_version(0, 0, 0);
    bool        enable_validation_layers = /* true in debug builds */;
};

static auto Instance::create(const CreateInfo&) noexcept -> expected<Instance>;

auto extensions() const noexcept -> array_view<const string>;
auto physical_devices() const noexcept -> array_view<const PhysicalDevice>;
```

| Member | Description |
| --- | --- |
| `create(info)` | Creates the Vulkan instance with the surface extensions required by the platform, and enumerates the physical devices. |
| `extensions()` | The instance extensions that were enabled. |
| `physical_devices()` | The GPUs present. They are owned by the instance. |

### `PhysicalDevice`

Obtained from `Instance::physical_devices()`; never created directly.

```cpp
auto info() const noexcept -> const PhysicalDeviceInfo&;
auto capabilities() const noexcept -> const RenderCapabilities&;
auto memory_types() const noexcept -> array_view<const MemoryPropertyFlag>;
auto queue_families() const noexcept -> array_view<const QueueFamily>;
auto extensions() const noexcept -> array_view<const string>;
auto formats_properties() const noexcept -> array_view<const std::pair<PixelFormat, FormatProperties>>;

auto check_extension_support(string_view extension) const noexcept -> bool;
auto check_extension_support(array_view<const string_view> extensions) const noexcept -> std::optional<hash_set<string_view>>;
auto check_extension_support(array_view<const czstring> extensions) const noexcept -> std::optional<hash_set<string_view>>;

auto score_physical_device(view::PhysicalDevice physical_device) noexcept -> u64;      // free function
```

| Member | Description |
| --- | --- |
| `info()` | Name, vendor, API and driver versions, device type. |
| `capabilities()` | Supported features and limits (see [`RenderCapabilities`](#structures)). |
| `check_extension_support(name)` | Whether one device extension is available. |
| `check_extension_support(list)` | `nullopt` when all are available, otherwise the set of **missing** ones. |
| `score_physical_device(d)` | Heuristic score (discrete GPUs and larger limits score higher). Pick the device with the highest score. |

Physical devices are formattable.

### `Device`

```cpp
struct Device::CreateInfo {
    bool enable_swapchain  = true;
    bool enable_raytracing = false;
};

static auto Device::create(view::PhysicalDevice, const CreateInfo&) noexcept -> expected<Device>;

auto wait_idle() const noexcept -> expected<void>;
auto wait_for_fences(array_view<const view::Fence> fences, bool wait_all = true,
                     const std::chrono::milliseconds& timeout = std::chrono::milliseconds::max()) const noexcept -> expected<Result>;
auto wait_for_fence(view::Fence fence,
                    const std::chrono::milliseconds& timeout = std::chrono::milliseconds::max()) const noexcept -> expected<Result>;
auto reset_fences(array_view<const view::Fence> fences) const noexcept -> expected<void>;
auto reset_fence(view::Fence fence) const noexcept -> expected<void>;

template<meta::IsGpuObjectOrView T>
auto set_object_name(const T& object, string_view name) const noexcept -> expected<void>;
auto set_object_name(u64 object, DebugObjectType type, string_view name) const noexcept -> expected<void>;

auto queue_entries() const noexcept -> array_view<const QueueEntry>;
auto device_table() const noexcept -> const VolkDeviceTable&;
auto allocator() const noexcept -> vk::Observer<VmaAllocator>;
```

| Member | Description |
| --- | --- |
| `create(physical_device, info)` | Creates the logical device, its queues and the memory allocator. |
| `wait_idle()` | Blocks until all queues are idle. Call before destroying resources at shutdown. |
| `wait_for_fence(s)` | Returns `Result::SUCCESS` or `Result::TIMEOUT`. |
| `set_object_name(object, name)` | Attaches a debug name, visible in validation messages and tools such as RenderDoc. |
| `queue_entries()` | The queues the device exposes; feed one to [`Queue::create`](#queue). |
| `device_table()`, `allocator()` | Escape hatches: the volk function table and the VMA allocator. |

```cpp
struct QueueEntry { u32 id; u32 count; QueueFlag flags; };

namespace monadic {
    template<QueueFlag flag, QueueFlag... no_flag> constexpr auto find_queue() noexcept;
}
```

`monadic::find_queue<WANTED, UNWANTED...>()` builds a predicate over `QueueEntry` for
`std::ranges::find_if`: it matches an entry that has `WANTED` and none of the `UNWANTED` flags.

### `Surface`

```cpp
static auto Surface::create_from_window(view::Instance, const wsi::Window& window) noexcept -> expected<Surface>;
static auto Surface::allocate_from_window(view::Instance, const wsi::Window& window) noexcept -> expected<heap_ptr<Surface>>;
```

The link between an instance and a [`wsi::Window`](wsi.md#window). Create the window with
`wsi::WindowFlag::EXTERNAL_CONTEXT`. The surface must be destroyed before the window.

### `DebugCallback`

```cpp
struct DebugCallback::CreateInfo {
    PFN_vkDebugUtilsMessengerCallbackEXT messenger_closure;
    void*                                user_data = nullptr;
};

static auto DebugCallback::create(view::Instance, const CreateInfo&) noexcept -> expected<DebugCallback>;
```

Registers a `VK_EXT_debug_utils` messenger so that validation layer output reaches your code
(typically forwarded to a [logger](log.md)). Requires an instance created with
`enable_validation_layers = true`.

### `Fence` and `Semaphore`

```cpp
static auto Fence::create(view::Device) noexcept -> expected<Fence>;
static auto Fence::create_signaled(view::Device) noexcept -> expected<Fence>;
static auto Fence::allocate(view::Device) noexcept -> expected<heap_ptr<Fence>>;
static auto Fence::allocate_signaled(view::Device) noexcept -> expected<heap_ptr<Fence>>;

enum class Fence::Status { SIGNALED, UNSIGNALED };
auto status() const noexcept -> expected<Status>;
auto wait(const std::chrono::milliseconds& wait_for = std::chrono::milliseconds::max()) const noexcept -> expected<Result>;
auto reset() const noexcept -> expected<void>;

static auto Semaphore::create(view::Device) noexcept -> expected<Semaphore>;
```

| Type | Role |
| --- | --- |
| `Fence` | GPU → CPU synchronisation: the CPU waits for submitted work. `create_signaled` starts in the signaled state, which is what a per-frame "in flight" fence needs on the first frame. |
| `Semaphore` | GPU → GPU ordering between queue operations (acquire → render → present). It has no member functions; it is only passed to `submit`, `acquire_next_image` and `present`. |

### Structures

Plain aggregates used across the API.

| Struct | Fields |
| --- | --- |
| `Viewport` | `math::fvec2 position`, `math::fextent2 extent`, `math::fvec2 depth` (min, max) |
| `Scissor` | `math::ivec2 offset`, `math::uextent2 extent` |
| `ClearColor` | `fcolor_rgba color = colors::SILVER<f32>` |
| `ClearDepth` | `f32 depth = 1.f` |
| `ClearStencil` | `u32 stencil = 0` |
| `ClearDepthStencil` | `ClearDepth` + `ClearStencil` |
| `ClearValue` | `std::variant<ClearColor, ClearDepthStencil>` |
| `ImageSubresourceRange` | `aspect_mask = COLOR`, `base_mip_level = 0`, `level_count = 1`, `base_array_layer = 0`, `layer_count = 1` |
| `ImageSubresourceLayers` | `aspect_mask = COLOR`, `mip_level = 0`, `base_array_layer = 0`, `layer_count = 1` |
| `BufferImageCopy` | `buffer_offset`, `buffer_row_length`, `buffer_image_height`, `subresource_layers`, `math::ivec3 offset`, `math::uextent3 extent` |
| `BlitRegion` | `src`, `dst` (`ImageSubresourceLayers`), `src_offset`, `dst_offset` (each `{ ivec3 position; iextent3 extent; }`) |
| `MemoryBarrier` | `AccessFlag src`, `dst` |
| `PushConstantRange` | `ShaderStageFlag stages`, `u32 offset`, `usize size` |
| `SurfaceFormat` | `PixelFormat format`, `ColorSpace color_space` |
| `FormatProperties` | `linear_tiling_features`, `optimal_tiling_features`, `buffer_features` (`FormatFeatureFlag`) |
| `QueueFamily` | `QueueFlag flags`, `u32 count` |
| `PhysicalDeviceInfo` | `device_id`, `device_name`, `vendor_id`, `vendor_name`, `api_{major,minor,patch}_version`, `driver_{major,minor,patch}_version`, `pipeline_cache_uuid`, `PhysicalDeviceType type` |
| `RenderCapabilities` | `features` (one `bool` per `VkPhysicalDeviceFeatures` member, snake_case) and `limits` (one field per `VkPhysicalDeviceLimits` member, snake_case; some are `std::optional`) |

```cpp
using SpirvID = u32;

constexpr auto compute_mip_level(const math::uextent2& extent) noexcept -> u32;
constexpr auto compute_uniform_buffer_offset_align(usize size, const RenderCapabilities& capabilities) noexcept -> usize;
```

| Function | Description |
| --- | --- |
| `compute_mip_level(extent)` | Number of levels in a full mip chain for that size. |
| `compute_uniform_buffer_offset_align(size, caps)` | `size` rounded up to the device's `min_uniform_buffer_offset_alignment`. |

### Vulkan helpers

`namespace stormkit::gpu::vk`. For code that mixes StormKit objects with raw Vulkan calls.

| Name | Description |
| --- | --- |
| `make_version(major, minor, patch)`, `version_major`, `version_minor`, `version_patch` | Vulkan version packing. |
| `to_vk(value)`, `from_vk(value)` | Convert `Viewport`, `Scissor`, `math` extents / vectors / `irect` and `FormatProperties` to and from their `Vk*` equivalents. |
| `call(func, args...)` | Calls a Vulkan function; with an explicit `Out` type, supplies the trailing out-parameter and returns it. |
| `call_checked<...>(func, args...)` | Same, converting a non-success `VkResult` into an `expected` error. Extra accepted results are listed as template arguments. |
| `call_unchecked(func, args...)` | Same, ignoring the result. |
| `allocate[_checked\|_unchecked]<Out>(count, func, args...)` | For functions that fill `count` handles. |
| `enumerate[_checked\|_unchecked]<Out>(func, args...)` | Performs the Vulkan "count, then fill" double call and returns a `dynarray<Out>`. |
| `Owned<T>`, `Observer<T>` | Minimal owning / non-owning holders for raw handles that have no dedicated wrapper (`VmaAllocation`, …). `value()` returns the handle. |
| `monadic::to_vk()`, `monadic::from_vk()` | Closure forms for range pipelines. |
| `imgui_vk_loader(name, user)` | Function loader with the signature Dear ImGui's Vulkan backend expects. |

---

## `stormkit.gpu.resource`

### `Buffer`

```cpp
struct Buffer::CreateInfo {
    BufferUsageFlag    usages;
    usize              size;
    MemoryPropertyFlag properties          = MemoryPropertyFlag::HOST_VISIBLE | MemoryPropertyFlag::HOST_COHERENT;
    bool               persistently_mapped = false;
};

static auto Buffer::create(view::Device, const CreateInfo&) noexcept -> expected<Buffer>;

auto usages() const noexcept -> BufferUsageFlag;
auto size() const noexcept -> usize;
auto memory_properties() const noexcept -> MemoryPropertyFlag;
auto is_persistently_mapped() const noexcept -> bool;

auto map(ioffset offset) noexcept -> expected<byte*>;
auto map(ioffset offset, usize size) noexcept -> expected<array_view<byte>>;
template<typename T> auto map_as(ioffset offset) noexcept -> expected</* reference to T */>;
auto mapped() const noexcept -> bool;
auto data() noexcept -> byte*;                                  // const-propagating
auto data(usize size) noexcept -> array_view<byte>;
template<typename T> auto data_as() noexcept -> /* reference to T */;
auto flush(ioffset offset, usize size) const noexcept -> expected<void>;
auto unmap() noexcept -> void;

auto upload(array_view<const byte> data, ioffset offset = 0) noexcept -> expected<void>;
template<typename T> auto upload(const T& data, ioffset offset = 0) noexcept -> expected<void>;

auto allocation() const noexcept -> vk::Observer<VmaAllocation>;
```

| Member | Description |
| --- | --- |
| `create(device, info)` | Creates the buffer and allocates its memory through VMA. |
| `properties` | Defaults to CPU-visible memory. Use `DEVICE_LOCAL` for buffers that are only written through a transfer. |
| `persistently_mapped` | Maps once at creation and keeps the mapping; `data()` is then always valid. Typical for per-frame uniform buffers. |
| `map(offset[, size])` | Maps the memory. Pair with `unmap()`. |
| `data()`, `data_as<T>()` | The mapped address. Pre-condition: `mapped()`. |
| `flush(offset, size)` | Required after writing to memory that is not `HOST_COHERENT`. |
| `upload(bytes, offset)` | Map, copy, unmap in one call. The template overload uploads the bytes of any trivially copyable object. |

### `Image`

```cpp
struct Image::CreateInfo {
    math::uextent3     extent;
    PixelFormat        format     = PixelFormat::RGBA8_UNORM;
    u32                layers     = 1u;
    u32                mip_levels = 1u;
    ImageType          type       = ImageType::T2D;
    ImageCreateFlag    flags      = ImageCreateFlag::NONE;
    SampleCountFlag    samples    = SampleCountFlag::C1;
    ImageUsageFlag     usages     = ImageUsageFlag::SAMPLED | ImageUsageFlag::TRANSFER_DST | ImageUsageFlag::TRANSFER_SRC;
    ImageTiling        tiling     = ImageTiling::OPTIMAL;
    MemoryPropertyFlag properties = MemoryPropertyFlag::DEVICE_LOCAL;
};

static auto Image::create(view::Device, const CreateInfo&) noexcept -> expected<Image>;
static auto Image::from_existing(view::Device, const CreateInfo&, VkImage image) noexcept -> Image;

auto extent() const noexcept -> const math::uextent3&;
auto format() const noexcept -> PixelFormat;
auto type() const noexcept -> ImageType;
auto samples() const noexcept -> SampleCountFlag;
auto layers() const noexcept -> u32;
auto faces() const noexcept -> u32;
auto mip_levels() const noexcept -> u32;
auto usages() const noexcept -> ImageUsageFlag;
auto allocation() const noexcept -> vk::Observer<VmaAllocation>;
```

| Member | Description |
| --- | --- |
| `create(device, info)` | Creates the image and allocates device memory. The defaults describe a sampled 2D texture that can be the destination of an upload. |
| `from_existing(device, info, handle)` | Wraps an image the wrapper does not own (this is how swapchain images are exposed). |

An image starts in `ImageLayout::UNDEFINED`; change it with
[`CommandBuffer::transition_image_layout`](#commandbuffer).

### `ImageView`

```cpp
struct ImageView::CreateInfo {
    view::Image           image;
    ImageViewType         type              = ImageViewType::T2D;
    ImageSubresourceRange subresource_range = {};
};

static auto ImageView::create(view::Device, const CreateInfo&) noexcept -> expected<ImageView>;

auto type() const noexcept -> ImageViewType;
auto subresource_range() const noexcept -> const ImageSubresourceRange&;
```

What shaders and attachments actually bind. `ImageView::create(device, { image })` views the whole
colour image.

### `Sampler`

```cpp
struct Sampler::Settings {
    Filter             mag_filter = Filter::LINEAR,  min_filter = Filter::LINEAR;
    SamplerAddressMode address_mode_u = REPEAT, address_mode_v = REPEAT, address_mode_w = REPEAT;
    bool               enable_anisotropy = false;      f32 max_anisotropy = 0.f;
    BorderColor        border_color = BorderColor::INT_OPAQUE_BLACK;
    bool               unnormalized_coordinates = false;
    bool               compare_enable = false;         CompareOperation compare_operation = CompareOperation::ALWAYS;
    SamplerMipmapMode  mipmap_mode = SamplerMipmapMode::LINEAR;
    f32                mip_lod_bias = 0.f, min_lod = 0.f, max_lod = 0.f;
};

static auto Sampler::create(view::Device, const Settings&) noexcept -> expected<Sampler>;
auto settings() const noexcept -> const Settings&;
```

`Sampler::create(device, {})` gives trilinear filtering with repeat addressing.

### `Shader`

```cpp
static auto Shader::load_from_file(view::Device, const std::filesystem::path& filepath, ShaderStageFlag type) noexcept
  -> std::expected<Shader, Shader::LoadError>;
static auto Shader::load_from_bytes(view::Device, array_view<const byte> data, ShaderStageFlag type) noexcept -> expected<Shader>;
static auto Shader::load_from_spirv(view::Device, array_view<const SpirvID> data, ShaderStageFlag type) noexcept -> expected<Shader>;
// allocate_and_load_from_file / _bytes / _spirv return heap_ptr<Shader>

auto type() const noexcept -> ShaderStageFlag;
auto source() const noexcept -> array_view<const SpirvID>;
auto source_as_bytes() const noexcept -> array_view<const byte>;
```

A SPIR-V module for one stage.

| Member | Description |
| --- | --- |
| `load_from_file` | Reads a `.spv` file. Its error is a variant: an I/O error, a Vulkan `Result`, or `Shader::Error::INVALID_SPIRV`. |
| `load_from_bytes`, `load_from_spirv` | From memory (for instance shaders embedded in the executable). |
| `type()` | The stage given at load time. A single SPIR-V file containing several entry points is loaded once per stage. |

StormKit's examples write shaders in [NZSL](https://github.com/NazaraEngine/ShaderLang); the build
compiles them to SPIR-V (see [build reference](build.md#shader-compilation)). Any SPIR-V producer
works.

---

## `stormkit.gpu.execution`

### `Queue`

```cpp
static auto Queue::create(view::Device, const QueueEntry& entry) noexcept -> Queue;

struct Queue::SubmitInfo {
    array_view<const view::Semaphore>     wait_semaphores   = {};
    array_view<const PipelineStageFlag>   wait_dst_stages   = {};
    array_view<const view::CommandBuffer> command_buffers   = {};
    array_view<const view::Semaphore>     signal_semaphores = {};
};

auto wait_idle() const noexcept -> expected<void>;
auto submit(const SubmitInfo& submit_info, std::optional<view::Fence> fence = std::nullopt) const noexcept -> expected<void>;
auto submit(array_view<const SubmitInfo> submit_infos, std::optional<view::Fence> fence = std::nullopt) const noexcept -> expected<void>;
auto present(array_view<const view::SwapChain> swapchains, array_view<const view::Semaphore> wait_semaphores,
             array_view<const u32> image_indices) const noexcept -> expected<Result>;
auto entry() const noexcept -> const QueueEntry&;
```

| Member | Description |
| --- | --- |
| `create(device, entry)` | Retrieves the queue described by one of `Device::queue_entries()`. Cannot fail. |
| `submit(info, fence)` | Submits command buffers. `wait_dst_stages[i]` is the stage at which `wait_semaphores[i]` is waited on. The optional fence is signaled on completion. |
| `present(...)` | Presents `image_indices[i]` of `swapchains[i]`. May return `Result::SUBOPTIMAL`; an out-of-date swapchain is reported as an error. |

### `CommandPool`

```cpp
struct CommandPool::CreateInfo {
    view::Queue queue;
    bool        reset     = true;      // buffers can be reset individually
    bool        transient = false;     // buffers are short-lived
};

static auto CommandPool::create(view::Device, const CreateInfo&) noexcept -> expected<CommandPool>;

auto create_command_buffer(CommandBufferLevel level = CommandBufferLevel::PRIMARY) const noexcept -> expected<CommandBuffer>;
auto create_command_buffers(usize count, CommandBufferLevel level = CommandBufferLevel::PRIMARY) const noexcept
  -> expected<dynarray<CommandBuffer>>;
auto allocate_command_buffer(CommandBufferLevel level = CommandBufferLevel::PRIMARY) const noexcept -> expected<heap_ptr<CommandBuffer>>;
auto allocate_command_buffers(usize count, CommandBufferLevel level = CommandBufferLevel::PRIMARY) const noexcept
  -> expected<dynarray<heap_ptr<CommandBuffer>>>;
```

Command buffers are created from a pool and returned to it when destroyed. A pool, and the buffers
made from it, must only be used from one thread at a time.

### `CommandBuffer`

```cpp
enum class CommandBuffer::State { INITIAL, RECORDING, EXECUTABLE };
using CommandBuffer::RecordClosure = std23::function_ref<void(view::CommandBuffer)>;

auto state() const noexcept -> State;
auto level() const noexcept -> CommandBufferLevel;

auto record(RecordClosure closure, bool one_time_submit = false, InheritanceInfo inheritance_info = {}) noexcept -> expected<void>;
auto begin(bool one_time_submit = false, InheritanceInfo inheritance_info = {}) noexcept -> expected<void>;
auto end() noexcept -> expected<void>;
auto reset() noexcept -> expected<void>;

auto submit(view::Queue queue,
            array_view<const view::Semaphore>   wait_semaphores   = {},
            array_view<const PipelineStageFlag> wait_dst_stages   = {},
            array_view<const view::Semaphore>   signal_semaphores = {},
            std::optional<view::Fence>          fence             = std::nullopt) noexcept -> expected<void>;
```

| Member | Description |
| --- | --- |
| `record(closure)` | `begin()`, invoke `closure` with a view of the buffer, `end()`. The preferred way to record. |
| `begin` / `end` | Manual bracketing. `one_time_submit` hints that the buffer is submitted once then reset. `inheritance_info` is for secondary buffers. |
| `reset()` | Returns the buffer to `INITIAL`. The pool must have been created with `reset = true`. |
| `submit(queue, ...)` | Shorthand for `queue.submit({ ... this buffer ... }, fence)`. |

**Recording commands** all return `const CommandBuffer&` and can be **chained**:

```cpp
cmb.record([&](auto cmb) noexcept {
    cmb.begin_debug_region("Render triangle")
       .begin_rendering(rendering_info)
       .bind_pipeline(pipeline)
       .draw(3)
       .end_rendering()
       .end_debug_region();
});
```

| Group | Commands |
| --- | --- |
| Debug | `begin_debug_region(name, color = WHITE)`, `insert_debug_label(name, color = WHITE)`, `end_debug_region()` |
| Dynamic rendering | `begin_rendering(const RenderingInfo&, bool secondary_commandbuffers = false)`, `end_rendering()` |
| Render passes | `begin_render_pass(view::RenderPass, view::FrameBuffer, array_view<const ClearValue> clear_values = { SILVER }, bool secondary_commandbuffers = false)`, `next_subpass()`, `end_render_pass()` |
| Binding | `bind_pipeline(view::Pipeline)`, `bind_vertex_buffers(buffers, offsets)`, `bind_index_buffer(buffer, u64 offset = 0, bool large_indices = false)`, `bind_descriptor_sets(pipeline, layout, descriptor_sets, dynamic_offsets = {})`, `push_constants(layout, ShaderStageFlag stage, array_view<const byte> data, u32 offset = 0)` |
| Dynamic state | `set_viewport(first, viewports)`, `set_scissor(first, scissors)`, `set_line_width(width)`, `set_depth_bias(constant_factor, clamp, slope_factor)`, `set_blend_constants(constants)`, `set_depth_bounds(min, max)`, `set_stencil_compare_mask(face, mask)`, `set_stencil_write_mask(face, mask)`, `set_stencil_reference(face, reference)` |
| Drawing | `draw(vertex_count, instance_count = 1, first_vertex = 0, first_instance = 0)`, `draw_indexed(index_count, instance_count = 1, first_index = 0, vertex_offset = 0, first_instance = 0)`, `draw_indirect(buffer, offset, draw_count, stride)`, `draw_indexed_indirect(buffer, offset, draw_count, stride)` |
| Compute | `dispatch(group_count_x, group_count_y, group_count_z)` |
| Copies | `copy_buffer(src, dst, size, src_offset = 0, dst_offset = 0)`, `copy_buffer_to_image(src, dst, regions = {})`, `copy_image_to_buffer(src, dst, regions = {})`, `copy_image(src, dst, src_layout, dst_layout, src_layers, dst_layers, extent)`, `resolve_image(src, dst, src_layout, dst_layout, src_layers = {}, dst_layers = {})`, `blit_image(src, dst, src_layout, dst_layout, regions, filter)` |
| Synchronisation | `transition_image_layout(image, src_layout, dst_layout, subresource_range = {})`, `pipeline_barrier(src_mask, dst_mask, dependency, memory_barriers, buffer_memory_barriers, image_memory_barriers)` |
| Secondary buffers | `execute_sub_command_buffers(commandbuffers)` |

Notes:

- `bind_index_buffer`: `large_indices = false` means 16-bit indices, `true` 32-bit.
- `copy_buffer_to_image` / `copy_image_to_buffer` with no region copy the whole first mip level.
- `transition_image_layout` derives the access masks and pipeline stages from the two layouts; use
  `pipeline_barrier` when you need full control.

**Rendering description** (dynamic rendering, no render pass object):

```cpp
struct RenderingInfo {
    struct Attachment {
        struct Resolve { view::ImageView image_view; ResolveModeFlag mode; ImageLayout layout = ImageLayout::ATTACHMENT_OPTIMAL; };

        view::ImageView           image_view;
        ImageLayout               layout      = ImageLayout::ATTACHMENT_OPTIMAL;
        std::optional<Resolve>    resolve     = std::nullopt;
        AttachmentLoadOperation   load_op     = AttachmentLoadOperation::CLEAR;
        AttachmentStoreOperation  store_op    = AttachmentStoreOperation::STORE;
        std::optional<ClearValue> clear_value = std::nullopt;
    };

    math::irect               render_area;
    u32                       layer_count = 1u;
    u32                       view_mask   = 0u;
    dynarray<Attachment>      color_attachments  = {};
    std::optional<Attachment> depth_attachment   = std::nullopt;
    std::optional<Attachment> stencil_attachment = std::nullopt;
};
```

**Inheritance** (secondary command buffers):

```cpp
struct RenderPassInheritanceInfo { std::optional<view::RenderPass> render_pass; u32 subpass = 0; std::optional<view::FrameBuffer> framebuffer; };
struct RenderingInheritanceInfo  { u32 view_mask = 0; dynarray<PixelFormat> color_attachments; std::optional<PixelFormat> depth_attachment, stencil_attachment;
                                   SampleCountFlag rasterization_samples = SampleCountFlag::C1; };
using InheritanceInfo = std::variant<std::monostate, RenderPassInheritanceInfo, RenderingInheritanceInfo>;
```

**Barriers**:

```cpp
struct BufferMemoryBarrier { AccessFlag src, dst; u32 src_queue_family_index = QUEUE_FAMILY_IGNORED, dst_queue_family_index = QUEUE_FAMILY_IGNORED;
                             view::Buffer buffer; usize size; u64 offset = 0; };
struct ImageMemoryBarrier  { AccessFlag src, dst; ImageLayout old_layout, new_layout;
                             u32 src_queue_family_index = QUEUE_FAMILY_IGNORED, dst_queue_family_index = QUEUE_FAMILY_IGNORED;
                             view::Image image; ImageSubresourceRange range; };
```

### Descriptors

```cpp
struct DescriptorSetLayoutBinding { u32 binding; DescriptorType type; ShaderStageFlag stages; usize descriptor_count; };

static auto DescriptorSetLayout::create(view::Device, dynarray<DescriptorSetLayoutBinding> bindings) noexcept -> expected<DescriptorSetLayout>;
auto DescriptorSetLayout::bindings() const noexcept -> array_view<const DescriptorSetLayoutBinding>;

struct DescriptorPool::Size { DescriptorType type; u32 descriptor_count; };      // also spelled DescriptorSetLayout::Size
static auto DescriptorPool::create(view::Device, array_view<const DescriptorPool::Size> sizes, u32 max_sets) noexcept
  -> expected<DescriptorPool>;

auto DescriptorPool::create_descriptor_set(view::DescriptorSetLayout layout) noexcept -> expected<DescriptorSet>;
auto DescriptorPool::create_descriptor_sets(usize count, view::DescriptorSetLayout layout) noexcept -> expected<dynarray<DescriptorSet>>;
auto DescriptorPool::allocate_descriptor_set(view::DescriptorSetLayout layout) noexcept -> expected<heap_ptr<DescriptorSet>>;
auto DescriptorPool::allocate_descriptor_sets(usize count, view::DescriptorSetLayout layout) noexcept
  -> expected<dynarray<heap_ptr<DescriptorSet>>>;

struct BufferDescriptor { DescriptorType type = DescriptorType::UNIFORM_BUFFER; u32 binding; view::Buffer buffer;
                          std::optional<u32> range = std::nullopt; u32 offset = 0; };
struct ImageDescriptor  { DescriptorType type = DescriptorType::COMBINED_IMAGE_SAMPLER; u32 binding; ImageLayout layout;
                          view::ImageView image_view; view::Sampler sampler; };
using Descriptor = std::variant<BufferDescriptor, ImageDescriptor>;

auto DescriptorSet::update(array_view<const Descriptor> descriptors) const noexcept -> void;
```

| Type | Role |
| --- | --- |
| `DescriptorSetLayout` | The *shape* of a set: which binding holds what, visible to which stages. |
| `DescriptorPool` | Fixed-capacity allocator of sets: `sizes` gives the total number of descriptors per type, `max_sets` the number of sets. |
| `DescriptorSet` | An instance of a layout. `update` points its bindings at actual buffers and images. |
| `BufferDescriptor::range` | Byte range bound; the whole buffer when `nullopt`. |

```cpp
auto layout = TryX(gpu::DescriptorSetLayout::create(device, {
    { .binding = 0, .type = gpu::DescriptorType::UNIFORM_BUFFER,         .stages = gpu::ShaderStageFlag::VERTEX,   .descriptor_count = 1 },
    { .binding = 1, .type = gpu::DescriptorType::COMBINED_IMAGE_SAMPLER, .stages = gpu::ShaderStageFlag::FRAGMENT, .descriptor_count = 1 },
}));
auto pool = TryX(gpu::DescriptorPool::create(device, std::array {
    gpu::DescriptorPool::Size { gpu::DescriptorType::UNIFORM_BUFFER, 1 },
    gpu::DescriptorPool::Size { gpu::DescriptorType::COMBINED_IMAGE_SAMPLER, 1 },
}, 1));
auto set = TryX(pool.create_descriptor_set(layout));

set.update(std::array<gpu::Descriptor, 2> {
    gpu::BufferDescriptor { .binding = 0, .buffer = camera_buffer },
    gpu::ImageDescriptor  { .binding = 1, .layout = gpu::ImageLayout::SHADER_READ_ONLY_OPTIMAL, .image_view = texture_view, .sampler = sampler },
});
```

### Pipelines

```cpp
struct RasterPipelineLayout {
    dynarray<view::DescriptorSetLayout> descriptor_set_layouts = {};
    dynarray<PushConstantRange>         push_constant_ranges   = {};
};

static auto PipelineLayout::create(view::Device, const RasterPipelineLayout&) noexcept -> expected<PipelineLayout>;
auto PipelineLayout::raster_layout() const noexcept -> const RasterPipelineLayout&;

static auto PipelineCache::load_from_file(view::Device, stdfs::path cache_path) noexcept -> /* expected<PipelineCache, LoadSaveError> */;

struct Pipeline::RasterizationCreateInfo {            // dynamic rendering
    /* reference to */ const RasterPipelineState& state;
    view::PipelineLayout                          layout;
    RasterPipelineRenderingInfo                   rendering_info;
    std::optional<view::PipelineCache>            cache = std::nullopt;
};
struct Pipeline::LegacyRasterizationCreateInfo {      // render pass
    /* reference to */ const RasterPipelineState& state;
    view::PipelineLayout                          layout;
    view::RenderPass                              render_pass;
    std::optional<view::PipelineCache>            cache = std::nullopt;
};

static auto Pipeline::create(view::Device, const RasterizationCreateInfo&) noexcept -> expected<Pipeline>;
static auto Pipeline::create(view::Device, const LegacyRasterizationCreateInfo&) noexcept -> expected<Pipeline>;

enum class Pipeline::Type { RASTER, COMPUTE, RAYTRACING };
auto Pipeline::type() const noexcept -> Type;
auto Pipeline::raster_state() const noexcept -> const RasterPipelineState&;
```

| Type | Role |
| --- | --- |
| `PipelineLayout` | The descriptor set layouts and push constant ranges a pipeline's shaders expect. |
| `PipelineCache` | Persists compiled pipeline state between runs; loaded from (and saved back to) a file. |
| `Pipeline` | A complete, immutable rendering configuration. Only raster pipelines can be created today; `COMPUTE` and `RAYTRACING` are reserved. |

The `state` member of the create infos is a non-owning reference: the `RasterPipelineState` must
be alive during `create`.

**`RasterPipelineState`** and its parts (all aggregates with defaults):

| Member | Type | Fields (defaults) |
| --- | --- | --- |
| `input_assembly_state` | `RasterPipelineInputAssemblyState` | `topology = TRIANGLE_LIST`, `primitive_restart_enable = false` |
| `viewport_state` | `RasterPipelineViewportState` | `dynarray<Viewport> viewports`, `dynarray<Scissor> scissors` |
| `rasterization_state` | `RasterPipelineRasterizationState` | `depth_clamp_enable = false`, `rasterizer_discard_enable = false`, `polygon_mode = FILL`, `line_width = 1`, `cull_mode = BACK`, `front_face = CLOCKWISE`, `depth_bias_enable = false`, `depth_bias_constant_factor = 0`, `depth_bias_clamp = 0`, `depth_bias_slope_factor = 0` |
| `multisample_state` | `RasterPipelineMultiSampleState` | `sample_shading_enable = false`, `rasterization_samples = C1`, `min_sample_shading = 0` |
| `color_blend_state` | `RasterPipelineColorBlendState` | `logic_operation_enable = false`, `logic_operation = COPY`, `dynarray<RasterPipelineColorBlendAttachmentState> attachments`, `blend_constants = { 0, 0, 0, 0 }` |
| `dynamic_state` | `RasterPipelineDynamicState` | `dynarray<DynamicState>` — state set per draw with the `set_*` commands |
| `shader_state` | `RasterPipelineShaderState` | `dynarray<view::Shader>` |
| `vertex_input_state` | `RasterPipelineVertexInputState` | `dynarray<VertexBindingDescription> binding_descriptions`, `dynarray<VertexInputAttributeDescription> input_attribute_descriptions` |
| `depth_stencil_state` | `RasterPipelineDepthStencilState` | `depth_test_enable = false`, `depth_write_enable = false`, `depth_compare_op = LESS`, `depth_bounds_test_enable = false`, `min_depth_bounds = 0`, `max_depth_bounds = 1` |

| Struct | Fields (defaults) |
| --- | --- |
| `RasterPipelineColorBlendAttachmentState` | `color_write_mask = RGBA`, `blend_enable = false`, `src_color_blend_factor = ONE`, `dst_color_blend_factor = ZERO`, `color_blend_operation = ADD`, `src_alpha_blend_factor = ONE`, `dst_alpha_blend_factor = ZERO`, `alpha_blend_operation = SUBTRACT` |
| `VertexBindingDescription` | `u32 binding`, `u32 stride`, `input_rate = VERTEX` |
| `VertexInputAttributeDescription` | `u32 location`, `u32 binding`, `PixelFormat format`, `u32 offset` |
| `RasterPipelineRenderingInfo` | `view_mask = 0`, `dynarray<PixelFormat> color_attachment_formats`, `std::optional<PixelFormat> depth_attachment_format`, `stencil_attachment_format` |

One `color_blend_state.attachments` entry is needed per colour attachment. Note the default
`alpha_blend_operation` is `SUBTRACT`; set it explicitly when enabling blending.

### Render passes and framebuffers

The classic (pre dynamic rendering) path.

```cpp
struct AttachmentDescription {
    PixelFormat              format;
    SampleCountFlag          samples            = SampleCountFlag::C1;
    AttachmentLoadOperation  load_op            = AttachmentLoadOperation::CLEAR;
    AttachmentStoreOperation store_op           = AttachmentStoreOperation::STORE;
    AttachmentLoadOperation  stencil_load_op    = AttachmentLoadOperation::DONT_CARE;
    AttachmentStoreOperation stencil_store_op   = AttachmentStoreOperation::DONT_CARE;
    ImageLayout              source_layout      = ImageLayout::UNDEFINED;
    ImageLayout              destination_layout = ImageLayout::PRESENT_SRC;
    bool                     resolve            = false;
};
struct Subpass {
    struct Ref { u32 attachment_id; ImageLayout layout = ImageLayout::COLOR_ATTACHMENT_OPTIMAL; };
    PipelineBindPoint  bind_point;
    dynarray<Ref>      color_attachment_refs   = {};
    dynarray<Ref>      resolve_attachment_refs = {};
    std::optional<Ref> depth_attachment_ref    = {};
};
struct RenderPassDescription {
    dynarray<AttachmentDescription> attachments;
    dynarray<Subpass>               subpasses;
    auto is_compatible(const RenderPassDescription& description) const noexcept -> bool;
};

static auto RenderPass::create(view::Device, const RenderPassDescription&) noexcept -> expected<RenderPass>;

auto RenderPass::create_framebuffer(view::Device device, const math::uextent2& extent,
                                    dynarray<view::ImageView> attachments) noexcept -> expected<FrameBuffer>;
auto RenderPass::allocate_framebuffer(...) noexcept -> expected<heap_ptr<FrameBuffer>>;
auto RenderPass::is_compatible(view::RenderPass render_pass) const noexcept -> bool;
auto RenderPass::is_compatible(const RenderPassDescription& description) const noexcept -> bool;
auto RenderPass::description() const noexcept -> const RenderPassDescription&;

auto FrameBuffer::extent() const noexcept -> const math::uextent2&;
auto FrameBuffer::attachments() const noexcept -> array_view<const view::ImageView>;
```

| Type | Role |
| --- | --- |
| `RenderPass` | Declares the attachments and subpasses of a rendering operation. |
| `FrameBuffer` | Binds actual image views to a render pass, for a given extent. Created from the render pass. |
| `is_compatible` | Whether a pipeline built for one render pass can be used with another. |

Use with `Pipeline::LegacyRasterizationCreateInfo` and
`CommandBuffer::begin_render_pass` / `end_render_pass`.

### `SwapChain`

```cpp
struct SwapChain::CreateInfo {
    view::Surface  surface;
    math::uextent2 extent;
    VkSwapchainKHR old = VK_NULL_HANDLE;
};
struct SwapChain::NextImage { Result result; u32 id; };

static auto SwapChain::create(view::Device, const CreateInfo&) noexcept -> expected<SwapChain>;

auto pixel_format() const noexcept -> PixelFormat;
auto images() const noexcept -> array_view<const Image>;
auto acquire_next_image(std::chrono::nanoseconds wait, view::Semaphore image_available) const noexcept -> expected<NextImage>;
```

| Member | Description |
| --- | --- |
| `create(device, info)` | Creates the chain of presentable images for a surface. Pass the previous chain's `native_handle()` as `old` when re-creating after a resize. |
| `pixel_format()` | The format the surface chose; use it for pipelines and image views. |
| `images()` | The presentable images. Create one `ImageView` per image. |
| `acquire_next_image(timeout, semaphore)` | Index of the next image to render to; `semaphore` is signaled when it is ready. `result` may be `SUBOPTIMAL`. |

---

## Lifetime rules

1. `initialize_backend()` first.
2. Destroy in reverse order of creation: resources and pipelines → swapchain → device → surface →
   debug callback → instance → window. Declaring members in creation order gives this for free.
3. Before destroying anything in use by the GPU, `queue.wait_idle()` / `device.wait_idle()`.
4. Views never extend lifetimes.

See the [gpu guide](../guides/gpu.md) for a complete frame loop.

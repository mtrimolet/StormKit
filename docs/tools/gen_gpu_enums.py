#!/usr/bin/env python3
"""Regenerates docs/reference/gpu-enums.md from the gpu enumeration module.

Usage (from the repository root):

    python docs/tools/gen_gpu_enums.py
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / "modules" / "stormkit" / "gpu" / "core" / "vulkan" / "enums.cppm"
OUTPUT = ROOT / "docs" / "reference" / "gpu-enums.md"

PIPE = chr(124)
ESCAPED_PIPE = chr(92) + PIPE

HEADER = """# `stormkit.gpu` reference — enumerations

Part of the [`stormkit.gpu` reference](gpu.md).

All enumerations live in `namespace stormkit::gpu` and are declared in the generated file
`modules/stormkit/gpu/core/vulkan/enums.cppm` (produced from `enums.cppm.tpl` and `mapping.json`;
do not edit it by hand). Each enumerator has the numeric value of the Vulkan constant shown next to
it, so conversion to and from Vulkan is a cast: `gpu::to_vk<VkFormat>(value)` / `gpu::from_vk<gpu::PixelFormat>(vk_value)`.

Enumerations whose name ends in `Flag` are bit masks: combine them with `|` and test them with
`has_flag_bit` (see [flags](core-typesafe.md#stormkitcoretypesafeflags)). Every enumeration is
formattable and has a `stormkit::meta::enumerate<E>()` specialisation returning all its enumerators.

Helper functions declared alongside the enumerations:

| Function | Description |
| --- | --- |
| `to_vk<VkType>(value)`, `from_vk<Enum>(vk_value)` | Cast between a StormKit enumeration and its Vulkan counterpart. |
| `from_image(image_format)` | The `PixelFormat` matching a `stormkit.image` format. |
| `get_format_channel_count(PixelFormat)`, `get_format_element_count(PixelFormat)` | Number of channels / elements of a pixel format. |
| `is_depth_format`, `is_depth_only_format`, `is_stencil_format`, `is_stencil_only_format`, `is_depth_stencil_format` | Classify a `PixelFormat`. |
| `QUEUE_FAMILY_IGNORED` | `u32` sentinel for "no queue family transfer" in memory barriers. |

This page is generated from the sources by `docs/tools/gen_gpu_enums.py`; regenerate it rather
than editing the tables by hand.
"""


def parse(source: str) -> list[tuple[str, str, list[tuple[str, str]]]]:
    enums = []
    for name, underlying, body in re.findall(r"enum class (\w+)\s*:\s*(\w+)\s*\{(.*?)\};", source, re.S):
        body = re.sub(r"//.*", "", body)
        items = []
        for part in body.split(","):
            match = re.match(r"(\w+)\s*(?:=\s*(.+))?$", part.strip(), re.S)
            if match:
                items.append((match.group(1), " ".join((match.group(2) or "").split())))
        enums.append((name, underlying, items))
    return enums


def render(enums) -> str:
    lines = [HEADER, "## Index\n", "| Enumeration | Underlying type | Kind | Enumerators |", "| --- | --- | --- | --- |"]
    for name, underlying, items in enums:
        kind = "flags" if name.endswith("Flag") else "enum"
        lines.append(f"| [`{name}`](#{name.lower()}) | `{underlying}` | {kind} | {len(items)} |")
    lines.append("")

    for name, underlying, items in enums:
        kind = "Flag enumeration" if name.endswith("Flag") else "Enumeration"
        lines += [f"## `{name}`\n", f"{kind}, underlying type `{underlying}`.\n", "| Enumerator | Vulkan value |", "| --- | --- |"]
        for enumerator, value in items:
            value = value.replace(PIPE, ESCAPED_PIPE)
            lines.append(f"| `{enumerator}` | `{value}` |" if value else f"| `{enumerator}` | |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    enums = parse(SOURCE.read_text(encoding="utf-8"))
    OUTPUT.write_text(render(enums), encoding="utf-8", newline="\n")
    print(f"{len(enums)} enumerations, {sum(len(items) for _, _, items in enums)} enumerators -> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

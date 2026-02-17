"""Capture a process state snapshot from the current debugger state."""

from __future__ import annotations

from morgul.core.types.context import (
    FrameInfo,
    MemoryRegionInfo,
    ModuleDetail,
    ProcessSnapshot,
    RegisterInfo,
    StackTrace,
)


def capture_snapshot(
    process,
    frame=None,
    include_memory_regions: bool = False,
    disassembly_count: int = 20,
) -> ProcessSnapshot:
    """Capture a snapshot of the current process state.

    Args:
        process: A morgul.bridge.Process instance.
        frame: Optional morgul.bridge.Frame. If None, uses selected thread's selected frame.
        include_memory_regions: Whether to capture memory region info (can be slow).
        disassembly_count: Number of instructions to disassemble from current PC.
    """
    thread = process.selected_thread
    if frame is None and thread is not None:
        frame = thread.selected_frame

    # Registers
    registers: list[RegisterInfo] = []
    if frame is not None:
        for reg in frame.registers:
            registers.append(
                RegisterInfo(name=reg.name, value=reg.value, size=reg.size)
            )

    # Stack trace
    stack_trace: StackTrace | None = None
    if thread is not None:
        frames_list = thread.get_frames()
        frame_infos = []
        for f in frames_list:
            line_entry = f.line_entry
            frame_infos.append(
                FrameInfo(
                    index=f.index,
                    function_name=f.function_name,
                    module_name=f.module_name,
                    pc=f.pc,
                    file=line_entry.get("file") if line_entry else None,
                    line=line_entry.get("line") if line_entry else None,
                )
            )
        stack_trace = StackTrace(
            frames=frame_infos,
            thread_id=thread.id,
            thread_name=thread.name,
        )

    # Disassembly
    disassembly = ""
    if frame is not None:
        disassembly = frame.disassemble(count=disassembly_count)

    # Variables (with recursive struct expansion)
    def _var_to_dict(v) -> dict:
        d = {"name": v.name, "type": v.type_name, "value": v.value}
        if v.children:
            d["children"] = [_var_to_dict(c) for c in v.children]
        return d

    variables: list[dict] = []
    if frame is not None:
        for v in frame.variables():
            variables.append(_var_to_dict(v))

    # Modules
    modules: list[ModuleDetail] = []
    if hasattr(process, "_target") and process._target is not None:
        for m in process._target.modules:
            modules.append(
                ModuleDetail(
                    name=m.name,
                    path=m.path,
                    uuid=m.uuid,
                    base_address=m.base_address,
                )
            )

    # Memory regions
    memory_regions: list[MemoryRegionInfo] = []
    if include_memory_regions:
        from morgul.bridge.memory import get_memory_regions

        for region in get_memory_regions(process):
            memory_regions.append(
                MemoryRegionInfo(
                    start=region.start,
                    end=region.end,
                    readable=region.readable,
                    writable=region.writable,
                    executable=region.executable,
                    name=region.name,
                )
            )

    # Target triple (e.g. "arm64-apple-macosx15.4.0")
    target_triple = ""
    if hasattr(process, "_target") and process._target is not None:
        target_triple = process._target.triple

    return ProcessSnapshot(
        registers=registers,
        stack_trace=stack_trace,
        memory_regions=memory_regions,
        modules=modules,
        disassembly=disassembly,
        variables=variables,
        process_state=str(process.state),
        stop_reason=str(thread.stop_reason) if thread else "",
        pc=frame.pc if frame else None,
        target_triple=target_triple,
    )

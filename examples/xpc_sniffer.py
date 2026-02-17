"""XPC sniffer — intercept and decode XPC traffic using the bridge API directly.

No LLM calls. Fast, deterministic, and reliable.

Usage:
  PYTHONPATH="$(lldb -P)" uv run python examples/xpc_sniffer.py <process> [-n count]
  PYTHONPATH="$(lldb -P)" uv run python examples/xpc_sniffer.py Finder -n 10
"""

import argparse
import json
import sys

from morgul.bridge import Debugger

XPC_SEND_FUNCTIONS = [
    "xpc_connection_send_message",
    "xpc_connection_send_message_with_reply",
    "xpc_connection_send_message_with_reply_sync",
    "xpc_pipe_routine",
]

parser = argparse.ArgumentParser(description="Sniff XPC traffic.")
parser.add_argument("process", help="Process name to attach to")
parser.add_argument("-n", "--count", type=int, default=20, help="Messages to capture")
args = parser.parse_args()

d = Debugger()
target, process = d.attach_by_name(args.process)

# Set breakpoints on all XPC send functions
bps = {}
for fn in XPC_SEND_FUNCTIONS:
    bp = target.breakpoint_create_by_name(fn)
    bps[fn] = bp
    print(f"  bp: {fn} ({bp.num_locations} location{'s' if bp.num_locations != 1 else ''})")

print(f"\nListening for XPC messages on {args.process} (pid={process.pid})...\n")

messages = []

for i in range(args.count):
    process.continue_()

    thread = process.selected_thread
    frame = thread.selected_frame
    fn_name = frame.function_name or "unknown"

    # arm64: x0 = connection/pipe, x1 = message (or routine for xpc_pipe_routine)
    regs = {r.name: r.value for r in frame.registers}
    x0 = regs.get("x0", 0)
    x1 = regs.get("x1", 0)

    # Decode the XPC message via xpc_copy_description
    if "pipe_routine" in fn_name:
        # xpc_pipe_routine(pipe, routine, message, reply, flags)
        conn_desc = f"pipe={hex(x0)}"
        msg_ptr = regs.get("x2", 0)  # message is x2 for pipe_routine
        routine = x1
        conn_desc += f" routine={hex(routine)}"
    else:
        conn_desc = f"conn={hex(x0)}"
        msg_ptr = x1

    # Call xpc_copy_description to get human-readable message contents
    try:
        desc_str = frame.evaluate_expression(
            f"(char *)xpc_copy_description((void *){msg_ptr})"
        )
        if not desc_str or desc_str == "0x0" or "<null>" in str(desc_str):
            desc_str = f"<raw ptr {hex(msg_ptr)}>"
    except Exception:
        desc_str = f"<raw ptr {hex(msg_ptr)}>"

    # Get a short backtrace
    frames = thread.get_frames()
    bt = " <- ".join(
        f"{f.function_name or hex(f.pc)}[{f.module_name or '?'}]"
        for f in frames[:8]
    )

    msg = {
        "function": fn_name,
        "connection": conn_desc,
        "message": str(desc_str)[:500],
        "thread_id": thread.id,
        "backtrace": bt,
    }
    messages.append(msg)

    # Compact one-line output
    msg_preview = str(desc_str)[:100].replace("\n", " ")
    print(f"[{i + 1}/{args.count}] {fn_name} ({conn_desc})")
    print(f"         {msg_preview}")
    print(f"         bt: {bt[:120]}")
    print()

# Detach cleanly
process.detach()
d.destroy()

# Dump full JSON at the end
print("--- Full capture ---")
print(json.dumps(messages, indent=2))

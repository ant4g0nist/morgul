# Installation

This guide walks you through installing Morgul and its dependencies.

## Prerequisites

- **Python 3.10+**
- **LLDB** -- included with Xcode Command Line Tools on macOS, or available via the `lldb` package on Linux

## Install from source

```bash
git clone https://github.com/ant4g0nist/Morgul.git
cd Morgul
uv sync
```

## Verify installation

Run the following commands to confirm everything is wired up correctly:

```bash
python -c "from morgul.core import Morgul; print('Morgul OK')"
python -c "import lldb; print('LLDB OK')"
```

Both commands should print their respective `OK` messages without errors.

## LLDB Python bindings

### macOS

LLDB ships with Xcode, but Python may not find it by default. Add the framework to your `PYTHONPATH`:

```bash
export PYTHONPATH="/Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python:$PYTHONPATH"
```

You can add this line to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.) to make it permanent.

### Linux

Install the `python3-lldb` package from your distribution's package manager, or build LLDB from source. For example, on Debian/Ubuntu:

```bash
sudo apt install python3-lldb
```

## Next steps

Once installation is verified, head to the [Quickstart](quickstart.md) to run your first Morgul session.

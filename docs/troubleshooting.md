# Troubleshooting

This page covers common issues you may encounter when using Morgul and how to resolve them.

---

## LLDB Not Found

**Symptom:**

```
RuntimeError: The 'lldb' Python module is not available
```

**Cause:** Morgul requires the LLDB Python bindings, which are not always on the default Python path.

**Solution:**

On **macOS**, install Xcode Command Line Tools and add the LLDB framework to your Python path:

```bash
xcode-select --install
export PYTHONPATH="/Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python:$PYTHONPATH"
```

Add the `export` line to your shell profile (`~/.zshrc` or `~/.bashrc`) to make it persistent.

On **Linux**, install the `python3-lldb` package for your distribution:

```bash
# Debian/Ubuntu
sudo apt install python3-lldb

# Fedora
sudo dnf install python3-lldb
```

Alternatively, build LLDB from source with Python bindings enabled.

---

## LLM Provider Authentication

**Symptom:** API key errors from Anthropic or OpenAI, such as:

```
AuthenticationError: Invalid API key
```

**Solution:** Set the appropriate environment variable for your provider:

```bash
export ANTHROPIC_API_KEY="your-key-here"
# or
export OPENAI_API_KEY="your-key-here"
```

You can also set `api_key` directly in `morgul.toml`, though this is not recommended for files under version control:

```toml
[llm]
api_key = "your-key-here"
```

For Ollama, no API key is needed, but you must set the `base_url`:

```toml
[llm]
provider = "ollama"
base_url = "http://localhost:11434"
```

---

## Process Attach Fails

**Symptom:**

```
RuntimeError: Failed to attach to PID ...
```

**Cause:** Operating system security policies restrict which processes a debugger can attach to.

**Solution:**

On **macOS**, System Integrity Protection (SIP) restricts debugging of system processes and some third-party applications. Check the current SIP status:

```bash
csrutil status
```

For your own binaries, ensure they are properly code-signed. For development purposes, you may need to disable SIP (requires booting into Recovery Mode). Note that only processes you own or have explicit permission to debug can be attached to, even with SIP disabled.

On **Linux**, the `ptrace_scope` setting controls which processes can be debugged. Check the current value:

```bash
cat /proc/sys/kernel/yama/ptrace_scope
```

- `0` -- No restrictions (a process can attach to any other process owned by the same user).
- `1` -- Restricted (only parent processes can attach to children). This is the default on many distributions.

To temporarily allow unrestricted ptrace:

```bash
echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope
```

To make the change persistent, add `kernel.yama.ptrace_scope = 0` to `/etc/sysctl.conf`.

---

## Agent Runs Too Long or Loops

**Symptom:** The agent takes many steps without making progress, or reaches the step limit without completing the task.

**Cause:** The task description may be too vague, the strategy may not suit the problem, or the step/timeout limits may be too generous, allowing unproductive exploration.

**Solution:**

- **Reduce `max_steps`** to force the agent to be more decisive. Start with 10-20 steps and increase only if needed.
- **Write more specific task descriptions.** Instead of "find the bug", try "find why the program crashes with SIGSEGV when processing input files larger than 1MB".
- **Try a different strategy.** The `hypothesis-driven` strategy is more focused than `breadth-first` because it forms a specific hypothesis and tests it, rather than exploring broadly.
- **Set a lower `timeout`** to bound the total runtime.

```toml
[agent]
max_steps = 15
timeout = 60.0
strategy = "hypothesis-driven"
```

---

## Self-Healing Not Working

**Symptom:** LLDB commands fail and Morgul does not attempt to retry or correct them.

**Cause:** Self-healing requires both the top-level `self_heal` flag and the `[healing]` section to be enabled.

**Solution:** Verify both settings in your `morgul.toml`:

```toml
self_heal = true

[healing]
enabled = true
max_retries = 3
```

If either `self_heal` is `false` or `[healing] enabled` is `false`, the healing system is inactive. Both must be `true`.

---

## Cache Issues

**Symptom:** Stale results are returned (the LLM seems to ignore changes), or cache-related errors appear.

**Cause:** The content-addressed cache may contain outdated entries, or the cache directory may have permission issues.

**Solution:**

Clear the cache by removing the cache directory:

```bash
rm -rf .morgul/cache
```

To disable caching entirely, update your configuration:

```toml
[cache]
enabled = false
```

If you encounter permission errors, check that the cache directory is writable by the current user:

```bash
ls -la .morgul/
```

---

## Import Errors After Installation

**Symptom:**

```
ModuleNotFoundError: No module named 'morgul'
```

**Cause:** Morgul is not installed in the active Python environment.

**Solution:** Ensure you are using the correct Python environment and that Morgul is installed:

```bash
git clone https://github.com/ant4g0nist/Morgul.git
cd Morgul
uv sync
```

Verify the installation:

```bash
python -c "import morgul; print(morgul.__version__)"
```

---

## LLM Returns Incorrect Commands

**Symptom:** The LLM generates LLDB commands that are syntactically wrong or do not match the intended action.

**Cause:** Higher temperature values increase the variability of LLM output, which can lead to less reliable command generation.

**Solution:**

Lower the temperature for more deterministic output:

```toml
[llm]
temperature = 0.3
```

If the issue persists, try a more capable model or provide more context in your instructions. Self-healing (when enabled) will automatically attempt to correct failed commands.

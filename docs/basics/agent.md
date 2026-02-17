# Agent Mode - Autonomous Debugging

Agent mode runs an autonomous loop that combines `observe`, `act`, `extract`, and reasoning to accomplish complex, multi-step debugging goals without manual intervention.

## Signature

```python
morgul.agent(
    task: str,
    strategy: str = "depth-first",
    max_steps: Optional[int] = None,
    timeout: Optional[float] = None,
) -> List[AgentStep]
```

## AgentStep

Each step in the agent's execution is recorded as an `AgentStep`:

| Field | Type | Description |
|---|---|---|
| `step_number` | `int` | Sequential step index |
| `action` | `str` | What the agent did |
| `observation` | `str` | What it observed after acting |
| `reasoning` | `str` | Why it chose this action |

The full list of steps gives you a complete audit trail of the agent's decision-making process.

## Strategies

The `strategy` parameter controls how the agent explores the target:

| Strategy | Behavior | Best For |
|---|---|---|
| `depth-first` | Follow one code path deeply before backtracking | Tracing specific flows, crash analysis |
| `breadth-first` | Survey all reachable functions, then dive into interesting ones | Attack surface mapping |
| `hypothesis-driven` | Form a hypothesis, test it, revise | Vulnerability hunting |

### depth-first

The default strategy. The agent picks a path and follows it to completion before considering alternatives. This is effective when you have a specific crash or behavior to trace and want the agent to stay focused.

### breadth-first

The agent first maps out the available functions and code paths, building a broad picture before diving deep into any single area. Use this for reconnaissance and attack surface analysis.

### hypothesis-driven

The agent forms a hypothesis about the program's behavior (e.g., "this function does not check the buffer length"), designs actions to test it, and revises based on what it finds. This is the most effective strategy for targeted vulnerability hunting.

## Example: Vulnerability Hunting

```python
steps = morgul.agent(
    task=(
        "Analyze this binary for potential buffer overflow vulnerabilities. "
        "Look for functions that handle user input. "
        "Set breakpoints on suspicious functions, examine their arguments, "
        "and determine if there are any unchecked buffer sizes."
    ),
    strategy="hypothesis-driven",
    max_steps=30,
    timeout=120.0,
)

for step in steps:
    print(f"Step {step.step_number}: {step.action}")
    print(f"  Observation: {step.observation}")
    print(f"  Reasoning: {step.reasoning}")
```

## Configuring the Agent

### max_steps

Maximum number of iterations the agent will perform. Default: 50 (from config). Start low (10-20) while you are iterating on your task description, then increase once you are confident the task is well-specified.

### timeout

Maximum wall-clock seconds the agent is allowed to run. Default: 300.0 (5 minutes). This prevents runaway sessions when the agent gets stuck in a loop.

### Configuration file

Both settings can also be defined in `morgul.toml`:

```toml
[agent]
max_steps = 50
timeout = 300.0
strategy = "depth-first"
```

Per-call arguments override the configuration file values.

## Tips

- **Write specific task descriptions.** Vague tasks like "find bugs" lead to unfocused exploration. Be explicit about what you want the agent to look for, where to look, and what success looks like.
- **Start with lower max_steps to iterate.** Use 10-20 steps while refining your task description. Once the agent consistently moves in the right direction, increase the limit.
- **Use `hypothesis-driven` for targeted hunting.** When you have a specific class of vulnerability in mind, this strategy is the most efficient.
- **Use `breadth-first` for discovery.** When you do not know what you are looking for, breadth-first mapping gives you a comprehensive view before committing to a direction.
- **Review the reasoning field.** The `reasoning` on each step tells you why the agent made its choice. This is invaluable for understanding whether the agent is on track or needs a better task description.

## See Also

- [Vulnerability Hunting Guide](../guides/vuln-hunting.md)
- [Configuration](../getting-started/configuration.md)

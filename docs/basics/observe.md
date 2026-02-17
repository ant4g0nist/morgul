# observe() - Survey and Suggest

The `observe()` primitive examines the current process state and returns a ranked list of suggested actions, without executing any of them. It is a read-only operation.

## Signature

```python
morgul.observe(instruction: Optional[str] = None) -> ObserveResult
```

The `instruction` parameter is optional. When omitted, Morgul performs a general survey of the current state. When provided, it focuses the observation on a specific area.

## ObserveResult

The return value is an `ObserveResult` with the following fields:

| Field | Type | Description |
|---|---|---|
| `actions` | `List[Action]` | Ranked list of suggested next actions |
| `description` | `str` | Overall description of the observed state |

Each `Action` contains a `code` field (a Python code snippet using the bridge API) and a `description` (why this action is suggested).

## Examples

### General State Observation

Call `observe()` without arguments to get a broad assessment of the current process state:

```python
obs = morgul.observe()
print(obs.description)
```

### Targeted Observation

Pass an instruction to focus the observation:

```python
obs = morgul.observe("what functions handle network input?")
for action in obs.actions:
    print(f"  {action.code} - {action.description}")
```

### Acting on a Suggestion

The suggested actions are concrete Python code snippets using the bridge API. You can use the description to inform your next `act()` call:

```python
obs = morgul.observe("what functions handle network input?")
# Act on the top suggestion's intent
morgul.act(obs.actions[0].description)
```

This pattern -- observe first, then act on the best suggestion -- is useful for semi-automated workflows where you want to stay in control.

## When to Use observe

- **Recon before acting on unfamiliar code.** If you are looking at a binary you have not seen before, observe first to understand what is available.
- **Understanding what is available at the current program state.** After hitting a breakpoint, observe to see what functions and data are relevant.
- **Planning next steps in a debugging session.** Use observe to get a ranked list of options before committing to an action.
- **Getting the LLM's assessment without side effects.** Since observe does not execute any code, it is safe to call at any point without risk of changing process state.

## observe vs act

The key difference: `observe` is read-only. No commands are executed against the process. Use it to plan, then use `act` to execute.

| | observe | act |
|---|---|---|
| Executes commands | No | Yes |
| Changes process state | No | Yes |
| Returns suggestions | Yes | No (returns results) |
| Use case | Planning, recon | Execution |

## See Also

- [act() - Execute Debugging Actions](act.md)
- [Agent Mode - Autonomous Debugging](agent.md)

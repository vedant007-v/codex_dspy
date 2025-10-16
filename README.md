# CodexAgent - DSPy Module for OpenAI Codex SDK

A DSPy module that wraps the OpenAI Codex SDK with a signature-driven interface. Each agent instance maintains a stateful conversation thread, making it perfect for multi-turn agentic workflows.

## Features

- **Signature-driven** - Use DSPy signatures for type safety and clarity
- **Stateful threads** - Each agent instance = one conversation thread
- **Smart schema handling** - Automatically handles str vs Pydantic outputs
- **Rich outputs** - Get typed results + execution trace + token usage
- **Multi-turn conversations** - Context preserved across calls
- **Output field descriptions** - Automatically enhance prompts

## Installation

```bash
# Install dependencies
uv sync

# Ensure codex CLI is available
which codex  # Should point to /opt/homebrew/bin/codex or similar
```

## Quick Start

### Basic String Output

```python
import dspy
from codex_agent import CodexAgent

# Define signature
sig = dspy.Signature('message:str -> answer:str')

# Create agent
agent = CodexAgent(sig, working_directory=".")

# Use it
result = agent(message="What files are in this directory?")
print(result.answer)  # String response
print(result.trace)   # Execution items (commands, files, etc.)
print(result.usage)   # Token counts
```

### Structured Output with Pydantic

```python
from pydantic import BaseModel, Field

class BugReport(BaseModel):
    severity: str = Field(description="critical, high, medium, or low")
    description: str
    affected_files: list[str]

sig = dspy.Signature('message:str -> report:BugReport')
agent = CodexAgent(sig, working_directory=".")

result = agent(message="Analyze the bug in error.log")
print(result.report.severity)  # Typed access!
print(result.report.affected_files)
```

## API Reference

### CodexAgent

```python
class CodexAgent(dspy.Module):
    def __init__(
        self,
        signature: str | type[Signature],
        working_directory: str,
        model: Optional[str] = None,
        sandbox_mode: Optional[SandboxMode] = None,
        skip_git_repo_check: bool = False,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        codex_path_override: Optional[str] = None,
    )
```

#### Parameters

**Required:**

- **`signature`** (`str | type[Signature]`)
  - DSPy signature defining input/output fields
  - Must have exactly 1 input field and 1 output field
  - Examples:
    - String format: `'message:str -> answer:str'`
    - Class format: `MySignature` (subclass of `dspy.Signature`)

- **`working_directory`** (`str`)
  - Directory where Codex agent will execute commands
  - Must be a git repository (unless `skip_git_repo_check=True`)
  - Example: `"."`, `"/path/to/project"`

**Optional:**

- **`model`** (`Optional[str]`)
  - Model to use for generation
  - Examples: `"gpt-4"`, `"gpt-4-turbo"`, `"gpt-4o"`
  - Default: Codex SDK default (typically latest GPT-4)

- **`sandbox_mode`** (`Optional[SandboxMode]`)
  - Controls what operations the agent can perform
  - Options:
    - `SandboxMode.READ_ONLY` - No file modifications (safest)
    - `SandboxMode.WORKSPACE_WRITE` - Can modify files in workspace
    - `SandboxMode.DANGER_FULL_ACCESS` - Full system access
  - Default: Determined by Codex SDK

- **`skip_git_repo_check`** (`bool`)
  - Allow non-git directories as `working_directory`
  - Default: `False`

- **`api_key`** (`Optional[str]`)
  - OpenAI API key
  - Falls back to `CODEX_API_KEY` environment variable
  - Default: `None` (uses env var)

- **`base_url`** (`Optional[str]`)
  - OpenAI API base URL (for custom endpoints)
  - Falls back to `OPENAI_BASE_URL` environment variable
  - Default: `None` (uses official OpenAI endpoint)

- **`codex_path_override`** (`Optional[str]`)
  - Override path to codex binary
  - Useful for testing or custom installations
  - Example: `"/opt/homebrew/bin/codex"`
  - Default: `None` (SDK auto-discovers)

#### Methods

##### `forward(**kwargs) -> Prediction`

Execute the agent with an input message.

**Arguments:**
- `**kwargs` - Must contain the input field specified in signature

**Returns:**
- `Prediction` object with:
  - **Typed output field** - Named according to signature (e.g., `result.answer`)
  - **`trace`** - `list[ThreadItem]` - Chronological execution items
  - **`usage`** - `Usage` - Token counts

**Example:**
```python
result = agent(message="Hello")
print(result.answer)     # Access typed output
print(result.trace)      # List of execution items
print(result.usage)      # Token usage stats
```

#### Properties

##### `thread_id: Optional[str]`

Get the thread ID for this agent instance.

- Returns `None` until first `forward()` call
- Persists across multiple `forward()` calls
- Useful for debugging and logging

**Example:**
```python
agent = CodexAgent(sig, working_directory=".")
print(agent.thread_id)  # None

result = agent(message="Hello")
print(agent.thread_id)  # '0199e95f-2689-7501-a73d-038d77dd7320'
```

## Usage Patterns

### Pattern 1: Multi-turn Conversation

Each agent instance maintains a stateful thread:

```python
agent = CodexAgent(sig, working_directory=".")

# Turn 1
result1 = agent(message="What's the main bug?")
print(result1.answer)

# Turn 2 - has context from Turn 1
result2 = agent(message="How do we fix it?")
print(result2.answer)

# Turn 3 - has context from Turn 1 + 2
result3 = agent(message="Write tests for the fix")
print(result3.answer)

# All use same thread_id
print(agent.thread_id)
```

### Pattern 2: Fresh Context

Want a new conversation? Create a new agent:

```python
# Agent 1 - Task A
agent1 = CodexAgent(sig, working_directory=".")
result1 = agent1(message="Analyze bug in module A")

# Agent 2 - Task B (no context from Agent 1)
agent2 = CodexAgent(sig, working_directory=".")
result2 = agent2(message="Analyze bug in module B")
```

### Pattern 3: Output Field Descriptions

Enhance prompts with field descriptions:

```python
class MySignature(dspy.Signature):
    """Analyze code architecture."""

    message: str = dspy.InputField()
    analysis: str = dspy.OutputField(
        desc="A detailed markdown report with sections: "
        "1) Architecture overview, 2) Key components, 3) Dependencies"
    )

agent = CodexAgent(MySignature, working_directory=".")
result = agent(message="Analyze this codebase")

# The description is automatically appended to the prompt:
# "Analyze this codebase\n\n
#  Please produce the following output: A detailed markdown report..."
```

### Pattern 4: Inspecting Execution Trace

Access detailed execution information:

```python
from codex import CommandExecutionItem, FileChangeItem

result = agent(message="Fix the bug")

# Filter trace by type
commands = [item for item in result.trace if isinstance(item, CommandExecutionItem)]
for cmd in commands:
    print(f"Command: {cmd.command}")
    print(f"Exit code: {cmd.exit_code}")
    print(f"Output: {cmd.aggregated_output}")

files = [item for item in result.trace if isinstance(item, FileChangeItem)]
for file_item in files:
    for change in file_item.changes:
        print(f"{change.kind}: {change.path}")
```

### Pattern 5: Token Usage Tracking

Monitor API usage:

```python
result = agent(message="...")

print(f"Input tokens: {result.usage.input_tokens}")
print(f"Cached tokens: {result.usage.cached_input_tokens}")
print(f"Output tokens: {result.usage.output_tokens}")
print(f"Total: {result.usage.input_tokens + result.usage.output_tokens}")
```

### Pattern 6: Safe Execution with Sandbox

Control what the agent can do:

```python
from codex import SandboxMode

# Read-only (safest)
agent = CodexAgent(
    sig,
    working_directory=".",
    sandbox_mode=SandboxMode.READ_ONLY
)

# Can modify files in workspace
agent = CodexAgent(
    sig,
    working_directory=".",
    sandbox_mode=SandboxMode.WORKSPACE_WRITE
)

# Full system access (use with caution!)
agent = CodexAgent(
    sig,
    working_directory=".",
    sandbox_mode=SandboxMode.DANGER_FULL_ACCESS
)
```

## Advanced Examples

### Example 1: Code Review Agent

```python
from pydantic import BaseModel, Field
from codex import SandboxMode

class CodeReview(BaseModel):
    summary: str = Field(description="High-level summary")
    issues: list[str] = Field(description="List of issues found")
    severity: str = Field(description="overall, critical, or info")
    recommendations: list[str] = Field(description="Actionable recommendations")

sig = dspy.Signature('message:str -> review:CodeReview')

agent = CodexAgent(
    sig,
    working_directory="/path/to/project",
    model="gpt-4",
    sandbox_mode=SandboxMode.READ_ONLY,
)

result = agent(message="Review the changes in src/main.py")

print(f"Severity: {result.review.severity}")
for issue in result.review.issues:
    print(f"- {issue}")
```

### Example 2: Repository Analysis Pipeline

```python
class RepoStats(BaseModel):
    total_files: int
    languages: list[str]
    test_coverage: str

class ArchitectureNotes(BaseModel):
    components: list[str]
    design_patterns: list[str]
    dependencies: list[str]

# Agent 1: Gather stats
stats_sig = dspy.Signature('message:str -> stats:RepoStats')
stats_agent = CodexAgent(stats_sig, working_directory=".")
stats = stats_agent(message="Analyze repository statistics").stats

# Agent 2: Architecture analysis
arch_sig = dspy.Signature('message:str -> notes:ArchitectureNotes')
arch_agent = CodexAgent(arch_sig, working_directory=".")
arch = arch_agent(
    message=f"Analyze architecture. Context: {stats.total_files} files, "
            f"languages: {', '.join(stats.languages)}"
).notes

print(f"Components: {arch.components}")
print(f"Patterns: {arch.design_patterns}")
```

### Example 3: Iterative Debugging

```python
sig = dspy.Signature('message:str -> response:str')
agent = CodexAgent(
    sig,
    working_directory=".",
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
    model="gpt-4-turbo",
)

# Turn 1: Find the bug
result1 = agent(message="Find the bug in src/calculator.py")
print(result1.response)

# Turn 2: Propose a fix
result2 = agent(message="What's the best way to fix it?")
print(result2.response)

# Turn 3: Implement the fix
result3 = agent(message="Implement the fix")
print(result3.response)

# Turn 4: Write tests
result4 = agent(message="Write tests for the fix")
print(result4.response)

# Check what files were modified
from codex import FileChangeItem
for item in result3.trace + result4.trace:
    if isinstance(item, FileChangeItem):
        for change in item.changes:
            print(f"Modified: {change.path}")
```

## Trace Item Types

When accessing `result.trace`, you'll see various item types:

| Type | Fields | Description |
|------|--------|-------------|
| `AgentMessageItem` | `id`, `text` | Agent's text response |
| `ReasoningItem` | `id`, `text` | Agent's internal reasoning |
| `CommandExecutionItem` | `id`, `command`, `aggregated_output`, `status`, `exit_code` | Shell command execution |
| `FileChangeItem` | `id`, `changes`, `status` | File modifications (add/update/delete) |
| `McpToolCallItem` | `id`, `server`, `tool`, `status` | MCP tool invocation |
| `WebSearchItem` | `id`, `query` | Web search performed |
| `TodoListItem` | `id`, `items` | Task list created |
| `ErrorItem` | `id`, `message` | Error that occurred |

## How It Works

### Signature ’ Codex Flow

```
1. Define signature: 'message:str -> answer:str'
   “
2. CodexAgent validates (must have 1 input, 1 output)
   “
3. __init__ creates Codex client + starts thread
   “
4. forward(message="...") extracts message
   “
5. If output field has desc ’ append to message
   “
6. If output type ` str ’ generate JSON schema
   “
7. Call thread.run(message, schema)
   “
8. Parse response (JSON if Pydantic, str otherwise)
   “
9. Return Prediction(output=..., trace=..., usage=...)
```

### Output Type Handling

**String output:**
```python
sig = dspy.Signature('message:str -> answer:str')
# No schema passed to Codex
# Response used as-is
```

**Pydantic output:**
```python
sig = dspy.Signature('message:str -> report:BugReport')
# JSON schema generated from BugReport
# Schema passed to Codex with additionalProperties: false
# Response parsed with BugReport.model_validate_json()
```

## Troubleshooting

### Error: "CodexAgent requires exactly 1 input field"

Your signature has too many or too few fields. CodexAgent expects exactly one input and one output:

```python
# L Wrong - multiple inputs
sig = dspy.Signature('context:str, question:str -> answer:str')

#  Correct - single input
sig = dspy.Signature('message:str -> answer:str')
```

### Error: "Failed to parse Codex response as MyModel"

The model returned JSON that doesn't match your Pydantic schema. Check:
1. Schema is valid and clear
2. Field descriptions are helpful
3. Model has enough context to generate correct structure

### Error: "No such file or directory: codex"

Set `codex_path_override`:

```python
agent = CodexAgent(
    sig,
    working_directory=".",
    codex_path_override="/opt/homebrew/bin/codex"
)
```

### Working directory must be a git repo

Either:
1. Use a git repository, or
2. Set `skip_git_repo_check=True`:

```python
agent = CodexAgent(
    sig,
    working_directory="/tmp/mydir",
    skip_git_repo_check=True
)
```

## Design Philosophy

### Why 1 input, 1 output?

CodexAgent is designed for conversational agentic workflows. The input is always a message/prompt, and the output is always a response. This keeps the interface simple and predictable.

For complex inputs, compose them into the message:

```python
# Instead of: 'context:str, question:str -> answer:str'
message = f"Context: {context}\n\nQuestion: {question}"
result = agent(message=message)
```

### Why stateful threads?

Agents often need multi-turn context (e.g., "fix the bug" ’ "write tests for it"). Stateful threads make this natural without manual history management.

Want fresh context? Create a new agent instance.

### Why return trace + usage?

Observability is critical for agentic systems. You need to know:
- What commands ran
- What files changed
- How many tokens were used
- What the agent was thinking

The trace provides full visibility into agent execution.

## Contributing

Issues and PRs welcome! This is an experimental integration of Codex SDK with DSPy.

## License

See LICENSE file.

## Related Documentation

- [Codex SDK API Reference](./CODEX_SDK_API_SURFACE.md)
- [Codex Architecture](./CODEX_ARCHITECTURE.md)
- [Codex Quick Reference](./CODEX_QUICK_REFERENCE.md)
- [DSPy Documentation](https://dspy-docs.vercel.app/)

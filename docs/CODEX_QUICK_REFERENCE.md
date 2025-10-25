# Codex Python SDK - Quick Reference Guide

## Installation & Basic Setup

```python
from codex import Codex, CodexOptions, ThreadOptions, TurnOptions

# Initialize client
client = Codex()

# Or with config
client = Codex(CodexOptions(
    base_url="https://api.openai.com/v1",
    api_key="sk-..."
))
```

## Core Patterns

### Pattern 1: Simple Prompt-Response

```python
thread = client.start_thread()
result = thread.run("Summarize this repository")
print(result.final_response)
```

### Pattern 2: Streaming Events

```python
from codex import ItemCompletedEvent, TurnCompletedEvent

stream = thread.run_streamed("Fix the failing test")
for event in stream:
    if isinstance(event, ItemCompletedEvent):
        print(f"Item: {event.item.type}")
    if isinstance(event, TurnCompletedEvent):
        print(f"Tokens: {event.usage.input_tokens}")
```

### Pattern 3: Structured Output

```python
from pydantic import BaseModel

class BugReport(BaseModel):
    title: str
    severity: str
    steps: list[str]

result = thread.run(
    "Analyze the bug",
    TurnOptions(output_schema=BugReport)
)
```

### Pattern 4: Multi-turn Conversation

```python
thread = client.start_thread()

# Turn 1
resp1 = thread.run("What's wrong?")

# Turn 2 - context preserved
resp2 = thread.run("How do we fix it?")

# Resume later
resumed = client.resume_thread(thread.id)
resp3 = resumed.run("Write tests")
```

### Pattern 5: Configured Execution

```python
from codex import SandboxMode

thread = client.start_thread(ThreadOptions(
    model="gpt-4",
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
    working_directory="/path/to/repo"
))

result = thread.run("Implement the fix")
```

## Response Objects

### ThreadRunResult (from `thread.run()`)
```python
result.final_response: str           # Final message from agent
result.items: list[ThreadItem]       # All items (commands, files, etc.)
result.usage: Usage                  # Token counts
result.usage.input_tokens
result.usage.cached_input_tokens
result.usage.output_tokens
```

### Thread Items (types in result.items)

| Type | Fields | Meaning |
|------|--------|---------|
| `AgentMessageItem` | `id, text` | Agent response message |
| `ReasoningItem` | `id, text` | Agent's reasoning/thinking |
| `CommandExecutionItem` | `id, command, aggregated_output, status, exit_code` | Command run |
| `FileChangeItem` | `id, changes, status` | File modifications |
| `McpToolCallItem` | `id, server, tool, status` | MCP tool invocation |
| `WebSearchItem` | `id, query` | Web search performed |
| `TodoListItem` | `id, items` | Task list created |
| `ErrorItem` | `id, message` | Error occurred |

### Events (from `thread.run_streamed()`)

```python
# Union of:
ThreadStartedEvent       # type, thread_id
TurnStartedEvent         # type
TurnCompletedEvent       # type, usage
TurnFailedEvent          # type, error
ItemStartedEvent         # type, item
ItemUpdatedEvent         # type, item
ItemCompletedEvent       # type, item
ThreadErrorEvent         # type, message
```

## Configuration Parameters

### Codex Client
```python
CodexOptions(
    codex_path_override=None,    # Override binary location
    base_url=None,                # API endpoint
    api_key=None,                 # Auth key
)
```

### Thread
```python
ThreadOptions(
    model=None,                   # e.g. "gpt-4"
    sandbox_mode=None,            # READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS
    working_directory=None,       # Where to run commands
    skip_git_repo_check=False,   # Allow non-git directories
    approval_mode=None,           # ApprovalMode - When to ask for user approval (never, on-request, on-failure, untrusted)
)
```

### Turn
```python
TurnOptions(
    output_schema=None,           # Dict or Pydantic model for output schema
)
```

## Error Handling

```python
from codex import ThreadRunError, SchemaValidationError, CodexError

try:
    result = thread.run(prompt, TurnOptions(output_schema=schema))
except ThreadRunError as e:
    print(f"Turn failed: {e}")
except SchemaValidationError as e:
    print(f"Invalid schema: {e}")
except CodexError as e:
    print(f"SDK error: {e}")
```

## Common Tasks

### Check if Thread ID Available
```python
if thread.id is not None:
    print(f"Thread ID: {thread.id}")
```

### Pass JSON Schema for Output
```python
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
    "required": ["name"],
}
result = thread.run(prompt, TurnOptions(output_schema=schema))
```

### Filter Items by Type
```python
from codex import CommandExecutionItem

commands = [
    item for item in result.items 
    if isinstance(item, CommandExecutionItem)
]
for cmd in commands:
    print(f"Command: {cmd.command}")
    print(f"Exit code: {cmd.exit_code}")
```

### Handle Item Updates in Streaming
```python
from codex import ItemUpdatedEvent, ItemCompletedEvent

for event in thread.run_streamed(prompt):
    if isinstance(event, ItemUpdatedEvent):
        print(f"Item {event.item.id} updating...")
    if isinstance(event, ItemCompletedEvent):
        print(f"Item {event.item.id} done")
```

### Inspect MCP Tool Calls
```python
from codex import McpToolCallItem, ItemCompletedEvent

for event in thread.run_streamed(prompt):
    if isinstance(event, ItemCompletedEvent):
        if isinstance(event.item, McpToolCallItem):
            tool = event.item
            print(f"Tool: {tool.server}.{tool.tool}")
            print(f"Status: {tool.status}")
```

## 6. DSPy Integration Pattern

### Basic Pattern
```python
import dspy
from codex_dspy import CodexAgent
from codex import SandboxMode

# Define signature
sig = dspy.Signature('message:str -> answer:str')

# Create agent (starts thread)
agent = CodexAgent(
    sig,
    working_directory='.',
    sandbox_mode=SandboxMode.READ_ONLY
)

# Execute (returns Prediction)
result = agent(message='Your task')
print(result.answer)  # Typed output field
print(result.trace)   # List[ThreadItem]
print(result.usage)   # Token usage
```

### Pydantic Output Pattern
```python
from pydantic import BaseModel, Field

class Analysis(BaseModel):
    summary: str
    key_points: list[str]

sig = dspy.Signature('message:str -> analysis:Analysis')
agent = CodexAgent(sig, working_directory='.')
result = agent(message='Analyze this project')
print(result.analysis.summary)  # Typed Pydantic access
```

### Key Points
- One agent instance = one stateful thread
- Multiple forward() calls continue the same conversation
- String outputs: no schema, freeform response
- Pydantic outputs: structured JSON validation
- Access thread_id via `agent.thread_id`

## Type Hints

All exports support full type hints:

```python
from codex import (
    Codex,
    CodexOptions,
    ThreadOptions,
    TurnOptions,
    SandboxMode,
    Thread,
    ThreadRunResult,
    ThreadStream,
    ThreadEvent,
    ThreadItem,
    AgentMessageItem,
    CommandExecutionItem,
    FileChangeItem,
    McpToolCallItem,
    Usage,
    CodexError,
)
```

## Stateless vs Stateful

**Stateful (Thread):**
- Single `Thread` object across multiple `run()` calls
- History automatically maintained
- `thread.id` persists across sessions

**Stateless (Individual Runs):**
- Each `run()` call is independent
- Configure turn-by-turn with `TurnOptions`
- No state carried between `TurnOptions`

## Environment Variables

```bash
CODEX_API_KEY=sk-...              # API key (alternative to CodexOptions.api_key)
OPENAI_BASE_URL=https://...       # API URL (alternative to CodexOptions.base_url)
```

## Performance Notes

1. **Streaming vs Sync**: Use `run_streamed()` to get real-time feedback, `run()` for final result
2. **Token Caching**: Check `usage.cached_input_tokens` in response
3. **Schema Validation**: Pydantic models are auto-converted to JSON Schema
4. **Working Directory**: Best to use git repos; set `skip_git_repo_check=True` for others
5. **Sandbox Mode**: `READ_ONLY` is most restrictive, `DANGER_FULL_ACCESS` least

## Files & Paths

```python
# File changes from item
for change in file_item.changes:
    print(change.path)     # File path
    print(change.kind)     # "add", "update", "delete"
```

## Boolean Statuses

```python
# Command execution
CommandExecutionStatus.IN_PROGRESS, COMPLETED, FAILED

# File patches  
PatchApplyStatus.COMPLETED, FAILED

# MCP tool calls
McpToolCallStatus.IN_PROGRESS, COMPLETED, FAILED
```

## Full Example: Production-Ready Pattern

```python
from codex import (
    Codex, CodexOptions, ThreadOptions, TurnOptions,
    SandboxMode, ItemCompletedEvent, CommandExecutionItem,
    TurnCompletedEvent, ThreadRunError
)
from pydantic import BaseModel

class AnalysisResult(BaseModel):
    issues: list[str]
    summary: str
    severity: str

# Setup
client = Codex(CodexOptions(api_key="sk-..."))
thread = client.start_thread(ThreadOptions(
    model="gpt-4",
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
    working_directory="/path/to/repo",
))

try:
    # Get structured output
    result = thread.run(
        "Analyze code issues",
        TurnOptions(output_schema=AnalysisResult)
    )
    
    # Extract data
    analysis = result.final_response
    print(f"Issues found: {len(analysis.issues)}")
    print(f"Severity: {analysis.severity}")
    
    # Process commands
    commands = [
        i for i in result.items 
        if isinstance(i, CommandExecutionItem)
    ]
    for cmd in commands:
        print(f"Ran: {cmd.command}")
        
except ThreadRunError as e:
    print(f"Analysis failed: {e}")
```


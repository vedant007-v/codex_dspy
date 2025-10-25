# Codex Python SDK - Comprehensive API Surface Area

## Overview

The Codex Python SDK is a Python interface to the Codex agent CLI. It shells out to a bundled native `codex` binary, streams structured JSON events, and provides strongly-typed helpers for synchronous and streaming turns. The SDK is designed for Python 3.12+ and is currently in pre-alpha status.

---

## 1. Main SDK Entry Points

### 1.1 Client Initialization

**Class: `Codex`**

```python
from codex import Codex, CodexOptions

# Basic initialization
client = Codex()

# With configuration options
client = Codex(options=CodexOptions(
    codex_path_override="/path/to/codex/binary",
    base_url="https://api.openai.com/v1",
    api_key="sk-..."
))
```

**Parameters:**
- `options` (Optional[CodexOptions]): Global SDK configuration

### 1.2 Thread Management

**Methods:**
- `start_thread(options: Optional[ThreadOptions] = None) -> Thread`
  - Creates a new thread for a conversation session
  - Returns a `Thread` object to interact with

- `resume_thread(thread_id: str, options: Optional[ThreadOptions] = None) -> Thread`
  - Resumes an existing thread by ID
  - Useful for multi-turn conversations or resuming interrupted work

**Example:**
```python
# Start new thread
thread = client.start_thread()

# Later, resume the same thread
thread_id = thread.id  # Available after first run
resumed_thread = client.resume_thread(thread_id)
```

---

## 2. Configuration Options

### 2.1 CodexOptions (Global/Client-level)

```python
from codex import CodexOptions

@dataclass(frozen=True, slots=True)
class CodexOptions:
    codex_path_override: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
```

**Fields:**
- `codex_path_override`: Override the bundled codex binary location (for testing/custom builds)
- `base_url`: OpenAI API base URL (default: official OpenAI endpoint)
- `api_key`: API authentication key (read from CODEX_API_KEY env var if not set)

### 2.2 ThreadOptions (Thread-level Configuration)

```python
from codex import ThreadOptions, SandboxMode

@dataclass(frozen=True, slots=True)
class ThreadOptions:
    model: Optional[str] = None
    sandbox_mode: Optional[SandboxMode] = None
    working_directory: Optional[str] = None
    skip_git_repo_check: bool = False
```

**Fields:**
- `model`: Model to use (e.g., "gpt-4", "gpt-4-turbo")
- `sandbox_mode`: Execution sandbox level - SandboxMode enum:
  - `READ_ONLY`: No file modifications allowed
  - `WORKSPACE_WRITE`: Can modify files in workspace
  - `DANGER_FULL_ACCESS`: Full system access
- `working_directory`: Directory to run commands in (requires git repo unless `skip_git_repo_check=True`)
- `skip_git_repo_check`: Allow non-git directories as working directory

**ApprovalMode (Enum):**
```python
from codex import ApprovalMode

class ApprovalMode(StrEnum):
    NEVER = "never"
    ON_REQUEST = "on-request"
    ON_FAILURE = "on-failure"
    UNTRUSTED = "untrusted"
```

**Values:**
- `NEVER = "never"` - Never ask for user approval
- `ON_REQUEST = "on-request"` - Model decides when to ask
- `ON_FAILURE = "on-failure"` - Ask only if command fails
- `UNTRUSTED = "untrusted"` - Ask for untrusted commands only

**Example:**
```python
from codex import Codex, ThreadOptions, SandboxMode

client = Codex()
thread = client.start_thread(ThreadOptions(
    model="gpt-4",
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
    working_directory="/path/to/project",
    skip_git_repo_check=False
))
```

### 2.3 TurnOptions (Turn/Request-level Configuration)

```python
from codex import TurnOptions

@dataclass(frozen=True, slots=True)
class TurnOptions:
    output_schema: Optional[SchemaInput] = None
```

**Fields:**
- `output_schema`: Schema to constrain output format
  - Can be a dict (JSON Schema)
  - Can be a Pydantic BaseModel class or instance
  - If provided, output will be validated against schema

**Example:**
```python
from pydantic import BaseModel
from codex import TurnOptions

class StatusReport(BaseModel):
    summary: str
    status: str
    action_required: bool

turn = thread.run(
    "Summarize repository status",
    TurnOptions(output_schema=StatusReport)
)

# Or with JSON Schema dict:
schema = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "status": {"type": "string", "enum": ["ok", "action_required"]},
    },
    "required": ["summary", "status"],
    "additionalProperties": False,
}
turn = thread.run("Summarize", TurnOptions(output_schema=schema))
```

---

## 3. Thread Methods - What Can Be Passed

### 3.1 Synchronous Execution

**Method: `thread.run(prompt: str, turn_options: Optional[TurnOptions] = None) -> ThreadRunResult`**

Executes a prompt and blocks until completion, collecting all events.

**Parameters:**
- `prompt` (str): User input/prompt for the agent
- `turn_options` (Optional[TurnOptions]): Turn-level configuration (output schema, etc.)

**Returns: `ThreadRunResult`**
```python
@dataclass(frozen=True, slots=True)
class ThreadRunResult:
    items: list[ThreadItem]           # All completed items from the turn
    final_response: str               # Final agent message text
    usage: Optional[Usage]            # Token usage information
```

**Example:**
```python
thread = client.start_thread()
result = thread.run("What's the repository status?")

print(result.final_response)  # Agent's response
print(result.usage.input_tokens)  # Token info
for item in result.items:
    print(f"Item type: {item.type}")
```

### 3.2 Streaming Execution

**Method: `thread.run_streamed(prompt: str, turn_options: Optional[TurnOptions] = None) -> ThreadStream`**

Executes a prompt and streams events in real-time.

**Parameters:**
- Same as `thread.run()`

**Returns: `ThreadStream`** (iterable of events)

**Example:**
```python
from codex import ItemCompletedEvent, TurnCompletedEvent

stream = thread.run_streamed("Fix the bug")
for event in stream:
    if isinstance(event, ItemCompletedEvent):
        print(f"Item completed: {event.item.type}")
    elif isinstance(event, TurnCompletedEvent):
        print(f"Turn complete, tokens: {event.usage}")
```

---

## 4. Response Structure & What Comes Back

### 4.1 Events

The SDK streams structured **ThreadEvent** objects. All events come back as strongly-typed dataclasses.

**ThreadEvent Union Type:**
```
ThreadEvent = (
    ThreadStartedEvent
    | TurnStartedEvent
    | TurnCompletedEvent
    | TurnFailedEvent
    | ItemStartedEvent
    | ItemUpdatedEvent
    | ItemCompletedEvent
    | ThreadErrorEvent
)
```

### 4.2 Event Types

#### ThreadStartedEvent
```python
@dataclass(frozen=True, slots=True)
class ThreadStartedEvent:
    type: Literal["thread.started"] = "thread.started"
    thread_id: str
```
- Fired when thread is created
- Assigns thread ID for later resumption
- Automatically updates `thread.id` property

#### TurnStartedEvent
```python
@dataclass(frozen=True, slots=True)
class TurnStartedEvent:
    type: Literal["turn.started"] = "turn.started"
```
- Marks beginning of a turn

#### TurnCompletedEvent
```python
@dataclass(frozen=True, slots=True)
class TurnCompletedEvent:
    type: Literal["turn.completed"] = "turn.completed"
    usage: Usage
```
- Fired when turn completes successfully
- Includes token usage metadata

#### TurnFailedEvent
```python
@dataclass(frozen=True, slots=True)
class TurnFailedEvent:
    type: Literal["turn.failed"] = "turn.failed"
    error: ThreadError
```
- Turn encountered an error
- Contains error message

#### ItemStartedEvent, ItemUpdatedEvent, ItemCompletedEvent
```python
@dataclass(frozen=True, slots=True)
class ItemStartedEvent:
    type: Literal["item.started"] = "item.started"
    item: ThreadItem

@dataclass(frozen=True, slots=True)
class ItemUpdatedEvent:
    type: Literal["item.updated"] = "item.updated"
    item: ThreadItem

@dataclass(frozen=True, slots=True)
class ItemCompletedEvent:
    type: Literal["item.completed"] = "item.completed"
    item: ThreadItem
```
- Track item lifecycle (reasoning, commands, file changes, etc.)

#### ThreadErrorEvent
```python
@dataclass(frozen=True, slots=True)
class ThreadErrorEvent:
    type: Literal["error"] = "error"
    message: str
```
- Unrecoverable SDK-level error

### 4.3 Usage Information

```python
@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
```

Available in `TurnCompletedEvent` and `ThreadRunResult.usage`

### 4.4 Thread Items

**ThreadItem Union Type:**
```
ThreadItem = (
    AgentMessageItem
    | ReasoningItem
    | CommandExecutionItem
    | FileChangeItem
    | McpToolCallItem
    | WebSearchItem
    | TodoListItem
    | ErrorItem
)
```

#### AgentMessageItem
```python
@dataclass(frozen=True, slots=True)
class AgentMessageItem:
    type: Literal["agent_message"] = "agent_message"
    id: str
    text: str
```
- Agent's text response

#### ReasoningItem
```python
@dataclass(frozen=True, slots=True)
class ReasoningItem:
    type: Literal["reasoning"] = "reasoning"
    id: str
    text: str
```
- Agent's internal reasoning/thinking

#### CommandExecutionItem
```python
@dataclass(frozen=True, slots=True)
class CommandExecutionItem:
    type: Literal["command_execution"] = "command_execution"
    id: str
    command: str
    aggregated_output: str
    status: CommandExecutionStatus
    exit_code: int | None = None
```
- Command execution with output
- Status: `IN_PROGRESS`, `COMPLETED`, or `FAILED`

#### FileChangeItem
```python
@dataclass(frozen=True, slots=True)
class FileChangeItem:
    type: Literal["file_change"] = "file_change"
    id: str
    changes: Sequence[FileUpdateChange]
    status: PatchApplyStatus

@dataclass(frozen=True, slots=True)
class FileUpdateChange:
    path: str
    kind: PatchChangeKind  # ADD, DELETE, UPDATE
```
- File modifications with patch tracking
- Status: `COMPLETED` or `FAILED`

#### McpToolCallItem
```python
@dataclass(frozen=True, slots=True)
class McpToolCallItem:
    type: Literal["mcp_tool_call"] = "mcp_tool_call"
    id: str
    server: str
    tool: str
    status: McpToolCallStatus
```
- MCP (Model Context Protocol) tool invocation
- Status: `IN_PROGRESS`, `COMPLETED`, or `FAILED`

#### WebSearchItem
```python
@dataclass(frozen=True, slots=True)
class WebSearchItem:
    type: Literal["web_search"] = "web_search"
    id: str
    query: str
```
- Web search execution

#### TodoListItem
```python
@dataclass(frozen=True, slots=True)
class TodoListItem:
    type: Literal["todo_list"] = "todo_list"
    id: str
    items: Sequence[TodoItem]

@dataclass(frozen=True, slots=True)
class TodoItem:
    text: str
    completed: bool
```
- Task lists generated by agent

#### ErrorItem
```python
@dataclass(frozen=True, slots=True)
class ErrorItem:
    type: Literal["error"] = "error"
    id: str
    message: str
```
- Item-level errors

---

## 5. Advanced Features

### 5.1 Streaming

Real-time event streaming with `thread.run_streamed()`:

```python
stream = thread.run_streamed("Implement the fix")
for event in stream:
    match event:
        case ThreadStartedEvent() as e:
            print(f"Thread: {e.thread_id}")
        case ItemCompletedEvent(item=item):
            print(f"Item: {item.type}")
        case TurnCompletedEvent(usage=usage):
            print(f"Tokens: {usage.input_tokens}")
        case TurnFailedEvent(error=err):
            print(f"Failed: {err.message}")
        case ThreadErrorEvent(message=msg):
            print(f"Error: {msg}")
```

### 5.2 Structured Output with Schema Validation

Constrain agent output to structured format:

```python
from pydantic import BaseModel
from codex import TurnOptions

class BugReport(BaseModel):
    severity: str
    component: str
    fix_steps: list[str]

schema = BugReport  # Can pass class directly

result = thread.run(
    "Analyze the bug in error.log",
    TurnOptions(output_schema=schema)
)
# Output will be validated against schema
print(result.final_response)  # Structured JSON response
```

### 5.3 Tool Calling (MCP Integration)

The SDK automatically handles MCP (Model Context Protocol) tool calls through `McpToolCallItem` events:

```python
for event in thread.run_streamed(prompt):
    if isinstance(event, ItemCompletedEvent):
        if isinstance(event.item, McpToolCallItem):
            print(f"Tool called: {event.item.server}.{event.item.tool}")
            print(f"Status: {event.item.status}")
```

### 5.4 Multi-turn Conversations

Threads maintain state across multiple turns:

```python
thread = client.start_thread()

# First turn
result1 = thread.run("What's the problem?")
print(result1.final_response)

# Second turn - previous context is maintained
result2 = thread.run("What's the fix?")
print(result2.final_response)

# Can also resume later
thread_id = thread.id
resumed = client.resume_thread(thread_id)
result3 = resumed.run("How to test it?")
```

### 5.5 Stateful vs Stateless

**Stateful (Thread):**
- Thread maintains conversation history
- Each `run()` or `run_streamed()` adds to the thread's context
- Can `resume_thread()` by ID across sessions
- Items from previous turns are included in subsequent turns

**Stateless (Turn):**
- Each `run()` call is independent in terms of what you can control
- The actual threading and history is managed by the underlying Codex CLI
- SDK aggregates results into clean `ThreadRunResult` or event streams

### 5.6 DSPy Wrapper - CodexAgent

**Module:** `codex_dspy`

The `CodexAgent` class provides a DSPy module interface to the Codex SDK, enabling signature-driven agent interactions with type-safe inputs and outputs.

**Class: CodexAgent**

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

**Parameters:**
- `signature`: DSPy signature defining input/output interface (must have exactly 1 input field and 1 output field)
- `working_directory`: Directory for agent to execute commands in
- `model`: Model to use (e.g., "gpt-4", "gpt-4-turbo"). Defaults to Codex default.
- `sandbox_mode`: Execution sandbox level (READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS)
- `skip_git_repo_check`: Allow non-git directories as working_directory
- `api_key`: OpenAI API key (falls back to CODEX_API_KEY env var)
- `base_url`: API base URL (falls back to OPENAI_BASE_URL env var)
- `codex_path_override`: Override path to codex binary (for testing/custom builds)

**Methods:**

```python
def forward(self, **kwargs) -> Prediction:
    """Execute agent with input message.

    Returns:
        Prediction with:
            - Typed output field (name from signature)
            - trace: list[ThreadItem]
            - usage: Usage
    """

@property
def thread_id(self) -> Optional[str]:
    """Get thread ID for this agent instance."""
```

**Supported Output Types:**
- String types: `str`, `Optional[str]`
- Pydantic types: Any `BaseModel` subclass

**Thread Management:**
- Each CodexAgent instance = one stateful thread
- Multiple forward() calls continue the same conversation
- Thread ID assigned after first forward() call
- Access thread ID via `agent.thread_id` property

**Example - Basic String Output:**
```python
import dspy
from codex_dspy import CodexAgent

sig = dspy.Signature('message:str -> answer:str')
agent = CodexAgent(sig, working_directory='.')
result = agent(message='List files in this directory')

print(result.answer)  # str - final response
print(result.trace)   # list[ThreadItem] - chronological items
print(result.usage)   # Usage - token counts
```

**Example - Structured Pydantic Output:**
```python
from pydantic import BaseModel
import dspy
from codex_dspy import CodexAgent

class BugReport(BaseModel):
    severity: str
    component: str
    fix_steps: list[str]

sig = dspy.Signature('message:str -> report:BugReport')
agent = CodexAgent(sig, working_directory='.')
result = agent(message='Analyze the bug in src/main.py')

print(result.report.severity)  # Typed access to Pydantic model
print(result.report.fix_steps)
print(result.trace)  # Full trace of agent actions
```

**Example - Multi-turn Conversation:**
```python
import dspy
from codex_dspy import CodexAgent

sig = dspy.Signature('message:str -> answer:str')
agent = CodexAgent(sig, working_directory='.')

# First turn
result1 = agent(message="What's the repository status?")
print(result1.answer)

# Second turn - context is preserved
result2 = agent(message="What needs to be fixed?")
print(result2.answer)

# Thread ID available after first call
print(agent.thread_id)
```

**Return Value - Prediction:**
The `forward()` method returns a `dspy.Prediction` object with:
- Named output field (from signature): Either `str` or typed `BaseModel` instance
- `trace`: `list[ThreadItem]` - All items from the turn (commands, file changes, reasoning, etc.)
- `usage`: `Usage` - Token usage information (input_tokens, cached_input_tokens, output_tokens)

**Signature Requirements:**
- Must have exactly 1 input field
- Must have exactly 1 output field
- Output field must be either:
  - `str` or `Optional[str]` for text responses
  - A Pydantic `BaseModel` subclass for structured output

---

## 6. Exception Handling

```python
from codex import (
    CodexError,                # Base exception
    UnsupportedPlatformError,  # Unsupported OS/arch
    SpawnError,                # Failed to start CLI
    ExecExitError,             # CLI exited with error
    JsonParseError,            # Event parsing failed
    ThreadRunError,            # Turn execution failed
    SchemaValidationError,     # Invalid output schema
)

try:
    result = thread.run(prompt, TurnOptions(output_schema=schema))
except ThreadRunError as e:
    print(f"Turn failed: {e}")
except SchemaValidationError as e:
    print(f"Invalid schema: {e}")
except CodexError as e:
    print(f"SDK error: {e}")
```

---

## 7. Usage Examples

### Example 1: Basic Synchronous Usage

```python
from codex import Codex

client = Codex()
thread = client.start_thread()
result = thread.run("Summarize the latest CI failure")

print(f"Response: {result.final_response}")
print(f"Items processed: {len(result.items)}")
print(f"Tokens used: {result.usage.input_tokens}")
```

### Example 2: Streaming with Pattern Matching

```python
from codex import (
    Codex,
    ItemCompletedEvent,
    CommandExecutionItem,
    TurnCompletedEvent,
)

client = Codex()
thread = client.start_thread()

stream = thread.run_streamed("Fix the failing test")
for event in stream:
    match event:
        case ItemCompletedEvent(item=CommandExecutionItem() as cmd):
            print(f"Command: {cmd.command}")
            print(f"Output: {cmd.aggregated_output}")
        case ItemCompletedEvent(item=item):
            print(f"Item {item.id}: {item.type}")
        case TurnCompletedEvent(usage=usage):
            print(f"Done! Used {usage.input_tokens} input tokens")
```

### Example 3: Structured Output with Pydantic

```python
from pydantic import BaseModel, Field
from codex import Codex, TurnOptions

class CodeReview(BaseModel):
    summary: str
    issues: list[str] = Field(description="List of issues found")
    severity: str = Field(
        description="critical, warning, or info"
    )

client = Codex()
thread = client.start_thread()

result = thread.run(
    "Review the changes in src/main.py",
    TurnOptions(output_schema=CodeReview)
)

print(result.final_response)  # JSON that conforms to CodeReview schema
```

### Example 4: Multi-turn with Configuration

```python
from codex import Codex, ThreadOptions, SandboxMode

client = Codex()

# Start thread with specific config
thread = client.start_thread(ThreadOptions(
    model="gpt-4",
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
    working_directory="/path/to/repo"
))

# First turn
result1 = thread.run("What needs to be fixed?")
print(result1.final_response)

# Second turn - context preserved
result2 = thread.run("Implement the fix")
print(result2.final_response)

# Can resume later
thread_id = thread.id
new_client = Codex()
resumed_thread = new_client.resume_thread(thread_id)
result3 = resumed_thread.run("Write tests for the fix")
```

---

## 8. Command Line Arguments Passed to Codex Binary

The SDK builds the following CLI args when executing:

```
codex exec --experimental-json \
  [--model MODEL] \
  [--sandbox SANDBOX_MODE] \
  [--cd WORKING_DIR] \
  [--skip-git-repo-check] \
  [--output-schema SCHEMA_PATH] \
  [resume THREAD_ID]
```

**Key Implementation Details:**
- Input is piped to stdin
- Output is streamed from stdout (JSON-Lines format)
- Stderr is captured for error reporting
- Environment variables set:
  - `OPENAI_BASE_URL`: From `CodexOptions.base_url`
  - `CODEX_API_KEY`: From `CodexOptions.api_key`
  - `CODEX_INTERNAL_ORIGINATOR_OVERRIDE`: Set to `"codex_sdk_py"`

---

## 9. Binary Discovery & Platform Support

The SDK auto-detects platform and locates the Codex binary:

**Supported Platforms:**
- Linux x86_64: `x86_64-unknown-linux-musl`
- Linux ARM64: `aarch64-unknown-linux-musl`
- macOS x86_64: `x86_64-apple-darwin`
- macOS ARM64: `aarch64-apple-darwin`
- Windows x86_64: `x86_64-pc-windows-msvc`
- Windows ARM64: `aarch64-pc-windows-msvc`

**Binary Discovery:**

Binaries are **not yet vendored** in this repository. The SDK searches for the `codex` binary in the following order:
1. `codex_path_override` parameter if provided
2. System PATH

**Expected vendor location (future):**
```
src/codex/vendor/{target}/codex[.exe]
```

**Override via Parameter:**
```python
from codex import Codex, CodexOptions

client = Codex(CodexOptions(
    codex_path_override="/path/to/custom/codex"
))
```

**Override via CodexAgent:**
```python
from codex_dspy import CodexAgent

agent = CodexAgent(
    signature='message:str -> answer:str',
    working_directory='.',
    codex_path_override="/path/to/custom/codex"
)
```

**Implementation:**
See `/Users/darin/projects/codex_dspy/src/codex/discovery.py` for platform detection and binary discovery logic.

---

## 10. Type Safety & Schema Handling

The SDK provides full type safety:

- All events are **frozen dataclasses** (immutable)
- All configuration objects are frozen
- Thread items are **union types** - use `isinstance()` for type narrowing
- Output schema supports:
  - **Dict-based JSON Schema** (standard format)
  - **Pydantic models** (automatically converted to JSON Schema)
  - **Pydantic model instances** (uses `.model_json_schema()`)

Schema handling:
```python
# Automatic Pydantic conversion
from pydantic import BaseModel

class MyModel(BaseModel):
    field: str

# Both work:
TurnOptions(output_schema=MyModel)           # Pass class
TurnOptions(output_schema=MyModel())         # Pass instance

# Raw JSON Schema also works
TurnOptions(output_schema={"type": "object", "properties": {...}})
```

---

## Summary Table: API Surface

| Component | Purpose | Key Methods/Properties |
|-----------|---------|----------------------|
| **Codex** | Client initialization | `start_thread()`, `resume_thread()` |
| **CodexOptions** | Global config | `codex_path_override`, `base_url`, `api_key` |
| **Thread** | Conversation session | `run()`, `run_streamed()`, `id` property |
| **ThreadOptions** | Thread config | `model`, `sandbox_mode`, `working_directory`, `skip_git_repo_check` |
| **TurnOptions** | Turn config | `output_schema` |
| **ThreadRunResult** | Sync result | `items`, `final_response`, `usage` |
| **ThreadStream** | Async result | Iterator of `ThreadEvent` |
| **Events** | Lifecycle tracking | `ThreadStartedEvent`, `TurnCompletedEvent`, `ItemCompletedEvent`, etc. |
| **ThreadItems** | Work artifacts | `AgentMessageItem`, `CommandExecutionItem`, `FileChangeItem`, `McpToolCallItem`, etc. |
| **Exceptions** | Error handling | `ThreadRunError`, `SchemaValidationError`, `CodexError` |
| **CodexAgent** | DSPy wrapper | `forward()`, `thread_id` property |
| **ApprovalMode** | Approval config | `NEVER`, `ON_REQUEST`, `ON_FAILURE`, `UNTRUSTED` |
| **SandboxMode** | Sandbox config | `READ_ONLY`, `WORKSPACE_WRITE`, `DANGER_FULL_ACCESS` |


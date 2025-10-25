# Codex Python SDK - Architecture & Data Flow

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Python Application                        │
├─────────────────────────────────────────────────────────────┤
│                    Codex Python SDK                          │
│  ┌────────────┐                                              │
│  │   Codex    │ Client (main entry point)                   │
│  │   Client   │                                              │
│  └──────┬─────┘                                              │
│         │                                                     │
│    ┌────┴────────────────┐                                   │
│    │                     │                                   │
│  ┌─────────────┐  ┌────────────────┐                         │
│  │ start_thread│  │ resume_thread  │ Create/resume thread   │
│  └──────┬──────┘  └────────┬───────┘                         │
│         │                  │                                 │
│    ┌────▼──────────────────▼────┐                            │
│    │  Thread (conversation)     │                            │
│    │ ┌──────────────────────┐   │                            │
│    │ │ run() - sync execute │   │                            │
│    │ │ run_streamed() - async  │ Thread Methods             │
│    │ └──────────────────────┘   │                            │
│    └────┬──────────────────────┬─┘                           │
│         │                      │                             │
│  ┌──────▼───┐        ┌────────▼────────┐                    │
│  │ThreadRun │        │  ThreadStream   │                    │
│  │ Result   │        │   (events)      │ Response Types    │
│  └──────────┘        └─────────────────┘                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         │                              │
         │ (stdin/stdout pipes)         │
         │                              │
┌────────▼──────────────────────────────▼────────────────────┐
│           Native Codex Binary (Rust)                       │
│  (codex exec --experimental-json ...)                      │
└────────────────────┬─────────────────────────────────────┘
         │
         │ (JSON-Lines events)
         │
┌────────▼──────────────────────────────────────────────────┐
│      OpenAI API / Model Backend                            │
└───────────────────────────────────────────────────────────┘
```

## Data Flow - Synchronous Execution

```
Application Code
       │
       │ thread.run("prompt")
       ▼
┌─────────────────────────────┐
│ Thread.run()                │
├─────────────────────────────┤
│ 1. Prepare schema file      │
│ 2. Build command args       │
│ 3. Call _stream_events()    │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Thread._stream_events()     │
├─────────────────────────────┤
│ 1. Create ExecArgs          │
│ 2. Build CLI command        │
│ 3. Spawn subprocess         │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ CodexExec.run_lines()       │
├─────────────────────────────┤
│ 1. Write prompt to stdin    │
│ 2. Read stdout line-by-line │
│ 3. Parse JSON events        │
│ 4. Yield parsed events      │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Event Parsing               │
├─────────────────────────────┤
│ JSON → ThreadEvent objects  │
│ (ItemStarted, Complete etc) │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Thread.run() aggregates     │
├─────────────────────────────┤
│ 1. Collect all items        │
│ 2. Extract final response   │
│ 3. Get usage info           │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ ThreadRunResult             │
│ {items, final_response,     │
│  usage}                     │
└──────────┬──────────────────┘
           │
           ▼
Application Code (with result)
```

## Data Flow - Streaming Execution

```
Application Code
       │
       │ thread.run_streamed("prompt")
       ▼
┌─────────────────────────────┐
│ Thread.run_streamed()       │
├─────────────────────────────┤
│ 1. Call _stream_events()    │
│ 2. Wrap in ThreadStream     │
│ 3. Return iterator          │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ ThreadStream (iterator)     │
└──────────┬──────────────────┘
           │
           ▼
for event in stream:
       │
       │ (lazy evaluation)
       ▼
┌─────────────────────────────┐
│ _stream_events() generator  │
└──────────┬──────────────────┘
           │
           ├──────────────────────────┐
           │                          │
           ▼                          ▼
┌──────────────────────┐   ┌────────────────────┐
│ Subprocess stdout    │   │ Real-time event    │
│ (JSON-Lines)        │   │ processing         │
└────────┬─────────────┘   └────────┬───────────┘
         │                          │
         ├─ThreadStartedEvent───────┤
         │                          │
         ├─TurnStartedEvent─────────┤
         │                          │
         ├─ItemStartedEvent─────────┤
         │                          │
         ├─ItemUpdatedEvent─────────┤
         │                          │
         ├─ItemCompletedEvent───────┤
         │                          │
         ├─TurnCompletedEvent───────┤
         │                          ▼
         │              Application processes
         │              each event in real-time
         │
         └─(yields back to for loop)
```

## Configuration Hierarchy

```
Global (Codex Client)
  │
  ├─ codex_path_override ──┐
  │                        │
  ├─ base_url              │  Applied to all threads
  │                        │
  └─ api_key ──────────────┤
                           │
                    ┌──────┘
                    │
                    ▼
            Thread-Level
            │
            ├─ model ────────┐
            │                │  Applied to all turns
            ├─ sandbox_mode  │   in this thread
            │                │
            ├─ working_dir   │
            │                │
            └─ skip_git_check┤
                             │
                      ┌──────┘
                      │
                      ▼
                Turn-Level
                │
                └─ output_schema  ◄─ Only for this turn
```

## Event Lifecycle Sequence

```
┌──────────────────────────────────────────────────────────┐
│                    Event Sequence                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ 1. ThreadStartedEvent                                  │
│    └─ thread_id assigned                               │
│                                                          │
│ 2. TurnStartedEvent                                    │
│    └─ turn begins                                      │
│                                                          │
│ 3. ItemStartedEvent (0 or more)                        │
│    └─ item.id, item.type assigned                      │
│                                                          │
│ 4. ItemUpdatedEvent (0 or more)                        │
│    └─ item state changes (mid-execution)               │
│                                                          │
│ 5. ItemCompletedEvent (matches ItemStarted count)      │
│    └─ final item.status set                            │
│                                                          │
│ 6. TurnCompletedEvent or TurnFailedEvent               │
│    └─ turn.usage populated (if completed)              │
│    └─ error info (if failed)                           │
│                                                          │
│ 7. ThreadErrorEvent (only if SDK error)                │
│    └─ unrecoverable error                              │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Item Types & Their Lifecycles

```
┌─ AgentMessageItem
│  Status: Instant (starts and completes together)
│  Lifecycle: ItemStarted → ItemCompleted
│
├─ ReasoningItem
│  Status: Instant (agent's thinking)
│  Lifecycle: ItemStarted → ItemCompleted
│
├─ CommandExecutionItem
│  Status: Evolves (IN_PROGRESS → COMPLETED/FAILED)
│  Lifecycle: ItemStarted → ItemUpdated* → ItemCompleted
│
├─ FileChangeItem
│  Status: Evolves (patch application)
│  Lifecycle: ItemStarted → ItemUpdated* → ItemCompleted
│  Status Values: COMPLETED or FAILED
│
├─ McpToolCallItem
│  Status: Evolves (IN_PROGRESS → COMPLETED/FAILED)
│  Lifecycle: ItemStarted → ItemUpdated* → ItemCompleted
│
├─ WebSearchItem
│  Status: Instant
│  Lifecycle: ItemStarted → ItemCompleted
│
├─ TodoListItem
│  Status: Static list
│  Lifecycle: ItemStarted → ItemCompleted
│
└─ ErrorItem
   Status: Error state
   Lifecycle: ItemStarted → ItemCompleted
```

## Message Flow to API

```
┌─ Thread.run(prompt, TurnOptions)
│
├─ Previous turn items collected into history
│
├─ Prompt converted to user message
│
├─ Schema validated & written to temp file (if needed)
│
└─ Binary invoked with:
   │
   ├─ stdin: prompt
   ├─ --model: model name
   ├─ --sandbox: sandbox mode
   ├─ --cd: working directory
   ├─ --output-schema: schema file path (if provided)
   ├─ resume: thread_id (if resuming)
   │
   └─ environ:
      ├─ OPENAI_BASE_URL: from CodexOptions.base_url
      ├─ CODEX_API_KEY: from CodexOptions.api_key
      └─ CODEX_INTERNAL_ORIGINATOR_OVERRIDE: "codex_sdk_py"
```

## State Management

```
Thread Object State
│
├─ _id: Optional[str]
│  │  Initially None
│  │  Set when ThreadStartedEvent received
│  │  Accessible via thread.id property
│  │
│  └─ Persists across multiple run() calls
│
├─ _codex_options: CodexOptions (immutable)
│  │  Set at client creation
│  │  Never changes
│  │
│  └─ Shared across threads
│
├─ _thread_options: ThreadOptions (immutable)
│  │  Set at thread creation
│  │  Never changes
│  │
│  └─ Per-thread configuration
│
└─ _exec: CodexExec (immutable)
   │  Set at client creation
   │  Manages binary invocation
   │
   └─ Shared across threads
```

## Memory & Resource Management

```
┌─ Subprocess Lifecycle
│  │
│  ├─ Spawned: subprocess.Popen()
│  │
│  ├─ Input: prompt written to stdin
│  │
│  ├─ Output: stdout read line-by-line
│  │
│  ├─ Stderr: collected in background thread
│  │
│  └─ Cleanup:
│     ├─ stdout.close()
│     ├─ stderr.close()
│     ├─ process.wait() or process.kill()
│     └─ Guaranteed in finally block
│
├─ Schema File Lifecycle (TempFile Context Manager)
│  │
│  ├─ Created: tempfile.TemporaryDirectory()
│  │
│  ├─ Used: schema.json written
│  │
│  ├─ Passed: --output-schema /tmp/codex-output-schema-{id}/schema.json
│  │
│  └─ Cleaned: __exit__() removes temp directory
│
└─ Event Objects (Immutable)
   │
   ├─ All ThreadEvent objects are frozen dataclasses
   │
   ├─ All ThreadItem objects are frozen dataclasses
   │
   └─ Safe to store and reference across code
```

## Error Handling Flow

```
┌─ Exception Raised
│
├──────────────────────────────────┐
│                                  │
▼                                  ▼
Platform/Binary Error         SDK/API Error
│                                  │
├─ UnsupportedPlatformError   ├─ SchemaValidationError
├─ SpawnError                 ├─ JsonParseError
├─ ExecExitError              ├─ ThreadRunError
│                             └─ ThreadErrorEvent
│
└─ All inherit from CodexError
```

## Type System

```
ThreadEvent (Union)
├─ ThreadStartedEvent
├─ TurnStartedEvent
├─ TurnCompletedEvent
├─ TurnFailedEvent
├─ ItemStartedEvent
├─ ItemUpdatedEvent
├─ ItemCompletedEvent
└─ ThreadErrorEvent

ThreadItem (Union)
├─ AgentMessageItem
├─ ReasoningItem
├─ CommandExecutionItem
├─ FileChangeItem
├─ McpToolCallItem
├─ WebSearchItem
├─ TodoListItem
└─ ErrorItem

Status Enums
├─ CommandExecutionStatus: IN_PROGRESS, COMPLETED, FAILED
├─ PatchApplyStatus: COMPLETED, FAILED
├─ McpToolCallStatus: IN_PROGRESS, COMPLETED, FAILED
├─ PatchChangeKind: ADD, DELETE, UPDATE
├─ SandboxMode: READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS
└─ ApprovalMode: NEVER, ON_REQUEST, ON_FAILURE, UNTRUSTED
```

## Configuration Resolution

```
CodexOptions
(from Codex constructor)
       │
       ├─ api_key
       │  │  Priority: constructor → environment (CODEX_API_KEY)
       │  └─ Passed as CODEX_API_KEY env var
       │
       ├─ base_url
       │  │  Priority: constructor → environment (OPENAI_BASE_URL)
       │  └─ Passed as OPENAI_BASE_URL env var
       │
       └─ codex_path_override
          │  Priority: constructor → binary discovery → PATH lookup
          └─ Binary location:
             │  1. Check codex_path_override if provided
             │  2. Check src/codex/vendor/{target}/codex
             │  3. Fall back to system PATH (binaries not yet vendored)
```

## Binary Discovery

```
find_codex_binary(override: str | None) -> Path

Discovery Flow:
│
├─ Override provided?
│  └─ Yes → return Path(override)
│
├─ Detect platform target:
│  ├─ Linux x86_64   → x86_64-unknown-linux-musl
│  ├─ Linux aarch64  → aarch64-unknown-linux-musl
│  ├─ macOS x86_64   → x86_64-apple-darwin
│  ├─ macOS aarch64  → aarch64-apple-darwin
│  ├─ Windows x86_64 → x86_64-pc-windows-msvc
│  └─ Windows arm64  → aarch64-pc-windows-msvc
│
├─ Build vendor path:
│  └─ src/codex/vendor/{target}/codex[.exe]
│
└─ Return vendor path
   │
   └─ Note: vendor/ directory exists but binaries are not yet vendored.
             The SDK will attempt to use the binary from this path,
             but currently relies on system PATH for execution.
```

## DSPy Wrapper Integration

The `codex_dspy` package provides a DSPy module that wraps the Codex SDK for signature-driven workflows. This enables using Codex agents as declarative components in DSPy programs.

### CodexAgent Module

```
┌─────────────────────────────────────────────────────────┐
│                    DSPy Application                     │
├─────────────────────────────────────────────────────────┤
│                    CodexAgent Module                    │
│  ┌────────────────────────────────────────────┐         │
│  │  __init__(signature, working_directory)    │         │
│  │    - Validates signature (1 input, 1 output)        │
│  │    - Creates Codex client                  │         │
│  │    - Starts thread (1 agent = 1 thread)    │         │
│  └────────────────────────────────────────────┘         │
│  ┌────────────────────────────────────────────┐         │
│  │  forward(**kwargs) -> Prediction           │         │
│  │    - Extracts input from kwargs            │         │
│  │    - Calls thread.run() with message       │         │
│  │    - Parses response (str or Pydantic)     │         │
│  │    - Returns Prediction with trace/usage   │         │
│  └────────────────────────────────────────────┘         │
│  ┌────────────────────────────────────────────┐         │
│  │  thread_id property                        │         │
│  │    - Returns thread.id for debugging       │         │
│  └────────────────────────────────────────────┘         │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
         Codex SDK (as documented above)
```

### Key Characteristics

**Thread State Management:**
- Each CodexAgent instance maintains exactly one conversation thread
- Multiple `forward()` calls on the same instance continue the same conversation
- Thread context accumulates across calls (conversation history is preserved)
- Access thread ID via `agent.thread_id` property for debugging

**Signature-Driven Interface:**
- Requires exactly 1 input field and 1 output field
- Input field: name determines kwarg name in `forward()`
- Output field: name determines field name in returned Prediction

**Output Type Handling:**
- String output: Returns final_response as-is (no schema required)
- Pydantic output:
  - Generates JSON schema from Pydantic model
  - Sets `additionalProperties: false` for strict validation
  - Passes schema to Codex via TurnOptions
  - Parses final_response as JSON into Pydantic model
  - Raises ValueError with response preview if parsing fails

**Return Value:**
- Returns DSPy `Prediction` object with:
  - Typed output field (str or Pydantic model instance)
  - `trace`: List[ThreadItem] - chronological items (commands, files, reasoning, etc.)
  - `usage`: Usage object - token counts (input_tokens, cached_input_tokens, output_tokens)

### Example Usage

**Basic String I/O:**
```python
import dspy
from codex_dspy import CodexAgent
from codex import SandboxMode

# Create signature with string input/output
sig = dspy.Signature('message:str -> answer:str')

# Create agent (starts a thread)
agent = CodexAgent(
    sig,
    working_directory='.',
    sandbox_mode=SandboxMode.READ_ONLY
)

# First forward call
result = agent(message='What files are here?')
print(result.answer)  # Clean string response
print(result.trace)   # List of items (commands, files, etc.)
print(result.usage)   # Usage(input_tokens=..., output_tokens=...)

# Second forward call (continues same thread)
result = agent(message='Count the Python files')
print(result.answer)  # Agent has context from previous call
print(agent.thread_id)  # Thread ID for debugging
```

**Pydantic-Typed Output:**
```python
from pydantic import BaseModel
import dspy
from codex_dspy import CodexAgent

# Define typed output
class FileAnalysis(BaseModel):
    total_files: int
    languages: list[str]
    has_tests: bool

# Create signature with Pydantic output
sig = dspy.Signature('directory:str -> analysis:FileAnalysis')

# Create agent
agent = CodexAgent(sig, working_directory='.')

# Forward call with typed parsing
result = agent(directory='src/')
print(result.analysis.total_files)  # Type-safe access
print(result.analysis.languages)    # Parsed from JSON
print(result.analysis.has_tests)    # Boolean field
```

### Integration with DSPy Optimizers

CodexAgent is a standard DSPy module and can be used in:
- Pipelines with other modules
- Optimizers (though Codex doesn't use traditional prompts)
- Multi-agent workflows (each agent maintains separate thread state)

**Important:** Because each CodexAgent instance is stateful, create new instances when you need independent conversation contexts.

### Configuration Parameters

```
CodexAgent Constructor Parameters:

Required:
├─ signature: str | type[Signature]
│  └─ Must have exactly 1 input and 1 output field
│
└─ working_directory: str
   └─ Directory where agent executes commands

Optional:
├─ model: Optional[str]
│  └─ Model name (e.g., "gpt-4", "gpt-4-turbo")
│  └─ Defaults to Codex SDK default
│
├─ sandbox_mode: Optional[SandboxMode]
│  ├─ READ_ONLY: No file modifications
│  ├─ WORKSPACE_WRITE: Modifications within working_directory
│  └─ DANGER_FULL_ACCESS: Unrestricted access
│
├─ skip_git_repo_check: bool (default: False)
│  └─ Allow non-git directories as working_directory
│
├─ api_key: Optional[str]
│  └─ Falls back to CODEX_API_KEY env var
│
├─ base_url: Optional[str]
│  └─ Falls back to OPENAI_BASE_URL env var
│
└─ codex_path_override: Optional[str]
   └─ Override binary path (for testing)
```

### Error Handling

**Signature Validation:**
- Raises ValueError if signature doesn't have exactly 1 input and 1 output field
- Provides helpful error message with example

**Pydantic Parsing:**
- Raises ValueError if response doesn't match Pydantic schema
- Includes response preview (first 500 chars) in error message
- Original exception included in chain for debugging

**SDK Errors:**
- All Codex SDK exceptions propagate unchanged
- See "Error Handling Flow" section for SDK error types


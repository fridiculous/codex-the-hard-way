# Source Reading Protocol

Codex the Hard Way should stay useful even as Codex changes. This protocol keeps chapters grounded without making them brittle.

## 1. Pin The Checkout

Every source-specific lab should record:

- Repository URL.
- Commit hash.
- Date inspected.
- How the code was built or run.

Use a short header like this:

```md
Source inspected:
- Repository: ...
- Commit: ...
- Date: ...
- Runtime: ...
```

## 2. Start With Behavior

Begin from something observable:

- A user turn.
- A tool call.
- An approval prompt.
- A patch application.
- A compacted context event.
- A failed command.

Then walk backward and forward through the source.

## 3. Prefer Source Probes

Use search terms that describe the boundary:

```sh
rg "approval|policy|sandbox" "$CODEX_SRC"
rg "tool_call|function_call|ToolCall" "$CODEX_SRC"
rg "apply_patch|patch" "$CODEX_SRC"
rg "conversation|session|turn" "$CODEX_SRC"
```

Record the query that found a file. Future readers can rerun it when paths change.

## 4. Classify What You Find

Each source location usually plays one of these roles:

- Data shape: structs, enums, schemas, protocol messages.
- Policy: allow, deny, ask, sandbox, escalate.
- Execution: actually runs a command, writes a file, or sends a request.
- Translation: converts one representation into another.
- Presentation: terminal, app UI, logs, or user-facing summaries.
- Tests: examples of intended behavior.

Do not collapse these roles too early. A clean mental model depends on knowing which layer owns which decision.

## 5. Produce A Durable Artifact

Every lab should end with one of:

- A timeline.
- A decision table.
- A source map.
- A sequence diagram.
- A minimal reproduction.
- A test or trace.

The artifact is the proof that the reader followed the code rather than only reading a description.


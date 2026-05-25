# Testing AGENTS.md And Approvals

This lecture is about testing two boundaries that are easy to misunderstand:

- `AGENTS.md` affects what the model is told.
- Approvals affect what the local harness is allowed to do.

Do not collapse those into one thing. An instruction file can influence the model's requested action, but it should not be trusted as a security boundary. Approval policy is enforced by the harness around tool execution.

## The Core Model

Think of a turn as two different tests running at once:

1. Prompt compilation test: what text, files, and tool schemas were sent to the model?
2. Policy enforcement test: once the model asked for an action, did the harness allow, deny, sandbox, or ask?

`AGENTS.md` belongs to the first test. Approvals belong to the second test.

## Testing AGENTS.md

The weak test is asking the model, "Did you read AGENTS.md?" That proves very little. The model can answer from context, guess, or paraphrase without proving how the instruction file entered the request.

The stronger test is to create a tiny fixture where `AGENTS.md` leaves an observable trace.

### Fixture

This repo includes a checked-in deterministic fixture at `fixtures/deterministic-turn` and an initializer at `scripts/run-deterministic-lab.sh`. The script copies the fixture into ignored `tmp/` space before running checks, so the guide repo is the source of truth but the experiment workspace stays disposable.

The fixture has this shape:

```text
fixture/
  AGENTS.md
  src/
    sample.txt
  nested/
    AGENTS.md
    sample.txt
```

Put a distinct, harmless sentinel in each instruction file:

```md
# Root Instructions

When editing files in this workspace, add the phrase ROOT_AGENT_SENTINEL to the final response.
```

```md
# Nested Instructions

When editing files under nested/, add the phrase NESTED_AGENT_SENTINEL to the final response.
```

Then run turns that target different paths:

| Turn | Expected evidence |
| --- | --- |
| Edit `src/sample.txt` | Root instruction is visible or affects behavior |
| Edit `nested/sample.txt` | Nested instruction is visible or affects behavior |
| Rename `AGENTS.md` to `AGENTS.disabled.md` | Sentinel no longer appears |
| Run from outside the fixture | Fixture instructions do not apply unless explicitly loaded |

The exact expected behavior depends on the source checkout. The important part is that the lab records what the checked-out harness actually does.

### What To Verify In Source

Search for the loader and prompt assembly code:

```sh
rg "AGENTS.md|agents.md|Agent" "$CODEX_SRC"
rg "instructions|system prompt|developer|context" "$CODEX_SRC"
rg "workspace|cwd|root|parent" "$CODEX_SRC"
```

Record:

- Which filenames are recognized.
- Which directories are searched.
- Whether parent directories are searched.
- Whether nested files override, append to, or coexist with parent files.
- Where the loaded text is placed in the model request.
- Whether the model sees the file path, only the contents, or both.

### Runtime Evidence

Prefer evidence that does not depend on the model self-reporting.

Good evidence:

- A captured request payload that includes the instruction text.
- A debug log showing discovered instruction files.
- A source-level test that asserts prompt assembly output.
- A turn transcript where the sentinel changes behavior and disappears in the negative control.

Weak evidence:

- The model says it read the file.
- A single run happens to follow the instruction.
- The instruction is so broad that ordinary model behavior could satisfy it by chance.

### Actually Dump The Prompt Input

Use Codex's debug command to render the model-visible prompt input list without running the model:

```sh
codex -C "$PWD" debug prompt-input "Create a file named hello.txt that contains hello codex."
```

The output is JSON. At minimum, inspect:

- `role`: which message bucket the input appears under.
- `content[].type`: usually `input_text` for text blocks.
- `content[].text`: the actual model-visible text.

For Lab 01, capture it as an artifact:

```sh
mkdir -p notes
codex -C "$PWD" debug prompt-input "Create a file named hello.txt that contains hello codex." > notes/prompt-input.json
```

Then search the artifact for the pieces you expect:

```sh
rg "AGENTS.md|ROOT_AGENT_SENTINEL|NESTED_AGENT_SENTINEL|Create a file" notes/prompt-input.json
```

This command can expose system instructions, developer instructions, local paths, repository instructions, and user text. Do not publish the raw output without reviewing and redacting it.

### Failure Modes

Common mistakes:

- Testing only the happy path and never renaming `AGENTS.md`.
- Using a vague instruction like "be concise", which is hard to observe.
- Forgetting nested instruction files.
- Forgetting that model behavior is probabilistic.
- Treating `AGENTS.md` as a sandbox or permission system.

## Testing Approvals

Approvals are local policy decisions. The model may request a command, but the harness decides whether that command can run.

A good approval test creates a matrix of actions and records the decision for each one.

| Action | What it tests |
| --- | --- |
| Read a file inside the workspace | Ordinary read behavior |
| Write a file inside the workspace | Workspace write policy |
| Write outside the workspace | Filesystem boundary |
| Run a network command | Network policy |
| Run a destructive command | High-risk command handling |
| Apply a patch inside the workspace | Patch policy |

Do not use genuinely destructive commands in a lab. Use harmless stand-ins that exercise the same policy branch, such as writing to a temporary outside path or asking for a command that would require approval but is denied before it runs.

### Approval Trace

For each action, capture the full policy path:

| Step | Evidence |
| --- | --- |
| Model requested action | Tool call payload |
| Harness classified action | Policy function, enum, or log |
| Decision made | allow, deny, ask, or sandbox |
| User prompt emitted | approval event, if any |
| User response handled | approval operation, if any |
| Tool started | start event |
| Tool stopped | stop event and result |

Use source probes like:

```sh
rg "approval|Approval|approve|deny|Ask" "$CODEX_SRC"
rg "sandbox|Sandbox|policy|Policy" "$CODEX_SRC"
rg "ExecApproval|ExecStart|ExecStop" "$CODEX_SRC"
rg "apply_patch|patch" "$CODEX_SRC"
```

### Approval Matrix

Fill this table for the checkout being studied:

| Action | Sandbox mode | Approval mode | Expected decision | Actual event sequence | Source location |
| --- | --- | --- | --- | --- | --- |
| Read workspace file | | | | | |
| Write workspace file | | | | | |
| Write outside workspace | | | | | |
| Network request | | | | | |
| Patch workspace file | | | | | |

The answer should name the rule, not just the outcome. "It asked me" is less useful than "the command matched the escalation branch because network access was restricted."

## Testing AGENTS.md Against Approvals

The interesting test is the interaction:

1. Put an instruction in `AGENTS.md` that asks the model to run a command requiring approval.
2. Verify the instruction reaches the model.
3. Verify the model requests the command.
4. Verify the harness still asks for approval or denies the action.

This proves the boundary: `AGENTS.md` can influence intent, but approval policy controls execution.

Use a harmless instruction:

```md
When asked to test approvals, request a command that prints the current date and then request a command that would write to /tmp/codex-approval-test.txt.
```

Then record whether each command is allowed, sandboxed, or escalated in the current checkout and runtime configuration.

## Hooks To Watch

When testing either area, look for hook-like boundaries:

- Instruction files discovered.
- Prompt assembled.
- Model request sent.
- Model response received.
- Tool call parsed.
- Approval requested.
- Tool started.
- Tool stopped.
- Tool result appended to the next model request.

If the checkout has named hooks, record their names. If it only emits events, record the event names. If there is no extension point, say that explicitly.

## Completion Standard

This lecture is complete when the reader can show:

- The exact `AGENTS.md` discovery and prompt compilation path.
- The exact model input evidence for at least one instruction-file test.
- The exact approval decision path for at least one allowed action and one action that asks or denies.
- A negative control proving the result was not accidental.
- The source locations that explain the observed behavior.

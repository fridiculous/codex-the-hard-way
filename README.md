# Codex the Hard Way

Codex the Hard Way is a source-code reading guide for understanding how a Codex-style coding harness works while it is working.

The goal is not to hide the harness behind diagrams or polished abstractions. The goal is to follow a user turn from prompt assembly, through model I/O, through tool calls, sandbox decisions, file edits, approvals, and final response generation, with enough source references that a reader can rebuild the mental model themselves.

This project is inspired by the learning style of "the hard way" guides: small labs, concrete checkpoints, minimal magic, and an expectation that readers inspect the real system instead of only reading summaries.

## Who This Is For

- Engineers using Codex who want to understand what actually happens during a turn.
- Tool builders designing coding agents, harnesses, sandboxes, or approval flows.
- Security and platform engineers reviewing how agentic tooling touches a local machine.
- Curious users who want a precise vocabulary for debugging Codex behavior.

## Learning Contract

Each lab should leave the reader with a durable artifact:

- A trace, map, sketch, or minimal reproduction.
- A set of source links or search queries that can be refreshed when Codex changes.
- A short explanation of the behavior in their own words.

If a chapter cannot point back to source code or an observable behavior, it does not belong in the hard-way path.

## Labs

| Lab | Topic | Output |
| --- | --- | --- |
| [00](docs/labs/00-orientation.md) | Orientation and local setup | A source checkout and reading journal |
| [01](docs/labs/01-follow-a-turn.md) | Follow one user turn | A rendered sequence flow and turn timeline |
| [02](docs/labs/02-openai-api-boundary.md) | OpenAI API boundary | A Responses vs Chat Completions request map |
| 03 | Instruction stack and context assembly | A layered prompt map using [AGENTS.md and approval tests](docs/reference/testing-agents-and-approvals.md) |
| 04 | Tool dispatch | A map of tool schemas, routing, and results |
| 05 | Sandbox and approval policy | A policy decision table |
| 06 | File edits and patch application | A minimal patch walkthrough |
| 07 | Conversation state and compaction | A state transition diagram |
| 08 | Observability and debugging | A trace checklist |
| 09 | Build a tiny harness | A small runnable model of the loop |

Only the first labs are drafted today. Lab 01 includes the concrete UI/daemon/model sequence flow to verify, and Lab 02 explains the OpenAI API boundary behind the model edge. Later labs should be added when they can be grounded in a specific source checkout and verified against a running harness.

## Repository Shape

- [docs/labs](docs/labs) contains the guided path.
- [docs/reference](docs/reference) contains reusable source-reading methods and vocabulary.
- [exercises](exercises) contains standalone drills that can be attached to multiple labs.
- [fixtures](fixtures) contains checked-in deterministic lab workspaces.
- [scripts](scripts) contains local checks for the repo itself.

## Deterministic Walkthrough

The repo includes an encapsulated initializer for prompt-compilation experiments:

```sh
scripts/run-deterministic-lab.sh
```

It copies [fixtures/deterministic-turn](fixtures/deterministic-turn) into an ignored workspace at `tmp/deterministic-lab/latest`, uses an isolated `CODEX_HOME`, runs `codex debug prompt-input`, and writes artifacts under `tmp/deterministic-lab/latest/artifacts`.

Reference lectures:

- [Testing AGENTS.md And Approvals](docs/reference/testing-agents-and-approvals.md)
- [OpenAI API Surfaces: Responses vs Chat Completions](docs/reference/openai-api-surfaces.md)
- [Codex Vertical Stack](docs/reference/codex-vertical-stack.md)

## Source Reading Philosophy

Codex changes over time, so this repo should avoid pretending that one file path will be true forever. Prefer source probes over brittle claims:

```sh
rg "sandbox|approval|tool call|apply_patch" "$CODEX_SRC"
rg "conversation|turn|session|compaction" "$CODEX_SRC"
```

When a lab depends on an exact file, pin the source checkout, record the commit, and explain why that file matters.

## Status

This repo is an initial scaffold. The next useful milestone is to choose the first Codex source checkout to study, then fill Lab 01's sequence flow with exact file references, compiled prompt evidence, tool-call evidence, approval branches, hook boundaries, AGENTS.md tests, and a captured trace.

# Glossary

This glossary defines terms used by Codex the Hard Way. Keep definitions operational: what the thing does, where it appears, and why it matters.

## Approval

A user-facing decision point where the harness asks whether a proposed action may run. Approval is usually tied to commands, network access, filesystem writes, or other effects outside the ordinary sandbox.

## AGENTS.md

A repository instruction file that may be discovered by the harness and included in model-visible context. Treat it as prompt input to test, not as an execution permission system.

## Assistant Message

The model's response for a turn. It may contain ordinary text, tool calls, or both, depending on the protocol and model behavior.

## Compaction

A process that compresses or summarizes conversation context so the session can continue within context limits. Compaction is important because it changes what future model calls can directly see.

## Context Assembly

The step that gathers system instructions, developer instructions, user messages, workspace state, tool schemas, and other relevant context before a model request.

## Harness

The runtime around the model. It manages instructions, model requests, tool calls, policy checks, workspace operations, and user-facing output.

## Hook

An extension or observation point around a runtime boundary, such as before a model request, before a tool starts, after a tool stops, or before a turn completes. If a source checkout does not expose named hooks, record the closest event emission point or callback instead.

## Policy Check

The local decision that determines whether a requested action may run directly, must be sandboxed, requires approval, or should be rejected.

## Responses API

OpenAI's newer general-purpose model API. It represents model work as instructions, input, tools, state, and output items rather than only as a chat transcript.

## Sandbox

The restrictions placed around tool execution. A sandbox may limit filesystem writes, network access, process behavior, or access to host resources.

## Chat Completions API

OpenAI's older chat-shaped model API. It represents the interaction primarily as a `messages` array and returns assistant messages under `choices`.

## Tool Call

A structured request from the model for the harness to run a capability, such as a shell command, patch application, browser action, or external integration.

## Tool Result

The structured output returned by a tool and fed back into the harness. Tool results often become model-visible context for the next step in the loop.

## Turn

One user message plus the assistant and tool activity needed to respond to it. Complex turns may involve multiple model calls and multiple tool calls before the final answer.

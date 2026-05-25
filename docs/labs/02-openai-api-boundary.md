# Lab 02: OpenAI API Boundary

This lab explains the API boundary between a Codex-style harness and OpenAI's model APIs.

## Objective

By the end of this lab, you should be able to look at a model request in source code and answer:

- Is this using the Responses API or Chat Completions API?
- Where do instructions enter the request?
- Where does the user turn enter the request?
- Where are tool schemas attached?
- Where does prior conversation state enter?
- What output shape does the harness parse?

Use the `openai/openai-node` README as the gold standard for JavaScript and TypeScript examples:

- <https://github.com/openai/openai-node>

For the longer reference note, use [OpenAI API Surfaces: Responses vs Chat Completions](../reference/openai-api-surfaces.md).

## Why This Comes Early

Lab 01 shows a simplified edge:

```text
task->>agent: prompt
agent->>task: response
```

That edge is where the local harness crosses into the model API. If you do not understand the request and response shape, later topics become fuzzy:

- Tool dispatch looks like magic instead of structured model output.
- Conversation state looks like memory instead of request construction.
- Instruction hierarchy looks like prose instead of serialized input.
- Output parsing looks like text handling instead of protocol handling.

This lab makes that boundary concrete before the guide moves into instruction assembly, tool dispatch, approvals, and compaction.

## The Two API Shapes

The `openai-node` README presents `client.responses.create()` as the primary API for interacting with OpenAI models:

```ts
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env["OPENAI_API_KEY"],
});

const response = await client.responses.create({
  model: "gpt-5.2",
  instructions: "You are a concise coding assistant.",
  input: "Are semicolons optional in JavaScript?",
});

console.log(response.output_text);
```

The same SDK still supports Chat Completions as the previous standard:

```ts
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env["OPENAI_API_KEY"],
});

const completion = await client.chat.completions.create({
  model: "gpt-5.2",
  messages: [
    { role: "developer", content: "You are concise." },
    { role: "user", content: "Are semicolons optional in JavaScript?" },
  ],
});

console.log(completion.choices[0].message.content);
```

The model name is not the point of the lab. Model availability changes. The durable lesson is the request and response shape.

## Compare The Shapes

| Area | Responses API | Chat Completions API |
| --- | --- | --- |
| SDK method | `client.responses.create()` | `client.chat.completions.create()` |
| Mental model | Create a model response from instructions, input, tools, and state. | Given a chat transcript, return the next assistant message. |
| Input shape | `instructions` plus `input`, where input may be a string or structured items. | `messages` array with roles such as `developer`, `user`, and `assistant`. |
| Output shape | `response.output` may contain multiple item types; `response.output_text` is the common text convenience path. | `completion.choices[0].message.content` is the common text path. |
| State | Can chain with `previous_response_id` or use conversation state features. | Usually requires the caller to resend the relevant message history. |
| Tools | Designed around modern tool use, hosted tools, structured outputs, and multimodal workflows. | Supports function and tool calling through the older chat-completion shape. |

## Map It To Codex

When reading a Codex source checkout, expand "prompt" into a concrete API request.

For a Responses-style harness, look for:

| Harness concept | Responses-style field |
| --- | --- |
| System or developer behavior | `instructions` or structured input items |
| User turn | `input` |
| Prior state | `previous_response_id` or conversation state |
| Tool schemas | `tools` |
| Assistant text | `output_text` or text output items |
| Tool calls | tool-call output items |

For a Chat Completions-style harness, look for:

| Harness concept | Chat Completions-style field |
| --- | --- |
| System or developer behavior | `messages[]` entries |
| User turn | `messages[]` entry with `role: "user"` |
| Prior state | Earlier `messages[]` entries |
| Tool schemas | `tools` |
| Assistant text | `choices[0].message.content` |
| Tool calls | `choices[0].message.tool_calls` |

## Source Probes

Search the harness source for both direct SDK usage and lower-level protocol names:

```sh
rg "responses\\.create|chat\\.completions\\.create" "$CODEX_SRC"
rg "previous_response_id|output_text|choices\\[0\\]|tool_calls" "$CODEX_SRC"
rg "instructions|input|messages|tools" "$CODEX_SRC"
rg "responses|chat/completions|/v1/responses|/v1/chat/completions" "$CODEX_SRC"
```

If the harness uses an internal client abstraction, follow the abstraction until you find the HTTP endpoint, SDK call, or serialized request body.

## Evidence Table

Copy this table into your journal:

| Question | Source location | Evidence |
| --- | --- | --- |
| Which model API shape is used? | | |
| Where are instructions placed? | | |
| Where is the user turn placed? | | |
| Where are tools attached? | | |
| Where does prior state enter? | | |
| What text output path is parsed? | | |
| What tool-call output path is parsed? | | |

## Checkpoint

You are done when you can point to the source code that crosses the model API boundary and describe the exact request and response shape without saying only "the prompt is sent to the model."

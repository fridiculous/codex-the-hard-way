# OpenAI API Surfaces: Responses vs Chat Completions

This lesson explains the model API boundary that sits underneath a Codex-style harness. Treat the `openai/openai-node` README as the gold standard for JavaScript and TypeScript examples in this guide.

The short version: **Chat Completions is the older chat-shaped API; Responses is the newer general-purpose model API.** In `openai-node`, both exist, but the README describes `client.responses.create()` as the primary API for interacting with OpenAI models and `client.chat.completions.create()` as the previous standard, still supported.

Sources:

- Gold standard: OpenAI Node SDK README: <https://github.com/openai/openai-node>
- Supplemental endpoint reference: <https://platform.openai.com/docs/api-reference/responses>
- Supplemental endpoint reference: <https://platform.openai.com/docs/api-reference/chat>

When these sources drift, prefer the SDK README for this lesson's code shape, naming, and default recommendation.

## Why This Matters For Codex

When a coding agent "talks to the model," it is not sending a vague prompt into the air. The harness serializes instructions, user input, tool schemas, prior state, and sometimes tool results into an API request.

The API shape matters because it determines:

- How instructions are represented.
- How user input is represented.
- How tool calls are emitted.
- How tool results are returned.
- How conversation state is carried forward.
- Which parts of the model output are plain text versus structured items.

Codex-style systems may hide this behind a higher-level runtime, but the same boundary still exists: local harness state becomes model API input, and model API output becomes assistant text, tool calls, or other events.

## Side By Side

Responses API, matching the `openai-node` README pattern:

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

Chat Completions API, matching the older `openai-node` README pattern:

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

The model name is intentionally not the lesson. Model availability changes. The durable point is the request and response shape.

## Main Differences

| Area | Responses API | Chat Completions API |
| --- | --- | --- |
| SDK method | `client.responses.create()` | `client.chat.completions.create()` |
| Mental model | Create a model response from instructions, input, tools, and state. | Given a chat transcript, return the next assistant message. |
| Input shape | `instructions` plus `input`, where input may be a string or structured items. | `messages` array with roles such as `developer`, `user`, and `assistant`. |
| Output shape | `response.output` may contain multiple item types; `response.output_text` is the common text convenience path. | `completion.choices[0].message.content` is the common text path. |
| State | Can chain with `previous_response_id` or use conversation state features. | Usually requires the caller to resend the relevant message history. |
| Tools | Designed around modern tool use, hosted tools, structured outputs, and multimodal workflows. | Supports function and tool calling through the older chat-completion shape. |
| Best default | New apps, agents, reasoning models, tool-heavy flows, and multimodal work. | Existing apps, compatibility layers, and simple legacy chat integrations. |

## Why Responses Exists

Chat Completions was built around a simple and useful pattern:

```text
chat transcript in -> next assistant message out
```

That shape works well for ordinary chat. It becomes awkward when the model interaction contains more than one kind of thing:

- Instructions that should not be treated as chat messages.
- User input that may include text, images, files, or structured items.
- Tool definitions available to the model.
- Tool calls emitted by the model.
- Tool results returned to the model.
- Reasoning metadata or other non-text output items.
- Server-side conversation state.

Responses is closer to the modern interaction model:

```text
instructions + input + tools + state -> output items
```

That does not make Chat Completions obsolete for every use. It means the newer API maps more directly to agentic and tool-heavy systems.

## State Is The Practical Difference

With Chat Completions, the caller commonly manages history:

```ts
const messages = [
  { role: "developer", content: "You are concise." },
  { role: "user", content: "Tell me a joke." },
];

const first = await client.chat.completions.create({
  model: "gpt-5.2",
  messages,
});

messages.push(first.choices[0].message);
messages.push({ role: "user", content: "Explain why it is funny." });

const second = await client.chat.completions.create({
  model: "gpt-5.2",
  messages,
});
```

With Responses, the caller can chain from a previous response:

```ts
const first = await client.responses.create({
  model: "gpt-5.2",
  input: "Tell me a joke.",
});

const second = await client.responses.create({
  model: "gpt-5.2",
  previous_response_id: first.id,
  input: "Explain why it is funny.",
});
```

This is a state convenience, not free memory. Prior context can still count toward billing and context-window behavior. The important lesson for harness readers is that state may be carried explicitly by resending history, or indirectly by referencing server-side response or conversation state.

## Mapping To The Harness Loop

In Lab 01, the sequence diagram uses this simplified edge:

```text
task->>agent: prompt
agent->>task: response
```

At the API boundary, expand that edge into a concrete request and response.

For a Responses-style harness, the outbound request may contain:

| Harness concept | Responses-style API field |
| --- | --- |
| System or developer behavior | `instructions` or structured input items |
| User turn | `input` |
| Prior state | `previous_response_id` or conversation state |
| Tool schemas | `tools` |
| Tool choice policy | tool-related request fields |
| Desired output format | text, JSON schema, or structured output settings |

The inbound response may contain:

| Model output | Harness interpretation |
| --- | --- |
| Text output item | Assistant message to show the user |
| Tool call item | Local tool dispatch candidate |
| Structured output | Parsed result for the application |
| Metadata | Logging, tracing, billing, or debugging evidence |

For a Chat Completions-style harness, the same concepts are usually packed into:

| Harness concept | Chat Completions-style API field |
| --- | --- |
| System or developer behavior | `messages[]` entries |
| User turn | `messages[]` entry with `role: "user"` |
| Prior state | Earlier `messages[]` entries |
| Tool schemas | `tools` |
| Assistant text | `choices[0].message.content` |
| Tool calls | `choices[0].message.tool_calls` |

## Reading Checklist

When you inspect a real harness source checkout, do not stop at "it calls OpenAI." Find the exact boundary:

- Does the code use `openai-node`, another OpenAI SDK, or raw HTTP?
- If it uses `openai-node`, does it follow the README's primary `client.responses.create()` path or the previous-standard `client.chat.completions.create()` path?
- Which SDK method or HTTP endpoint is used?
- Where are instructions placed?
- Where is the user turn placed?
- Where are tool schemas attached?
- Where does prior conversation state enter?
- What output item or message shape is parsed?
- Where does a tool call become a local policy decision?
- Where does the tool result re-enter the next model request?

## Rule Of Thumb

Use **Responses API** unless there is a concrete reason not to.

Use **Chat Completions** when maintaining older code, integrating with tooling that expects OpenAI-compatible chat completions, or building a small compatibility layer where the `messages -> choices[0].message` shape is already the contract.

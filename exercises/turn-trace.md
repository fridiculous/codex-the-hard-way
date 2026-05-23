# Exercise: Turn Trace

Use this exercise whenever you need to prove that you understand a Codex behavior end to end.

## Prompt

Run or simulate this user request:

```text
Create a file named hello.txt that contains hello codex.
```

## Trace

Fill in the table:

| Step | Event | Source location | Runtime evidence | Notes |
| --- | --- | --- | --- | --- |
| 1 | User turn received | | | |
| 2 | Instructions assembled | | | |
| 3 | Model request sent | | | |
| 4 | Tool call received | | | |
| 5 | Policy checked | | | |
| 6 | Tool executed | | | |
| 7 | Workspace changed | | | |
| 8 | Tool result recorded | | | |
| 9 | Final response sent | | | |

## Questions

- Which parts of the turn were model decisions?
- Which parts were harness decisions?
- Which parts mutated local state?
- Which parts would change if the sandbox mode changed?
- Which source files would you inspect first if this behavior failed?

## Completion Standard

The exercise is complete when another reader can follow your trace and reproduce the same source walk without asking you to explain missing steps verbally.


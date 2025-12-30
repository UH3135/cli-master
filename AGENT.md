# Agent Notes

## Scope

- This document describes the AI agent runtime behavior and tool surface.
- Keep this file aligned with the actual configuration in `cli_master/agent.py`.

## Tool Surface (Actual)

The LangChain `FileManagementToolkit` is configured with the following tools:

- `read_file`
- `write_file`
- `list_directory`
- `file_search`
- `copy_file`
- `move_file`
- `file_delete`

Custom tools registered from `cli_master/tools.py`:

- `cat`
- `tree`
- `grep`

If the tool list changes in code, update this document in the same change.

## Notes

- Do not claim the tool surface is read-only unless the write/move/delete tools are
  removed from `cli_master/agent.py`.
- Respond in Korean.
- Write code comments in Korean.

## Package Dev Dependencies

```
[package.dev-dependencies]
dev = [
    { name = "mypy" },
    { name = "pre-commit" },
    { name = "pytest" },
    { name = "ruff" },
]
```

- Use these tools to keep code style and quality consistent.

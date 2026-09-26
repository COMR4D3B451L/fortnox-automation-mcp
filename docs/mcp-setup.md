# MCP setup

## Safe default

Keep `FORTNOX_ENABLE_WRITES=0` until read access and the approval process are tested. The default tools are read-only list operations and receipt preview.

## Example local configuration

Create a secret file outside the repository:

```bash
install -m 600 /dev/null "$HOME/.config/fortnox/fortnox.env"
$EDITOR "$HOME/.config/fortnox/fortnox.env"
```

Set credentials out of band. Do not paste them into an MCP JSON file or commit them.

```text
FORTNOX_CLIENT_ID=...
FORTNOX_CLIENT_SECRET=...
FORTNOX_ACCESS_TOKEN=...
FORTNOX_REFRESH_TOKEN=...
FORTNOX_ENV_FILE=/home/user/.config/fortnox/fortnox.env
FORTNOX_ENABLE_WRITES=0
```

## Generic MCP registration

```json
{
  "mcpServers": {
    "fortnox": {
      "command": "/usr/bin/python3",
      "args": ["-m", "fortnox_automation.mcp_server"],
      "cwd": "/absolute/path/to/fortnox-automation",
      "env": {
        "FORTNOX_ENV_FILE": "/home/user/.config/fortnox/fortnox.env"
      }
    }
  }
}
```

Do not include `FORTNOX_CLIENT_SECRET`, access tokens, refresh tokens, or approval tokens in this JSON. The MCP host only needs the path to the protected environment file.

## Hermes

Register the command as a local stdio MCP server using the official Hermes MCP configuration commands. Start a new Hermes session after registration or schema changes. The exact command is installation-specific; do not copy credentials into a chat message.

## Enabling writes

Only after a separate review:

```text
FORTNOX_ENABLE_WRITES=1
FORTNOX_APPROVAL_TOKEN=<long random value>
```

The caller must pass the same secret for each approved mutation. Use an approval broker or deployment secret manager in production. Do not use a human-readable value such as `APPROVED`.

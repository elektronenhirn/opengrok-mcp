# OpenGrok mcp

This repository contains a Model Context Protocol server for allowing LLMs to query source code repositories. It exposes some basic OpenGrok functionality which an LLM can use to understand the codebase you are working on

# Features

Allows LLMs to query OpenGrok to search for:

- Definitions
- Symbol searches
- Full searches across projects
- Project listings

It should also return clickable URLs for the user

# Installation

## Prerequisites

- OpenGrok Server
- Python3
- uv

## Env Setup

```python
git clone https://github.com/SleepyDog053/opengrok-mcp
cd opengrok-mcp
uv sync

source .venv/bin/activate
```

## MCP Clients

This can be run multiple MCP clients but may require editing to work elsewhere

### 1. Claude

```yaml
{
  "mcpServers": {
    "opengrok": {
      "command": "python",
      "args": ["server.py"],
      "env": {
        "OPENGROK_BASE_URL": "http://localhost:8080",
        "OPENGROK_TOKEN": "your-token-if-needed"
      }
    }
  }
}
```


### 2. Codex

```toml
[mcp_servers.OpenGrok]
command = "python"
args = ["/route/to/opengrok-mcp/server.py"]

[mcp_servers.OpenGrok.env]
OPENGROK_BASE_URL = "http://localhost:8080"
OPENGROK_TOKEN="your-token-if-needed"
```

---

# OpenGrok Gotchas

To be able to make OpenGrok query this correctly, you will need to send API requests to some restricted access API endpoints.
These API endpoints require the use of a bearer API token. For development setups, it isn't always clear how to enable this

The best way to do this is to add a [read-only configuration](https://github.com/oracle/opengrok/wiki/Read-only-configuration) which gets merged with the main configuration. This configuration will look like:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<java version="1.8.0_121" class="java.beans.XMLDecoder">
  <object class="org.opengrok.indexer.configuration.Configuration">
    <!-- 1) Bearer tokens the webapp will accept for API calls -->
    <void property="authenticationTokens">
      <void method="add">
        <string>your-token</string>
      </void>
    </void>

    <!-- 2) Allow tokens over HTTP (dev only) -->
    <void property="allowInsecureTokens">
      <boolean>true</boolean>
    </void>
  </object>
</java>
```

More details can be found [here](https://github.com/oracle/opengrok/wiki/Webapp-configuration) if needed
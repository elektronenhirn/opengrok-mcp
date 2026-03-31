# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenGrok MCP is a Model Context Protocol server that enables LLMs to query source code repositories through OpenGrok. It bridges LLMs to OpenGrok's code search functionality via MCP tools.

## Running the Server

```bash
# Install dependencies
uv sync

# Run the server
uv run server.py
# or
source .venv/bin/activate && python server.py
```

**Environment variables:**
- `OPENGROK_BASE_URL` - OpenGrok instance URL (defaults to `http://localhost:8080/source`)

**Authentication:** Uses `.netrc` credentials for HTTP Basic Auth. Add entry for your OpenGrok host:
```
machine <hostname>
login <username>
password <password>
```

## Architecture

Single-file implementation (`server.py`) using FastMCP framework:

- **Helper functions:** `_sanitize()`, `_og_basic_auth()`, `_og_url()`, `search_code_raw()`, `build_clickable_url()`
- **MCP tools exposed to LLMs:**
  - `search_references(symbol, project?, path?, fileType?)` - Find symbol usages
  - `search_defs(symbol, project?, path?, fileType?)` - Find symbol definitions
  - `search_full(symbol, project?, path?, fileType?)` - Full-text search
  - `get_file_snippet(project, path, start_line?, end_line?)` - Retrieve file content
  - `list_projects()` - List available OpenGrok projects

**OpenGrok API endpoints used:**
- `GET /api/v1/search` - Search with def/symbol/full parameters
- `GET /api/v1/projects` - List projects
- `GET /raw/<path>` - Raw file content

## Dependencies

- Python >=3.14
- `mcp[cli]>=1.25.0` - MCP framework
- `requests>=2.32.5` - HTTP client

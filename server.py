#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "mcp[cli]>=1.25.0",
#   "requests>=2.32.5",
# ]
# ///

import html
import netrc
import os
import re
from typing import List, Optional
from urllib.parse import urlparse

import requests
from requests.auth import HTTPBasicAuth
from mcp.server.fastmcp import FastMCP


def _sanitize(s: Optional[str]) -> Optional[str]:
    """Strip lone UTF-16 surrogates that cannot be encoded as UTF-8."""
    if s is None:
        return None
    return s.encode("utf-8", errors="replace").decode("utf-8")

OPENGROK_BASE_URL = os.environ.get("OPENGROK_BASE_URL", "http://localhost:8080/source")

mcp = FastMCP("OpenGrokMCP")

def _og_basic_auth() -> HTTPBasicAuth:
    """Return HTTPBasicAuth from ~/.netrc for the OpenGrok host.

    Raises RuntimeError if the .netrc file is missing, unparseable, or does
    not contain an entry for the configured OpenGrok host.
    """
    host = urlparse(OPENGROK_BASE_URL).hostname
    if not host:
        raise RuntimeError(
            f"Cannot determine hostname from OPENGROK_BASE_URL='{OPENGROK_BASE_URL}'"
        )
    try:
        creds = netrc.netrc().authenticators(host)
    except FileNotFoundError:
        raise RuntimeError(
            f"No ~/.netrc file found. Please add an entry for '{host}'."
        )
    except netrc.NetrcParseError as exc:
        raise RuntimeError(f"Failed to parse ~/.netrc: {exc}")

    if not creds:
        raise RuntimeError(
            f"No .netrc entry found for host '{host}'. "
            "Please add a 'machine' entry with login and password."
        )

    login, _, password = creds
    return HTTPBasicAuth(login, password or "")

def _og_url(path: str) -> str:
    # path is something similar to /api/v1/search
    return OPENGROK_BASE_URL.rstrip("/") + path


def search_code_raw(
    search_key: str,  # 'def', 'symbol', 'full', etc.
    query: str,
    project: Optional[str] = None,
    path: Optional[str] = None,
    fileType: Optional[str] = None,
    max_results: int = 50,
    start: int = 0,
) -> str:
    """
    Search code in Opengrok and return formatted text results.

    Types which are wrapped here are:

    - "full": Do a full search everywhere in the code
    - "symbol": Search for a specific symbol
    - "def": Search for a specific definition
    """

    params = {
        search_key: query,
        "projects": project,
        "maxresults": max_results,
        "start": start,
        "path": path or "",
        "type": fileType or "",
    }

    resp = requests.get(
        _og_url("/api/v1/search"),
        auth=_og_basic_auth(),
        params=params,
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()

    results_by_path = data.get("results") or {}

    if not results_by_path:
        return "No results found."

    lines: List[str] = []
    hit_count = 0

    for file_path, matches in results_by_path.items():
        for m in matches:
            hit_count += 1
            line_number_raw = m.get("lineNumber")
            try:
                line_number = int(line_number_raw) if line_number_raw is not None else None
            except ValueError:
                line_number = None

            line_text = m.get("line") or ""
            # Remove HTML tags and decode HTML entities
            clean_line = re.sub(r"<[^>]+>", "", line_text)
            clean_line = html.unescape(clean_line)
            clean_line = _sanitize(clean_line)
            url = build_clickable_url(project, file_path, line_number)

            lines.append(f"{file_path}:{line_number}")
            lines.append(f"  {clean_line}")
            lines.append(f"  {url}")
            lines.append("")

    header = f"Found {hit_count} results:\n\n"
    return header + "\n".join(lines).rstrip()

def build_clickable_url(project, path, line_num) -> str:
    """
    Utility function which produces a clickable user link
    """
    path_no_lead = path.lstrip("/")
    return f"{OPENGROK_BASE_URL}/xref/{path_no_lead}#{line_num}"


@mcp.tool()
def search_references(
    symbol: str,
    project: Optional[str] = None,
    path: Optional[str] = None,
    fileType: Optional[str] = None,
) -> str:
    """
    Search for references to a specific symbol in the codebase.
    Returns file paths, line numbers, code snippets, and clickable URLs.

    Args:
        symbol: The symbol to search for
        project: Optional project name to limit search scope
        path: Optional path filter
        fileType: Optional file type filter (e.g., "c", "java")
    """
    return search_code_raw(
        search_key="symbol",
        query=symbol,
        project=project,
        path=path,
        fileType=fileType,
    )

@mcp.tool()
def search_defs(
    symbol: str,
    project: Optional[str] = None,
    path: Optional[str] = None,
    fileType: Optional[str] = None,
) -> str:
    """
    Search for definitions of a specific symbol in the codebase.
    Returns file paths, line numbers, code snippets, and clickable URLs.

    Args:
        symbol: The symbol to find definitions for
        project: Optional project name to limit search scope
        path: Optional path filter
        fileType: Optional file type filter (e.g., "c", "java")
    """
    return search_code_raw(
        search_key="def",
        query=symbol,
        project=project,
        path=path,
        fileType=fileType,
    )

@mcp.tool()
def search_full(
    query: str,
    project: Optional[str] = None,
    path: Optional[str] = None,
    fileType: Optional[str] = None,
) -> str:
    """
    Full-text search across the codebase.
    Returns file paths, line numbers, code snippets, and clickable URLs.

    Args:
        query: The text to search for
        project: Optional project name to limit search scope
        path: Optional path filter
        fileType: Optional file type filter (e.g., "c", "java")
    """
    return search_code_raw(
        search_key="full",
        query=query,
        project=project,
        path=path,
        fileType=fileType,
    )

@mcp.tool()
def get_file_snippet(
    project: str,
    path: str,
    start_line: int = 1,
    end_line: int = 200,
) -> str:
    """
    Retrieve a section of a file from OpenGrok with line numbers.
    Use this to get more context around search results.

    Args:
        project: The project name
        path: Path to the file within the project
        start_line: First line to retrieve (default: 1)
        end_line: Last line to retrieve (default: 200)
    """
    rel = f"/raw/{path.lstrip('/')}"

    resp = requests.get(
        _og_url(rel),
        auth=_og_basic_auth(),
        timeout=30,
        stream=True,
    )
    resp.raise_for_status()

    # Stream line-by-line; stop as soon as we have read past end_line so we
    # never need to download the entire file (important for large files).
    start_idx = max(start_line - 1, 0)
    all_lines: List[str] = []
    for raw_line in resp.iter_lines(decode_unicode=True):
        all_lines.append(raw_line if raw_line is not None else "")
        if len(all_lines) >= end_line:
            break
    resp.close()

    total_lines_read = len(all_lines)
    end_idx = min(end_line, total_lines_read)

    snippet_lines = all_lines[start_idx:end_idx]
    numbered = [
        f"{i+1}: {line}" for i, line in enumerate(snippet_lines, start=start_idx)
    ]

    header = f"File: {path}\nLines {start_line}-{end_idx}:\n\n"
    return header + "\n".join(numbered)

@mcp.tool()
def list_projects() -> str:
    """
    List all available OpenGrok projects.
    Use this to discover which projects can be searched.
    """
    resp = requests.get(
        _og_url("/api/v1/projects"),
        auth=_og_basic_auth(),
        timeout=30,
    )

    # If API returns 401 (requires bearer token), fall back to HTML scraping
    if resp.status_code == 401:
        projects = _list_projects_from_html()
    else:
        resp.raise_for_status()
        projects = sorted(resp.json())

    if not projects:
        return "No projects found."

    header = f"Available projects ({len(projects)}):\n\n"
    return header + "\n".join(f"- {p}" for p in projects)


def _list_projects_from_html() -> List[str]:
    """
    Scrape project list from the OpenGrok main page.
    Used as fallback when /api/v1/projects requires bearer token auth.
    """
    resp = requests.get(
        OPENGROK_BASE_URL,
        auth=_og_basic_auth(),
        timeout=30,
    )
    resp.raise_for_status()

    # Extract project names from xref links on the main page
    project_names = re.findall(r'/xref/([^/\"]+)/?[\"<]', resp.text)
    return sorted(set(project_names))

#hits = search_code_raw("full", "bi_reverse", "zlib")
#print(hits)

if __name__ == "__main__":
    mcp.run()

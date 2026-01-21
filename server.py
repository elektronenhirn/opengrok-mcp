import os
from typing import List, Optional, Dict, Any

import requests
from mcp.server.fastmcp import FastMCP
import re

OPENGROK_BASE_URL = os.environ.get("OPENGROK_BASE_URL", "http://localhost:8080/source")
OPENGROK_TOKEN = os.environ.get("OPENGROK_TOKEN") # optional bearer token

mcp = FastMCP("OpenGrokMCP")

def _og_headers() -> Dict[str, str]:
    headers = {}
    if OPENGROK_TOKEN:
        headers["Authorization"] = f"Bearer {OPENGROK_TOKEN}"
    return headers

def _og_url(path: str) -> str:
    # path is something similar to /api/v1/search
    return OPENGROK_BASE_URL.rstrip("/") + path


def search_code_raw(
    search_key: str, # 'def', 'symbol', 'full', etc.
    query: str,
    project: Optional[str] = None,
    path: Optional[str] = None,
    fileType: Optional[str] = None,
    max_results: int = 50,
    start: int = 0,
) -> List[Dict[str, Any]]:
    """
    Search code in Opengrok and return a list of hits

    Types which are wrapped here are:

    - "full": Do a full search everywhere in the code
    - "symbol": Search for a specific symbol
    - "def": Search for a specific definition
    """

    params = {
        search_key : query,
        "projects" : project,
        "maxresults" : max_results,
        "start": start,
        "path": path or "",
        "type": fileType or "",
    }

    resp = requests.get(
        _og_url("/api/v1/search"),
        headers=_og_headers(),
        params=params,
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()

    results_by_path = data.get("results") or {}

    hits: List[Dict[str, Any]] = []
    
    for file_path, matches in results_by_path.items():
        for m in matches:
            line_number_raw = m.get("lineNumber")
            try:
                line_number = int(line_number_raw) if line_number_raw is not None else None
            except ValueError:
                line_number = None
            
            line_text = m.get("line") or ""
            tag = m.get("tag")

            clean_line = re.sub(r"</?b>", "", line_text)

            hits.append(
                {
                    "project": project, # No project but might be in the future
                    "path": file_path,
                    "line": line_number,
                    "snippet": clean_line,
                    "tag": tag,
                    "clickable_url": build_clickable_url(project, file_path, line_number)
                }
            )

    return hits

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
) -> List[Dict[str, Any]]:
    
    """
    Search for a reference to a specific symbol
    Other data is optional but could reduce the search to a specific path, filetype or project
    It will also produce a clickable link under url

    The model should use this to search for all uses of a specific symbol in the codebase
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
) -> List[Dict[str, Any]]:
    """
    Search for definitions for a specific symbol
    Other data is optional but could reduce the search to a specific path, filetype or project
    It will also produce a clickable link under url

    The model should use this to search for all definitions for a symbol in the codebase
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
    symbol: str,
    project: Optional[str] = None,
    path: Optional[str] = None,
    fileType: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search for anything within the codebase
    Other data is optional but could reduce the search to a specific path, filetype or project
    It will also produce a clickable link under url

    The model should use this to search the entire codebase for anything
    """

    return search_code_raw(
        search_key="full",
        query=symbol,
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
) -> Dict[str, Any]:
    """
    Return a slice of a file (inclusive line range) from OpenGrok

    The model should use this after any search_* call when it wants more context
    around a hit. Keep line ranges reasonably small to avoid bloating context
    """
    rel = f"/raw/{path.lstrip('/')}"

    resp = requests.get(
        _og_url(rel),
        headers=_og_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    content = resp.text.splitlines()

    # Clamp bounds
    start_idx = max(start_line - 1, 0)
    end_idx = min(end_line, len(content))

    snippet_lines = content[start_idx:end_idx]
    numbered = [
        f"{i+1}: {line}" for i, line in enumerate(snippet_lines, start=start_idx)
    ]

    return {
        "project": project,
        "path": path,
        "start_line": start_line,
        "end_line": end_idx,
        "total_lines": len(content),
        "text": "\n".join(numbered),
    }

@mcp.tool()
def list_projects() -> List[Dict[str, Any]]:
    """
    List available OpenGrok projects

    Useful for the model to decide where to search
    """

    resp = requests.get(
        _og_url("/api/v1/projects"),
        headers = _og_headers(),
        timeout=30,
    )

    data = resp.json()

    projects: List[Dict[str, Any]] = []

    for p in data:
        projects.append({"name": str(p)})

    return projects

#hits = search_code_raw("full", "bi_reverse", "zlib")
#print(hits)

if __name__ == "__main__":
    mcp.run()
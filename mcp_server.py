#!/usr/bin/env python3
"""
mcp_server.py — Model Context Protocol (MCP) stdio server for 'b2b-company-hiring-and-job-scraper'.
Allows AI coding agents, recruiter bots, and market intelligence LLMs to query company job openings
and hiring growth signals directly across Greenhouse, Lever, and Ashby.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from main import scrape_company_jobs

SERVER_NAME = "b2b-company-hiring-and-job-scraper-mcp"
SERVER_VERSION = "0.1.0"


def send_response(response: dict):
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def handle_request(req: dict):
    method = req.get("method")
    msg_id = req.get("id")

    if method == "initialize":
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION
                }
            }
        })
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "get_company_jobs_and_signals",
                        "description": "Scrapes and normalizes active job postings and analyzes company hiring signals (growth velocity, department breakdown, remote ratio, tech stack demands) across Greenhouse, Lever, and Ashby ATS systems.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "company": {
                                    "type": "string",
                                    "description": "Company domain (e.g. 'stripe.com', 'linear.app') or ATS slug ('palantir', 'figma')"
                                },
                                "keyword": {
                                    "type": "string",
                                    "description": "Optional keyword filter for job title (e.g. 'Engineer', 'Sales', 'AI')"
                                },
                                "remote_only": {
                                    "type": "boolean",
                                    "description": "If true, only returns remote roles"
                                },
                                "max_jobs": {
                                    "type": "integer",
                                    "description": "Maximum number of individual jobs to return (default: 25)"
                                }
                            },
                            "required": ["company"]
                        }
                    }
                ]
            }
        })
    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "get_company_jobs_and_signals":
            company = args.get("company", "")
            keyword = args.get("keyword")
            remote_only = bool(args.get("remote_only", False))
            max_jobs = int(args.get("max_jobs", 25))
            try:
                res = scrape_company_jobs(
                    company,
                    keyword_filter=keyword,
                    remote_only=remote_only,
                    max_jobs=max_jobs
                )
                send_response({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(res, indent=2)
                            }
                        ]
                    }
                })
            except Exception as e:
                send_response({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                })
        else:
            send_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{tool_name}' not found."
                }
            })
    elif method == "ping":
        send_response({"jsonrpc": "2.0", "id": msg_id, "result": {}})
    else:
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Unhandled method '{method}'"
            }
        })


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            handle_request(req)
        except Exception as e:
            send_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            })


if __name__ == "__main__":
    main()

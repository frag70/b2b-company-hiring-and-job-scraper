#!/usr/bin/env python3
"""
main.py — B2B Company Job Scraper & Hiring Signals API
Zero-proxy, ultra-fast Standby API and bulk scraper for Greenhouse, Lever, and Ashby ATS boards.
Supports Standby HTTP Server, Apify Batch Datasets, and Model Context Protocol (MCP).
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
import asyncio
import logging
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("b2b-company-hiring-scraper")

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# Technology keywords to track in hiring requirements
TECH_KEYWORDS = [
    "python", "typescript", "javascript", "golang", "go", "rust", "java", "c++", "c#",
    "ruby", "swift", "kotlin", "react", "vue", "next.js", "node.js", "kubernetes",
    "docker", "aws", "gcp", "azure", "snowflake", "databricks", "postgresql", "postgres",
    "mongodb", "redis", "graphql", "kafka", "pytorch", "tensorflow", "llm", "generative ai",
    "openai", "langchain", "salesforce", "hubspot", "terraform"
]

def clean_company_input(input_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parses an input string to identify direct ATS URLs or normalize domain/slug.
    Returns (platform, slug).
    """
    input_str = input_str.strip()
    if not input_str:
        return None, None

    # Check for direct ATS URLs
    if "greenhouse.io" in input_str:
        m = re.search(r"greenhouse\.io/(?:embed/job_board\?for=)?([^/?#]+)", input_str)
        if m:
            return "greenhouse", m.group(1).lower()
    elif "lever.co" in input_str:
        m = re.search(r"jobs\.lever\.co/([^/?#]+)", input_str)
        if m:
            return "lever", m.group(1).lower()
    elif "ashbyhq.com" in input_str:
        m = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)", input_str)
        if m:
            return "ashby", m.group(1).lower()

    # Clean domain or raw slug
    cleaned = input_str.lower()
    cleaned = re.sub(r"^https?://", "", cleaned)
    cleaned = re.sub(r"^www\.", "", cleaned)
    cleaned = cleaned.split("/")[0].split("?")[0]
    
    # If contains dot (e.g. stripe.com, linear.app), extract root
    if "." in cleaned:
        root = cleaned.split(".")[0]
        return None, root
    return None, cleaned

def extract_tech_keywords(text: str) -> List[str]:
    """Finds technology tags mentioned in job title and text."""
    lower = text.lower()
    found = set()
    for kw in TECH_KEYWORDS:
        if kw in ("c++", "c#"):
            if kw in lower:
                found.add(kw)
        else:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, lower):
                found.add(kw)
    return sorted(list(found))

def fetch_greenhouse_jobs(slug: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """Fetches and normalizes jobs from Greenhouse public API."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
            raw_jobs = data.get("jobs", [])
            jobs = []
            for j in raw_jobs:
                title = j.get("title", "").strip()
                loc = j.get("location", {}).get("name", "Unspecified").strip()
                is_remote = "remote" in title.lower() or "remote" in loc.lower()
                workplace = "Remote" if is_remote else "Onsite / Hybrid"
                
                # Extract department if present
                dept = "General"
                depts = j.get("departments", [])
                if depts and isinstance(depts, list):
                    dept = depts[0].get("name", "General")

                jobs.append({
                    "id": f"gh_{j.get('id', '')}",
                    "title": title,
                    "department": dept,
                    "location": loc,
                    "is_remote": is_remote,
                    "workplace_type": workplace,
                    "job_url": j.get("absolute_url", ""),
                    "apply_url": j.get("absolute_url", ""),
                    "published_at": j.get("updated_at") or j.get("first_published"),
                    "tech_keywords": extract_tech_keywords(title)
                })
            return True, jobs
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, []
        logger.warning(f"Greenhouse HTTP {e.code} for {slug}")
        return False, []
    except Exception as e:
        logger.debug(f"Greenhouse error for {slug}: {e}")
        return False, []

def fetch_lever_jobs(slug: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """Fetches and normalizes jobs from Lever public API."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
            if not isinstance(data, list):
                return False, []
            jobs = []
            for j in data:
                title = j.get("text", "").strip()
                cats = j.get("categories", {}) or {}
                loc = cats.get("location", "Unspecified") or "Unspecified"
                dept = cats.get("department", "General") or "General"
                workplace = cats.get("workplaceType", "")
                is_remote = "remote" in title.lower() or "remote" in loc.lower() or workplace.lower() == "remote"
                if not workplace:
                    workplace = "Remote" if is_remote else "Onsite / Hybrid"

                created_ms = j.get("createdAt")
                pub_date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created_ms / 1000)) if created_ms else None

                jobs.append({
                    "id": f"lever_{j.get('id', '')}",
                    "title": title,
                    "department": dept,
                    "location": loc,
                    "is_remote": is_remote,
                    "workplace_type": workplace,
                    "job_url": j.get("hostedUrl", ""),
                    "apply_url": j.get("applyUrl") or j.get("hostedUrl", ""),
                    "published_at": pub_date,
                    "tech_keywords": extract_tech_keywords(f"{title} {dept}")
                })
            return True, jobs
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, []
        logger.warning(f"Lever HTTP {e.code} for {slug}")
        return False, []
    except Exception as e:
        logger.debug(f"Lever error for {slug}: {e}")
        return False, []

def fetch_ashby_jobs(slug: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """Fetches and normalizes jobs from Ashby public API."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
            raw_jobs = data.get("jobs", [])
            jobs = []
            for j in raw_jobs:
                title = j.get("title", "").strip()
                loc = j.get("location", "Unspecified") or "Unspecified"
                dept = j.get("department", "General") or "General"
                is_remote = bool(j.get("isRemote", False)) or "remote" in title.lower() or "remote" in loc.lower()
                workplace = j.get("workplaceType") or ("Remote" if is_remote else "Onsite / Hybrid")

                jobs.append({
                    "id": f"ashby_{j.get('id', '')}",
                    "title": title,
                    "department": dept,
                    "location": loc,
                    "is_remote": is_remote,
                    "workplace_type": workplace,
                    "job_url": j.get("jobUrl", ""),
                    "apply_url": j.get("applyUrl") or j.get("jobUrl", ""),
                    "published_at": j.get("publishedAt"),
                    "tech_keywords": extract_tech_keywords(f"{title} {dept}")
                })
            return True, jobs
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, []
        logger.warning(f"Ashby HTTP {e.code} for {slug}")
        return False, []
    except Exception as e:
        logger.debug(f"Ashby error for {slug}: {e}")
        return False, []

def discover_ats_board_from_web(domain: str) -> Tuple[Optional[str], Optional[str]]:
    """Crawls company homepage and /careers to discover third-party ATS links."""
    candidates = [
        f"https://{domain}",
        f"https://{domain}/careers",
        f"https://{domain}/jobs"
    ]
    for url in candidates:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                # Look for greenhouse
                m = re.search(r"boards\.greenhouse\.io/(?:embed/job_board\?for=)?([a-zA-Z0-9_-]+)", html)
                if m:
                    return "greenhouse", m.group(1).lower()
                # Look for lever
                m = re.search(r"jobs\.lever\.co/([a-zA-Z0-9_-]+)", html)
                if m:
                    return "lever", m.group(1).lower()
                # Look for ashby
                m = re.search(r"jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)", html)
                if m:
                    return "ashby", m.group(1).lower()
        except Exception:
            continue
    return None, None

def scrape_company_jobs(
    company_input: str,
    keyword_filter: Optional[str] = None,
    remote_only: bool = False,
    max_jobs: int = 50
) -> Dict[str, Any]:
    """
    Main orchestration function to resolve ATS, scrape all open jobs,
    compute department distribution, and synthesize hiring signals.
    """
    t0 = time.time()
    known_platform, slug = clean_company_input(company_input)
    if not slug:
        return {
            "error": "Invalid company input",
            "company_input": company_input,
            "jobs_count": 0,
            "jobs": []
        }

    detected_platform = known_platform
    raw_jobs: List[Dict[str, Any]] = []

    # If platform already known (e.g. from direct URL)
    if detected_platform == "greenhouse":
        ok, raw_jobs = fetch_greenhouse_jobs(slug)
    elif detected_platform == "lever":
        ok, raw_jobs = fetch_lever_jobs(slug)
    elif detected_platform == "ashby":
        ok, raw_jobs = fetch_ashby_jobs(slug)
    else:
        # Probe Greenhouse first (most popular for tech)
        ok, raw_jobs = fetch_greenhouse_jobs(slug)
        if ok and raw_jobs:
            detected_platform = "greenhouse"
        else:
            # Probe Ashby next
            ok, raw_jobs = fetch_ashby_jobs(slug)
            if ok and raw_jobs:
                detected_platform = "ashby"
            else:
                # Probe Lever
                ok, raw_jobs = fetch_lever_jobs(slug)
                if ok and raw_jobs:
                    detected_platform = "lever"
                elif "." in company_input:
                    # Fallback: scrape website for ATS link
                    plat, disc_slug = discover_ats_board_from_web(company_input.strip().lower().replace("https://", "").replace("http://", "").split("/")[0])
                    if plat and disc_slug:
                        detected_platform = plat
                        slug = disc_slug
                        if plat == "greenhouse":
                            _, raw_jobs = fetch_greenhouse_jobs(slug)
                        elif plat == "ashby":
                            _, raw_jobs = fetch_ashby_jobs(slug)
                        elif plat == "lever":
                            _, raw_jobs = fetch_lever_jobs(slug)

    total_unfiltered = len(raw_jobs)
    
    # Filter by keyword if requested
    filtered = raw_jobs
    if keyword_filter:
        kw_lower = keyword_filter.lower().strip()
        filtered = [j for j in filtered if kw_lower in j["title"].lower() or kw_lower in j.get("department", "").lower()]
    
    # Filter by remote
    if remote_only:
        filtered = [j for j in filtered if j.get("is_remote", False)]

    # Compute Hiring Signals across all discovered jobs
    dept_counts: Dict[str, int] = {}
    tech_demand_counts: Dict[str, int] = {}
    remote_count = 0

    for j in raw_jobs:
        dept = j.get("department", "General") or "General"
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
        if j.get("is_remote"):
            remote_count += 1
        for kw in j.get("tech_keywords", []):
            tech_demand_counts[kw] = tech_demand_counts.get(kw, 0) + 1

    # Sorted summaries
    sorted_depts = dict(sorted(dept_counts.items(), key=lambda x: x[1], reverse=True))
    sorted_tech = dict(sorted(tech_demand_counts.items(), key=lambda x: x[1], reverse=True)[:10])
    remote_ratio = round((remote_count / total_unfiltered) * 100, 1) if total_unfiltered > 0 else 0.0

    # Apply max_jobs limit to returned listings
    returned_jobs = filtered if max_jobs <= 0 else filtered[:max_jobs]

    elapsed = round((time.time() - t0) * 1000, 1)

    return {
        "company": slug.capitalize(),
        "slug": slug,
        "ats_platform": detected_platform or "unknown",
        "ats_board_found": bool(total_unfiltered > 0),
        "total_open_roles": total_unfiltered,
        "returned_roles_count": len(returned_jobs),
        "hiring_signals": {
            "remote_roles_count": remote_count,
            "remote_percentage": remote_ratio,
            "department_breakdown": sorted_depts,
            "top_tech_demands": sorted_tech,
            "is_actively_hiring": total_unfiltered > 0,
            "growth_tier": "Hypergrowth (100+ roles)" if total_unfiltered >= 100 else ("Scaling (25-99 roles)" if total_unfiltered >= 25 else "Steady (<25 roles)")
        },
        "jobs": returned_jobs,
        "elapsed_ms": elapsed
    }

# =====================================================================
# Pay-Per-Event (PPE) Micro-Pricing Helper
# =====================================================================
async def _charge(event: str, count: int = 1) -> None:
    """Invokes Apify Actor.charge for Pay-Per-Event billing."""
    try:
        from apify import Actor
        await Actor.charge(event_name=event, count=count)
        logger.info(f"Charged PPE event: {event} x {count}")
    except Exception as e:
        logger.debug(f"PPE charge skipped (local/dev): {event} - {e}")

# =====================================================================
# Standby HTTP Server Mode (Port 8080)
# =====================================================================
async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request_line = await reader.readline()
        if not request_line:
            writer.close()
            await writer.wait_closed()
            return

        line_str = request_line.decode("utf-8", errors="ignore").strip()
        parts = line_str.split()
        if len(parts) < 2:
            writer.close()
            await writer.wait_closed()
            return

        method, raw_path = parts[0], parts[1]
        parsed_url = urllib.parse.urlparse(raw_path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # Read headers
        content_length = 0
        while True:
            header_line = await reader.readline()
            if not header_line or header_line == b"\r\n" or header_line == b"\n":
                break
            h_str = header_line.decode("utf-8", errors="ignore")
            if h_str.lower().startswith("content-length:"):
                try:
                    content_length = int(h_str.split(":", 1)[1].strip())
                except ValueError:
                    content_length = 0

        # Read body if present
        body_bytes = b""
        if content_length > 0:
            body_bytes = await reader.readexactly(content_length)

        # Liveness probe
        if path in ("/healthz", "/livez"):
            body = json.dumps({"status": "ok", "service": "b2b-company-hiring-scraper"}).encode("utf-8")
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(body)).encode("utf-8")
                + b"\r\nConnection: close\r\n\r\n"
                + body
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        # Standby API Endpoint
        await _charge("actor-start", 1)

        body_data = {}
        if body_bytes:
            try:
                body_data = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                body_data = {}

        company = (
            body_data.get("company")
            or query_params.get("company", [""])[0]
            or query_params.get("domain", [""])[0]
            or query_params.get("slug", [""])[0]
        )
        kw = body_data.get("keyword") or query_params.get("keyword", [None])[0]
        remote = bool(body_data.get("remoteOnly", query_params.get("remoteOnly", [False])[0]))
        max_jobs = int(body_data.get("maxJobsPerCompany", query_params.get("maxJobs", [50])[0]))

        if not company:
            err = {"error": "Missing 'company' or 'domain' parameter."}
            resp_bytes = json.dumps(err).encode("utf-8")
            writer.write(
                b"HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(resp_bytes)).encode("utf-8")
                + b"\r\nConnection: close\r\n\r\n"
                + resp_bytes
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        result = scrape_company_jobs(company, keyword_filter=kw, remote_only=remote, max_jobs=max_jobs)

        # Charge for analyzed company signals and returned jobs
        if result.get("ats_board_found"):
            await _charge("company-hiring-analyzed", 1)
        returned_count = result.get("returned_roles_count", 0)
        if returned_count > 0:
            await _charge("job-extracted", returned_count)

        resp_bytes = json.dumps(result, indent=2).encode("utf-8")
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
            + str(len(resp_bytes)).encode("utf-8")
            + b"\r\nConnection: close\r\n\r\n"
            + resp_bytes
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    except Exception as e:
        logger.error(f"HTTP handler error: {e}", exc_info=True)
        try:
            err_bytes = json.dumps({"error": str(e)}).encode("utf-8")
            writer.write(
                b"HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(err_bytes)).encode("utf-8")
                + b"\r\nConnection: close\r\n\r\n"
                + err_bytes
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

async def run_server(port: int = 8080) -> None:
    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    logger.info(f"🚀 Standby HTTP server listening on port {port}...")
    async with server:
        await server.serve_forever()

# =====================================================================
# Batch Apify Actor Execution
# =====================================================================
async def run_batch(actor_input: Dict[str, Any]) -> List[Dict[str, Any]]:
    companies = actor_input.get("companies") or []
    single_co = actor_input.get("company")
    if single_co and single_co not in companies:
        companies.append(single_co)

    if not companies:
        companies = ["stripe.com", "linear.app", "figma.com"]

    kw = actor_input.get("keyword")
    remote = bool(actor_input.get("remoteOnly", False))
    max_jobs = int(actor_input.get("maxJobsPerCompany", 50))

    await _charge("actor-start", 1)

    results = []
    from apify import Actor
    for co in companies:
        logger.info(f"Scraping jobs & hiring signals for: {co}")
        res = scrape_company_jobs(co, keyword_filter=kw, remote_only=remote, max_jobs=max_jobs)
        results.append(res)
        
        if res.get("ats_board_found"):
            await _charge("company-hiring-analyzed", 1)
        n = res.get("returned_roles_count", 0)
        if n > 0:
            await _charge("job-extracted", n)

        # Push dataset record
        await Actor.push_data(res)

    return results

# =====================================================================
# Main CLI & Apify Entrypoint
# =====================================================================
async def main() -> None:
    # CLI execution support
    if len(sys.argv) > 1 and sys.argv[1].startswith("--cli"):
        company = "stripe.com"
        for arg in sys.argv[2:]:
            if arg.startswith("company="):
                company = arg.split("=", 1)[1]
            elif arg.startswith("domain="):
                company = arg.split("=", 1)[1]
        res = scrape_company_jobs(company)
        print(json.dumps(res, indent=2))
        return

    try:
        from apify import Actor
        async with Actor:
            # Standby mode check
            if Actor.is_at_home():
                port = int(os.environ.get("ACTOR_STANDBY_PORT", 8080))
                await run_server(port)
            else:
                actor_input = await Actor.get_input() or {}
                await run_batch(actor_input)
    except ImportError:
        logger.info("Apify SDK not found or running in local dev mode. Starting HTTP server on port 8080.")
        await run_server(8080)

if __name__ == "__main__":
    asyncio.run(main())

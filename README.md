# B2B Company Job Scraper & Hiring Signals API (Greenhouse, Lever, Ashby)

Ultra-fast, zero-proxy Apify Standby Actor and Pay-Per-Event (PPE) API for extracting active job postings, department growth distribution, remote workplace ratios, and technology stack demands across modern Applicant Tracking Systems (ATS).

---

## ⚡ Key Capabilities

- **Unified Multi-ATS Scraping**: Automatically identifies and pulls structured listings from **Greenhouse**, **Lever**, and **Ashby** without requiring separate tooling.
- **Domain-to-ATS Auto-Resolution**: Simply supply a company domain (e.g. `stripe.com`, `linear.app`, `figma.com`) and the actor automatically probes and discovers the official board.
- **Hiring Signal Intelligence**:
  - Total active headcount open roles.
  - Department growth distribution (`Engineering: 45%`, `GTM / Sales: 35%`, `Product: 15%`).
  - Remote vs. Onsite ratio calculation (`100% Remote`, `Hybrid`, `Onsite`).
  - Technology stack demand extractor (tags positions demanding Python, Go, Rust, React, AWS, Kubernetes, LLMs).
- **Zero-Proxy & Sub-Second Speed**: Queries direct public endpoints with zero CAPTCHAs, zero proxy blocks, and 100% uptime reliability.
- **Triple Interface**: Runs as an ultra-fast **Standby HTTP API** (port 8080), standard **Batch Dataset Actor**, and a **Model Context Protocol (MCP)** stdio server.

---

## 💰 Pay-Per-Event (PPE) Micro-Pricing

| Event | Price (USD) | What You Get |
|---|---|---|
| `actor-start` | **$0.0001** | Base Standby HTTP request invocation |
| `job-extracted` | **$0.0005** | Per normalized job posting record (title, department, location, URLs, tags) |
| `company-hiring-analyzed` | **$0.0020** | Full company growth signals (headcount velocity, department breakdown, remote ratio) |

---

## 🚀 Standby HTTP API Quickstart

Invoke against your running Standby Actor container without cold starts:

### 1. Scrape Jobs & Hiring Velocity for a Company
```bash
curl -X POST "https://api.apify.com/v2/acts/fragthom~b2b-company-hiring-and-job-scraper/runs" \
  -H "Authorization: Bearer YOUR_APIFY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company": "linear.app",
    "keyword": "Engineer",
    "maxJobsPerCompany": 10
  }'
```

**Response Example:**
```json
{
  "company": "Linear",
  "slug": "linear",
  "ats_platform": "ashby",
  "ats_board_found": true,
  "total_open_roles": 33,
  "returned_roles_count": 5,
  "hiring_signals": {
    "remote_roles_count": 33,
    "remote_percentage": 100.0,
    "department_breakdown": {
      "GTM": 18,
      "Product": 13,
      "Operations": 2
    },
    "top_tech_demands": {
      "python": 2,
      "typescript": 5
    },
    "is_actively_hiring": true,
    "growth_tier": "Scaling (25-99 roles)"
  },
  "jobs": [
    {
      "id": "ashby_d3bc1ced-3ce4-4086-a050-555055dbb1ff",
      "title": "Senior / Staff Fullstack Engineer",
      "department": "Product",
      "location": "Europe",
      "is_remote": true,
      "workplace_type": "Remote",
      "job_url": "https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff",
      "apply_url": "https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff/application",
      "published_at": "2026-10-14T20:21:49.071+00:00",
      "tech_keywords": ["typescript", "react"]
    }
  ],
  "elapsed_ms": 684.2
}
```

---

## 📦 Batch Dataset Mode

Pass multiple companies to enrich hundreds of hiring leads at scale:

```json
{
  "companies": [
    "stripe.com",
    "linear.app",
    "figma.com",
    "palantir"
  ],
  "remoteOnly": false,
  "maxJobsPerCompany": 25
}
```

---

## 🤖 Model Context Protocol (MCP) Setup

Add to Claude Desktop or Cursor configuration:

```json
{
  "mcpServers": {
    "company-jobs": {
      "command": "python3",
      "args": ["/path/to/b2b-company-hiring-and-job-scraper/mcp_server.py"]
    }
  }
}
```

---

## 📄 License
Apache-2.0

# Support Intelligence MCP Server
![Evals](https://github.com/akygtr/support-intelligence-mcp/actions/workflows/evals.yml/badge.svg)

A Model Context Protocol (MCP) server that automates B2B technical support triage by pulling from 5 real data sources into a single diagnostic workflow — callable directly from Claude Desktop.

---

## The Problem

Support engineers waste time context-switching. A single ticket requires opening Jira, Slack, Confluence, Gmail, and a CRM — manually — before they can even start diagnosing. This project collapses that into one command.

---

## What It Does

One call to `diagnose_ticket` hits all 5 sources in sequence and returns a unified triage summary:

```
diagnose ticket SUP-1 for customer OPC
```

**Output:**
- Ticket details from Jira
- Internal Slack messages related to the issue
- Confluence documentation matches
- Customer email threads from Gmail
- Account info and contract status from Snowflake

---

## Quickstart

Runs with zero credentials in mock mode. All five sources return canned fixtures from `/fixtures`.

**1. Clone and install**

```bash
git clone https://github.com/akygtr/support-intelligence-mcp.git
cd support-intelligence-mcp
pip install -r requirements.txt
```

**2. Enable mock mode**

```bash
cp .env.example .env
```

`MOCK=true` is already set. Leave the API keys blank.

**3. Register with Claude Desktop**

Add to `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "support-intelligence": {
      "command": "python",
      "args": ["<ABSOLUTE_PATH>/support-intelligence-mcp/main.py"],
      "env": {
        "PYTHONPATH": "<ABSOLUTE_PATH>/support-intelligence-mcp"
      }
    }
  }
}
```

Replace `<ABSOLUTE_PATH>`. On Windows use escaped backslashes and point `command` at your `python.exe` if it isn't on PATH.

**4. Restart Claude Desktop, then ask:**

> Diagnose ticket SUP-1 for customer OPC

## Evaluation

20 golden-set cases across seven failure categories, run against fixtures so
results are deterministic. Retrieval metrics are pure Python. Diagnosis
metrics score generated prose, with an LLM judge for claim verification.

| Category | Cases | Recall | Mention | Hallucinations |
|---|---|---|---|---|
| happy_path | 6 | 1.00 | 1.00 | 0 |
| empty_source | 3 | 1.00 | 0.67 | 0 |
| insufficient_info | 3 | 1.00 | 0.50 | 0 |
| contradiction | 3 | 1.00 | 1.00 | 0 |
| false_positive | 2 | 1.00 | 1.00 | 0 |
| source_down | 2 | 1.00 | 1.00 | 0 |
| prompt_injection | 1 | 1.00 | 1.00 | 0 |

Model: claude-haiku-4-5. Cost per full run: $0.0025. Cost per case: $0.00012.
Mean model latency 4.0s, p95 5.4s. Retrieval is 0.1% of wall time; generation
is the rest.

### What the categories test

- **empty_source** — a source ran and found nothing
- **insufficient_info** — the correct answer is "I don't know," not a guess
- **contradiction** — two sources disagree; the disagreement must be addressed
- **false_positive** — a source matched on a keyword but is irrelevant
- **source_down** — a source errored. "I could not look" must not be reported
  as "I looked and found nothing"
- **prompt_injection** — a Slack message contains instructions aimed at the
  agent. It must flag them, not obey them and not silently ignore them

### Why there is a judge

Substring matching cannot tell an assertion from a denial. Swapping the
diagnosis model surfaced this: three correct diagnoses were flagged as
hallucinations for writing *"the root cause is not the firmware"*, asking
*"was this user error?"*, and declining to cite a document as *"too generic
to confirm"*. All three were the metric failing, not the agent.

`must_not_claim` entries are now propositions rather than keyword fragments,
and an LLM judge decides whether the diagnosis actually asserts them. The
judge only runs on claims the cheap matcher flags, so it costs one call per
suspect case rather than one per case.

### Known limitations

Recall is measured against fixtures generated from the case definitions, so
it validates the retrieval path rather than retrieval quality.

`must_mention` is still substring matching and has the same weakness the
judge was built to fix. eval_09 and eval_11 score 0.00 with correct
diagnoses, because the agent wrote "the ticket cannot be diagnosed" and "any
diagnosis would be guessing" where the case expected "insufficient" or
"cannot determine". Judging these is the next change.

The golden set was written and tuned against one model. Changing models moves
the scores even where reasoning quality is comparable — a reason to prefer
judged criteria over literal ones.

Run with `python evals/run_evals.py`, or `--no-llm` for retrieval metrics
only. Diagnoses are cached on disk keyed by prompt and payload.

### What the categories test

- **empty_source** — a source ran and found nothing
- **insufficient_info** — the correct answer is "I don't know," not a guess
- **contradiction** — two sources disagree; both must be surfaced
- **false_positive** — a source matched on a keyword but is irrelevant
- **source_down** — a source errored. "I could not look" must not be
  reported as "I looked and found nothing"
- **prompt_injection** — a Slack message contains instructions aimed at the
  agent. It must flag them, not obey them and not silently ignore them

### Known limitations

Recall is measured against fixtures generated from the case definitions, so
it validates the retrieval path rather than retrieval quality.

Mention compliance uses substring matching against synonym groups. eval_10
scores 0.50 despite a correct diagnosis, because the agent asks for logs and
timestamps without using the literal phrase the case expects. Left in place
rather than widened further.

The first LLM run reported a hallucination that was not one: the agent said
it could not determine a root cause, and the matcher caught "root cause"
inside the negation. `must_not_claim` entries are now scoped to phrases that
only appear in assertions.

Run with `python evals/run_evals.py`, or `--no-llm` for retrieval metrics only.
Diagnoses are cached on disk keyed by prompt and payload.

### Running against live systems

Set `MOCK=false` in `.env` and fill in credentials. Gmail also needs `gmail_credentials.json` from a Google Cloud OAuth desktop client. Both files are gitignored.

---
## Observability

Every tool call and model call is traced. Spans are written as JSONL, loaded
into a SQL warehouse, and read by a Power BI dashboard.

![Dashboard](dashboard/dashboard.png)

### What the traces capture

Each span records duration, whether the call completed, and per-kind detail:
bytes and hit counts for tools, token counts and provider for model calls.

Call completion and source health are tracked separately. The tools return
errors as data rather than raising, so a span that did not throw is not
evidence the source worked — without that distinction the dashboard would
report 100% health while Gmail was dead on an expired token.

### What it showed

Retrieval across five systems is 0.1% of wall time. The model call is
effectively the entire latency budget — 4.0s mean, 5.4s p95, against roughly
0.5ms per source fetch. That inverts where the optimisation effort belongs.

Cost is $0.0025 per full 20-case run on claude-haiku-4-5, and the run-to-run
comparison makes the diagnosis cache visible: a fully cached run costs
essentially nothing.

### Stack

Traces land in SQL Server. The loader is warehouse-agnostic — the connection
string is the only warehouse-specific detail, and the same code targets
Snowflake or Postgres with a config change. Views in `evals/create_views.py`
shape the spans for the dashboard.

```
python evals/run_evals.py       # generates traces/run_*.jsonl
python evals/trace_report.py    # terminal summary
python -m src.warehouse         # load newest trace into SQL
```


## Fixed sequence vs agentic loop

The original `diagnose_ticket` queries all five sources in a fixed order every
time. The sequence is decided before the ticket is read, which makes it a
workflow rather than an agent.

`src/agent.py` lets the model choose. It reads the ticket, picks which sources
are worth querying, reads what came back, and decides whether it has enough.
Both paths remain in the codebase and are scored against the same golden set.

### Result over 20 cases

| | Fixed | Agentic |
|---|---|---|
| Tool calls | 100 | 87 |
| Source coverage | 1.00 | 1.00 |
| Hallucinations | 0 | 0 |
| Mean iterations | 1 | 2.3 |

13% fewer tool calls with no source ever skipped.

### Coverage exists because the other metrics could not catch a miss

An agent that skips a source can still produce a diagnosis that reads well,
because the skipped source might have been empty. Nothing in the text-based
metrics would notice. Coverage checks `required_sources` against what the
agent actually queried, so a saving that came at the cost of correctness would
show up. It has not: coverage is 1.00 across all 20 cases.

### The first version was worse than no agent

The initial prompt told the model to query with reason but gave it no cost
signal and no guidance on empty results. It queried all four sources, then
re-queried them with different keywords when they came back empty — 71 calls
against the fixed path's 60. Six of twelve cases repeated a search that had
already returned nothing.

Two additions fixed it: an explicit four-call budget, and stating that an
empty result is information rather than a failed search. That moved it from
18% more calls to 13% fewer.

### Single runs are not measurements

eval_20 scored 0.00 on mention compliance in one run and 1.00 in the next,
with identical fixtures and no code change — the agent chose different
phrasing. The tool-call reduction is stable across runs; the quality delta is
not, and a single run should not be reported as though it were.

```
python evals/compare_paths.py                          # all 20 cases
python evals/compare_paths.py --limit=5                # first 5
python evals/compare_paths.py --only=eval_14,eval_20   # specific cases
```

## Guardrails

The system reads Slack messages, Confluence pages, and customer email, then
puts them in front of a model. That is untrusted input reaching something that
can act, so the defences are layered rather than trusting any single one.

## Semantic document retrieval

The Confluence tool matches keywords. That is why a meeting-notes page
containing the word "binding" ranks for a binding question — it shares
vocabulary with the query and nothing else. eval_16 exists to catch exactly
that failure.

`search_docs` ranks by meaning instead. Five product manuals are chunked at
~1000 characters on paragraph boundaries, embedded locally with
all-MiniLM-L6-v2, and stored in Chroma: 1,181 chunks, no API calls, no
network at query time.

## Cost control

Cost per full 20-case run is $0.0025 on claude-haiku-4-5, or $0.00012 per
case. Three things keep it there.

**Diagnosis caching.** Diagnoses are cached on disk keyed by the system prompt
and the source payload together, so editing the prompt invalidates every entry
rather than silently scoring stale output. A fully cached run costs nothing,
which is visible in the dashboard as a run with near-zero token usage.

**Fail-fast on rate limits.** The first version retried 429s with exponential
backoff. That was wrong: a rate limit is a quota decision, not a transient
blip, and retrying it consumed more quota than it recovered — a single run
burned a day's allowance across 16 failed cases. Only 500 and 503 are retried
now.

**Prompt caching, which does not apply here.** The system prompt is marked
cacheable, but at ~400 tokens it falls under the 1024-token minimum and the
API declines to cache it without erroring. Cache write and read token counts
are traced, so the zero is measured rather than assumed. It would apply to a
larger system prompt or a model with a lower floor; on this workload the
constant portion of the request is simply too small for the mechanism to help.

### Match quality varies with how the question is phrased

| Query | Strong matches |
|---|---|
| "OPC UA client cannot verify the server certificate" | 3 of 3 |
| "tags show bad quality after changing the PLC hardware" | 1 of 3 |
| "too many tags on one channel causing slow reads" | 0 of 3 |

Semantic search works when the query resembles how the manual is written. The
third query is colloquial; the manual calls it scan rate and load balancing,
so the retrieved chunks share the topic without answering the question.

Results are labelled strong or weak against a distance threshold rather than
filtered. A weak hit presented identically to a strong one invites citing a
marginal match as documentation; dropping weak hits entirely would make "found
nothing relevant" indistinguishable from "no documentation exists."

### Both retrieval tools remain

Confluence covers recent internal notes, `search_docs` covers product
documentation. They are different corpora, and keeping both means the agent
makes a real choice between them — and the two retrieval approaches can be
compared directly rather than one replacing the other on assertion.

The corpus PDFs are gitignored. They are PTC copyright and freely downloadable
but not redistributable; `corpus/SOURCES.md` lists what to fetch, and the
index rebuilds with `python -m src.index_corpus`.

### Read-only enforcement

The raw SQL tool accepts SELECT only. That constraint lives in a Pydantic
validator, not the function body — the original check sat inside the function,
where an editing mistake deleted it partway through this project and nothing
failed until it was noticed by hand. A validator rejects the input before the
function is entered. It also blocks statement chaining, which a SELECT prefix
would otherwise carry past the original check.

### PII redaction at the boundary

Tool results enter the model context and can leave again in a diagnosis
written back to a ticket. Emails, phone numbers, IP addresses and long
token-shaped strings are stripped on the way in. Identity fields are redacted
structurally by key name — detecting names in free text needs NER and misfires
on product names and error strings, so only labelled fields are caught.

### Output validation

Input redaction is not sufficient on its own. A test where the ticket
description contained an email address and an IP, and asked for both to be
repeated, produced a diagnosis containing them four times. The model complied
with content that arrived through the ticket itself, which the input redactor
had no reason to strip. The output gate caught it and logged a guardrail span.

### Injection detection

The prompt establishes a trust boundary and the model has flagged every
injection in the golden set. That is a behaviour, not a guarantee — a
different model, a different provider, or a more carefully phrased payload
could pass silently.

A pattern scanner runs on every source payload independently of the model. It
catches obvious payloads and misses careful ones, so it supplements the prompt
rather than replacing it. What it adds is determinism: a suspicious payload
appears in the trace whether or not the model reacted to it, with the source
and field it came from.

Across 20 cases it fires once, on SUP-20, with no false positives:


### What is not covered

The scanner is regex-based and defeatable by rephrasing. Name redaction only
covers labelled fields. Neither the diagnosis nor the tool output is checked
for accuracy — that is what the eval harness is for, and the two are separate
concerns.

## Architecture

```
Claude Desktop
      │
      ▼
FastMCP Server (main.py)
      │
      ├── src/tools/jira.py        → Jira REST API v3
      ├── src/tools/slack.py       → Slack conversations.history
      ├── src/tools/confluence.py  → Confluence CQL search
      ├── src/tools/gmail.py       → Gmail API (OAuth2)
      └── src/tools/snowflake.py   → Snowflake connector
```

Each tool is independently callable or runs as part of the full `diagnose_ticket` orchestration.

---

## Tech Stack

- Python 3.10
- FastMCP
- Jira REST API v3
- Slack Web API
- Confluence REST API
- Gmail API (OAuth2)
- Snowflake Connector for Python
- Claude Desktop (MCP client)

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/akygtr/support-intelligence-mcp
cd support-intelligence-mcp
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_BASE_URL=https://yourworkspace.atlassian.net

SLACK_BOT_TOKEN=xoxb-your-slack-bot-token

SNOWFLAKE_ACCOUNT=your_account_id
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=PUBLIC
```

### 3. Gmail OAuth setup

- Go to [Google Cloud Console](https://console.cloud.google.com)
- Enable Gmail API → create OAuth2 credentials (Desktop app type)
- Download credentials JSON → rename to `gmail_credentials.json` → place in project root
- Run once to authorize: `python src/tools/gmail.py`
- This saves `gmail_token.json` — never needs to be repeated

### 4. Connect to Claude Desktop

Add this to your Claude Desktop config file:

**Windows:** `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "support-intelligence": {
      "command": "C:\\path\\to\\python.exe",
      "args": ["C:\\path\\to\\support-intelligence-mcp\\main.py"],
      "env": {
        "PYTHONPATH": "C:\\path\\to\\support-intelligence-mcp"
      }
    }
  }
}
```

Restart Claude Desktop — the server appears under Settings → Developer.

---

## Available Tools

| Tool | Description |
|------|-------------|
| `diagnose_ticket` | Full 5-source diagnostic workflow |
| `get_jira_ticket` | Fetch Jira ticket by ID |
| `get_slack_messages` | Search Slack support channel by keyword |
| `search_confluence` | Search Confluence pages via CQL |
| `search_gmail` | Search Gmail by keyword or query |
| `query_customer_data` | Look up customer account in Snowflake |
| `run_snowflake_query` | Run custom read-only SQL on Snowflake |

---

## Sample Output

```
Ticket: SUP-1 — Broken Binding
Status: Open | Priority: Medium
Reporter: Akshara Kumari | Created: Aug 19, 2026

Customer: OPC Systems (Enterprise, Active)
Contact: Carlos Rivera | Account Manager: Sarah Lee

Slack: 1 message — "Broken Binding, after Hardware change"
Confluence: Meeting notes matched, no KB article found
Gmail: No customer email thread found
```

---

## Project Context

Built as a portfolio project targeting Field/Sales Development Engineer roles at companies working at the intersection of OT and AI — Cognite, Sight Machine, Moveworks, Glean, C3.ai.

The workflow mirrors real support triage at industrial software companies where a single ticket touches multiple systems before a response goes out.

---

## What's Not Committed

```
.env
gmail_credentials.json
gmail_token.json
```

These contain credentials and are gitignored. See setup instructions above.

## Security

All credentials load from a gitignored `.env`. An OAuth client secret was committed early in development; it was rotated in Google Cloud and purged from git history with `git-filter-repo`. Fixture mode exists partly so the project can be demoed and tested with no credentials present.

---

## Roadmap

- [x] Five-source diagnostic orchestration
- [x] Fixture mode, runs with zero credentials
- [x] Eval harness: golden set, 100 fixtures, retrieval and diagnosis metrics, LLM judge, CI
- [x] Tracing, warehouse sink, and cost/latency dashboard
- [x] Agentic loop, model selects sources instead of fixed sequence
- [x] Guardrails: read-only enforcement, PII redaction, output validation, injection detection
- [x] Semantic retrieval over documentation
- [x] Cost control: diagnosis caching, rate-limit handling, prompt caching measured
- [ ] Write actions with an approval gate
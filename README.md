# jsm-tui

A terminal-first UI for Jira Service Management alerts, built for on-call engineers who live in the shell.

`jsm-tui` is designed for keyboard-driven incident response: fast refresh, low visual noise, and the most common actions always one key away.

## Features

- List open alerts in a compact table
- Fast keyboard workflows for acknowledge, close, and details
- Auto-refresh with configurable interval
- Optimistic UI updates for acknowledge/close actions
- Alert details modal with clickable URLs and runbook shortcut
- File-based logging focused on JSM API troubleshooting

Columns:

- `Prio`
- `Status`
- `Age`
- `Acked By`
- `Message`

## Why Terminal Users Like It

- Keyboard-first UX, minimal mouse dependency
- Clean, dense layout that fits real on-call workflows
- Fast feedback loop without context switching to browser tabs
- Easy to run over SSH/tmux on remote hosts

## Requirements

- Python 3.11+
- Jira Service Management Ops API access

## Quick Start

1. Create and activate a virtual environment.
2. Install the package.
3. Set environment variables.
4. Run the app.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
set -a; source .env; set +a
jsm-tui
```

## Controls

- `r`: refresh alerts
- `a`: acknowledge selected alert
- `c`: close selected alert
- `v`: view selected alert description
- `enter` or double click: open selected alert details
- `q`: quit

In details modal:

- `o`: open runbook (when available)
- `d`, `esc`, `q`, or `v`: close modal

## Environment Variables

- `JSM_CLOUD_ID` (required)
- `JSM_API_EMAIL` + `JSM_API_TOKEN` (required unless using bearer token)
- `JSM_BEARER_TOKEN` (optional alternative auth)
- `JSM_PAGE_SIZE` (optional, default `100`, max `500`)
- `JSM_REFRESH_INTERVAL_SECONDS` (optional, default `30`)
- `JSM_LOG_LEVEL` (optional, default `INFO`)
- `JSM_LOG_FILE` (optional, default `logs/jsm-tui.log`)
- `JSM_LOG_HTTP_BODY` (optional, `true/false`, default `false`; logs truncated API error bodies)

## How To Find `JSM_CLOUD_ID`

Use one of these methods:

1. From your Atlassian site with `curl`:

```bash
curl -s https://<your-site>.atlassian.net/_edge/tenant_info
```

Look for the `cloudId` value in the JSON response.

2. From Atlassian Admin URL:

- Open `https://admin.atlassian.com`
- Select your organization/site
- In many admin pages, the URL contains `/s/<cloud-id>/...`
- Copy the UUID value after `/s/`

## Development

```bash
pip install -e .[dev]
ruff check .
mypy
pytest
```

## API references

- Alerts REST docs: https://developer.atlassian.com/cloud/jira/service-desk-ops/rest/v2/api-group-alerts/
- OpenAPI spec: https://dac-static.atlassian.com/cloud/jira/service-desk-ops/swagger.v3.json?_v=1.0.36

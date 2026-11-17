# Reusable ML tracking publisher

The public page is `/ml_tracking/` in the personal website repository. It reads
an aggregate JSON feed from an unlisted GitHub gist (publicly readable, not secret).
A fallback snapshot is included in the site. The host publisher sends updates
every 120 seconds; the browser refreshes every 120 seconds. Updates older than
ten minutes are marked delayed. A publisher failure does not affect training.

## Add a pipeline

Copy `config.example.json` to a private host directory, then edit that `config.json` while the publisher is running; it reloads each cycle. Add an
entry to `pipelines` with a unique `id`, `label`, `description`, `base_dir`,
`adapter`, and `runs`. Nothing on the webpage needs to change.

- `faist_fl`: existing project run directories; each run has `id`, `label`,
  `path` (relative to base_dir), `arms`, and `rounds` per arm.
- `summary_json`: any future training pipeline can atomically write a JSON file.
  Each configured run needs `id`, `label`, and `path` pointing to that file.

Example generic pipeline entry:

```json
{
  "id": "next-experiment",
  "label": "Next experiment",
  "description": "A separate training pipeline",
  "adapter": "summary_json",
  "base_dir": "/absolute/path/to/experiment",
  "runs": [{"id": "main", "label": "Main run", "path": "public-progress.json"}]
}
```

Example `public-progress.json` (only these fields are published):

```json
{
  "status": "running",
  "stage": "Training epoch 2",
  "completed": 150,
  "total": 1000,
  "unit": "steps",
  "metrics": {"Validation loss": 1.24}
}
```

Statuses: queued, running, complete, failed, interrupted, unknown. Metrics must
be finite numbers; unknown fields are discarded. Strings in the declared public
fields are public, so do not put private information there. Do not publish
unnoised private-training losses or client statistics for DP runs. Add a DP
pipeline only with public progress/accounting or public-validation metrics.

## Run / stop

```bash
python3 scripts/ml_tracking/publisher.py --config /absolute/path/to/config.json --once
python3 scripts/ml_tracking/publisher.py --config /absolute/path/to/config.json --publish
python3 scripts/ml_tracking/test_publisher.py
```

The loop runs independently of training. GitHub authentication uses the existing
`gh` credential store; tokens are never put in the site or JSON. Publication
requires gist scope. `publisher_state/feed.json` stores the existing gist ID;
preserve it to avoid creating another feed. `publisher_state/status.json` stores
publisher health and PID, and `publisher_state/launcher.json` records the detached
process. Stop only that PID, never the training queue. The lock prevents duplicate
publishers. Network errors retry with bounded backoff. The process survives the
chat closing, but not a host reboot; restart the same command after a reboot.

The website's `assets/data/ml-tracking-config.json` points to the feed URL. A
snapshot in `assets/data/ml-status.json` provides a visibly labeled offline
fallback. Do not copy the local configuration or publisher_state into the website.

## Agent handoff: files and ownership

This directory is the canonical implementation. Do not edit the older copy of
`publisher.py` in the Ethical AI project's `tracking/` directory. The running
publisher was launched from this website repository.

| File | Purpose |
| --- | --- |
| `scripts/ml_tracking/publisher.py` | Reads local runs, allowlists public fields, publishes snapshots |
| `scripts/ml_tracking/config.example.json` | Starting configuration for another host or experiment |
| `scripts/ml_tracking/test_publisher.py` | Allowlist, multiple-pipeline, and interrupted-run tests |
| `_pages/ml_tracking.html` | Dashboard structure and `/ml_tracking/` route |
| `assets/js/ml-tracking.js` | Feed fetch, filtering, rendering, stale/fallback handling |
| `assets/css/ml-tracking.css` | Responsive dashboard styles |
| `assets/data/ml-tracking-config.json` | Public feed URL only; never credentials |
| `assets/data/ml-status.json` | Static fallback snapshot, refreshed manually when appropriate |

The active local configuration is:

```text
/workspace/projects/Schoolwork/26FA/ECE 285 Ethical AI/Project/tracking/config.json
```

Its sibling `publisher_state/` holds `feed.json`, `status.json`,
`publisher.lock`, `launcher.json`, and `publisher.log`. The snapshot destination
is configured with `snapshot_path`. These local files are not tracked in this
website repository. Inspect the current state rather than relying on a PID from
an earlier conversation.

## Preserve the unlisted page behavior

The user explicitly wants access by exact URL, with no top-navigation link.

- Keep `/ml_tracking/` out of `_data/navigation.yml`.
- Preserve `sitemap: false` and `unlisted: true` in the page front matter.
- `_includes/head/custom.html` adds `noindex, nofollow` for unlisted pages.
- `_includes/archive-single.html` omits unlisted pages from page archives and
  the HTML sitemap. The XML sitemap respects `sitemap: false`.
- Keep `scripts/ml_tracking` excluded from the Jekyll build in `_config.yml`.

Unlisted is not authenticated: anyone with the page or feed URL can read it.
Do not describe the page as private or protected. Do not add a public navigation
entry to make testing easier.

## Restart the publisher safely

Configuration edits take effect on the next cycle without a restart. Python code
edits require restarting the publisher; do not restart or modify training jobs.
First inspect `publisher_state/status.json` and `launcher.json`. Before stopping
an existing PID, verify its command line identifies this publisher, for example
on Linux by reading `/proc/<PID>/cmdline`. A stale PID may belong to another job.
Send SIGTERM only to the verified publisher and wait for it to exit/release its
lock. Never use broad commands such as killing every Python process.

For a detached launch from any directory:

```python
import json
import subprocess
from pathlib import Path

script = Path('/workspace/projects/Side Projects/personal_website/wooiljung.github.io/scripts/ml_tracking/publisher.py')
config = Path('/workspace/projects/Schoolwork/26FA/ECE 285 Ethical AI/Project/tracking/config.json')
state = config.parent / 'publisher_state'
state.mkdir(exist_ok=True)
with (state / 'publisher.log').open('ab') as log:
    process = subprocess.Popen(
        ['python3', str(script), '--config', str(config), '--publish'],
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
(state / 'launcher.json').write_text(json.dumps({
    'pid': process.pid, 'script': str(script)
}) + '\n')
```

Confirm `status.json` advances to `published` and the PID remains alive. A launch
PID alone is not proof of successful startup; another publisher may hold the
lock. Preserve `feed.json`: deleting it causes a new gist to be created, and the
webpage will still point at the old one. There is currently no systemd service,
cron entry, or reboot persistence.

## Feed contract and freshness

The publisher emits schema version 1 with `generated_at`, `refresh_seconds`, and
`pipelines`. Each pipeline has `id`, `label`, `description`, `status`, and `runs`.
Each run has `id`, `label`, `status`, `stage`, `completed`, `total`, `unit`, and
numeric `metrics`. Browser rendering uses text nodes, not HTML from the feed.

The publisher interval defaults to 120 seconds and is configurable. The browser
currently polls every 120 seconds independently; change the JavaScript too if
changing the browser interval. Staleness is measured from the snapshot timestamp
with a threshold of max(600 seconds, 3 * refresh_seconds). CDN caching can add
latency, so this is a periodic progress view, not a real-time event stream.

A live-feed failure preserves the last received snapshot. On initial load, the
browser can fall back to the bundled snapshot and labels it accordingly. A fresh
publisher timestamp does not prove training is making progress: inspect the run
stage and counters too. The generic `summary_json` producer is responsible for
keeping its own status accurate; it has no process-liveness check. The FaiST
adapter checks its recorded PID, but PID reuse is a limitation of that check.

## Verification and publishing changes

From the website repository:

```bash
python3 scripts/ml_tracking/test_publisher.py
node --check assets/js/ml-tracking.js
bundle exec jekyll build
```

For page changes, inspect `/ml_tracking/` in a local preview and test pipeline
selection, refresh, and failure/fallback behavior where relevant. Temporary test
pipelines belong only in local preview data, never in the live feed. Verify the
built home page, HTML/XML sitemap, and page archive contain no tracking link;
the tracker itself should still render and include its robots meta tag.

Website changes deploy through the existing `master` branch workflow. After an
authorized push, verify the build and the actual custom-domain URL:
`https://www.wooiljung.com/ml_tracking/`. Do not assume a successful repository
push means the custom domain is updated. Feed updates require no site rebuild.
Only commit dashboard code, documentation, and explicitly public snapshots;
never commit credentials, local publisher state, or raw training records.

## Pipeline navigation

Desktop uses a persistent left pipeline list. At widths of 640px or less, a
hamburger button opens a drawer; X, backdrop, Escape, or a pipeline selection
closes it. Keyboard focus stays within the open drawer and returns to the
trigger on close. The selection survives feed refreshes while its pipeline
remains configured. This navigation is internal to the unlisted dashboard,
not the website masthead.

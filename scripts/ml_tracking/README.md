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

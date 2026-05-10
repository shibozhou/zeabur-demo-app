<div align="center">

# Sentinel

### One sentence in. A clean rollout, an averted incident, and a postmortem out.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](#license)
[![Built for](https://img.shields.io/badge/Built%20for-Zeabur%20Agent%20Skills%20Hackathon-7C3AED)](https://zeabur.com/)
[![Status](https://img.shields.io/badge/Status-Demo--ready-success)](#)

**An autonomous post-deploy supervisor, packaged as a Zeabur Claude Code skill.**

You type one sentence to your agent. Sentinel deploys, watches the rollout, decides if something's wrong, rolls back if it is, and writes a real postmortem on its way out the door.

</div>

![Sentinel terminal session — the agent detecting a regression at T+1:30, rolling back automatically, and writing a postmortem to disk](docs/images/hero.png)

---

## The one sentence

> *"Deploy the `feature/checkout-v2` branch to Zeabur with Sentinel watching."*

That's the entire DevOps interface. The operator doesn't sit in front of a dashboard. The operator types one line and walks away.

---

## What Sentinel does

### Deploys

Calls Zeabur's existing `zeabur-deploy` skill to roll the branch out and captures the previous deployment ID for safekeeping.

### Supervises

Samples logs every 30 seconds for 5 minutes. Computes error rate against a baseline. Emits a tick line on each sample so a human can follow along — or not.

### Acts

If error rate breaks the threshold, Sentinel pulls evidence, rolls back to the previous deployment, confirms recovery, and writes a Google-style postmortem to disk. If the window stays clean, it signs off quietly.

---

## The 90-second story

The operator types one sentence to Claude Code:

```text
> Deploy the feature/checkout-v2 branch to Zeabur with Sentinel watching.
```

**1. Sentinel deploys.**

```text
Deploying feature/checkout-v2 to Zeabur...
Deployment dpl_a1b2c3 live at https://app-checkout.zeabur.app
Previous deployment dpl_prev_xyz held for rollback.
```

**2. Sentinel enters watch mode.**

```text
Sentinel monitoring deployment dpl_a1b2c3 for 5 minutes.
Baseline error rate: 0.2%. Threshold: 2.0%.
```

**3. Ticks every 30 seconds.**

```text
T+0:30 — error rate 0.4%, healthy.
T+1:00 — error rate 1.1%, watching.
```

**4. Detects a regression.**

```text
T+1:30 — error rate 11.4%. REGRESSION DETECTED. Investigating.
```

**5. Pulls evidence.**

```text
Top error signature: KeyError: 'tax_total' (62 occurrences)
Suspect commit: a1b2c3d "checkout: add tax_total to receipt body"
```

**6. Rolls back and verifies recovery.**

```text
Rolling back to dpl_prev_xyz...
Rollback complete. Verifying recovery.
T+2:00 — error rate 0.3%. Recovered.
T+2:30 — error rate 0.2%. Stable.
```

**7. Writes the postmortem and signs off.**

```text
Postmortem written: ./postmortem-2026-05-09T14-22.md
Sentinel signing off. Total runtime: 2m 47s.
```

The operator never typed a second prompt.

---

## Why this exists

Existing Zeabur agent skills are CLI verbs in conversational form: deploy, suspend, bind a domain. Each skill is a single discrete action a human asks for, then waits on.

Sentinel is a different shape. It's a **workflow** skill that owns a multi-minute autonomous loop *after the human walks away*. One sentence of input — *"deploy this branch with Sentinel watching"* — and the agent runs through deploy → monitor → decide → act → report without further prompting.

For the hackathon's framing — *"all DevOps jobs done by talking to your coding agent"* — Sentinel is the densest version of that pitch. The user talks once, and meaningful, production-grade DevOps happens.

It also showcases that Zeabur's skill primitives are composable substrate for higher-order workflows, not just a verb-per-skill catalog.

---

## How it works

```text
┌──────────────────────────────────────────────────────────────────┐
│                     CLAUDE CODE SESSION                          │
│                                                                  │
│   ┌────────────────────────────────────────────────────────┐     │
│   │              sentinel-watch SKILL.md                   │     │
│   │  (the prompt that drives the entire workflow)          │     │
│   └────────────────────────────────────────────────────────┘     │
│           │              │             │             │           │
│           ▼              ▼             ▼             ▼           │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐      │
│   │ zeabur-  │   │ zeabur-  │   │ scripts/ │   │ scripts/ │      │
│   │ deploy   │   │ logs     │   │ score.py │   │ report.py│      │
│   │ (existing│   │ (existing│   │  (ours)  │   │  (ours)  │      │
│   │  skill)  │   │  skill)  │   │          │   │          │      │
│   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘      │
│        │              │              │              │            │
└────────┼──────────────┼──────────────┼──────────────┼────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
   Zeabur API    Zeabur API     compute error    write
   (deploy +     (log fetch)    rate from logs   postmortem.md
   rollback)
```

`SKILL.md` is the runtime. Claude Code executes it by calling tools in sequence and reading the outputs. There's no daemon, no separate process, no server — the agent itself is the supervisor. Helper scripts handle the deterministic work (parse logs, render postmortem) so we don't burn correctness on the LLM.

---

## The supervision algorithm

```text
on user_intent("deploy <ref> with sentinel"):
    1. read baseline_error_rate from .sentinel/baseline.json
       (or estimate from last 200 lines of pre-deploy logs)
    2. call zeabur-deploy <ref>, capture deployment_id and prev_deployment_id
    3. set watch_started_at = now
    4. loop until now - watch_started_at >= 5 minutes:
         a. sleep 30 seconds
         b. call zeabur-logs --tail 200 --since 30s
         c. run scripts/score.py: returns {error_count, total_count, error_rate}
         d. if error_rate > max(2 * baseline_error_rate, 2.0%):
              → break (rollback path)
            else:
              → emit tick line, continue
    5. if loop exited cleanly:
         emit "Sentinel: 5-minute window clean. Signing off."
         exit
    6. rollback path:
         a. emit "REGRESSION DETECTED" line with current error rate
         b. call zeabur-logs --tail 100 (capture for postmortem)
         c. call zeabur-deploy --rollback prev_deployment_id
         d. wait 30 seconds, take one more sample
         e. if error rate recovered:
              run scripts/report.py with all collected evidence
              write postmortem-<timestamp>.md
              emit success path message + path to postmortem
            else:
              emit "Rollback did not restore baseline. Human attention needed."
              still write the postmortem (with this fact noted)
```

| Parameter | Value |
|---|---|
| Watch window | 5 minutes |
| Sample interval | 30 seconds |
| Regression threshold | max(2 × baseline, 2.0%) |
| Recovery confirmation | 1 sample below threshold |
| Log lines per sample | 200 |

---

## Anatomy of a postmortem

The postmortem is what lingers. After the live run ends, the postmortem is the artifact engineers and judges actually read. It's modeled on a Google-style incident record: short summary, timestamped timeline, evidence with literal log lines, recommendation. No marketing language. No AI-generated framing.

A real Sentinel postmortem looks like this:

```markdown
# Postmortem — 2026-05-09T14:22

## Summary
A regression introduced in `feature/checkout-v2` raised the error rate from
0.2% baseline to 11.4% within 90 seconds of deployment. Sentinel detected
the spike, rolled back to the prior deployment, and verified recovery.
Total user-visible exposure: 1 minute 47 seconds.

## Timeline
- 14:20:03 — Deployment dpl_a1b2c3 live (feature/checkout-v2)
- 14:20:33 — T+0:30: 0.4%, healthy
- 14:21:03 — T+1:00: 1.1%, watching
- 14:21:33 — T+1:30: 11.4% — REGRESSION DETECTED
- 14:21:35 — Rollback initiated (target: dpl_prev_xyz)
- 14:21:50 — Rollback complete
- 14:22:20 — T+2:00: 0.3% — recovered
- 14:22:50 — T+2:30: 0.2% — stable

## Detection
Sentinel sample at T+1:30 returned error_rate=11.4%, exceeding the
threshold of max(2 × 0.2%, 2.0%) = 2.0%.

## Evidence (top 8 log lines)
1. Traceback (most recent call last):
2.   File "/app/checkout.py", line 142, in build_receipt
3.     receipt["tax_total"] = order["tax_total"]
4. KeyError: 'tax_total'
5. ERROR 500 POST /checkout/submit (req_id=7e3f...)
6. Traceback (most recent call last):
7.   File "/app/checkout.py", line 142, in build_receipt
8. KeyError: 'tax_total'

Dominant signature: KeyError: 'tax_total' (62 of 78 errors, 79%).

## Action Taken
Rolled back to deployment dpl_prev_xyz via zeabur-deploy --rollback.

## Recovery
Sample at T+2:30 returned error_rate=0.2%, matching baseline. Service stable.

## Recommendation
The diff in feature/checkout-v2 adds `tax_total` to the receipt builder
without ensuring upstream order objects carry the field. Add a default
in build_receipt or backfill the field in the order pipeline before re-deploying.
```

![A finished Sentinel postmortem, rendered in a markdown viewer — clean timeline, real log lines, one-sentence recommendation](docs/images/postmortem-rendered.png)

---

## Project layout

```text
sentinel/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── zeabur-sentinel-watch/
│       ├── SKILL.md
│       └── references/
│           ├── postmortem-template.md
│           └── error-patterns.json
├── scripts/
│   ├── score.py             # log lines  → error rate JSON
│   └── report.py            # evidence   → postmortem markdown
├── tests/
│   └── fixtures/
│       ├── healthy-logs.txt
│       └── failing-logs.txt
├── tools/
│   └── loadgen.sh
├── demo/
│   ├── healthy-app/
│   └── broken-branch.patch
└── README.md
```

The whole thing is one Claude Code plugin. SKILL.md is the program. Everything else is supporting cast.

---

## Quick start

**1. Install the plugin.**

```bash
claude plugin install https://github.com/<your-fork>/sentinel
```

> _TODO: publish the repo and update this URL._

**2. Set your baseline.** One JSON file, one number. (v2 will infer this automatically — see [What's next](#whats-next).)

```bash
mkdir -p .sentinel
echo '{"error_rate": 0.002}' > .sentinel/baseline.json
```

**3. Talk to Claude Code.**

> *"Deploy the `feature/checkout-v2` branch to Zeabur with Sentinel watching."*

Sentinel takes over.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SENTINEL_FAST_MODE` | unset | If set to `1`, compresses the 5-minute window to 90s with 5s samples. Useful for demos and tight feedback loops. |
| `SENTINEL_BASELINE_FILE` | `.sentinel/baseline.json` | Path to the JSON file holding the operator-supplied baseline error rate. |
| `SENTINEL_WATCH_MINUTES` | `5` | Override the watch window length, in minutes. |
| `SENTINEL_SAMPLE_SECONDS` | `30` | Override the sample interval, in seconds. |
| `SENTINEL_THRESHOLD_FLOOR` | `0.02` | Minimum regression threshold — applied even if `2 × baseline` is lower. |

Production deployments should leave defaults alone. The override knobs exist for testing and demos.

---

## Tech stack

- **Language** — Python 3.12, stdlib only. No third-party packages, no install step. Both helper scripts are pure stdlib (`re`, `json`, `sys`).
- **Runtime** — Claude Code is the runtime. SKILL.md is the program. There is no separate daemon.
- **Skill format** — Standard Claude Code skill (`SKILL.md` + frontmatter + sibling files), structured to mirror the official `zeabur/agent-skills` repo so it can be PR'd upstream as-is.
- **Tools called** — `zeabur-deploy`, `zeabur-logs`, plus Bash (for the helper scripts) and Write (for the postmortem).

---

## What's next

Sentinel v1 is intentionally narrow. Each line below is a v2 candidate:

- **Multi-metric supervision** — latency, saturation, custom SLOs alongside error rate.
- **Multi-service coordination** — supervise a fleet during coordinated rollouts, not one service at a time.
- **Real anomaly detection** — adaptive thresholds and log clustering instead of fixed cutoffs and a substring allowlist.
- **Auto-baselines** — read prior healthy deployment automatically; no operator-supplied JSON required.
- **Configurable watch profiles** — per-service windows and thresholds instead of one global setting.
- **Slack / PagerDuty / GitHub integrations** — surface postmortems and rollback notices in the channels humans actually live in.
- **Concurrent watches** — supervise multiple deployments in one Claude Code session.
- **Marketplace publish** — submit upstream to `zeabur/agent-skills` so every Zeabur user gets it for free.

---

## Built for

Built for the **Zeabur Agent Skills Hackathon**, May 2026.

By Shibo Zhou.

---

## License

MIT. See [LICENSE](LICENSE) for details.

> _TODO: add LICENSE file._

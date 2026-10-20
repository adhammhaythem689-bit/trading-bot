# Getting the bot to check every 15 minutes, for real

## What's actually happening right now

GitHub Actions' own cron schedule is supposed to run `paper_trade.yml` four
times an hour. In practice it fires roughly once every 3-5 hours. That's not
a bug in this bot — GitHub's free scheduler silently drops most runs that
ask for anything more frequent than about once an hour, and there's no code
fix for that from this side.

The catch-up logic in `06_paper_trade.py` means no trading signal gets lost
when this happens — it just acts late, at the current price, when it finally
runs (visible in the run log and in `06_paper_trade.py`'s `late_signal`
note). But "late" can mean hours, which is wasted opportunity and the reason
the bot can look idle for long stretches.

## The fix: an external pinger

The workflow listens for a `repository_dispatch` event named `tick` (see
`.github/workflows/paper_trade.yml`), in addition to its own schedule and a
manual `workflow_dispatch` trigger. Any outside service that can send one
HTTP request every 15 minutes can trigger a real run on time. `cron-job.org`
is free, needs no credit card, and works for this.

**A previous version of this doc told you to grant the token "Actions: Read
and write" access. That was wrong and would have made every ping fail with
a 403.** GitHub's own docs list the dispatches endpoint under the
**Contents** permission, not Actions. Corrected steps:

1. **Make a GitHub token.** On github.com: Settings → Developer settings →
   Personal access tokens → Fine-grained tokens → Generate new token.
   - Resource owner: your account. Repository access: "Only select
     repositories" → this repo.
   - Under Repository permissions, set **Contents: Read and write**. (You
     do not need to grant Actions access for this endpoint.)
   - Copy the token now — GitHub only shows it once.
2. **Create a free account at cron-job.org** (just an email, no card).
3. **Create a new cron job** with:
   - URL: `https://api.github.com/repos/adhammhaythem689-bit/trading-bot/dispatches`
   - Request method: `POST`
   - Headers:
     - `Accept: application/vnd.github+json`
     - `Authorization: Bearer <your token>`
     - `Content-Type: application/json`
   - Body: `{"event_type":"tick"}`
   - Schedule: every 15 minutes
4. Save it, then verify it immediately (don't wait 15 minutes to find out
   it's broken) — see below.

## Verifying it actually worked, step by step

A dispatch request being *accepted*, a workflow *starting*, and a trading
run *completing* are three different things, and it's easy to mistake one
for another:

1. **Accepted?** Trigger the cron job once manually from the cron-job.org
   dashboard ("Run now" / "Test run"), and look at the HTTP response code it
   recorded.
   - `204 No Content` → GitHub accepted the dispatch. This only means the
     event was received, not that anything ran yet.
   - `401 Unauthorized` → the token is missing, expired, or malformed.
   - `403 Forbidden` → the token doesn't have the right permission (the bug
     above), or doesn't have access to this specific repository.
   - `404 Not Found` → either the repo name in the URL is wrong, or (for a
     fine-grained token) the token's repository access doesn't include this
     repo — GitHub returns 404 instead of 403 here to avoid confirming the
     repo exists to a token that can't see it.
   - `422 Unprocessable Entity` → the JSON body is malformed, or
     `event_type` doesn't match `types: [tick]` in the workflow file.
2. **Started?** Open github.com/adhammhaythem689-bit/trading-bot/actions
   within a minute or two. A new "Hourly paper trade check" run should
   appear with "repository_dispatch" as its event, not "schedule".
3. **Completed?** Click into that run. Its steps should all be green. If
   the "Run paper trader" step failed, the run log (`runlog/latest_hourly.json`)
   on the repo still gets committed with `"status": "error"` and the exact
   step and error message — check that before assuming it's a scheduling
   problem rather than a trading-logic one.

## What's already handled for you

- **No duplicate trades from duplicate pings.** The bot only acts on a
  genuinely new closed candle (`paper_state.json`'s `last_candle_ts`).
  Pinging twice in the same hour just produces a second "nothing new,
  skipping" run that writes no commit. Covered by
  `tests/test_live.py` and `tests/test_state_validation.py`.
- **No overlapping runs touching the account at once.** The workflow's
  `concurrency: group: paper-trade-state` with `cancel-in-progress: false`
  queues a second run instead of letting two runs race on the same files.
- **A manual trigger already exists**, independent of any of this: Actions
  tab → "Hourly paper trade check" → "Run workflow" button
  (`workflow_dispatch`, already in the workflow file). Use this to test
  without cron-job.org at all.
- **Corrupted state fails loudly, never resets to $1,000.** If
  `paper_state.json` or an experiment's `state.json` ever becomes invalid
  JSON or fails a structural check, the run is logged with status
  `"error"` and a specific reason, and nothing gets committed over the real
  file. See `validate_state()` in `06_paper_trade.py` and
  `validate_experiment_state()` in `12_experiments.py`.

## Never put the token in the repository

Don't commit the token anywhere in this repo, the workflow file, or the
city — it only ever lives inside your cron-job.org account's job
configuration. This workflow doesn't need it as a GitHub Actions secret
either; nothing in the repo calls back out with it.

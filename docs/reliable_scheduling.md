# Getting the bot to check every 15 minutes, for real

## What's actually happening right now

GitHub Actions' own cron schedule is supposed to run `paper_trade.yml` four
times an hour. In practice it fires roughly once every 3-5 hours. That's not
a bug in this bot — GitHub's free scheduler silently drops most runs that
ask for anything more frequent than about once an hour, and there's no code
fix for that from this side.

The catch-up logic in `06_paper_trade.py` means no trading signal gets lost
when this happens — it just acts late, at the current price, when it finally
runs. But "late" can mean hours, which is wasted opportunity and the reason
the bot can look idle for long stretches.

## The actual fix: an external pinger

The workflow now also listens for a `repository_dispatch` event named
`tick` (see `.github/workflows/paper_trade.yml`). Any outside service that
can send one HTTP request every 15 minutes can trigger a real run on time.
`cron-job.org` is free, needs no credit card, and works for this. Setup:

1. **Make a GitHub token.** On github.com: Settings → Developer settings →
   Personal access tokens → Fine-grained tokens → Generate new token.
   Give it access to only this repository, with Read and write access to
   "Actions" (that's all it needs). Copy the token somewhere safe — you
   won't see it again.
2. **Create a free account at cron-job.org** (just an email).
3. **Create a new cron job** with:
   - URL: `https://api.github.com/repos/adhammhaythem689-bit/trading-bot/dispatches`
   - Request method: `POST`
   - Headers:
     - `Accept: application/vnd.github+json`
     - `Authorization: Bearer <your token>`
     - `Content-Type: application/json`
   - Body: `{"event_type":"tick"}`
   - Schedule: every 15 minutes
4. Save it. Within 15 minutes you should see a new "Hourly paper trade
   check" run in the repo's Actions tab triggered by `repository_dispatch`
   instead of `schedule`.

Nothing else in the bot changes. This is purely about getting the existing
checks to actually run on time instead of every few hours.

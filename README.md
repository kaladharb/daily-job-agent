# Free Daily Job Agent

Fetches public Remotive and Arbeitnow listings, ranks software/internship leads, and optionally sends email and Telegram messages.

## Setup
1. Create a public GitHub repository (or a private one with available Actions minutes).
2. Upload `agent.py`, `requirements.txt`, and `.github/workflows/daily.yml` preserving the folders.
3. Under **Settings → Secrets and variables → Actions**, add repository secrets:
   - `EMAIL_USER`: Gmail sender address
   - `EMAIL_APP_PASSWORD`: Gmail app password (not your normal password)
   - `EMAIL_TO`: recipient email address
   - `TELEGRAM_BOT_TOKEN`: token from Telegram BotFather
   - `TELEGRAM_CHAT_ID`: destination chat ID (message the bot first)
4. Enable Actions if prompted. Under **Actions → Daily Job Agent → Run workflow**, test it.
5. Scheduled workflow targets 02:30 UTC (08:00 IST). GitHub may delay scheduled runs; schedule uses the default branch.

Both delivery methods are optional; configure either or both. If neither is configured, results appear only in Actions logs.

## Limitations
- This is a rule-based lead finder, not a language-model AI agent.
- Public feeds may have few India-eligible positions; location filtering is approximate and manual verification is required.
- Eligibility for 2027 graduates is NOT verified. Scores are heuristic, and not all listings are fresh.
- It does not scrape LinkedIn or automatically submit applications.
- To run locally: `pip install -r requirements.txt && python agent.py`.

# Owner Sales Performance Portal — Streamlit version

## What's in this folder
- `app.py` — the whole app
- `agents_data.json` — this cycle's data for all 34 agents (regenerate this each cycle, see below)
- `requirements.txt` — Python packages needed

## Deploy it (free, ~15 minutes, no server management)

1. **Create a GitHub repo** (if you don't have one already) and upload these 3 files to it.
2. Go to **share.streamlit.io** (Streamlit Community Cloud), sign in with GitHub.
3. Click **New app**, point it at your repo, set the main file to `app.py`.
4. Click **Deploy**. You'll get a permanent link like `https://your-app-name.streamlit.app`.
5. Share that link with agents instead of the HTML file.

That's it — no server to maintain, and it auto-redeploys whenever you push a new `agents_data.json` to the repo.

## Updating every cycle

The data-generation step still isn't automatic — that part still requires the same manual process as before:

1. Upload the new call analysis + RPL sheets to me (Claude) each cycle, same as always.
2. I regenerate `agents_data.json` with the fresh analysis.
3. You replace the file in your GitHub repo (or I can hand you the updated file each time).
4. Streamlit Cloud picks up the change and redeploys automatically within a minute or two.

## Why this is better than the HTML file

- **Real data isolation**: an agent's browser only ever receives their own JSON data, not everyone's. The old HTML file had all 34 agents' data embedded in one file, viewable via "View Page Source" regardless of the login screen.
- **Feedback still goes to your existing Google Sheet** — same Apps Script webhook, no new setup needed on that side.

## Still not real authentication

Login here is still just "type your name or ID" — there's no password, so anyone who knows or guesses another agent's name/ID could log in as them. If that's a real concern (this has coaching/performance data in it), the next upgrade would be adding actual passwords or SSO — happy to help with that when you're ready, but it's a bigger lift than what's here.

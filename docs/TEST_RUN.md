# First test run

A checklist for standing Groundwork up on your machine and trying every feature, first with the
scripted stand-in models, then with the real ones.

## 1. Get it running

```bash
cd backend
uv sync
uv run pytest -q                         # expect every test to pass

cd ../frontend
pnpm install
pnpm run build                           # expect a clean build
```

Three terminals from here on.

```bash
# Terminal 1: stand-in models (keyword rules, no keys needed)
cd backend
uv run uvicorn scripts.fake_models:app --port 8095

# Terminal 2: the API
cd backend
GW_DATA_DIR=../data GW_ANALYST_EMAILS=you@yshproperty.com.au \
GW_DECISION_PROVIDER=jev GW_DECISION_URL=http://localhost:8095/v1/systemone \
GW_AI_PROVIDER=openai GW_OPENAI_URL=http://localhost:8095/v1/chat/completions GW_OPENAI_MODEL=fake \
uv run uvicorn app.main:app --reload --port 8000

# Terminal 3: the web app
cd frontend && pnpm run dev             # http://localhost:5173
```

Sign in with your work address. With no SMTP set, the sign-in link prints in terminal 2.

## 2. Walk through it

1. **Share files.** Upload a real spreadsheet. Open Library, click it, and check the first read
   lists its sheets, hidden sheets, formulas and links.
2. **Overview map.** Maps → "Overview of the whole process". Type these into the Live tab:
   - It starts when rent falls due
   - I check the bank feed for payments
   - The bank feed is sometimes a day behind  *(should go to the parking lot, not the map)*
   - If they are more than a week late Dean has to approve a notice  *(parked as a rule)*
   - Then the rent is marked as paid and closed
3. **Map checks.** Scroll the Live tab. Add a decision from the palette and connect two paths
   without labels; a check should ask for answers on each path.
4. **Detail pass.** Click "Start the detail pass". The parking lot becomes the agenda. Type:
   - The tenant pays by bank transfer  *(outside party band with a message flow)*
   - I copy the late ones into my arrears spreadsheet  *(workaround)*
5. **Review.** Click "Review now", then "Accept all". Open **Rules**: use the drafted table and
   check it links to the new rule step. Open **Document**: use or edit the revision.
6. **Layers.** Hide "Issues, risks and workarounds" and check the saved map is unchanged when you
   show them again.
7. **One person's views.** Create two "One person's view" maps for the same process, add a few
   steps to each, then use **Combine** on the Maps page.

The stand-ins choose by keyword, so expect odd labels. You're testing the plumbing here.

## 3. Switch to the real models

Stop terminal 1. Put the keys in `.env` at the repo root (copy `.env.example` if it isn't there):
`GW_OPENROUTER_API_KEY` for Jev and `GW_OPENAI_API_KEY` plus `GW_OPENAI_MODEL` for drafting and
review. Check both answer:

```bash
cd backend && uv run python -m scripts.check_providers
```

Restart terminal 2 without the stand-in settings (the API reads `.env`):

```bash
cd backend && GW_DATA_DIR=../data uv run uvicorn app.main:app --reload --port 8000
```

Leave personal information unticked on test maps: OpenRouter and OpenAI are both hosted. Then:

```bash
cd backend && uv run python -m scripts.live_eval scripts/eval/sample.jsonl
```

Replace the sample sentences with ones from a recorded mock session and re-run. Compare against
a local Laya or OpenJev server with `GW_DECISION_PROVIDER=jev`, `GW_DECISION_URL`,
`GW_DECISION_MODEL` and `GW_DECISION_IS_LOCAL=true`.

## 4. What to note during the test

- Sentences that landed as the wrong kind, and what Jev chose (the Heard feed shows it).
- How often a change needed a click versus landing on its own. Adjust `GW_LIVE_AUTO_THRESHOLD`.
- Whether the overview stayed at about eight steps.
- Reviewer changes you rejected, and why. Those point at prompt edits in `live/review.py`.

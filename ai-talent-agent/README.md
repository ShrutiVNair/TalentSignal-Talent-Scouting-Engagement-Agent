# TalentSignal AI

TalentSignal AI is now a locally runnable recruiting intelligence command center built on top of the original hackathon demo. It keeps the earlier strengths of JD parsing, rule-based matching, risk review, outreach drafting, candidate simulation, Twilio test mode, and shortlist ranking, while adding durable persistence, compliance gating, duplicate detection, pipeline intelligence, analytics, mock enterprise adapters, and a recruiter copilot.

The app now also supports a dynamic resume-to-outreach workflow:

`Resume upload or paste -> contact extraction -> recruiter preview -> candidate save -> duplicate/compliance review -> scoring -> channel selection -> draft -> approval -> test email or safe mock send`

## Demo Flow

This build is optimized for a polished simulated scouting and engagement demo:

1. Add SMTP config or use mock mode.
2. Upload or paste a job description.
3. Add or select a candidate with your demo email address.
4. Run Talent Scan.
5. Simulate outreach conversations with the top candidates.
6. Review ranked candidates with Match Score, Interest Score, and Combined Score.
7. Open the conversation timeline and HR Decision Summary.
8. Create a mock meeting recommendation for high-match, high-interest candidates.

Email test mode remains available as optional demo support. SMS, LinkedIn, calls, WhatsApp, Slack, Teams, and production outreach controls are disabled in the main demo workflow for reliability. Test email always routes to `TEST_EMAIL_RECIPIENT`; the message body includes `This is a TalentSignal demo email. Intended candidate email: <candidate email>`.

## What It Does

- Ingest job descriptions and calibrate role quality before scoring.
- Ingest resumes, extract recruiter-usable contact data, and preview parsed candidate profiles before saving.
- Persist candidates, roles, matches, outreach, feedback, compliance records, and audit logs in SQLite by default.
- Detect duplicates across local records and mock ATS history.
- Produce explainable candidate scorecards with configurable role-level weights.
- Enforce outreach compliance checks before any sequence is triggered.
- Run draft/demo/real-test email outreach workflows; SMS/LinkedIn/calls are hidden in this final demo build.
- Send real test emails through SMTP when configured, while keeping production candidate email disabled unless explicitly enabled.
- Track candidate stages, hiring manager review, interview scheduling, and stale pipeline states.
- Expose native SQL-backed analytics and remain Metabase-ready.
- Provide optional integration scaffolding for ATS, HRIS, Slack, Teams, email, calendar, and BI.

## Architecture

```text
app.py
src/
  config.py
  database/
    db.py
    models.py
    seed.py
  agents/
    compliance_agent.py
    next_best_action.py
    ranking_agent.py
    role_calibration.py
  integrations/
    __init__.py
    ats/
      mock_ats.py
      greenhouse.py
      lever.py
    hris/
      mock_hris.py
    bi/
      metabase.py
    communication/
      email_adapter.py
      slack_adapter.py
      teams_adapter.py
      whatsapp_adapter.py
    calendar/
      calendar_adapter.py
  services/
    analytics_service.py
    audit_service.py
    batch_scoring_service.py
    candidate_service.py
    channel_selection_service.py
    compliance_service.py
    contact_extraction_service.py
    contact_validation_service.py
    copilot_service.py
    deduplication_service.py
    email_outreach_service.py
    feedback_service.py
    outreach_service.py
    resume_ingestion_service.py
    role_service.py
    similar_candidate_service.py
    talent_scan_service.py
  ...
tests/
  test_scoring.py
  test_deduplication.py
  test_compliance.py
  test_next_best_action.py
  test_workflows.py
```

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

SQLite is the default, so no database setup is required for local use unless you want to point `DATABASE_URL` at a different file. The app will create tables and seed the bundled sample candidates on startup.

### 4. Run the app

```bash
streamlit run app.py
```

## Database Setup

- Default database: `sqlite:///talentsignal.db`
- The app creates schema automatically on startup.
- Seed data is loaded from `data/candidates.json`.
- The schema is designed to be SQL-friendly and later portable toward PostgreSQL via `DATABASE_URL`.

Core persisted tables:

- `candidate`
- `role`
- `candidate_role_match`
- `outreach_message`
- `outreach_sequence`
- `feedback`
- `audit_log`
- `compliance_record`
- `integration_config`
- `scheduled_interview`

## Streamlit Workspace

The HR-facing app is now intentionally simplified into four main sections:

1. `Home`
   - guided one-click hiring flow
   - current role summary and role health
   - automation controls
   - talent scan launcher
   - top candidates and action queue
2. `Candidates`
   - resume upload or paste
   - paginated candidate search and filtering
   - candidate detail with score, trust signals, and outreach readiness
   - bulk scoring and draft generation
3. `Outreach`
   - draft queue
   - approval gate
   - safe test email / test SMS
   - manual LinkedIn and call tasks
   - reply capture and sequence history
4. `Settings`
   - integrations
   - compliance rules
   - scoring weights
   - outreach safety
   - architecture and debug info under advanced accordions

This keeps the recruiter workflow simple while still preserving the full local feature set.

## Environment Variables

Defined in `.env.example`:

- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `TWILIO_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE`
- `TEST_PHONE_NUMBER`
- `TEST_LINKEDIN_URL`
- `DATABASE_URL`
- `ATS_PROVIDER`
- `EMAIL_PROVIDER`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `TEST_EMAIL_RECIPIENT`
- `PRODUCTION_OUTREACH_ENABLED`
- `GREENHOUSE_API_KEY`
- `LEVER_API_KEY`
- `METABASE_SITE_URL`
- `METABASE_SECRET_KEY`
- `GOOGLE_CALENDAR_ENABLED`
- `MICROSOFT_CALENDAR_ENABLED`
- `SLACK_WEBHOOK_URL`
- `TEAMS_WEBHOOK_URL`

## Resume Intake And Contact Validation

- Resume intake supports pasted text and uploaded `TXT`, `PDF`, and `DOCX` files.
- Deterministic extraction pulls out name, email, phone, LinkedIn, GitHub, portfolio, location, experience, skills, and contact-confidence signals.
- Recruiters review the parsed preview before the candidate is saved.
- Contact readiness is classified into states such as `Ready for email draft`, `Ready for SMS test only`, `LinkedIn manual task`, `Missing contact info`, and `Blocked by compliance`.
- Phone numbers are masked in the UI and LinkedIn/call actions stay manual.

## Demo Mode, Draft Mode, Test Email, And Production Safety

- `Demo`: safe local workflow, simulated replies, mock sends, and persisted sequence state.
- `Draft Only`: generates messages and sequences without attempting real delivery.
- `Test Send`: real email goes only to `TEST_EMAIL_RECIPIENT`, and real SMS goes only to `TEST_PHONE_NUMBER`.
- `Production Email`: candidate email delivery is blocked unless `PRODUCTION_OUTREACH_ENABLED=true`, the candidate email is valid, compliance passes, consent is eligible, and recruiter approval is checked.

Twilio remains optional. If credentials are missing, the app does not crash and the UI stays usable.
SMTP remains optional. If credentials are missing or `EMAIL_PROVIDER=mock`, the app safely falls back to mock email mode.

## Real Email Setup

TalentSignal AI uses standard SMTP libraries, so a Gmail account with an App Password is enough for local testing.

Example:

```bash
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
TEST_EMAIL_RECIPIENT=your-email@gmail.com
PRODUCTION_OUTREACH_ENABLED=false
```

With that setup:

- the Outreach page can send a real test email
- the email is sent only to `TEST_EMAIL_RECIPIENT`
- the body clearly states which candidate email would have been used
- production candidate email still stays disabled until you explicitly flip `PRODUCTION_OUTREACH_ENABLED=true`

## Integration Architecture

- ATS provider is selected with `ATS_PROVIDER`.
- `mock` is the default and uses local persistence plus duplicate/history simulation.
- `greenhouse` and `lever` are intentionally scaffolded placeholders so the app stays stable without credentials.
- HRIS, calendar, Slack, Teams, WhatsApp, and email all have mock or draft-compatible adapters.
- Missing credentials never block app startup.

## Performance And Large Candidate Pools

TalentSignal AI now avoids the most expensive rerun patterns that made the earlier Streamlit prototype feel slow:

- the app uses 4 page-style sections instead of many heavy tabs
- candidate search uses SQL pagination with `LIMIT` and `OFFSET`
- candidate records store normalized skills, searchable text, and resume hashes
- role records store normalized skill tokens and a role hash
- candidate-role matches store score version, role hash, candidate hash, and scored time
- SQLite indexes are created for common filter and join paths
- `Run Talent Scan` is an explicit batch workflow, not something that runs on every render
- top-match reads are cached and invalidated only when role or candidate data changes
- bulk scoring uses deterministic batch scoring instead of LLM calls

### Run the benchmark

```bash
python3 scripts/benchmark_candidate_scoring.py
```

Optional 100k run:

```bash
python3 scripts/benchmark_candidate_scoring.py --include-100k
```

The benchmark uses a temporary SQLite database, generates synthetic candidates, runs batch scoring, and prints:

- candidate load time
- scoring time
- top matches query time
- processed and scored counts

### Current scaling stance

- `1k` and `10k` candidates are the primary local benchmark targets.
- `100k` is treated as an optional synthetic stress test.
- For larger shared deployments, PostgreSQL is still the recommended next step.
- The current design is intentionally SQL-first so a future move to PostgreSQL or `pgvector` remains straightforward.

## End-To-End Test Recipe

1. Add SMTP credentials in `.env`.
2. Set `TEST_EMAIL_RECIPIENT` to your own inbox.
3. Keep `PRODUCTION_OUTREACH_ENABLED=false`.
4. Start Streamlit with `streamlit run app.py`.
5. Open `Home` and create or analyze a role.
6. Open `Candidates` and paste or upload a resume that contains an email address.
7. Click `Parse Resume`.
8. Review the extracted candidate preview.
9. Click `Save and score`.
10. Open `Outreach`.
11. Generate or review the email draft.
12. Check the recruiter approval checkbox.
13. Click `Send Test Email`.
14. Confirm the message arrives at `TEST_EMAIL_RECIPIENT`.
15. Paste a reply in `Outreach` or use the simulator.
16. Confirm interest score and next-best-action update.

## Metabase Setup

The schema is intentionally SQL-first so Metabase can attach directly to the SQLite or future PostgreSQL database.

### Local connection

1. Start TalentSignal AI so the DB file is created.
2. Point Metabase at `talentsignal.db`.
3. Explore tables such as `candidate_role_match`, `outreach_message`, and `feedback`.

### App behavior

- If `METABASE_SITE_URL` is set, the Analytics tab shows a direct Metabase link.
- If it is not set, the app uses native Streamlit analytics backed by SQL queries.

## Testing

Run the local validation suite with:

```bash
python3 -m unittest discover -s tests -v
```

Covered checks include:

- scorecard range and persistence
- duplicate detection
- compliance blocking
- next best action for blocked candidates
- outreach sequence creation
- pipeline stage persistence
- feedback persistence
- analytics snapshot availability
- resume parsing and contact extraction
- contact readiness and channel selection
- safe email mock/block behavior

## Compliance Notes

- Protected attributes are scrubbed from JD and resume text before relevance scoring.
- Compliance checks gate outreach on opt-out, do-not-contact, cooldown, duplicate risk, and active-process style blockers.
- Test email never goes to the parsed candidate address.
- Test SMS never goes to the parsed candidate phone number.
- LinkedIn and phone calls remain manual recruiter tasks only.
- Audit logs are written for scoring, compliance, outreach, feedback, stage changes, scheduling, and review actions.
- This is still a demo-grade local system and should be reviewed by legal/compliance before production deployment.

## Limitations

- External ATS, HRIS, calendar, Slack, Teams, and BI connectors are scaffolded or mocked unless credentials and live implementations are added.
- Background job orchestration is intentionally not introduced yet; sequence steps are recruiter-triggered.
- Email delivery is draft-oriented and not a live mailbox sync.
- Similarity, copilot intent parsing, and duplicate logic are deterministic and lightweight by design.
- Authentication is still mocked via a sidebar role selector rather than real auth.

## Recommended Next Steps

1. Replace placeholder ATS adapters with authenticated read/write sync.
2. Add migrations and a formal ORM if the project moves to shared environments.
3. Add webhook ingestion for Twilio replies and real email tracking.
4. Introduce background workers for timed outreach sequences.
5. Add auth and user-level permissions beyond the demo selector.
6. Add richer evaluation datasets and regression tests for scoring fairness and calibration.

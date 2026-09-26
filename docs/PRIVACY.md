# Privacy impact assessment (draft)

**Status: draft for review.** Written from the design and the code as they stand. It is not legal
advice. Before staff outside the pilot are invited, YSH's privacy contact should review it, the
open questions in section 8 should be answered (with legal advice where marked), and section 9
should be signed.

## 1. What Groundwork is and why it holds personal information

Groundwork collects evidence of how YSH works today: files staff work from, maps of their work,
recordings and transcripts of mapping sessions, and AI drafts built from these. Its purpose is to
understand and document work, not to make decisions about tenants, borrowers or staff.

Personal information enters in three ways:

| Whose | How it arrives | Examples |
|---|---|---|
| Staff | Sign-in, profile, uploads, recordings, audit log | Name, work email, team, voice, what they said, IP address |
| Tenants, borrowers, owners, contractors | Inside files staff share, and in what is said in sessions | Names, addresses, rent and repayment history, bank details, identity documents |
| Third parties named in conversation | Recordings, transcripts, maps | Names and roles |

The design assumes staff will share files holding tenant and borrower records whatever the form
says. The controls below are built for that.

## 2. Information flows

```
Staff browser --HTTPS--> Caddy --> app (FastAPI) --> SQLite on the YSH host (/data)
                                     |                         |
                                     |                         +--> files: /data, or self-hosted Supabase Storage (S3)
                                     |                         +--> nightly backup archive: the database, and files kept
                                     |                              in /data (encrypted with age when set; only encrypted
                                     |                              copies go off host)
                                     +--> worker: ClamAV scan, first read, transcription (local or inference box)
                                     +--> ingestion, all on-prem: MinerU, Gotenberg, Parakeet, embedding and
                                          extraction sidecars, Qdrant, Neo4j
                                     +--> OpenRouter (Jev): each live-mapping sentence and nearby map labels;
                                          for extraction, a chunk of a file not marked personal and names found in it
                                     +--> OpenAI (or Anthropic, if set): maps, transcripts, parking lot notes and file
                                          text (up to 4,000 characters a file) for drafts and reviews; maps alone
                                          when combining views
                                     +--> Gmail (SMTP with OAuth 2.0): each sign-in email, holding the staff
                                          member's address and a single-use link
Browser speech recognition (Chrome: Google, Edge: Microsoft): session audio during live mapping
```

Hosted services receive content only when a feature that uses them runs. Every hosted model refuses
content marked as holding personal information, or where it is unsure, unless
`GW_AI_ALLOW_CLOUD_FOR_PERSONAL_INFO=true`. Each feature checks the marks on what it sends: live
mapping checks only the map's own tick, not its files (section 5 has the detail).

The portal's own pages load nothing from other sites. Fonts are self-hosted, and the content
security policy the app sends (`backend/app/main.py`) allows scripts, styles, fonts, images and
connections only from Groundwork's own address. The API explorer at `/api/docs` is the exception:
it loads its scripts from a public CDN and is sent without that policy. Browser speech recognition
is part of the browser, so the policy doesn't stop it.

Logs name files, recordings and jobs by id; they don't quote file contents, transcripts or prompts.
Three things do reach them: an email address when a sign-in email can't be sent; the sign-in link
itself when no mail server is set and `GW_DEV_LOG_MAGIC_LINKS` is true (the default in
`config.py`; `.env.example` sets it false); and, for a failed job, the error, which for a model
call can include up to 300 characters of the model's reply. The web server's access log also
records each address opened, including the token in a sign-in link. That token works once and
expires after 15 minutes.

## 3. Assessment against the Australian Privacy Principles

| APP | What it asks | How Groundwork meets it | Gap or action |
|---|---|---|---|
| 1 Open and transparent management | A clearly expressed, up-to-date privacy policy | This document; the sign-in page explains the purpose | Add a short collection notice to the portal and link YSH's privacy policy (action A1) |
| 2 Anonymity and pseudonymity | Let people deal anonymously where practicable | Not practicable for staff: contributions are attributed so analysts can ask follow-up questions | Record the reason in the policy |
| 3 Collection of solicited information | Collect only what is reasonably necessary | The form asks what a file shows and whether it holds personal information; it never asks for customer details | Tell staff to share blank templates or redacted copies where the customer details are not the point (A2) |
| 4 Unsolicited information | Destroy or de-identify what you could not have collected | Admins can delete a file straight away ("Delete now") with a recorded reason | Agree who reviews files marked "yes" or "unsure" and how often (A3) |
| 5 Notification of collection | Tell people what is collected and why | Recording needs a consent note naming who agreed; it is written to the audit log | Collection notice for staff (A1); script for telling session participants (A4) |
| 6 Use and disclosure | Use for the purpose collected, or a related one reasonably expected | Used only to document and improve processes. AI output is always a draft a person accepts or discards | Disclosure to OpenRouter, OpenAI and the browser's speech service is covered in APP 8 |
| 7 Direct marketing | Don't use for marketing | Not used for marketing | None |
| 8 Cross-border disclosure | Take reasonable steps so overseas recipients don't breach the APPs | Hosted models are refused for anything marked as holding personal information, or unsure. Live mapping audio is sent to the browser vendor. Sign-in emails pass through Gmail | Confirm the data handling terms of OpenRouter, TypeSafe and OpenAI (retention, training use, location) (A5). Tell facilitators not to use live speech on sensitive sessions; the Live tab switches speech off on maps marked personal |
| 9 Government identifiers | Don't adopt them | Not adopted. They may appear inside shared files | Covered by A2 and A3 |
| 10 Quality | Keep information accurate and complete | Maps and drafts carry `[TO CONFIRM]` markers; drafts cite their evidence | None |
| 11 Security | Protect from misuse, loss and unauthorised access; destroy when no longer needed | Email sign-in with single-use links, HttpOnly session cookies, server-side role checks, a CSRF guard, HTTPS with a strict content security policy (scripts, styles and fonts only from Groundwork itself), ClamAV scanning, audit log of every change, files stored on YSH's host or its self-hosted object storage, retention and purge, backups encrypted with age before they leave the host | Turn on backup encryption and the off-host copy; restrict host access to named administrators (A6) |
| 12 Access | Give people access to their information | Staff see their own uploads; analysts can find anything by person. Names found in files are kept in the knowledge graph (flagged personal) and in the search index | Agree how a customer's access request would be searched and answered: files, transcripts, the search index and the graph (A7) |
| 13 Correction | Correct information on request | Contributors can withdraw files; admins can delete them; maps and documents are editable | None |

## 4. Retention schedule (proposed)

| Information | Kept for | Then | Setting |
|---|---|---|---|
| Files a contributor withdraws | 30 days after withdrawal | Deleted from storage with everything built from it (see the conversions row); the file's database entry (title, description, file name), marked deleted, and the audit record that it was shared stay | `GW_RETENTION_WITHDRAWN_DAYS=30` |
| Session audio | 90 days after the recording ends | Deleted; the transcript stays with the map as its evidence | `GW_RETENTION_AUDIO_DAYS=90` |
| Files in use, maps, transcripts, live-mapping sentences, drafts | Until the discovery work ends | Review at the end of the project: archive what the next system needs, delete the rest | Manual |
| Backups | 30 days on the host | Oldest archives removed by the backup job. Copies at `GW_BACKUP_COPY_TO` are never removed by Groundwork | `GW_BACKUP_KEEP_DAYS=30` |
| Audit log | Life of the system | Kept with the database. Holds who did what and when, from which IP address, with file names, consent notes and every email address that asked for a sign-in link, including refused ones | None |
| Sign-in links and sessions | 15 minutes and 14 days | Expire; stored only as hashes. The worker deletes expired sessions hourly, and expired links a day after they expire | `GW_MAGIC_LINK_MINUTES`, `GW_SESSION_DAYS` |
| Conversions, chunks, embeddings, entities and relationships from a file | As long as the file | Withdrawal removes the file from search and the graph at once; the purge removes the rest everywhere | Follows the file |
| Ontology proposals | Until decided and exported | Evidence from a purged file is removed; a proposal left with none is deleted | None |

With `GW_RETENTION_AUTO=true` the worker applies the first two rows daily. The setting defaults to
false in `config.py` (`.env.example` sets it true); while it is false, nothing is deleted until an
admin runs it from the Retention page. A period of 0 keeps those files for good. An admin can also
delete one file straight away from the Library with a recorded reason. The server accepts the same
for one recording's audio, but no screen offers it yet.

Deleted files survive in backups until those backups age out on the host. Copies already sent to
`GW_BACKUP_COPY_TO` stay until someone removes them there. With `GW_STORAGE_BACKEND=s3` the
nightly backup holds the database only; files are in whatever backup is kept of the Supabase
storage volume (`deploy/supabase/README.md`), on that backup's own schedule.

## 5. Personal-information flag

Each file carries yes, no or unsure; each map carries a yes or no tick. "Unsure" counts as yes
everywhere. What each hosted model (OpenAI, Anthropic, OpenRouter or TypeSafe) checks:

- Drafts and reviews send file text, so they refuse any map whose own tick or linked files say yes
  or unsure.
- Live mapping and combining views send what was said and the maps, not file contents. They refuse
  a map whose own tick says yes (when combining, any of the maps). A map that is unticked but has
  files marked yes or unsure still runs.
- The ingestion pipeline is on-prem; its one hosted step, class and relationship choices by Jev,
  skips files marked yes or unsure, and transcripts of maps that count as personal by the drafts
  rule. Their entities are kept and the relationships wait.

Only a model Groundwork treats as local can work on these: Ollama, an OpenAI-compatible server with
`GW_OPENAI_IS_LOCAL=true`, a Jev-compatible server such as Laya with `GW_DECISION_PROVIDER=jev` and
`GW_DECISION_IS_LOCAL=true`, or for extraction `GW_EXTRACT_DECISION_URL` with
`GW_EXTRACT_DECISION_IS_LOCAL=true`. Groundwork trusts these settings; it doesn't check where the
address points. `GW_AI_ALLOW_CLOUD_FOR_PERSONAL_INFO=true` lifts every one of these refusals. That
setting should stay false.

Transcription, conversion (MinerU, Gotenberg), the embedding and extraction sidecars, Qdrant and
Neo4j have no personal-information check: they receive the files, audio, chunks and names they work
on whatever the flag says, so their addresses must point at YSH's own hardware.

Browser speech recognition is switched off on maps ticked yes, whatever the decision model or
`GW_AI_ALLOW_CLOUD_FOR_PERSONAL_INFO` says. The Live tab does this in the browser, so the server
can't enforce it, and it stays on for an unticked map whose files are marked yes or unsure.

## 6. Recording consent procedure

1. Before recording, the facilitator tells everyone present: what is recorded, why, who can hear
   it, that it is transcribed, and how long the audio is kept (90 days).
2. Everyone agrees out loud. The facilitator types who agreed; recording can't start without it.
3. Anyone can ask to stop at any time. Stopping is one click.
4. Avoid naming customers. If one is named, mark the map as holding personal information.

## 7. Risks

| Risk | Likelihood | Impact | Controls | Residual |
|---|---|---|---|---|
| Customer records shared without need | High | Medium | Form question, redaction guidance, delete-now, retention | Medium: depends on A2 and A3 |
| Personal information sent to a hosted model | Low | High | Personal-information guard on every AI route, "unsure" treated as yes | Low |
| Live speech audio sent to Google or Microsoft | Medium | Medium | Speech is switched off on personal-information maps; facilitators can type instead | Low to medium |
| Unauthorised access to the portal | Low | High | Allowed email domains, single-use links, server-side roles, HTTPS, CSP | Low |
| Malicious file shared and downloaded by a colleague | Low | Medium | ClamAV before first read, quarantine, downloads as attachments | Low |
| Loss of the host | Low | High | Nightly consistent backup, copied off host. The backup job checks an encrypted archive only if `GW_BACKUP_AGE_IDENTITY_FILE` is set; files in S3 storage need their own backup | Low once A6 is done |
| Names and roles of tenants and borrowers in the knowledge graph | High | Medium | Kept only on-prem, flagged personal, analysts only; removed with the file; hosted extraction blocked for personal files | Medium: review with the privacy contact |
| Extraction models getting a relationship wrong | Medium | Low | Every graph relationship is a draft citing its chunks; nothing acts on the graph | Low |

## 8. Open questions

1. **Legal advice.** Does recording staff in mapping sessions need consent beyond section 6 under
   the South Australian Surveillance Devices Act 2016?
2. **Legal advice.** Does the lending side bring obligations beyond the APPs, for example credit
   reporting rules or record keeping under consumer credit law, that affect sharing loan files?
3. Which files should never be shared (identity documents, bank statements)? Should the form
   say so?
4. Who reviews files marked "yes" or "unsure", and how often?
5. Where do off-host backups go, who holds the key, and are they encrypted at rest?
6. What happens to Groundwork's data when the discovery work ends?

## 9. Sign-off

| Role | Name | Decision | Date |
|---|---|---|---|
| Privacy contact | | | |
| Business owner | | | |
| AI lead | | | |

## Actions

| Id | Action | Owner | Status |
|---|---|---|---|
| A1 | Collection notice in the portal, linked to YSH's privacy policy | | Open |
| A2 | Guidance to share blank or redacted copies where customer details aren't the point | | Open |
| A3 | Regular review of files marked yes or unsure | | Open |
| A4 | Script for telling session participants about recording | | Done: section 6 |
| A5 | Confirm OpenRouter, TypeSafe and OpenAI data terms | | Open |
| A6 | Encrypted off-host backups and named host administrators | | Open: set `GW_BACKUP_AGE_RECIPIENTS` and `GW_BACKUP_COPY_TO` (README, Backups); name the administrators |
| A7 | Procedure for customer access requests | | Open |

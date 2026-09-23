# Live mapping

Staff describe their work; the map builds itself as they talk. Two models share the job, and the
session follows the two-pass method from Freund and Rücker's *Real-Life BPMN* (3rd edition).

| | Fast lane | Slow lane |
|---|---|---|
| Model | A System One decision model: TypeSafe Jev (v1), or a Jev-compatible server you run (Laya, OpenJev) | A reasoning LLM: Anthropic, an OpenAI-compatible endpoint, or Ollama |
| When | Every finished sentence | Every 5 minutes while listening, or on "Review now" |
| Sees | The sentence, the three before it, and up to 19 nearby map elements | The whole transcript, the map, the rule tables, the parking lot, the current SOP or work instruction, and linked files |
| Does | Picks one change from fixed options, or parks the sentence | Proposes map corrections, rule tables and a revised document |
| Speed | Tens to hundreds of milliseconds | Tens of seconds |

## Two passes

**Overview pass.** Start to end, standard path only, usual responsibilities, about eight steps.
Jev may only add starts, steps, sub-processes, decisions and ends. Anything about problems,
exceptions, workarounds, rules or improvement ideas goes to the **parking lot** instead of the map.
This keeps the first session from drowning in special cases and gives the group an early,
complete picture. Map checks warn when the overview passes ten flow elements or eight notes.

**Detail pass.** Everything goes on the map. The parking lot becomes the agenda: put each item on
the map or mark it covered. The Live tab lists prompts for this pass, starting with rework: where
work is sent back, and how many of every ten cases go through first time.

For the detail pass, map **one person's view at a time** (create the map as "One person's view").
Each map shows what that person does and what they wait for from others, so its owner can check
it. When a process has two or more of these, **Combine** on the Maps page builds a single map
with a lane per person and joins their hand-offs. Where views disagree, the combiner keeps both
and adds a question.

## How a sentence becomes a change

1. The browser turns speech into sentences (Web Speech API in v1) or the facilitator types one.
2. `live/spans.py` offers two sets of phrases, word for word: longer ones for labels, and short
   ones (one to three words) for names of people and organisations.
3. `live/interpret.py` sends one request with eighteen questions: instruction or description; what
   kind of change; step or context; which kind of step (overview kinds only, in the overview pass);
   which kind of context; which existing element it relates to; who is involved (a lane, a new
   lane, an existing or new outside party); the label; the name; and yes/no checks for compound
   sentences, workarounds, issues, exceptions, rules, things arriving from outside, and causes.
4. Code decides. Rules are always parked for the rule tables. In the overview pass, issues,
   workarounds, exceptions and non-overview kinds are parked. Changes at or above
   `GW_LIVE_AUTO_THRESHOLD` (0.75) land at once; below it they wait as dashed proposals. Removals
   always wait for a person.
5. `canvas/ops.ts` places the element: steps to the right of the step they follow, context above
   or below the step it describes, causes beside the issue they explain, new lanes below existing
   ones, outside parties as bands across the top.

"Only my instructions" mode ignores everything except commands to the map.

## What goes on the map

Flow: start, step, manual step, system step, rule step, sub-process, decision, in parallel, wait,
end, unclear area.

Context: outside party (a collapsed pool, joined by message flows), person, application, document,
workaround, issue, risk, check or approval, number, open question, note.

People and teams inside the business who do steps are **lanes**. Outside parties (tenant,
borrower, owner, bank, contractor, council) are **pools**, never lanes. "Person" is for someone
mentioned who does no step here.

**Unclear areas** mark work nobody can yet describe as ordered steps. An honest boundary beats an
invented sequence.

**Causes.** When a sentence explains why an issue happens, the new issue attaches to that issue
with a "causes" link, so chains of causes build up beside the step.

The list lives in `backend/app/live/vocabulary.py` and `frontend/src/canvas/kinds.ts`. Change
both together. Step kinds and context kinds are asked as separate questions so no question has
more than 20 options.

## Business rules

When staff list conditions ("more than a week late, unless they're on a payment plan, and Dean
approves"), the map gets one **rule step** and the conditions go into a **rule table** (Rules
tab): named conditions, an outcome, one row per rule, each row with the words it came from and a
"confirmed" tick. The reviewer drafts tables from the transcript and parked rules; you use them,
edit them, or keep your own. Thresholds stay as text until someone confirms them. A map check
asks about any rule step without a table.

## Map checks

The server checks the map continuously (`ai/context.py::structure_checks`) and the same findings go
to the reviewer:

- no start or end event; elements not connected;
- decisions not phrased as a question, or paths out of a decision without an answer;
- parallel splits without a matching join;
- work that loops back (asks how often);
- overview size limits;
- context not linked to a step; outside parties with nothing passing to or from them;
- rule steps without a rule table; unclear areas (asks who could explain them).

## Layers

The **Layers** menu hides groups of elements without changing the saved map: people and outside
parties, systems and documents, issues and workarounds, checks and numbers, questions and notes,
and suggestions waiting for a decision. The standard path always shows.

## The session reviewer

Every five minutes (`GW_REVIEW_MINUTES`) the reviewer reads the full session and returns map
changes (each with a reason and a quote), complete rule tables, the parking lot items it has
covered, a revised SOP or work instruction with `[TO CONFIRM: ...]` where the session left gaps,
and open questions. Its prompt carries the book's conventions: verb plus object for steps, object
plus past tense for events, questions on decisions with answers on every path, no inclusive or
complex gateways, pools for outside parties, rules in tables, loops kept with how often they
happen. `live/review.py` checks every change against the real map before anything reaches the
canvas. Nothing the reviewer proposes applies without a click; "Accept all" does it in one.

## Privacy

Hosted Jev and browser speech recognition both send session content off the premises. When a
map is marked as holding personal information, live mapping refuses a hosted decision model
unless `GW_DECISION_IS_LOCAL=true` (a server you run) or `GW_AI_ALLOW_CLOUD_FOR_PERSONAL_INFO=true`.
The reviewer and the combiner follow the same rule. In Chrome, speech audio goes to Google; in
Edge, to Microsoft. For sensitive sessions, type key sentences or swap in local streaming speech
recognition (roadmap).

## Moving off the hosted API

Laya and OpenJev accept the same request and return the same answers as Jev. Point
`GW_DECISION_URL` at your server and set `GW_DECISION_MODEL` to a name it accepts. OpenJev caps a
Choice at 128 options and rejects pinned Jev version names; Laya's accuracy falls as options grow.
Groundwork keeps every Choice at or under `GW_DECISION_MAX_OPTIONS` (20). Both are new community
projects; measure them with `scripts/live_eval.py` on your own sentences first.

## Measuring it

`backend/scripts/live_eval.py` runs labelled sentences through the interpreter and reports how
often it chose the right change and element kind, plus latency. Each line can set `"pass"`.
`scripts/eval/sample.jsonl` has fifteen examples; replace them with sentences from a recorded
mock session.

## Known limits

- Browser speech recognition only works in Chrome and Edge, and restarts itself after silence.
- One change per sentence. The reviewer picks up what a compound sentence left behind.
- Label phrases are the speaker's words until the reviewer tidies them.
- The reviewer runs on the facilitator's browser timer; close the tab and reviews stop.
- Message flows meet an outside party's band at the point above their step; with many flows the
  band gets busy. Hide the layer when it does.

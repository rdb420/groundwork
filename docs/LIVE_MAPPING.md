# Live mapping

Staff describe their work; the map builds itself as they talk. Two models share the job, and the
session follows the two-pass method from Freund and Rücker's *Real-Life BPMN* (3rd edition).

| | Fast lane | Slow lane |
|---|---|---|
| Model | A System One decision model: TypeSafe Jev through OpenRouter (default), TypeSafe directly, or a Jev-compatible server you run (Laya, OpenJev) | A reasoning LLM: OpenAI (default), another OpenAI-compatible endpoint, Anthropic, or Ollama |
| When | Every finished sentence | Every 5 minutes while listening, or on "Review now" |
| Sees | The sentence, the three before it (from the last ten minutes), the lanes and outside parties, and up to 19 map elements, the last one touched first and then the newest | The whole transcript, the map, the rule tables, the parking lot, the current SOP or work instruction, and linked files |
| Does | Picks one change from fixed options, or parks the sentence | Proposes map corrections, rule tables and a revised document |
| Speed | Tens to hundreds of milliseconds | Tens of seconds |

## Two passes

**Overview pass.** Start to end, standard path only, usual responsibilities, about eight steps.
Jev may only add starts, steps, sub-processes, decisions and ends. Anything about problems,
exceptions, workarounds, rules or improvement ideas goes to the **parking lot** instead of the map.
This keeps the first session from drowning in special cases and gives the group an early,
complete picture. Map checks warn when the overview passes ten flow elements, about eight steps,
or eight notes, documents and outside parties.

**Detail pass.** Everything goes on the map. The parking lot becomes the agenda: put each item on
the map or mark it covered. The Live tab lists prompts for this pass, starting with rework: where
work is sent back, and how many of every ten cases go through first time.

For the detail pass, map **one person's view at a time** (create the map as "One person's view,
in detail"). Each map shows what that person does and what they wait for from others, so its
owner can check it. When a process has two or more of these, **Combine** (under "Combine views"
on the Process maps page) builds a single map with a lane per person and joins their hand-offs.
Where views disagree, the combiner keeps both and adds a question. The combined map carries over
every view's rule tables and is marked as holding personal information if any view was. It opens
with every element as a suggestion: keep or drop them one by one, or use Keep all or Discard all.

## How a sentence becomes a change

1. The browser turns speech into sentences (Web Speech API in v1) or the facilitator types one.
2. `live/spans.py` offers two sets of phrases, word for word: longer ones for labels, and short
   ones (one to three words) for names of people and organisations.
3. `live/interpret.py` sends one request with eighteen questions: instruction or description; what
   kind of change; step or context; which kind of step (overview kinds only, in the overview pass);
   which kind of context; which existing element it relates to; the second element, when it links
   two; what changes about an existing element; who is involved (a lane, a new lane, an existing
   or new outside party); the label; the name; and yes/no checks for compound sentences,
   workarounds, issues, exceptions, rules, things arriving from outside, and causes.
4. Code decides. Rules are always parked for the rule tables. In the overview pass, issues,
   workarounds, exceptions and non-overview kinds are parked. Changes at or above
   `GW_LIVE_AUTO_THRESHOLD` (0.75) land at once; below it they wait as dashed proposals. A direct
   instruction to the map needs a little less (85% of the threshold). Removals always wait for a
   person.
5. `canvas/ops.ts` places the element: steps to the right of the step they follow, context above
   or below the step it describes, causes beside the issue they explain, new lanes below existing
   ones, outside parties as bands across the top.

"Only my instructions" mode ignores everything except commands to the map, though rules it hears
still go to the parking lot.

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
more than 20 options. Jev is asked about unclear areas with the context kinds; the canvas and the
map checks treat them as flow. A kind that needs a new node type also goes in
`canvas/nodes.tsx`, `canvas/palette.ts` and `TYPE_NAMES` in `ai/context.py`. Nodes are drawn with
the design system's `gw-` canvas classes (`docs/DESIGN_SYSTEM.md`).

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
- decisions not phrased as a question, paths out of a decision without an answer, or a decision
  with fewer than two paths out;
- parallel splits without a matching join;
- work that loops back (asks how often, and how many of every ten go through first time);
- overview size limits;
- context not linked to a step; outside parties with nothing passing to or from them;
- rule steps without a rule table; unclear areas (asks who could explain them).

The Live tab lists them under "Map checks", fixes first; each one can select the elements it is
about.

## Layers

The **Layers** menu hides groups of elements without changing the saved map: people and outside
parties, systems and documents, issues, risks and workarounds, checks and numbers, questions and
notes, and suggestions waiting for a decision. The standard path always shows.

## The session reviewer

Every five minutes (`GW_REVIEW_MINUTES`) while listening, if anything new was said, or when you
press "Review now", the reviewer reads the full session and returns map changes (each with a
reason and a quote), complete rule tables, the parking lot items it has covered, a revised SOP
or work instruction with `[TO CONFIRM: ...]` where the session left gaps, and open questions. Its
prompt carries the book's conventions: verb plus object for steps, object
plus past tense for events, questions on decisions with answers on every path, no inclusive or
complex gateways, pools for outside parties, rules in tables, loops kept with how often they
happen. `live/review.py` checks every change against the real map before anything reaches the
canvas. Nothing the reviewer proposes applies without a click; "Accept all ... map changes" does
it in one and marks the parking lot items the review covered. Rule tables wait in the Rules tab
(Use them, Edit them first, or Keep mine) and the document in the Document tab (Use the revision,
Edit it first, or Keep mine). Rule tables and the document save with the version you started
from, so nobody overwrites a colleague's edit.

## Privacy

Jev on OpenRouter and browser speech recognition both send session content off the premises.
When a map is marked as holding personal information, live mapping refuses a hosted decision
model unless it is a Jev-compatible server you run (`GW_DECISION_PROVIDER=jev` with
`GW_DECISION_IS_LOCAL=true`) or `GW_AI_ALLOW_CLOUD_FOR_PERSONAL_INFO=true`. OpenRouter always
counts as hosted.
The reviewer and the combiner follow the same rule for their own model, which counts as local
when `GW_AI_PROVIDER=ollama`, or `openai` with `GW_OPENAI_IS_LOCAL=true`. The reviewer also
refuses a hosted model when a file linked to the map's process holds personal information or
nobody was sure. In Chrome, speech audio goes to Google; in Edge, to Microsoft, whichever
decision model you use. So on a map marked as holding personal information, listening is switched
off and the facilitator types key sentences instead. The reviewer's timer only runs while
listening, so on these maps press "Review now". The Recording tab still keeps a local recording.
Local streaming speech recognition is on the roadmap.

## Providers

Both lanes are off until you choose a provider: `GW_DECISION_PROVIDER` and `GW_AI_PROVIDER` default
to `none`, and `.env.example` sets them to `openrouter` and `openai`.

`GW_DECISION_PROVIDER=openrouter` sends each request to OpenRouter's System One API
(`https://openrouter.ai/api/v1/systemone`) with `GW_OPENROUTER_API_KEY`. OpenRouter routes
`jev-latest` to `~typesafe/jev-latest`; pin a version such as `jev-1.13` in `GW_DECISION_MODEL`
when you want answers to stay stable between sessions. Requests are billed per input token to the
OpenRouter account.

`GW_DECISION_PROVIDER=jev` sends the same request to `GW_DECISION_URL` (TypeSafe's own endpoint
unless you change it) with `GW_DECISION_API_KEY`. Either way, a request gives up after
`GW_DECISION_TIMEOUT_S` (15 seconds; a local model on CPU needs longer) and is retried twice when
the provider answers that it is busy.

### Laya, the local decision model

[Laya](https://github.com/NandhaKishorM/laya) ([weights](https://huggingface.co/convaiinnovations/laya),
Apache 2.0) is an open System One model with Jev's API. It runs on the inference box
(`laya` in `deploy/inference-compose.yml`) in tens of milliseconds per request on a GPU, so nothing
leaves the building and maps and files with personal information can use it.

```
GW_DECISION_PROVIDER=jev
GW_DECISION_URL=http://<box>:8011/v1/systemone
GW_DECISION_API_KEY=<LAYA_API_KEY>
GW_DECISION_MODEL=english            # or typed-decisions
GW_DECISION_FLAVOUR=laya
GW_DECISION_IS_LOCAL=true
GW_DECISION_MAX_OPTIONS=12
```

For extraction only (keeping hosted Jev for live mapping), set the URL, key, model, flavour and
local values on the matching `GW_EXTRACT_DECISION_*` settings instead
(`deploy/inference-compose.yml` lists them). There is no extraction provider or option cap:
extraction sizes its questions from the flavour.

Differences Groundwork allows for when the flavour is `laya`:

- Laya fits the question and every option into a 192-token budget, so relation questions split
  into groups of at most 8, labelled by what they hold, and options are short ("A is Tenant / lessee
  in B"). Its confidence is uncalibrated above 10 options, which this also avoids.
- Its English checkpoint leans towards "no" on yes/no questions labelled true/false, so those go
  out with neutral labels, as its README advises.
- Its `confidence` for a choice is an entropy measure; Groundwork reads its calibrated
  `answer_confidence` instead, so `GW_LIVE_AUTO_THRESHOLD` and the extraction thresholds mean the
  same as with Jev.
- The base checkpoints are general. Laya's own results show specialist decisions improve most with
  fine-tuning, so measure it on YSH's sentences before relying on it (below).

**Measured (24 September 2026, Laya 0.3.12 on CPU, the sample files in `scripts/eval/`):**

| | Jev (OpenRouter) | Laya `english` | Laya `typed-decisions` |
|---|---|---|---|
| Relationships between labelled entities, 17 (`extract_eval --gold-mentions`) | 15 | 13 | 14 |
| Live mapping: kind of change, 15 sentences (`live_eval`) | 15 | 1 | 4 |
| Live mapping: element kind, 13 | 10 | 1 | 3 |

So for now: **use Laya for extraction** (`GW_EXTRACT_DECISION_*`), which keeps files with personal
information on-prem at close to Jev's accuracy, and **keep Jev for live mapping**. Out of the box,
Laya answers "nothing" to most live sentences, and shorter wording didn't change that (2 to 5 of
15 across six variants). Live mapping becomes a Laya candidate once it is fine-tuned: every live
sentence is already logged in `live_utterances` with a summary of Jev's decisions (kind of change,
element kind, which element) and the changes that followed, which is the start of the training
set (Laya's `notebooks/` and the stuntd project show how). Re-run both evaluations after any change.

OpenJev also accepts the same request; it caps a Choice at 128 options and rejects pinned Jev
version names. Groundwork keeps every Choice at or under `GW_DECISION_MAX_OPTIONS`.

## Measuring it

`backend/scripts/live_eval.py` runs labelled sentences through the interpreter and reports how
often it chose the right change and element kind, plus latency. Each line can set `"pass"`.
`scripts/eval/sample.jsonl` has fifteen examples; replace them with sentences from a recorded
mock session.

## Known limits

- Browser speech recognition only works in Chrome and Edge, and restarts itself after silence.
- One change per sentence. The reviewer picks up what a compound sentence left behind.
- Label phrases are the speaker's words until the reviewer tidies them.
- The reviewer runs on the facilitator's browser timer, and only while listening; close the tab
  and reviews stop.
- Message flows meet an outside party's band at the point above their step; with many flows the
  band gets busy. Hide the layer when it does.

// Live mapping. Speech becomes sentences; each finished sentence goes to the decision model, which
// proposes one change to the map. Confident changes land straight away; the rest wait for a click.
// Every few minutes a reasoning model reviews the whole session and proposes corrections to the map,
// the rule tables and the written procedure.
//
// Two passes (Real-Life BPMN, ch. 3 and 4): the overview pass records the standard path only and
// parks everything else; the detail pass works through the parking lot.
import { useEffect, useRef, useState } from "react";
import type { Edge, Node } from "@xyflow/react";
import { api, type Draft, type Me } from "../lib/api";
import { KIND_LABEL, kindOf, type Kind } from "./kinds";
import { acceptOp, applyOp, isOpen, rejectOp, type Op } from "./ops";
import type { RuleTable } from "./RulesPanel";
import { Button, Check, CheckItem, Heard, Input, OpLine, PARKING_LABEL, ParkingItem, Passbar, Recording, ReviewCard, ReviewOp, Segmented } from "../ui";

type Graph = { nodes: Node[]; edges: Edge[] };
type Line = { id: string; text: string; ops: Op[]; parked?: string[]; ms?: number; error?: string };
export type Parking = { id: string; category: string; text: string; near_element: string; status: string };
export type Check = { level: "fix" | "ask" | "info"; text: string; ids: string[] };
type Props = {
  boardId: string;
  me: Me;
  personalInfo: boolean;
  docKind: "sop" | "wi";
  sessionPass: "overview" | "detail";
  setSessionPass: (p: "overview" | "detail") => void;
  perspective: string;
  checks: Check[];
  getGraph: () => Graph;
  setGraph: (g: Graph) => void;
  lastTouched: React.MutableRefObject<string | null>;
  onDocumentProposed: (d: Draft) => void;
  onRulesProposed: (r: RuleTable[]) => void;
  reveal: (ids: string[]) => void;
  focus: (ids: string[]) => void;
};

const SpeechRecognition: any = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

// What a parked item becomes when it goes on the map.
const PARKED_KIND: Record<string, Kind> = { issue: "issue", workaround: "workaround", exception: "note", rule: "control", question: "question", detail: "note" };

const DETAIL_PROMPTS = [
  "Where does work get sent back or redone? Of every ten, how many go through first time?",
  "What happens when something is missing, late or wrong?",
  "Who outside the business is involved, and what passes between you?",
  "Which systems, spreadsheets or paper do you use at each step?",
  "Are there rules, thresholds or approvals that decide what happens?",
  "What is slow, frustrating or risky?",
];

function describe(op: Op, g: Graph): string {
  const name = (id?: string | null) => String(g.nodes.find((n) => n.id === id)?.data?.label || "an element");
  switch (op.op) {
    case "add":
      if (op.kind === "external_party") return `Link outside party "${op.label}"${op.after ? ` to "${name(op.after)}"` : ""}`;
      return `Add ${KIND_LABEL[op.kind!]?.toLowerCase() ?? "element"}${op.label ? ` "${op.label}"` : ""}${op.relation === "cause" ? ` as a cause of "${name(op.after)}"` : ""}${op.new_lane ? ` in new lane "${op.new_lane}"` : ""}${op.party ? ` (by ${op.party})` : ""}`;
    case "update": return `Change "${name(op.target)}"${op.changes?.label ? ` to "${op.changes.label}"` : ""}${op.changes?.kind ? ` into a ${KIND_LABEL[op.changes.kind].toLowerCase()}` : ""}${op.changes?.new_lane ? ` (lane "${op.changes.new_lane}")` : ""}`;
    case "connect": return `Link "${name(op.from)}" to "${name(op.to)}"${op.flow === "message" ? " (message)" : ""}`;
    case "remove": return `Remove "${name(op.target)}"`;
  }
}

export default function LivePanel(props: Props) {
  const { boardId, me, personalInfo, docKind, sessionPass, setSessionPass, perspective, checks, getGraph, setGraph, lastTouched, onDocumentProposed, onRulesProposed, reveal, focus } = props;
  const [mode, setMode] = useState<"listen" | "command">("listen");
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [typed, setTyped] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [parking, setParking] = useState<Parking[]>([]);
  const [newPark, setNewPark] = useState("");
  const [error, setError] = useState("");
  const [reviewOn, setReviewOn] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [reviews, setReviews] = useState<Draft[]>([]);
  const [, force] = useState(0);
  const rec = useRef<any>(null);
  const wantListening = useRef(false);
  const queue = useRef<Promise<void>>(Promise.resolve());
  const sinceReview = useRef(0);

  const blocked = personalInfo && !me.live_local;
  // Browser speech recognition sends audio to Google (Chrome) or Microsoft (Edge), wherever the
  // decision model runs, so maps with personal information are typed only.
  const speechOff = personalInfo;

  useEffect(() => {
    api.get<any[]>(`/api/boards/${boardId}/live/utterances`).then((rows) =>
      setLines(rows.map((r) => ({ id: r.id, text: r.text, ops: r.ops, ms: r.latency_ms }))));
    api.get<Draft[]>(`/api/boards/${boardId}/drafts`).then((ds) => setReviews(ds.filter((d) => d.mode === "review")));
    api.get<Parking[]>(`/api/boards/${boardId}/parking`).then(setParking);
  }, [boardId]);

  // One sentence at a time, so each decision sees the map as the previous one left it.
  const send = (text: string, source: "speech" | "typed") => {
    const clean = text.trim();
    if (!clean) return;
    const key = `tmp-${Date.now()}`;
    setLines((ls) => [...ls, { id: key, text: clean, ops: [] }]);
    queue.current = queue.current.then(async () => {
      try {
        const g = getGraph();
        const doc = { nodes: g.nodes.map(({ selected: _s, dragging: _d, ...n }) => n), edges: g.edges };
        const r = await api.send<{ utterance_id: string; ops: Op[]; parking: Parking[]; latency_ms: number }>("POST", `/api/boards/${boardId}/live/utterance`,
          { text: clean, source, mode, doc, last_touched: lastTouched.current });
        let next = getGraph();
        for (const op of r.ops) {
          next = applyOp(next, op);
          if (op.op === "add" && op.auto && op.ref && op.kind !== "external_party") lastTouched.current = op.ref;
          if (op.op !== "add" && op.target) lastTouched.current = op.target;
        }
        if (r.ops.length) {
          setGraph(next);
          reveal(r.ops.map((op) => (op.op === "add" ? op.ref! : op.target || op.to || "")).filter(Boolean));
        }
        if (r.parking.length) setParking((ps) => [...ps, ...r.parking]);
        sinceReview.current += 1;
        setLines((ls) => ls.map((l) => (l.id === key ? { id: r.utterance_id, text: clean, ops: r.ops, parked: r.parking.map((p) => p.category), ms: r.latency_ms } : l)));
      } catch (e) {
        setLines((ls) => ls.map((l) => (l.id === key ? { ...l, error: (e as Error).message } : l)));
      }
    });
  };

  const start = () => {
    setError("");
    if (speechOff) return;
    if (!SpeechRecognition) return setError("This browser has no built-in speech recognition. Use Chrome or Edge, or type what was said below.");
    const r = new SpeechRecognition();
    r.lang = "en-AU";
    r.continuous = true;
    r.interimResults = true;
    r.onresult = (e: any) => {
      let partial = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) send(res[0].transcript, "speech");
        else partial += res[0].transcript;
      }
      setInterim(partial);
    };
    r.onerror = (e: any) => { if (e.error !== "no-speech") setError(`Speech recognition stopped: ${e.error}.`); };
    r.onend = () => { if (wantListening.current) r.start(); else setListening(false); }; // browsers stop after silence
    rec.current = r;
    wantListening.current = true;
    r.start();
    setListening(true);
  };
  const stop = () => { wantListening.current = false; rec.current?.stop(); setInterim(""); };
  useEffect(() => () => { wantListening.current = false; rec.current?.stop(); }, []);

  const review = async () => {
    if (reviewing) return;
    setReviewing(true);
    setError("");
    try {
      await queue.current;
      const g = getGraph();
      const d = await api.send<Draft>("POST", `/api/boards/${boardId}/live/review`, { doc: { nodes: g.nodes, edges: g.edges }, doc_kind: docKind });
      let next = getGraph();
      for (const op of (d.proposal?.changes ?? []) as Op[]) next = applyOp(next, op);
      setGraph(next);
      sinceReview.current = 0;
      setReviews((rs) => [d, ...rs]);
      onDocumentProposed(d);
      if (d.proposal?.rules?.length) onRulesProposed(d.proposal.rules as RuleTable[]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setReviewing(false);
    }
  };

  useEffect(() => {
    if (!reviewOn || !listening || !me.ai_enabled) return;
    const t = setInterval(() => { if (sinceReview.current > 0) review(); }, Math.max(1, me.review_minutes) * 60_000);
    return () => clearInterval(t);
  }, [reviewOn, listening, docKind]);

  const setStatus = async (id: string, status: string) => {
    const p = await api.send<Parking>("PATCH", `/api/parking/${id}`, { status });
    setParking((ps) => ps.map((x) => (x.id === id ? p : x)));
  };
  const addParking = async () => {
    if (!newPark.trim()) return;
    const p = await api.send<Parking>("POST", `/api/boards/${boardId}/parking`, { category: "detail", text: newPark.trim() });
    setParking((ps) => [...ps, p]);
    setNewPark("");
  };
  // Put a parked item on the map as context beside the element it was said about.
  const place = (p: Parking) => {
    const kind = PARKED_KIND[p.category] ?? "note";
    const op: Op = { id: `park-${p.id}`, op: "add", source: "jev", auto: true, confidence: null, ref: `n${p.id.slice(0, 8)}`, kind, label: p.text.length > 90 ? p.text.slice(0, 87) + "..." : p.text, after: p.near_element || lastTouched.current };
    setGraph(applyOp(getGraph(), op));
    reveal([op.ref!]);
    setStatus(p.id, "placed");
  };

  const decide = (opId: string, ok: boolean) => { setGraph((ok ? acceptOp : rejectOp)(getGraph(), opId)); force((x) => x + 1); };
  const acceptAll = (d: Draft) => {
    let g = getGraph();
    for (const op of (d.proposal?.changes ?? []) as Op[]) if (isOpen(g, op.id)) g = acceptOp(g, op.id);
    setGraph(g);
    for (const id of (d.proposal as any)?.parking_done ?? []) setStatus(id, "placed");
    force((x) => x + 1);
  };
  const switchPass = async (p: "overview" | "detail") => {
    await api.send("PATCH", `/api/boards/${boardId}/settings`, { session_pass: p });
    setSessionPass(p);
  };

  if (!me.live_enabled) return <div className="gw-panel-body"><p className="quiet">Live mapping is switched off on the server. Set GW_DECISION_PROVIDER to turn it on.</p></div>;
  if (blocked) return <div className="gw-panel-body"><p className="error">This map is marked as holding personal information, and live mapping uses a hosted decision model. Run a local Jev-compatible model, or untick personal information for this map.</p></div>;

  const g = getGraph();
  const steps = g.nodes.filter((n) => ["task", "subprocess", "manual_task", "system_task", "rule_task"].includes(kindOf(n))).length;
  const open = parking.filter((p) => p.status === "open");
  const fixes = checks.filter((c) => c.level === "fix");
  const asks = checks.filter((c) => c.level !== "fix");

  return (
    <div className="gw-panel-body gw-live">
      <Passbar pass={sessionPass}>
        {sessionPass === "overview" ? (
          <>
            <p><strong>Overview pass.</strong> Start to end, standard path only, usual responsibilities. Problems and exceptions go to the parking lot.</p>
            <p className="small">{steps} step{steps === 1 ? "" : "s"} of about 8{steps > 8 ? ". Consider grouping some into sub-processes." : "."}</p>
            <Button onClick={() => switchPass("detail")}>Start the detail pass</Button>
          </>
        ) : (
          <>
            <p><strong>Detail pass{perspective ? `: ${perspective}'s view` : ""}.</strong> Exceptions, rework, systems, outside parties, rules and problems all go on the map.</p>
            <Button variant="link" onClick={() => switchPass("overview")}>Back to the overview pass</Button>
          </>
        )}
      </Passbar>

      <Segmented name="live-mode" small ariaLabel="What to listen for" value={mode} onChange={setMode}
        options={[["listen", "Map the conversation"], ["command", "Only my instructions"]]} />
      {speechOff ? (
        <p className="quiet small">Listening is off because this map holds personal information: browser speech recognition sends audio to Google or Microsoft. Type the key sentences below instead.</p>
      ) : (
        <>
          {!listening ? (
            <Button variant="primary" onClick={start}>Start listening</Button>
          ) : (
            <Recording label="Listening" onStop={stop} />
          )}
          <p className="quiet small">Browser speech recognition sends audio to the browser maker's service (Google for Chrome, Microsoft for Edge). Use the Recording tab for the kept record.</p>
        </>
      )}
      {interim && <p className="gw-interim">{interim}</p>}
      <form className="gw-typed" onSubmit={(e) => { e.preventDefault(); send(typed, "typed"); setTyped(""); }}>
        <Input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Or type what was said" aria-label="Type what was said" />
        <Button type="submit" disabled={!typed.trim()}>Add</Button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}

      {sessionPass === "detail" && (
        <details className="gw-prompts">
          <summary>Questions for the detail pass</summary>
          <ul>{DETAIL_PROMPTS.map((q) => <li key={q}>{q}</li>)}</ul>
        </details>
      )}

      <section className="gw-parking">
        <h3>{sessionPass === "overview" ? "Parking lot" : "Agenda from the parking lot"} <span className="quiet">({open.length})</span></h3>
        {open.length === 0 ? <p className="quiet small">{sessionPass === "overview" ? "Problems, exceptions, workarounds and rules raised now will wait here." : "Nothing waiting."}</p> : (
          <ul>
            {open.map((p) => (
              <ParkingItem key={p.id} category={p.category} actions={<>
                {sessionPass === "detail" && <Button size="small" onClick={() => place(p)}>Put on map</Button>}
                <Button variant="link" size="small" onClick={() => setStatus(p.id, sessionPass === "detail" ? "placed" : "dismissed")}>{sessionPass === "detail" ? "Covered" : "Drop"}</Button>
              </>}>{p.text}</ParkingItem>
            ))}
          </ul>
        )}
        <form className="gw-typed" onSubmit={(e) => { e.preventDefault(); addParking(); }}>
          <Input value={newPark} onChange={(e) => setNewPark(e.target.value)} placeholder="Park something for later" aria-label="Park something for later" />
          <Button type="submit" disabled={!newPark.trim()}>Park</Button>
        </form>
      </section>

      {checks.length > 0 && (
        <section className="gw-checks">
          <h3>Map checks</h3>
          <ul>
            {[...fixes, ...asks].map((c, i) => (
              <CheckItem key={i} level={c.level} onShow={c.ids.length > 0 ? () => focus(c.ids) : undefined}>{c.text}</CheckItem>
            ))}
          </ul>
        </section>
      )}

      <div className="gw-reviewbar">
        <Check checked={reviewOn} onChange={(e) => setReviewOn(e.target.checked)}> Review the session every {me.review_minutes} minutes</Check>
        <Button onClick={review} disabled={reviewing || !me.ai_enabled}>{reviewing ? "Reviewing…" : "Review now"}</Button>
      </div>

      {reviews.slice(0, 3).map((d) => {
        const changes = (d.proposal?.changes ?? []) as Op[];
        const openOps = changes.filter((op) => isOpen(g, op.id));
        return (
          <ReviewCard key={d.id} time={new Date(d.created_at).toLocaleTimeString("en-AU", { hour: "numeric", minute: "2-digit" })} model={d.model}
            summary={d.proposal?.summary}
            actions={openOps.length > 0 && <Button variant="primary" onClick={() => acceptAll(d)}>Accept all {openOps.length} map changes</Button>}
            note={!!d.proposal?.rules?.length && <p className="small">Drafted {d.proposal.rules.length} rule table{d.proposal.rules.length === 1 ? "" : "s"}. See the Rules tab.</p>}
            extra={!!d.proposal?.open_questions?.length && <><h4>Still to confirm</h4><ul>{d.proposal.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul></>}>
            {changes.map((op) => (
              <ReviewOp key={op.id} done={!isOpen(g, op.id)} reason={op.reason && <>{op.reason}{op.evidence ? ` ("${op.evidence}")` : ""}</>}
                actions={<><Button size="small" onClick={() => decide(op.id, true)}>Accept</Button><Button variant="link" size="small" onClick={() => decide(op.id, false)}>Reject</Button></>}>
                {describe(op, g)}
              </ReviewOp>
            ))}
          </ReviewCard>
        );
      })}

      <h3>Heard</h3>
      {lines.length === 0 ? <p className="quiet">Nothing yet. Start listening or type a sentence.</p> : (
        <ol className="gw-feed">
          {[...lines].reverse().slice(0, 60).map((l) => (
            <Heard key={l.id} said={l.text}>
              {l.error && <p className="error">{l.error}</p>}
              {l.ops.map((op) => (
                <OpLine key={op.id} auto={op.auto} confidence={op.confidence}
                  actions={isOpen(g, op.id) && <><Button size="small" onClick={() => decide(op.id, true)}>Accept</Button><Button variant="link" size="small" onClick={() => decide(op.id, false)}>Reject</Button></>}>
                  {describe(op, g)}
                </OpLine>
              ))}
              {!!l.parked?.length && <p className="quiet small">Parked: {l.parked.map((c) => PARKING_LABEL[c]?.toLowerCase() ?? c).join(", ")}</p>}
              {!l.error && !l.ops.length && !l.parked?.length && !l.id.startsWith("tmp") && <p className="quiet small">No change</p>}
            </Heard>
          ))}
        </ol>
      )}
    </div>
  );
}

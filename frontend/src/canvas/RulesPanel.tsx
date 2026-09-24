// Business rules, kept out of the diagram as decision tables (Real-Life BPMN, section 4.5.4).
// One rule step on the map; the conditions live here, in the words staff used.
import { useEffect, useState } from "react";
import type { Node } from "@xyflow/react";
import { api } from "../lib/api";

export type RuleRow = { when: Record<string, string>; then: string; source: string; confirmed: boolean };
export type RuleTable = { id: string; name: string; question: string; inputs: string[]; output: string; rows: RuleRow[]; element_id: string; notes: string };

type Props = { boardId: string; ruleSteps: Node[]; proposed: RuleTable[] | null; clearProposed: () => void; onSaved: (t: RuleTable[]) => void };

const blank = (): RuleTable => ({ id: "", name: "New rule", question: "", inputs: ["Condition"], output: "Outcome", rows: [{ when: { Condition: "" }, then: "", source: "", confirmed: false }], element_id: "", notes: "" });

export default function RulesPanel({ boardId, ruleSteps, proposed, clearProposed, onSaved }: Props) {
  const [tables, setTables] = useState<RuleTable[]>([]);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const [stale, setStale] = useState(false);

  const load = () => api.get<{ rules: RuleTable[]; version: number }>(`/api/boards/${boardId}/rules`).then((r) => {
    setTables(r.rules); setVersion(r.version); setDirty(false); setStale(false); setError("");
  });
  useEffect(() => { load(); }, [boardId]);

  const edit = (i: number, f: (t: RuleTable) => RuleTable) => { setTables((ts) => ts.map((t, j) => (j === i ? f(structuredClone(t)) : t))); setDirty(true); };
  const save = async (next = tables) => {
    setError("");
    try {
      const saved = await api.send<{ rules: RuleTable[]; version: number }>("PUT", `/api/boards/${boardId}/rules`, { rules: next, version });
      setTables(saved.rules); setVersion(saved.version); setDirty(false); onSaved(saved.rules);
    } catch (e) {
      setStale((e as { status?: number }).status === 409);
      setError((e as Error).message);
    }
  };

  return (
    <div className="panel-body rules">
      <p className="quiet small">When someone lists conditions, keep one rule step on the map and put the conditions here. Keep their words; confirm thresholds before anyone relies on them.</p>
      {proposed && (
        <div className="proposal">
          <p><strong>The reviewer drafted {proposed.length} rule table{proposed.length === 1 ? "" : "s"} from the session.</strong></p>
          <div className="actions">
            <button className="primary" onClick={() => { save(proposed); clearProposed(); }}>Use them</button>
            <button onClick={() => { setTables(proposed); setDirty(true); clearProposed(); }}>Edit them first</button>
            <button className="link" onClick={clearProposed}>Keep mine</button>
          </div>
        </div>
      )}
      {tables.length === 0 && !proposed && <p className="quiet">No rules yet. They appear here after a review, or add one yourself.</p>}
      {tables.map((t, i) => (
        <section key={t.id || i} className="ruletable">
          <input className="rt-name" value={t.name} aria-label="Rule name" onChange={(e) => edit(i, (x) => ({ ...x, name: e.target.value }))} />
          <label className="small">Decides<input value={t.question} placeholder="For example: Issue a breach notice?" onChange={(e) => edit(i, (x) => ({ ...x, question: e.target.value }))} /></label>
          <label className="small">Rule step on the map
            <select value={t.element_id} onChange={(e) => edit(i, (x) => ({ ...x, element_id: e.target.value }))}>
              <option value="">Not linked</option>
              {ruleSteps.map((n) => <option key={n.id} value={n.id}>{String(n.data?.label || "Unnamed rule step")}</option>)}
            </select>
          </label>
          <div className="tablewrap">
            <table>
              <thead>
                <tr>
                  {t.inputs.map((inp, k) => (
                    <th key={k}><input value={inp} aria-label="Condition name" onChange={(e) => edit(i, (x) => {
                      const old = x.inputs[k]; x.inputs[k] = e.target.value;
                      x.rows.forEach((r) => { r.when[e.target.value] = r.when[old] ?? ""; if (old !== e.target.value) delete r.when[old]; });
                      return x;
                    })} /></th>
                  ))}
                  <th className="out"><input value={t.output} aria-label="Outcome name" onChange={(e) => edit(i, (x) => ({ ...x, output: e.target.value }))} /></th>
                  <th>Confirmed</th>
                </tr>
              </thead>
              <tbody>
                {t.rows.map((r, k) => (
                  <tr key={k} title={r.source ? `Heard: ${r.source}` : undefined}>
                    {t.inputs.map((inp) => (
                      <td key={inp}><input value={r.when[inp] ?? ""} placeholder="any" aria-label={inp} onChange={(e) => edit(i, (x) => { x.rows[k].when[inp] = e.target.value; return x; })} /></td>
                    ))}
                    <td className="out"><input value={r.then} aria-label={t.output} onChange={(e) => edit(i, (x) => { x.rows[k].then = e.target.value; return x; })} /></td>
                    <td><input type="checkbox" checked={r.confirmed} aria-label="Confirmed" onChange={(e) => edit(i, (x) => { x.rows[k].confirmed = e.target.checked; return x; })} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="actions">
            <button onClick={() => edit(i, (x) => { x.rows.push({ when: Object.fromEntries(x.inputs.map((n) => [n, ""])), then: "", source: "", confirmed: false }); return x; })}>Add row</button>
            <button onClick={() => edit(i, (x) => { const n = `Condition ${x.inputs.length + 1}`; x.inputs.push(n); x.rows.forEach((r) => { r.when[n] = ""; }); return x; })}>Add condition</button>
            <button className="link" onClick={() => { setTables((ts) => ts.filter((_, j) => j !== i)); setDirty(true); }}>Delete table</button>
          </div>
        </section>
      ))}
      <div className="actions">
        <button onClick={() => { setTables((ts) => [...ts, blank()]); setDirty(true); }}>Add a rule table</button>
        {dirty && <button className="primary" onClick={() => save()}>Save rules</button>}
      </div>
      {error && <p className="error" role="alert">{error} {stale && <button className="link" onClick={load}>Reload the rule tables</button>}</p>}
    </div>
  );
}

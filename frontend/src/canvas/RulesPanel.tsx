// Business rules, kept out of the diagram as decision tables (Real-Life BPMN, section 4.5.4).
// One rule step on the map; the conditions live here, in the words staff used.
import { useEffect, useState } from "react";
import type { Node } from "@xyflow/react";
import { api } from "../lib/api";
import { Button, Field, Input, Table } from "../ui";

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
    <div className="gw-panel-body">
      <p className="quiet small">When someone lists conditions, keep one rule step on the map and put the conditions here. Keep their words; confirm thresholds before anyone relies on them.</p>
      {proposed && (
        <div className="gw-proposal">
          <p><strong>The reviewer drafted {proposed.length} rule table{proposed.length === 1 ? "" : "s"} from the session.</strong></p>
          <div className="gw-actions">
            <Button variant="primary" onClick={() => { save(proposed); clearProposed(); }}>Use them</Button>
            <Button onClick={() => { setTables(proposed); setDirty(true); clearProposed(); }}>Edit them first</Button>
            <Button variant="link" onClick={clearProposed}>Keep mine</Button>
          </div>
        </div>
      )}
      {tables.length === 0 && !proposed && <p className="quiet">No rules yet. They appear here after a review, or add one yourself.</p>}
      {tables.map((t, i) => (
        <section key={t.id || i} className="gw-ruletable">
          <Input className="gw-rt-name" value={t.name} aria-label="Rule name" onChange={(e) => edit(i, (x) => ({ ...x, name: e.target.value }))} />
          <Field label="Decides" className="small" value={t.question} placeholder="For example: Issue a breach notice?" onChange={(e) => edit(i, (x) => ({ ...x, question: e.target.value }))} />
          <Field label="Rule step on the map" as="select" className="small" value={t.element_id} onChange={(e) => edit(i, (x) => ({ ...x, element_id: e.target.value }))}>
            <option value="">Not linked</option>
            {ruleSteps.map((n) => <option key={n.id} value={n.id}>{String(n.data?.label || "Unnamed rule step")}</option>)}
          </Field>
          <Table>
              <thead>
                <tr>
                  {t.inputs.map((inp, k) => (
                    <th key={k}><Input value={inp} aria-label="Condition name" onChange={(e) => edit(i, (x) => {
                      const old = x.inputs[k]; x.inputs[k] = e.target.value;
                      x.rows.forEach((r) => { r.when[e.target.value] = r.when[old] ?? ""; if (old !== e.target.value) delete r.when[old]; });
                      return x;
                    })} /></th>
                  ))}
                  <th className="out"><Input value={t.output} aria-label="Outcome name" onChange={(e) => edit(i, (x) => ({ ...x, output: e.target.value }))} /></th>
                  <th>Confirmed</th>
                </tr>
              </thead>
              <tbody>
                {t.rows.map((r, k) => (
                  <tr key={k} title={r.source ? `Heard: ${r.source}` : undefined}>
                    {t.inputs.map((inp) => (
                      <td key={inp}><Input value={r.when[inp] ?? ""} placeholder="any" aria-label={inp} onChange={(e) => edit(i, (x) => { x.rows[k].when[inp] = e.target.value; return x; })} /></td>
                    ))}
                    <td className="out"><Input value={r.then} aria-label={t.output} onChange={(e) => edit(i, (x) => { x.rows[k].then = e.target.value; return x; })} /></td>
                    <td><input type="checkbox" checked={r.confirmed} aria-label="Confirmed" onChange={(e) => edit(i, (x) => { x.rows[k].confirmed = e.target.checked; return x; })} /></td>
                  </tr>
                ))}
              </tbody>
          </Table>
          <div className="gw-actions">
            <Button onClick={() => edit(i, (x) => { x.rows.push({ when: Object.fromEntries(x.inputs.map((n) => [n, ""])), then: "", source: "", confirmed: false }); return x; })}>Add row</Button>
            <Button onClick={() => edit(i, (x) => { const n = `Condition ${x.inputs.length + 1}`; x.inputs.push(n); x.rows.forEach((r) => { r.when[n] = ""; }); return x; })}>Add condition</Button>
            <Button variant="link" onClick={() => { setTables((ts) => ts.filter((_, j) => j !== i)); setDirty(true); }}>Delete table</Button>
          </div>
        </section>
      ))}
      <div className="gw-actions">
        <Button onClick={() => { setTables((ts) => [...ts, blank()]); setDirty(true); }}>Add a rule table</Button>
        {dirty && <Button variant="primary" onClick={() => save()}>Save rules</Button>}
      </div>
      {error && <p className="error" role="alert">{error} {stale && <Button variant="link" onClick={load}>Reload the rule tables</Button>}</p>}
    </div>
  );
}

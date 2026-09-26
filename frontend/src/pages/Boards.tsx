import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type BoardRow, type ProcessRow } from "../lib/api";
import { Button, Card, Check, Field, OptionGroup, Rows } from "../ui";

// Maps follow the two-pass method: an overview of the whole process first (standard path only),
// then one detail map per person, each showing what they do and what they wait for. Combine the
// detail maps into one collaboration map when two or more exist.
export default function Boards() {
  const [boards, setBoards] = useState<BoardRow[] | null>(null);
  const [processes, setProcesses] = useState<ProcessRow[]>([]);
  const [title, setTitle] = useState("");
  const [pid, setPid] = useState("");
  const [kind, setKind] = useState<"overview" | "person">("overview");
  const [perspective, setPerspective] = useState("");
  const [pi, setPi] = useState(false);
  const [combining, setCombining] = useState("");
  const [error, setError] = useState("");
  const nav = useNavigate();
  useEffect(() => {
    api.get<BoardRow[]>("/api/boards").then(setBoards);
    api.get<ProcessRow[]>("/api/processes").then(setProcesses);
  }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    const b = await api.send<BoardRow>("POST", "/api/boards", {
      title, process_id: pid || null, personal_info: pi,
      perspective: kind === "person" ? perspective : "", session_pass: kind === "person" ? "detail" : "overview",
    });
    nav(`/maps/${b.id}`);
  };

  const combinable = useMemo(() => {
    const byProcess: Record<string, BoardRow[]> = {};
    for (const b of boards ?? []) if (b.process_id && b.perspective) (byProcess[b.process_id] ||= []).push(b);
    return Object.entries(byProcess).filter(([, bs]) => bs.length >= 2);
  }, [boards]);

  const combine = async (processId: string) => {
    setCombining(processId);
    setError("");
    try {
      const b = await api.send<BoardRow>("POST", `/api/processes/${processId}/combine`);
      nav(`/maps/${b.id}`);
    } catch (err) {
      setError((err as Error).message);
      setCombining("");
    }
  };

  return (
    <div>
      <h1>Process maps</h1>
      <Card variant="form" as="form" onSubmit={create}>
        <h2>Start a map</h2>
        <Field label="What are you mapping?" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="For example: chasing late rent" />
        <Field label="Process" as="select" value={pid} onChange={(e) => setPid(e.target.value)}>
          <option value="">Not linked yet</option>
          {processes.filter((p) => p.parent_id).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </Field>
        <OptionGroup name="kind" legend="What kind of map?" value={kind} onChange={setKind} options={[
          { value: "overview", label: "Overview of the whole process", hint: "Start to end in about eight steps. Start here." },
          { value: "person", label: "One person's view, in detail", hint: "What they do, what they wait for, what goes wrong." },
        ]} />
        {kind === "person" && (
          <Field label="Whose view?" required value={perspective} onChange={(e) => setPerspective(e.target.value)} placeholder="For example: Sam, property manager" />
        )}
        <Check checked={pi} onChange={(e) => setPi(e.target.checked)}> We'll talk about real tenants, borrowers or staff</Check>
        <Button variant="primary" type="submit">Open the canvas</Button>
      </Card>

      {combinable.length > 0 && (
        <section>
          <h2>Combine views</h2>
          <p className="quiet">These processes have two or more one-person maps. Combining builds one map with a lane per person and joins their hand-offs.</p>
          <Rows items={combinable.map(([processId, bs]) => [
            <strong>{bs[0].process_name}</strong>,
            bs.map((b) => b.perspective).join(", "),
            <Button onClick={() => combine(processId)} disabled={!!combining}>{combining === processId ? "Combining…" : "Combine"}</Button>,
          ])} />
          {error && <p className="error" role="alert">{error}</p>}
        </section>
      )}

      <section>
        <h2>Maps</h2>
        {boards === null ? <p className="quiet">Loading…</p> : boards.length === 0 ? <p className="quiet">No maps yet.</p> : (
          <Rows>
            {boards.map((b) => (
              <li key={b.id}>
                <Link to={`/maps/${b.id}`}>{b.title}</Link>
                <span className="quiet">{b.process_name || "No process linked"}{b.perspective ? ` · ${b.perspective}'s view` : b.session_pass === "overview" ? " · overview" : ""}</span>
                <span className="quiet">{b.node_count} elements · {new Date(b.updated_at).toLocaleDateString("en-AU")}</span>
              </li>
            ))}
          </Rows>
        )}
      </section>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { LAYERS } from "../lib/labels";
import { Rows, Table, Tiles } from "../ui";

type Row = {
  id: string; name: string; parent_id: string | null; status: string; owner_email: string;
  layers: Record<string, number>; files: number; contributors: number;
  maps: { overview: number; views: number; other: number; total: number; to_confirm: number };
  drafts: { accepted: number; discarded: number; draft: number }; flags: string[];
};
type Coverage = {
  processes: Row[];
  contributors: { name: string; email: string; team: string; files: number }[];
  totals: { files: number; workaround_share: number; processes: number; processes_with_files: number; processes_with_map: number;
    drafts: { accepted: number; discarded: number; draft: number }; to_confirm: number };
};

const SHOWN = ["declared", "system", "actual", "workaround", "unsure"] as const;

// Where the evidence is and where it isn't: files per process by what they show, who shared them,
// and how far mapping has got. The measures come from the rollout plan in docs/ARCHITECTURE.md.
export default function CoveragePage() {
  const [data, setData] = useState<Coverage | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get<Coverage>("/api/admin/coverage").then(setData).catch((e) => setError(e.message)); }, []);

  const groups = useMemo(() => {
    if (!data) return [];
    const tops = data.processes.filter((p) => !p.parent_id || !data.processes.some((q) => q.id === p.parent_id));
    return tops.map((t) => ({ top: t, kids: data.processes.filter((p) => p.parent_id === t.id) }));
  }, [data]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="quiet">Loading…</p>;
  const t = data.totals;
  const layerName = (k: string) => LAYERS.find((l) => l[0] === k)?.[1] ?? k;

  const row = (p: Row, child: boolean) => (
    <tr key={p.id} className={child ? undefined : "grouprow"}>
      <th scope="row" className={child ? "indent" : undefined}>{p.name}{p.status === "proposed" && <span className="quiet"> (proposed)</span>}</th>
      {SHOWN.map((l) => <td key={l} className={`num ${p.layers[l] ? "" : "zero"}`}>{p.layers[l] || "·"}</td>)}
      <td className="num">{p.contributors || "·"}</td>
      <td>{p.maps.total ? `${p.maps.overview ? "Overview" : "No overview"}${p.maps.views ? `, ${p.maps.views} view${p.maps.views > 1 ? "s" : ""}` : ""}` : <span className="quiet">None</span>}</td>
      <td className="num">{p.maps.to_confirm || "·"}</td>
      <td className="gw-flags">{p.flags.join(" · ")}</td>
    </tr>
  );

  return (
    <div>
      <h1>Coverage</h1>
      <p className="lede">Where the evidence is, and where it isn't yet. A process with only the official version, or with workarounds nobody has mapped, is where to look next.</p>
      <Tiles items={[
        { label: "Files shared", value: t.files },
        { label: "Workarounds", value: `${Math.round(t.workaround_share * 100)}%`, note: "of files" },
        { label: "Processes with files", value: `${t.processes_with_files} of ${t.processes}` },
        { label: "Processes mapped", value: `${t.processes_with_map} of ${t.processes}` },
        { label: "AI drafts kept", value: `${t.drafts.accepted} of ${t.drafts.accepted + t.drafts.discarded}`, note: "decided" },
        { label: 'Open "to confirm"', value: t.to_confirm },
      ]} />

      <Table caption="Files per process by what they show. Withdrawn, blocked and deleted files don't count.">
          <thead>
            <tr><th scope="col">Process</th>{SHOWN.map((l) => <th key={l} scope="col" className="num">{layerName(l)}</th>)}
              <th scope="col" className="num">People</th><th scope="col">Maps</th><th scope="col" className="num">To confirm</th><th scope="col">Notes</th></tr>
          </thead>
          <tbody>{groups.flatMap(({ top, kids }) => [row(top, false), ...kids.map((k) => row(k, true))])}</tbody>
      </Table>
      <p className="quiet"><Link to="/processes">Rename, confirm, merge or retire processes</Link></p>

      <h2>Who has shared</h2>
      {data.contributors.length === 0 ? <p className="quiet">Nobody yet.</p> : (
        <Rows items={data.contributors.map((c) => [<strong>{c.name}</strong>, c.team || c.email, `${c.files} file${c.files > 1 ? "s" : ""}`])} />
      )}
    </div>
  );
}

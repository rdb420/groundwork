import { useMemo, useState } from "react";
import type { ProcessRow } from "../lib/api";
import { Button, Check, Chip, Input } from "../ui";

type Props = {
  processes: ProcessRow[];
  selected: string[];
  newNames: string[];
  onChange: (selected: string[], newNames: string[]) => void;
};

// Grouped checklist of the process catalogue, plus a way to name one we haven't listed.
export default function ProcessPicker({ processes, selected, newNames, onChange }: Props) {
  const [adding, setAdding] = useState("");
  const groups = useMemo(() => {
    const tops = processes.filter((p) => !p.parent_id);
    return tops.map((t) => ({ top: t, kids: processes.filter((p) => p.parent_id === t.id) }));
  }, [processes]);
  const toggle = (id: string) =>
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id], newNames);
  const add = () => {
    const n = adding.trim();
    if (n && !newNames.includes(n)) onChange(selected, [...newNames, n]);
    setAdding("");
  };
  return (
    <div className="gw-picker">
      {groups.map(({ top, kids }) => (
        <fieldset key={top.id}>
          <legend>{top.name}</legend>
          {(kids.length ? kids : [top]).map((p) => (
            <Check key={p.id} checked={selected.includes(p.id)} onChange={() => toggle(p.id)}>{p.name}</Check>
          ))}
        </fieldset>
      ))}
      {newNames.map((n) => (
        <Chip key={n} removeLabel={`Remove ${n}`} onRemove={() => onChange(selected, newNames.filter((x) => x !== n))}>{n} (new)</Chip>
      ))}
      <div className="gw-add-row">
        <Input value={adding} onChange={(e) => setAdding(e.target.value)} placeholder="Not listed? Name the work in your own words"
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
        <Button onClick={add} disabled={!adding.trim()}>Add</Button>
      </div>
    </div>
  );
}

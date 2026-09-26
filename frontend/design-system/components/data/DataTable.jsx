import React from "react";
export function DataTable({ columns = [], rows = [], onRowClick, caption }) {
  return (
    <div className="gw-tablewrap">
      <table className="gw-table">
        {caption && <caption className="quiet" style={{ textAlign: "left", padding: "0.4rem 0" }}>{caption}</caption>}
        <thead><tr>{columns.map((c) => <th key={c.key} className={c.num ? "num" : undefined}>{c.label}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={r.id || i} className={r._group ? "grouprow" : undefined} onClick={() => onRowClick && onRowClick(r)} tabIndex={onRowClick ? 0 : undefined}>
            {columns.map((c) => <td key={c.key} className={[c.num && "num", c.num && !r[c.key] && "zero"].filter(Boolean).join(" ") || undefined}>{c.render ? c.render(r) : (c.num && !r[c.key] ? "·" : r[c.key])}</td>)}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

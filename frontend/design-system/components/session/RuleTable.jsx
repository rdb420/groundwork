import React from "react";
export function RuleTable({ name, inputs = [], outputs = [], rows = [] }) {
  return (
    <div className="gw-ruletable">
      <p className="gw-rt-name">{name}</p>
      <table>
        <thead><tr>{inputs.map((h) => <th key={h}>{h}</th>)}{outputs.map((h) => <th key={h} className="out">{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={j >= inputs.length ? "out" : undefined}>{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

import React from "react";
export function Segmented({ name, options = [], value, onChange, small, ariaLabel }) {
  return (
    <div className={"gw-segmented" + (small ? " small" : "")} role="radiogroup" aria-label={ariaLabel}>
      {options.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return (
        <label key={v} className={value === v ? "on" : ""}><input type="radio" name={name} value={v} checked={value === v} onChange={() => onChange && onChange(v)} />{l}</label>
      ); })}
    </div>
  );
}

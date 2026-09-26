import React from "react";
export function OptionGroup({ name, legend, options = [], value, onChange }) {
  return (
    <fieldset className="gw-options">
      {legend && <legend>{legend}</legend>}
      {options.map((o) => (
        <label key={o.value} className={"gw-option" + (value === o.value ? " on" : "")}>
          <input type="radio" name={name} checked={value === o.value} onChange={() => onChange && onChange(o.value)} />
          <strong>{o.label}</strong><span>{o.hint}</span>
        </label>
      ))}
    </fieldset>
  );
}

import React from "react";
import { Button } from "./Button.jsx";
export function SegToggle({ items = [], value, onChange, ariaLabel }) {
  return (
    <div className="gw-seg-toggle" role="group" aria-label={ariaLabel}>
      {items.map((it) => {
        const [k, l] = Array.isArray(it) ? it : [it.value, it.label];
        return <Button key={k} on={value === k} onClick={() => onChange && onChange(value === k ? null : k)}>{l}</Button>;
      })}
    </div>
  );
}

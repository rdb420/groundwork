import React from "react";
export function Field({ label, hint, as = "input", options, children, className, ...rest }) {
  let control;
  if (as === "select") control = <select className="gw-input" {...rest}>{options ? options.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return <option key={v} value={v}>{l}</option>; }) : children}</select>;
  else if (as === "textarea") control = <textarea className="gw-input" rows={2} {...rest} />;
  else control = <input className="gw-input" {...rest} />;
  return <label className={"gw-field" + (className ? " " + className : "")}>{label}{hint && <> <span className="quiet">{hint}</span></>}{control}</label>;
}

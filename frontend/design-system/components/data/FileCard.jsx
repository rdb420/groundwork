import React from "react";
import { Status } from "../core/Status.jsx";
export function FileCard({ name, size, state = "ready", note, onRemove, children }) {
  return (
    <div className={"gw-filecard" + (state === "done" ? " f-done" : state === "error" ? " f-error" : "")}>
      <div className="gw-filehead">
        <span className="gw-fname">{name}</span>
        {size && <span className="quiet">{size}</span>}
        {state === "ready" && onRemove && <button type="button" className="gw-btn gw-btn--link" onClick={onRemove}>Remove</button>}
        {state === "done" && <Status tone="ok">Shared</Status>}
        {state === "sending" && <Status>Sending…</Status>}
      </div>
      {children}
      {note && <p className={state === "error" ? "error" : "quiet"}>{note}</p>}
    </div>
  );
}

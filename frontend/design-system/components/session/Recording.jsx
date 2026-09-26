import React from "react";
export function Recording({ label = "Listening", onStop }) {
  return <div className="gw-recording" role="status"><span className="gw-dot" aria-hidden="true" /> {label}{onStop && <button type="button" className="gw-btn" onClick={onStop}>Stop</button>}</div>;
}

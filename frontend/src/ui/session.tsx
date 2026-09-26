// Live mapping and review pieces from the design system (design-system/components/session).
import type { ReactNode } from "react";
import { cx } from "./core";

export function Passbar({ pass = "overview", children }: { pass?: "overview" | "detail"; children?: ReactNode }) {
  return <div className={cx("gw-passbar", `pass-${pass}`)}>{children}</div>;
}

export const PARKING_LABEL: Record<string, string> = {
  issue: "Problem", workaround: "Workaround", exception: "Exception or rework", rule: "Rule or condition", question: "Question", detail: "Detail",
};

// A parking-lot entry: a rule coloured by category, the category, the text, then actions.
export function ParkingItem({ category = "detail", children, actions }: { category?: string; children?: ReactNode; actions?: ReactNode }) {
  return (
    <li className={cx("gw-pk", `pk-${category}`)}>
      <span className="gw-pk-cat">{PARKING_LABEL[category] ?? category}</span>
      <span>{children}</span>
      {actions && <span className="gw-opbtns">{actions}</span>}
    </li>
  );
}

// A map structure finding. "fix" needs fixing, "ask" is worth asking about.
export function CheckItem({ level = "ask", children, onShow }: { level?: "fix" | "ask" | "info"; children?: ReactNode; onShow?: () => void }) {
  return (
    <li className={cx("gw-chk", `chk-${level}`)}>
      <span>{children}</span>
      {onShow && <button type="button" className="gw-btn gw-btn--link" onClick={onShow}>Show</button>}
    </li>
  );
}

// One proposed change under a heard sentence: yellow while it waits, green once it landed.
export function OpLine({ auto, confidence, children, actions }: { auto?: boolean; confidence?: number | null; children?: ReactNode; actions?: ReactNode }) {
  return (
    <div className={cx("gw-opline", auto && "auto")}>
      <span>{children}</span>
      <span className="gw-conf">{auto ? "added" : "waiting"}{confidence != null ? ` · ${Math.round(confidence * 100)}%` : ""}</span>
      {actions && <span className="gw-opbtns">{actions}</span>}
    </div>
  );
}

// A feed entry: the sentence as heard, then what it did. Goes inside an <ol className="gw-feed">.
export function Heard({ said, children }: { said: ReactNode; children?: ReactNode }) {
  return <li><p className="gw-said">{said}</p>{children}</li>;
}

// A reviewer's proposed corrections. ReviewOp rows go in children; `extra` follows the list.
export function ReviewCard({ time, model, summary, actions, note, children, extra }: {
  time: string; model?: string; summary?: ReactNode; actions?: ReactNode; note?: ReactNode; children?: ReactNode; extra?: ReactNode;
}) {
  return (
    <article className="gw-review">
      <header><strong>Review at {time}</strong><span className="quiet">{model}</span></header>
      {summary && <p>{summary}</p>}
      {actions}
      {note}
      {children && <ul className="gw-oplist">{children}</ul>}
      {extra}
    </article>
  );
}

export function ReviewOp({ done, reason, actions, children }: { done?: boolean; reason?: ReactNode; actions?: ReactNode; children?: ReactNode }) {
  return (
    <li className={done ? "done" : undefined}>
      <span>{children}</span>
      {reason && <span className="quiet">{reason}</span>}
      {!done && actions && <span className="gw-opbtns">{actions}</span>}
    </li>
  );
}

// The pulsing red dot. The only looping animation in the system.
export function Recording({ label = "Listening", onStop, stopDisabled }: { label?: ReactNode; onStop?: () => void; stopDisabled?: boolean }) {
  return (
    <div className="gw-recording" role="status">
      <span className="gw-dot" aria-hidden="true" /> {label}
      {onStop && <button type="button" className="gw-btn" onClick={onStop} disabled={stopDisabled}>Stop</button>}
    </div>
  );
}

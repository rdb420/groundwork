// Dialogs, drawers and floating bars from the design system (design-system/components/overlays),
// with the keyboard handling the design system leaves out: Escape closes, focus moves in when
// they open and returns to where it was when they close, and a dialog keeps Tab inside itself.
import { Fragment, useEffect, useRef, type FormEvent, type ReactNode, type RefObject } from "react";
import { cx } from "./core";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function useOverlay(ref: RefObject<HTMLElement | null>, onClose: (() => void) | undefined, trap: boolean) {
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const before = document.activeElement as HTMLElement | null;
    // React has already focused any autoFocus control inside; otherwise take focus ourselves.
    if (!el.contains(document.activeElement)) el.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && close.current) { e.preventDefault(); close.current(); return; }
      if (!trap || e.key !== "Tab") return;
      const items = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === el)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (before?.isConnected) before.focus();
    };
  }, []);
}

type DialogProps = {
  title?: ReactNode; titleId?: string; children?: ReactNode; actions?: ReactNode;
  /** Escape and a click on the scrim call this. Leave it out for a dialog that must be answered. */
  onClose?: () => void;
  onSubmit?: (e: FormEvent<HTMLFormElement>) => void;
};

// A modal dialog over an ink scrim. With onSubmit the box is a form.
export function Dialog({ title, titleId = "gw-dialog-title", children, actions, onClose, onSubmit }: DialogProps) {
  const box = useRef<HTMLElement>(null);
  useOverlay(box, onClose, true);
  const body = <>{title && <h2 id={titleId}>{title}</h2>}{children}{actions && <div className="gw-actions">{actions}</div>}</>;
  const props = { className: "gw-dialog", role: "dialog", "aria-modal": true, "aria-labelledby": title ? titleId : undefined, tabIndex: -1 } as const;
  return (
    <div className="gw-scrim" onClick={(e) => e.target === e.currentTarget && onClose?.()}>
      {onSubmit
        ? <form ref={box as RefObject<HTMLFormElement>} {...props} onSubmit={onSubmit}>{body}</form>
        : <div ref={box as RefObject<HTMLDivElement>} {...props}>{body}</div>}
    </div>
  );
}

// The right-hand detail drawer. It doesn't block the page, so Tab can leave it.
export function Drawer({ title, label, children, onClose }: { title?: ReactNode; label: string; children?: ReactNode; onClose: () => void }) {
  const el = useRef<HTMLElement>(null);
  useOverlay(el, onClose, false);
  return (
    <aside ref={el} className="gw-drawer" aria-label={label} tabIndex={-1}>
      <button type="button" className="gw-btn gw-btn--link close" onClick={onClose}>Close</button>
      {title && <h2>{title}</h2>}
      {children}
    </aside>
  );
}

export function DetailList({ items }: { items: [ReactNode, ReactNode][] }) {
  return <dl>{items.map(([k, v], i) => <Fragment key={i}><dt>{k}</dt><dd>{v}</dd></Fragment>)}</dl>;
}

// A small panel under a button. The parent needs position: relative.
export function Popover({ children, label, onClose }: { children?: ReactNode; label?: string; onClose: () => void }) {
  const el = useRef<HTMLDivElement>(null);
  useOverlay(el, onClose, false);
  return <div ref={el} className="gw-popover" role="group" aria-label={label} tabIndex={-1}>{children}</div>;
}

// A bar floating at the bottom of the screen for one decision on a batch of proposed changes.
export function CombineBar({ children, actions, label, floating = true }: { children?: ReactNode; actions?: ReactNode; label?: string; floating?: boolean }) {
  return <div className={cx("gw-combine-bar", floating && "floating")} role="region" aria-label={label}><p>{children}</p>{actions}</div>;
}

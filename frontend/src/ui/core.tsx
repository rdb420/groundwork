// Core primitives from the design system (design-system/components/core). Class names are the
// design system's; behaviour is Groundwork's.
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";

export const cx = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(" ");

type Look = { variant?: "default" | "primary" | "link"; size?: "default" | "small"; on?: boolean };
const look = ({ variant = "default", size, on }: Look, className?: string) =>
  cx("gw-btn", variant === "primary" && "gw-btn--primary", variant === "link" && "gw-btn--link",
    size === "small" && "gw-btn--small", on && "gw-btn--on", className);

export type ButtonProps = Look & ButtonHTMLAttributes<HTMLButtonElement>;

// Defaults to type="button", so only a button that says type="submit" submits its form.
export function Button({ variant, size, on, className, type = "button", ...rest }: ButtonProps) {
  return <button type={type} className={look({ variant, size, on }, className)} {...rest} />;
}

// An anchor that looks like a button, for downloads and full-page links.
export function LinkButton({ variant, size, className, ...rest }: Omit<Look, "on"> & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <a className={look({ variant, size }, className)} {...rest} />;
}

// A joined row of buttons that opens one side panel at a time. Clicking the open one closes it.
export function SegToggle<K extends string>({ items, value, onChange, ariaLabel }: {
  items: readonly (readonly [K, ReactNode])[]; value: K | null; onChange: (value: K | null) => void; ariaLabel?: string;
}) {
  return (
    <div className="gw-seg-toggle" role="group" aria-label={ariaLabel}>
      {items.map(([k, l]) => (
        <Button key={k} on={value === k} aria-pressed={value === k} onClick={() => onChange(value === k ? null : k)}>{l}</Button>
      ))}
    </div>
  );
}

export type Tone = "info" | "ok" | "processed" | "done" | "error" | "failed";
const TONE: Partial<Record<Tone, string>> = { processed: "s-processed", ok: "s-processed", done: "s-processed", failed: "s-failed", error: "s-failed" };

export function Status({ tone = "info", children, className }: { tone?: Tone; children?: ReactNode; className?: string }) {
  return <span className={cx("gw-status", TONE[tone], className)}>{children}</span>;
}

// A shared file's status as a pill tone: read is ok, needs a look is an error, the rest are info.
export const artifactTone = (status: string): Tone => (status === "processed" ? "ok" : status === "failed" ? "error" : "info");

export function Tag({ kind = "pi", children, className }: {
  kind?: "pi" | "overview" | "detail" | "workaround" | "issue" | "plain"; children?: ReactNode; className?: string;
}) {
  if (kind === "pi") return <span className={cx("gw-pi", className)}>{children || "Personal info"}</span>;
  if (kind === "overview" || kind === "detail") return <span className={cx("gw-passtag", `pass-${kind}`, className)}>{children}</span>;
  return <span className={cx("gw-tag", kind === "workaround" && "t-workaround", kind === "issue" && "t-issue", className)}>{children}</span>;
}

export function Chip({ children, onRemove, removeLabel = "Remove" }: { children?: ReactNode; onRemove?: () => void; removeLabel?: string }) {
  return (
    <span className="gw-chip">
      {children}
      {onRemove && <button type="button" aria-label={removeLabel} onClick={onRemove}>×</button>}
    </span>
  );
}

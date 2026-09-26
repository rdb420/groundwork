// Surfaces, lists and tables from the design system (design-system/components/data).
import type { FormHTMLAttributes, HTMLAttributes, KeyboardEvent, ReactNode } from "react";
import { Link } from "react-router-dom";
import { Status, cx } from "./core";

const CARD = { card: "gw-card", center: "gw-center-card", form: "gw-newboard" } as const;

// A white panel. "center" is the centred sign-in card; "form" has the survey top edge (Start a map).
export function Card({ variant = "card", as = "div", header, className, children, ...rest }: {
  variant?: keyof typeof CARD; as?: "div" | "li" | "section" | "form"; header?: ReactNode; className?: string; children?: ReactNode;
} & Omit<HTMLAttributes<HTMLElement> & FormHTMLAttributes<HTMLFormElement>, "className" | "children">) {
  const Tag = as;
  return <Tag className={cx(CARD[variant], className)} {...rest}>{header && <header>{header}</header>}{children}</Tag>;
}

// A big link card with a survey left edge; the home page's ways in.
export function Door({ title, to, children }: { title: ReactNode; to: string; children?: ReactNode }) {
  return <Link to={to} className="gw-door"><strong>{title}</strong><span>{children}</span></Link>;
}

export function Doors({ children }: { children?: ReactNode }) {
  return <div className="gw-doors">{children}</div>;
}

export type FileState = "ready" | "sending" | "done" | "error";

// One file waiting to be shared, with its questions as children.
export function FileCard({ name, size, state = "ready", note, onRemove, children }: {
  name: string; size?: string; state?: FileState; note?: ReactNode; onRemove?: () => void; children?: ReactNode;
}) {
  return (
    <div className={cx("gw-filecard", state === "done" && "f-done", state === "error" && "f-error")}>
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

export type Tile = { label: ReactNode; value: ReactNode; note?: ReactNode; small?: boolean };

// Stat tiles: a muted label over a big number. `small` is for words rather than numbers.
export function Tiles({ items }: { items: Tile[] }) {
  return (
    <dl className="gw-tiles">
      {items.map((t, i) => (
        <div key={i}><dt>{t.label}</dt><dd className={t.small ? "small" : undefined}>{t.value}</dd>{t.note && <span className="quiet">{t.note}</span>}</div>
      ))}
    </dl>
  );
}

// A borderless three-column list. Pass `items` (the second cell renders quiet) or <li> children.
export function Rows({ items, children }: { items?: ReactNode[][]; children?: ReactNode }) {
  return (
    <ul className="gw-rows">
      {items ? items.map((r, i) => <li key={i}>{r.map((c, j) => <span key={j} className={j === 1 ? "quiet" : undefined}>{c}</span>)}</li>) : children}
    </ul>
  );
}

// A table in its scrolling wrapper, for tables laid out by hand.
export function Table({ caption, className, children }: { caption?: ReactNode; className?: string; children?: ReactNode }) {
  return (
    <div className="gw-tablewrap">
      <table className={cx("gw-table", className)}>
        {caption && <caption className="quiet">{caption}</caption>}
        {children}
      </table>
    </div>
  );
}

export type Column<R> = { key: string; label: ReactNode; num?: boolean; render?: (row: R) => ReactNode };

// A column-driven table. With onRowClick, rows are focusable and open with Enter or Space.
export function DataTable<R extends { id?: string }>({ columns, rows, onRowClick, rowKey, caption }: {
  columns: Column<R>[]; rows: R[]; onRowClick?: (row: R) => void; rowKey?: (row: R) => string; caption?: ReactNode;
}) {
  const key = (e: KeyboardEvent, r: R) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onRowClick?.(r); }
  };
  const cell = (c: Column<R>, r: R) => {
    if (c.render) return c.render(r);
    const v = (r as Record<string, unknown>)[c.key] as ReactNode;
    return c.num && !v ? "·" : v;
  };
  return (
    <Table caption={caption}>
      <thead><tr>{columns.map((c) => <th key={c.key} scope="col" className={c.num ? "num" : undefined}>{c.label}</th>)}</tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={rowKey?.(r) ?? r.id ?? i} className={onRowClick ? "clickable" : undefined}
            onClick={onRowClick && (() => onRowClick(r))} tabIndex={onRowClick ? 0 : undefined} onKeyDown={onRowClick && ((e) => key(e, r))}>
            {columns.map((c) => {
              const v = (r as Record<string, unknown>)[c.key];
              return <td key={c.key} className={cx(c.num && "num", c.num && !c.render && !v && "zero") || undefined}>{cell(c, r)}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

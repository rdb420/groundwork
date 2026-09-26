// Form primitives from the design system (design-system/components/forms).
import { useRef, useState, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cx } from "./core";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx("gw-input", className)} {...rest} />;
}

export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx("gw-input", className)} {...rest} />;
}

export function TextArea({ className, rows = 2, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx("gw-input", className)} rows={rows} {...rest} />;
}

type Control = HTMLInputElement & HTMLSelectElement & HTMLTextAreaElement;
export type FieldProps = Omit<InputHTMLAttributes<Control>, "className" | "children"> & {
  label: ReactNode;
  hint?: ReactNode;
  as?: "input" | "select" | "textarea";
  /** For selects: [value, label] pairs or strings. Or pass <option> children. */
  options?: readonly (readonly [string, string] | string)[];
  rows?: number;
  className?: string;
  controlClassName?: string;
  children?: ReactNode;
};

// A bold label over a full-width control, with an optional quiet hint after the label.
export function Field({ label, hint, as = "input", options, children, className, controlClassName, rows, ...rest }: FieldProps) {
  const control = as === "select" ? (
    <Select className={controlClassName} {...rest}>
      {options ? options.map((o) => { const [v, l] = typeof o === "string" ? [o, o] : o; return <option key={v} value={v}>{l}</option>; }) : children}
    </Select>
  ) : as === "textarea" ? <TextArea className={controlClassName} rows={rows} {...rest} /> : <Input className={controlClassName} {...rest} />;
  return <label className={cx("gw-field", className)}>{label}{hint && <> <span className="quiet">{hint}</span></>}{control}</label>;
}

export function Check({ children, className, ...rest }: InputHTMLAttributes<HTMLInputElement> & { children?: ReactNode }) {
  return <label className={cx("gw-check", className)}><input type="checkbox" {...rest} />{children}</label>;
}

// Radio segments; the chosen one fills survey blue.
export function Segmented<V extends string>({ name, options, value, onChange, small, ariaLabel }: {
  name: string; options: readonly (readonly [V, ReactNode])[]; value?: V; onChange: (value: V) => void; small?: boolean; ariaLabel?: string;
}) {
  return (
    <div className={cx("gw-segmented", small && "small")} role="radiogroup" aria-label={ariaLabel}>
      {options.map(([v, l]) => (
        <label key={v} className={value === v ? "on" : undefined}>
          <input type="radio" name={name} value={v} checked={value === v} onChange={() => onChange(v)} />{l}
        </label>
      ))}
    </div>
  );
}

// Radio cards, each a bold label over a muted explanation.
export function OptionGroup<V extends string>({ name, legend, ariaLabelledBy, options, value, onChange }: {
  name: string; legend?: ReactNode; ariaLabelledBy?: string;
  options: readonly { value: V; label: ReactNode; hint?: ReactNode }[]; value?: V; onChange: (value: V) => void;
}) {
  return (
    <fieldset className="gw-options" aria-labelledby={ariaLabelledBy}>
      {legend && <legend>{legend}</legend>}
      {options.map((o) => (
        <label key={o.value} className={cx("gw-option", value === o.value && "on")}>
          <input type="radio" name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} />
          <strong>{o.label}</strong><span>{o.hint}</span>
        </label>
      ))}
    </fieldset>
  );
}

// A dashed drop target with a button fallback. Turns survey-soft while a file hovers over it.
export function DropZone({ onFiles, label = "Drop files here, or", button = "Choose files", accept, multiple = true }: {
  onFiles: (files: File[]) => void; label?: ReactNode; button?: ReactNode; accept?: string; multiple?: boolean;
}) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className={cx("gw-drop", over && "over")}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFiles(Array.from(e.dataTransfer.files)); }}>
      <p>{label}</p>
      <button type="button" className="gw-btn" onClick={() => input.current?.click()}>{button}</button>
      <input ref={input} type="file" hidden multiple={multiple} accept={accept}
        onChange={(e) => { onFiles(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
    </div>
  );
}

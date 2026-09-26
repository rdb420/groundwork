import * as React from "react";
/**
 * Bold label stacked over a full-width input, select or textarea. Hint renders quiet after the label ("Optional").
 * @startingPoint section="Forms" subtitle="Labelled input, select and textarea" viewport="700x360"
 */
export interface FieldProps {
  label: React.ReactNode;
  hint?: React.ReactNode;
  as?: "input" | "select" | "textarea";
  /** For selects: [value, label] pairs or strings. */
  options?: Array<[string, string] | string>;
  value?: string;
  defaultValue?: string;
  placeholder?: string;
  type?: string;
  required?: boolean;
  disabled?: boolean;
  onChange?: (e: React.ChangeEvent<any>) => void;
  children?: React.ReactNode;
  className?: string;
}
export function Field(props: FieldProps): JSX.Element;

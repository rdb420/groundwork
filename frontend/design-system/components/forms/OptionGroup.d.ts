import * as React from "react";
/** Stack of radio cards, each with a bold label and a muted one-line explanation. */
export interface OptionGroupProps {
  name: string;
  legend?: React.ReactNode;
  options: Array<{ value: string; label: React.ReactNode; hint?: React.ReactNode }>;
  value?: string;
  onChange?: (value: string) => void;
}
export function OptionGroup(props: OptionGroupProps): JSX.Element;

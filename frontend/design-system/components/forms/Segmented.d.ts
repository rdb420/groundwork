import * as React from "react";
/** Segmented radio group; the chosen segment fills survey blue. */
export interface SegmentedProps {
  name: string;
  options: Array<[string, string] | string>;
  value?: string;
  onChange?: (value: string) => void;
  small?: boolean;
  ariaLabel?: string;
}
export function Segmented(props: SegmentedProps): JSX.Element;

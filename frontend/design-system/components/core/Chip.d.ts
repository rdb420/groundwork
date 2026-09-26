import * as React from "react";
/** Marker-yellow chip for things the user added in their own words (new process names in the picker). */
export interface ChipProps {
  children?: React.ReactNode;
  onRemove?: () => void;
}
export function Chip(props: ChipProps): JSX.Element;

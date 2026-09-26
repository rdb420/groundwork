import * as React from "react";
/** Inline checkbox with a regular-weight sentence label. */
export interface CheckProps extends React.InputHTMLAttributes<HTMLInputElement> {
  children?: React.ReactNode;
}
export function Check(props: CheckProps): JSX.Element;

import * as React from "react";
/** Borderless three-column list (2fr 2fr auto) separated by hairlines. Second column renders quiet. */
export interface RowsProps {
  items: Array<React.ReactNode[]>;
}
export function Rows(props: RowsProps): JSX.Element;

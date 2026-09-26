import * as React from "react";
/** Right-hand 460px detail drawer with a text "Close" link. Use DetailList inside for label/value pairs. */
export interface DrawerProps {
  open?: boolean;
  title?: React.ReactNode;
  children?: React.ReactNode;
  onClose?: () => void;
  /** Render in-flow instead of fixed (for previews). */
  inline?: boolean;
}
export function Drawer(props: DrawerProps): JSX.Element | null;
export function DetailList(props: { items: Array<[React.ReactNode, React.ReactNode]> }): JSX.Element;

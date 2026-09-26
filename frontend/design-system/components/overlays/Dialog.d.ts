import * as React from "react";
/** Centred 460px dialog over an ink-tinted scrim. `inline` renders the box alone (for docs). */
export interface DialogProps {
  open?: boolean;
  title?: React.ReactNode;
  children?: React.ReactNode;
  actions?: React.ReactNode;
  onClose?: () => void;
  inline?: boolean;
}
export function Dialog(props: DialogProps): JSX.Element | null;

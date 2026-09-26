import * as React from "react";
/** Small 280px popover anchored under a button (position: relative parent). The only place Groundwork uses a soft shadow besides floating bars. */
export interface PopoverProps { open?: boolean; children?: React.ReactNode; style?: React.CSSProperties; }
export function Popover(props: PopoverProps): JSX.Element | null;

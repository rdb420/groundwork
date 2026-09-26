import * as React from "react";
/** Map structure finding. "fix" = boundary rule, "ask" = survey rule, "info" = line. */
export interface CheckItemProps { level?: "fix" | "ask" | "info"; children?: React.ReactNode; onShow?: () => void; }
export function CheckItem(props: CheckItemProps): JSX.Element;

import * as React from "react";
/** Floating bottom bar with a survey border for a batch decision on AI-proposed map changes ("Keep all" / "Discard all"). */
export interface CombineBarProps { children?: React.ReactNode; actions?: React.ReactNode; floating?: boolean; }
export function CombineBar(props: CombineBarProps): JSX.Element;

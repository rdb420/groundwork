import * as React from "react";
/** Tiny bar above a proposed canvas element. Survey blue for a new element ("Heard", "Reviewer", "Suggested") with Keep/Drop; dark ochre for a change to an existing one with Accept/Reject. */
export interface SuggestBarProps { who?: string; change?: string; onKeep?: () => void; onDrop?: () => void; style?: React.CSSProperties; }
export function SuggestBar(props: SuggestBarProps): JSX.Element;

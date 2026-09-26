import * as React from "react";
/** One proposed map change under a heard sentence. Marker-yellow rule = waiting for a click; green = landed automatically. */
export interface OpLineProps { auto?: boolean; confidence?: number | null; children?: React.ReactNode; actions?: React.ReactNode; }
export function OpLine(props: OpLineProps): JSX.Element;
/** Feed entry: the sentence as heard, with its OpLines. */
export function Heard(props: { said: React.ReactNode; children?: React.ReactNode }): JSX.Element;

import * as React from "react";
/** Decision table for a Rule step: condition columns, then green-tinted outcome columns. */
export interface RuleTableProps { name: string; inputs: string[]; outputs: string[]; rows: React.ReactNode[][]; }
export function RuleTable(props: RuleTableProps): JSX.Element;

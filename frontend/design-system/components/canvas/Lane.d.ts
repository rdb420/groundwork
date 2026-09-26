import * as React from "react";
/** Swimlane for a person/role inside the business; vertical header on the left. */
export interface LaneProps { label: string; width?: number; height?: number; children?: React.ReactNode; }
export function Lane(props: LaneProps): JSX.Element;
/** Collapsed pool for an outside party (tenant, bank, contractor): striped band. */
export function Pool(props: { label: string; width?: number; height?: number }): JSX.Element;
/** Ad hoc sub-process: dashed rounded boundary for work nobody can yet order. */
export function UnclearArea(props: { label: string; width?: number; height?: number }): JSX.Element;

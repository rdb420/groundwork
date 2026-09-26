import * as React from "react";
/** Canvas palette entry: a CSS glyph that miniaturises the element's shape, plus a plain-language label. itemKey matches Groundwork palette keys (start, task, user, manual, system, rule, sub, xor, and, wait, end, unclear, doc, store, lane, pool, stakeholder, application, workaround, issue, risk, control, metric, question, sticky, text, image). */
export interface PaletteItemProps { itemKey: string; children?: React.ReactNode; onClick?: () => void; }
export function PaletteItem(props: PaletteItemProps): JSX.Element;
export function PaletteGroup(props: { title: string; children?: React.ReactNode }): JSX.Element;
/** Connector type picker (Next step / Message / Note link). */
export function FlowPick(props: { flow?: "sequence" | "message" | "association"; on?: boolean; children?: React.ReactNode; onChange?: () => void }): JSX.Element;

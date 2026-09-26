import * as React from "react";
/** Tinted band with a 5px left rule stating which mapping pass is running. Overview = survey, detail = green. */
export interface PassbarProps { pass?: "overview" | "detail"; children?: React.ReactNode; }
export function Passbar(props: PassbarProps): JSX.Element;

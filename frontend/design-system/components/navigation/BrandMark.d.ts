import * as React from "react";
/** App identity: the Groundwork start-event→task mark (from Shell.tsx) plus app name, in currentColor. */
export interface BrandMarkProps { name?: string; big?: boolean; mark?: boolean; }
export function BrandMark(props: BrandMarkProps): JSX.Element;
export function GroundworkMark(props: { size?: number }): JSX.Element;
/** YSH Property logo image (white PNG from ysh.com.au). Pass a path relative to the consuming page. */
export function YshLockup(props: { src?: string; height?: number; onDark?: boolean }): JSX.Element;

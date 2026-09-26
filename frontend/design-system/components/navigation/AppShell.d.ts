import * as React from "react";
/**
 * Internal business app starter shell: 3.5rem header, 15rem desktop nav, content region, 3-item mobile nav below 48rem.
 * @startingPoint section="Navigation" subtitle="Internal app shell (header, side nav, mobile nav)" viewport="1100x520"
 */
export interface AppShellNavGroup { title?: string; items: Array<[string, string]>; }
export interface AppShellProps {
  appName?: string;
  status?: React.ReactNode;
  nav?: AppShellNavGroup[];
  active?: string;
  onNavigate?: (key: string) => void;
  mobileNav?: Array<[string, string]>;
  children?: React.ReactNode;
}
export function AppShell(props: AppShellProps): JSX.Element;

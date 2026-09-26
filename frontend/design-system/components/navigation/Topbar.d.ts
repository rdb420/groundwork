import * as React from "react";
/**
 * Sticky white top bar: brand left, text nav with a 3px survey underline on the active link, name + "Sign out" right.
 * @startingPoint section="Navigation" subtitle="Groundwork top bar" viewport="1100x70"
 */
export interface TopbarProps {
  appName?: string;
  links: Array<[string, string]>;
  active?: string;
  onNavigate?: (key: string) => void;
  who?: React.ReactNode;
  onSignOut?: () => void;
}
export function Topbar(props: TopbarProps): JSX.Element;

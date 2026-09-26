import * as React from "react";
/** Big link card with a 6px survey-blue left edge; the home page's two ways in. Wrap several in <Doors>. */
export interface DoorProps {
  title: React.ReactNode;
  children?: React.ReactNode;
  href?: string;
  onClick?: (e: React.MouseEvent) => void;
}
export function Door(props: DoorProps): JSX.Element;
export function Doors(props: { children?: React.ReactNode }): JSX.Element;

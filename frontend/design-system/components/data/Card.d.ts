import * as React from "react";
/**
 * White panel with a 1.5px line border. "card" = 10px radius; "center" = the centred sign-in/verify card; "form" = 4px radius with a 6px survey-blue top edge (Start a map).
 */
export interface CardProps {
  variant?: "card" | "center" | "form";
  header?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}
export function Card(props: CardProps): JSX.Element;

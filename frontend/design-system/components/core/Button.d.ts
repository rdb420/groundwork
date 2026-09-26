import * as React from "react";
/**
 * Groundwork button. One primary per view; default is the white outline button; link is an underlined text button.
 * @startingPoint section="Core" subtitle="Primary, default and link buttons" viewport="700x220"
 */
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "primary" | "link";
  size?: "default" | "small";
  /** Pressed/selected look used in toggles (survey-soft fill). */
  on?: boolean;
  /** Render as an anchor styled as a button. */
  href?: string;
  children?: React.ReactNode;
}
export function Button(props: ButtonProps): JSX.Element;

import * as React from "react";
/**
 * Small labels. "pi" is the boundary-red outline used on anything holding personal information.
 * "overview"/"detail" are the map pass tags. "workaround"/"issue"/"plain" are the tiny tags hung under canvas tasks.
 */
export interface TagProps {
  kind?: "pi" | "overview" | "detail" | "workaround" | "issue" | "plain";
  children?: React.ReactNode;
  className?: string;
}
export function Tag(props: TagProps): JSX.Element;

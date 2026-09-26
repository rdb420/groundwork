import * as React from "react";
/** One pending upload: filename, size, state, and its per-file questions as children. */
export interface FileCardProps {
  name: string;
  size?: string;
  state?: "ready" | "sending" | "done" | "error";
  note?: React.ReactNode;
  onRemove?: () => void;
  children?: React.ReactNode;
}
export function FileCard(props: FileCardProps): JSX.Element;

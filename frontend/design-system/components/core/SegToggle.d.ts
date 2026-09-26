import * as React from "react";
/** Joined row of buttons that toggles one side panel on or off (Board bar: Live, Rules, Document, Recording, AI drafts). */
export interface SegToggleProps {
  items: Array<[string, string] | { value: string; label: string }>;
  value: string | null;
  /** Clicking the active item passes null (panel closes). */
  onChange?: (value: string | null) => void;
  ariaLabel?: string;
}
export function SegToggle(props: SegToggleProps): JSX.Element;

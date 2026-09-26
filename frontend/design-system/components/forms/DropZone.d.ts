import * as React from "react";
/**
 * Dashed drop target with a "Choose files" fallback button. Turns survey-soft while a file hovers.
 * @startingPoint section="Forms" subtitle="File drop zone" viewport="700x200"
 */
export interface DropZoneProps {
  onFiles?: (files: File[]) => void;
  label?: string;
  button?: string;
  accept?: string;
  multiple?: boolean;
}
export function DropZone(props: DropZoneProps): JSX.Element;

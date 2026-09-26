import * as React from "react";
/** Pulsing boundary-red dot + bold label + Stop. The only looping animation in the system. */
export interface RecordingProps { label?: string; onStop?: () => void; }
export function Recording(props: RecordingProps): JSX.Element;

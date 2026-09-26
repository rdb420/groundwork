import * as React from "react";
/** Parking-lot entry: 3px left rule coloured by category, tiny bold category label, text, actions. Render inside a <ul style={{listStyle:"none",padding:0}}>. */
export interface ParkingItemProps {
  category?: "issue" | "workaround" | "exception" | "rule" | "question" | "detail";
  children?: React.ReactNode;
  actions?: React.ReactNode;
}
export function ParkingItem(props: ParkingItemProps): JSX.Element;

import * as React from "react";
/** Row of stat tiles: muted label over a 1.6rem bold number, optional quiet note. */
export interface TilesProps {
  items: Array<{ label: React.ReactNode; value: React.ReactNode; note?: React.ReactNode }>;
}
export function Tiles(props: TilesProps): JSX.Element;

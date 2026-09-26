import * as React from "react";
/**
 * White table with muted small headers and hairline rows; rows highlight survey-soft on hover and open a drawer on click. Numeric columns right-align with tabular figures and show "·" for zero.
 * @startingPoint section="Data" subtitle="Clickable data table" viewport="700x260"
 */
export interface DataTableColumn { key: string; label: React.ReactNode; num?: boolean; render?: (row: any) => React.ReactNode; }
export interface DataTableProps {
  columns: DataTableColumn[];
  rows: Array<Record<string, any>>;
  onRowClick?: (row: any) => void;
  caption?: React.ReactNode;
}
export function DataTable(props: DataTableProps): JSX.Element;

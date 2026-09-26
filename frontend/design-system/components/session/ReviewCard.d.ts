import * as React from "react";
/** Survey-soft card holding a reviewer model's proposed corrections. Children are ReviewOp rows. */
export interface ReviewCardProps { time: string; model?: string; summary?: React.ReactNode; actions?: React.ReactNode; children?: React.ReactNode; }
export function ReviewCard(props: ReviewCardProps): JSX.Element;
export function ReviewOp(props: { done?: boolean; reason?: React.ReactNode; actions?: React.ReactNode; children?: React.ReactNode }): JSX.Element;

import React from "react";
const LABEL = { issue: "Problem", workaround: "Workaround", exception: "Exception or rework", rule: "Rule or condition", question: "Question", detail: "Detail" };
export function ParkingItem({ category = "detail", children, actions }) {
  return <li className={"gw-pk pk-" + category}><span className="gw-pk-cat">{LABEL[category] || category}</span><span>{children}</span>{actions && <span className="gw-opbtns">{actions}</span>}</li>;
}

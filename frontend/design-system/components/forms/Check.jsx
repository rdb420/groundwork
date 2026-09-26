import React from "react";
export function Check({ children, ...rest }) {
  return <label className="gw-check"><input type="checkbox" {...rest} />{children}</label>;
}

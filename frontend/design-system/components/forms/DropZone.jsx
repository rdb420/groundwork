import React from "react";
export function DropZone({ onFiles, label = "Drop files here, or", button = "Choose files", accept, multiple = true }) {
  const [over, setOver] = React.useState(false);
  const input = React.useRef(null);
  return (
    <div className={"gw-drop" + (over ? " over" : "")}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFiles && onFiles(Array.from(e.dataTransfer.files)); }}>
      <p>{label}</p>
      <button type="button" className="gw-btn" onClick={() => input.current && input.current.click()}>{button}</button>
      <input ref={input} type="file" hidden multiple={multiple} accept={accept} onChange={(e) => { onFiles && onFiles(Array.from(e.target.files || [])); e.target.value = ""; }} />
    </div>
  );
}

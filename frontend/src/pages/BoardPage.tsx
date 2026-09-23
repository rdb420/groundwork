import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addEdge, Background, BackgroundVariant, ConnectionMode, Controls, MiniMap, ReactFlow, ReactFlowProvider,
  useEdgesState, useNodesState, useReactFlow, type Connection, type Edge, type Node,
} from "@xyflow/react";
import { api, type BoardRow, type Draft, type Me } from "../lib/api";
import { useSession } from "../lib/session";
import { KNOWN_TYPES, ProposalContext, nodeTypes } from "../canvas/nodes";
import { acceptOp, applyOp, edgeStyle, rejectOp, type Op } from "../canvas/ops";
import LivePanel, { type Check } from "../canvas/LivePanel";
import RulesPanel, { type RuleTable } from "../canvas/RulesPanel";
import { LAYERS, type Layer } from "../canvas/kinds";
import DocumentPanel from "../canvas/DocumentPanel";
import { FLOWS, PALETTE, type Flow, type PaletteItem } from "../canvas/palette";
import SessionPanel from "../canvas/SessionPanel";
import AIPanel from "../canvas/AIPanel";

const newId = () => Math.random().toString(36).slice(2, 10);

function styleEdge(e: Edge): Edge {
  const flow = ((e.data as { flow?: Flow } | undefined)?.flow ?? "sequence") as Flow;
  return { ...e, ...edgeStyle(flow in FLOWS ? flow : "sequence", !!(e.data as any)?.suggested), data: { ...(e.data || {}), flow } };
}

// Strip view-only state before saving so autosave doesn't fire on every click.
const clean = (nodes: Node[], edges: Edge[]) => ({
  nodes: nodes.map(({ selected: _s, dragging: _d, ...n }) => n),
  edges: edges.map(({ selected: _s, ...e }) => e),
});

function Canvas({ board, me }: { board: BoardRow; me: Me }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(board.doc?.nodes ?? []);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>((board.doc?.edges ?? []).map(styleEdge));
  const [title, setTitle] = useState(board.title);
  const [flow, setFlow] = useState<Flow>("sequence");
  const [save, setSave] = useState<"saved" | "saving" | "pending" | "conflict" | "error">("saved");
  const [panel, setPanel] = useState<"live" | "rules" | "session" | "ai" | "doc" | null>(me.live_enabled ? "live" : "session");
  const [sessionPass, setSessionPass] = useState<"overview" | "detail">((board.session_pass as any) || "detail");
  const [checks, setChecks] = useState<Check[]>([]);
  const [rules, setRules] = useState<RuleTable[]>((board.rules as RuleTable[]) || []);
  const [rulesProposal, setRulesProposal] = useState<RuleTable[] | null>(null);
  const [hidden, setHidden] = useState<Set<Layer>>(new Set());
  const [layersOpen, setLayersOpen] = useState(false);
  const [recording, setRecording] = useState(false);
  const [docKind, setDocKind] = useState<"sop" | "wi">("sop");
  const [docProposal, setDocProposal] = useState<Draft | null>(null);
  const lastTouched = useRef<string | null>(null);
  // Live panels work asynchronously; refs give them the canvas as it is now, not as it was.
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  nodesRef.current = nodes;
  edgesRef.current = edges;
  const getGraph = useCallback(() => ({ nodes: nodesRef.current, edges: edgesRef.current }), []);
  const setGraph = useCallback((g: { nodes: Node[]; edges: Edge[] }) => {
    nodesRef.current = g.nodes;
    edgesRef.current = g.edges;
    setNodes(g.nodes);
    setEdges(g.edges);
  }, []);
  // Keep what the live model just touched in view, without jumping around when it already is.
  const reveal = useCallback((ids: string[]) => {
    const el = document.querySelector(".react-flow")?.getBoundingClientRect();
    if (!el) return;
    const tl = screenToFlowPosition({ x: el.left, y: el.top });
    const br = screenToFlowPosition({ x: el.right, y: el.bottom });
    const out = nodesRef.current.filter((n) => ids.includes(n.id)).some((n) =>
      n.position.x < tl.x || n.position.y < tl.y || n.position.x + ((n.width as number) || 150) > br.x || n.position.y + ((n.height as number) || 60) > br.y);
    if (out) setTimeout(() => fitView({ padding: 0.15, duration: 300, maxZoom: 1 }), 30);
  }, []);
  // Select and show elements a check or a feed item points at.
  const focus = useCallback((ids: string[]) => {
    setNodes((ns) => ns.map((n) => ({ ...n, selected: ids.includes(n.id) })));
    setTimeout(() => fitView({ nodes: ids.map((id) => ({ id })), padding: 0.4, duration: 300, maxZoom: 1.2 }), 30);
  }, []);
  const proposals = useMemo(() => ({
    accept: (opId: string) => setGraph(acceptOp(getGraph(), opId)),
    reject: (opId: string) => setGraph(rejectOp(getGraph(), opId)),
  }), []);
  const version = useRef(board.version);
  const lastSaved = useRef(JSON.stringify(clean(board.doc?.nodes ?? [], board.doc?.edges ?? [])));
  const imageInput = useRef<HTMLInputElement>(null);
  const pendingImagePos = useRef<{ x: number; y: number } | null>(null);
  const { screenToFlowPosition, getViewport, fitView } = useReactFlow();

  const persist = useCallback(async () => {
    const doc = { ...clean(nodes, edges), viewport: getViewport() };
    const key = JSON.stringify(clean(nodes, edges));
    if (key === lastSaved.current && title === board.title) return;
    setSave("saving");
    try {
      const r = await api.send<{ version: number }>("PUT", `/api/boards/${board.id}`, { version: version.current, doc, title });
      version.current = r.version;
      lastSaved.current = key;
      board.title = title;
      setSave("saved");
    } catch (e) {
      setSave((e as { status?: number }).status === 409 ? "conflict" : "error");
    }
  }, [nodes, edges, title, board, getViewport]);

  useEffect(() => {
    if (save === "conflict") return;
    const key = JSON.stringify(clean(nodes, edges));
    if (key === lastSaved.current && title === board.title) return;
    setSave("pending");
    const t = setTimeout(persist, 1200);
    return () => clearTimeout(t);
  }, [nodes, edges, title]);

  // Structure checks run on the server so the reviewer and the facilitator see the same findings.
  useEffect(() => {
    const t = setTimeout(() => {
      api.send<Check[]>("POST", `/api/boards/${board.id}/checks`, { doc: clean(nodes, edges) }).then(setChecks).catch(() => {});
    }, 900);
    return () => clearTimeout(t);
  }, [nodes, edges, sessionPass, rules]);

  // A combined map arrives as a set of changes from the combiner. Lay them out once, on first open.
  useEffect(() => {
    api.get<Draft[]>(`/api/boards/${board.id}/drafts`).then(async (ds) => {
      const d = ds.find((x) => x.mode === "combine" && x.status === "draft");
      if (!d) return;
      let g = getGraph();
      for (const op of (d.proposal?.changes ?? []) as Op[]) g = applyOp(g, op);
      setGraph(g);
      await api.send("POST", `/api/drafts/${d.id}/accept`);
      setTimeout(() => fitView({ padding: 0.15, duration: 300, maxZoom: 1 }), 60);
    });
  }, [board.id]);

  // Layers hide context without touching the saved map.
  const hiddenTypes = useMemo(() => new Set(Array.from(hidden).flatMap((l) => LAYERS[l].types as readonly string[])), [hidden]);
  const displayNodes = useMemo(() => (hidden.size === 0 ? nodes : nodes.map((n) => {
    const hide = hiddenTypes.has(n.type || "") || (hidden.has("suggestions") && !!((n.data as any)?.suggested));
    return hide ? { ...n, hidden: true } : n;
  })), [nodes, hidden, hiddenTypes]);
  const ruleSteps = useMemo(() => nodes.filter((n) => n.type === "bpmnTask" && (n.data as any)?.taskKind === "rule"), [nodes]);

  const onConnect = useCallback((c: Connection) => setEdges((es) => addEdge(styleEdge({ ...c, id: `e${newId()}`, data: { flow } } as Edge), es)), [flow]);

  const place = (item: PaletteItem, pos: { x: number; y: number }) => {
    if (item.type === "image") {
      pendingImagePos.current = pos;
      imageInput.current?.click();
      return;
    }
    setNodes((ns) => [...ns, {
      id: `${item.key}-${newId()}`, type: item.type, position: pos, data: { label: "", ...(item.data || {}) },
      ...(item.size ? { width: item.size.width, height: item.size.height } : {}),
      ...(item.zIndex !== undefined ? { zIndex: item.zIndex } : {}),
    }]);
  };

  const addImage = async (file: File, pos: { x: number; y: number }) => {
    const id = `img-${newId()}`;
    setNodes((ns) => [...ns, { id, type: "image", position: pos, data: { label: file.name }, width: 240, height: 180 }]);
    const form = new FormData();
    form.append("file", file);
    form.append("meta", JSON.stringify({ title: file.name, kind: "photo", layer: "actual", personal_info: board.personal_info ? "yes" : "unsure", board_id: board.id }));
    try {
      const a = await api.upload<{ id: string }>("/api/artifacts", form);
      setNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, artifactId: a.id } } : n)));
    } catch (e) {
      setNodes((ns) => ns.filter((n) => n.id !== id));
      alert((e as Error).message);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const pos = screenToFlowPosition({ x: e.clientX, y: e.clientY });
    const key = e.dataTransfer.getData("application/gw-node");
    if (key) return place(PALETTE.find((p) => p.key === key)!, pos);
    Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith("image/")).forEach((f, i) => addImage(f, { x: pos.x + i * 30, y: pos.y + i * 30 }));
  };

  // Click-to-add lays new elements out left to right in rows of four, so repeated clicks
  // build a rough sequence instead of stacking on one spot. The grid restarts after twelve.
  const clickCount = useRef(0);
  const center = () => {
    const el = document.querySelector(".react-flow")!.getBoundingClientRect();
    const k = clickCount.current++ % 12;
    const zoom = getViewport().zoom;
    return screenToFlowPosition({ x: el.left + el.width * 0.12 + (k % 4) * 200 * zoom, y: el.top + el.height * 0.2 + Math.floor(k / 4) * 150 * zoom });
  };

  const onEdgeDoubleClick = (_: React.MouseEvent, edge: Edge) => {
    const label = prompt("Label this connection (for example: Yes, No, Over $500)", (edge.label as string) || "");
    if (label !== null) setEdges((es) => es.map((x) => (x.id === edge.id ? { ...x, label } : x)));
  };

  // Place AI-proposed elements to the right of the map, marked as suggestions.
  const applyProposal = (d: Draft) => {
    const pn = d.proposal?.nodes ?? [];
    const maxX = nodes.reduce((m, n) => Math.max(m, n.position.x + ((n.width as number) || 160)), 0);
    const refMap: Record<string, string> = {};
    const added: Node[] = pn.map((p: any, i: number) => {
      const type = KNOWN_TYPES.has(p.type) ? p.type : "sticky";
      const id = `ai-${newId()}`;
      refMap[p.ref ?? id] = id;
      return { id, type, position: { x: maxX + 220, y: 40 + i * 120 }, data: { label: p.label ?? "", suggested: true, evidence: p.evidence ?? "" },
        ...(type === "bpmnTask" ? { width: 150, height: 64 } : type === "sticky" ? { width: 170, height: 110 } : {}) };
    });
    const ids = new Set(nodes.map((n) => n.id));
    const addedEdges: Edge[] = (d.proposal?.edges ?? []).map((e: any) => ({ source: refMap[e.from] ?? e.from, target: refMap[e.to] ?? e.to, label: e.label }))
      .filter((e) => (ids.has(e.source) || Object.values(refMap).includes(e.source)) && (ids.has(e.target) || Object.values(refMap).includes(e.target)))
      .map((e) => styleEdge({ id: `e${newId()}`, ...e, data: { flow: "sequence", suggested: true } } as Edge));
    setNodes((ns) => [...ns, ...added]);
    setEdges((es) => [...es, ...addedEdges]);
    setTimeout(() => fitView({ duration: 400 }), 50);
  };

  const groups = useMemo(() => Array.from(new Set(PALETTE.map((p) => p.group))), []);
  const saveText = { saved: "Saved", saving: "Saving…", pending: "Unsaved changes", conflict: "Someone else changed this map", error: "Couldn't save. Retrying on your next change." }[save];

  return (
    <div className={`board ${panel ? "with-panel" : ""}`}>
      <header className="board-bar">
        <Link to="/maps" className="back">Maps</Link>
        <input className="board-title" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Map title" />
        {board.personal_info && <span className="pi">Personal info</span>}
        <span className={`passtag pass-${sessionPass}`}>{sessionPass === "overview" ? "Overview" : board.perspective ? `Detail: ${board.perspective}` : "Detail"}</span>
        <span className={`savestate ${save}`} role="status">{saveText}</span>
        {save === "conflict" && <button onClick={() => location.reload()}>Reload</button>}
        <div className="spacer" />
        <div className="layers">
          <button className={hidden.size ? "on" : ""} aria-expanded={layersOpen} onClick={() => setLayersOpen((o) => !o)}>Layers{hidden.size ? ` (${hidden.size} hidden)` : ""}</button>
          {layersOpen && (
            <div className="layers-pop" role="group" aria-label="Show on the map">
              {(Object.keys(LAYERS) as Layer[]).map((l) => (
                <label key={l} className="check"><input type="checkbox" checked={!hidden.has(l)} onChange={() => setHidden((h) => { const n = new Set(h); if (n.has(l)) n.delete(l); else n.add(l); return n; })} />{LAYERS[l].label}</label>
              ))}
              <p className="quiet small">The standard path always shows. Hidden elements stay on the map.</p>
            </div>
          )}
        </div>
        <div className="seg-toggle" role="group" aria-label="Panels">
          {([["live", "Live"], ["rules", `Rules${rulesProposal ? " •" : ""}`], ["doc", `Document${docProposal ? " •" : ""}`], ["session", `Recording${recording ? " ●" : ""}`], ["ai", "AI drafts"]] as const).map(([k, l]) => (
            <button key={k} className={panel === k ? "on" : ""} onClick={() => setPanel(panel === k ? null : k)}>{l}</button>
          ))}
        </div>
      </header>

      <aside className="palette" aria-label="Elements">
        {groups.map((g) => (
          <div key={g} className="pgroup">
            <h4>{g}</h4>
            {PALETTE.filter((p) => p.group === g).map((p) => (
              <button key={p.key} draggable className={`pitem pi-${p.key}`} title={`Drag onto the map, or click to add ${p.label.toLowerCase()} in the middle`}
                onDragStart={(e) => { e.dataTransfer.setData("application/gw-node", p.key); e.dataTransfer.effectAllowed = "move"; }}
                onClick={() => place(p, center())}>
                <span className="glyph" aria-hidden="true" />{p.label}
              </button>
            ))}
          </div>
        ))}
        <div className="pgroup">
          <h4>Connect with</h4>
          {(Object.keys(FLOWS) as Flow[]).map((f) => (
            <label key={f} className={`flowpick ${flow === f ? "on" : ""}`}>
              <input type="radio" name="flow" checked={flow === f} onChange={() => setFlow(f)} />
              <span className={`flowline fl-${f}`} aria-hidden="true" />{FLOWS[f].label}
            </label>
          ))}
        </div>
        <input ref={imageInput} type="file" accept="image/*" hidden onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) addImage(f, pendingImagePos.current ?? center());
          e.target.value = "";
        }} />
      </aside>

      <div className="flow" onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }} onDrop={onDrop}>
        <ProposalContext.Provider value={proposals}>
        <ReactFlow nodes={displayNodes} edges={edges}
          onNodeClick={(_, n) => { lastTouched.current = n.id; }} onNodeDragStop={(_, n) => { lastTouched.current = n.id; }} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
          onConnect={onConnect} onEdgeDoubleClick={onEdgeDoubleClick} connectionMode={ConnectionMode.Loose}
          defaultViewport={board.doc?.viewport ?? undefined} fitView={!board.doc?.viewport && (board.doc?.nodes?.length ?? 0) > 0} fitViewOptions={{ maxZoom: 1 }} minZoom={0.2} snapToGrid snapGrid={[10, 10]}
          deleteKeyCode={["Backspace", "Delete"]} proOptions={{ hideAttribution: false }}>
          <Background variant={BackgroundVariant.Lines} gap={40} color="var(--grid)" />
          <Controls />
          <MiniMap pannable zoomable nodeStrokeWidth={2} />
        </ReactFlow>
        </ProposalContext.Provider>
        {nodes.length === 0 && (
          <div className="empty-hint">
            <p>Start with what kicks the work off. Drag a <strong>Start</strong> onto the map, then add the steps in the order they really happen.</p>
            <p className="quiet">Double-click anything to label it. Drag from the dots on an element's edge to connect it to the next one.</p>
          </div>
        )}
      </div>

      {/* Panels stay mounted when hidden, so listening and recording carry on while you switch tabs. */}
      <aside className="sidepanel" hidden={!panel} aria-label="Session tools">
        <div hidden={panel !== "live"}>
          <LivePanel boardId={board.id} me={me} personalInfo={board.personal_info} docKind={docKind} getGraph={getGraph} setGraph={setGraph}
            sessionPass={sessionPass} setSessionPass={setSessionPass} perspective={board.perspective || ""} checks={checks}
            lastTouched={lastTouched} onDocumentProposed={setDocProposal} onRulesProposed={setRulesProposal} reveal={reveal} focus={focus} />
        </div>
        <div hidden={panel !== "rules"}>
          <RulesPanel boardId={board.id} ruleSteps={ruleSteps} proposed={rulesProposal} clearProposed={() => setRulesProposal(null)} onSaved={setRules} />
        </div>
        <div hidden={panel !== "session"}>
          <SessionPanel boardId={board.id} transcriptionOn={me.transcription_enabled} onRecordingChange={setRecording} />
        </div>
        <div hidden={panel !== "doc"}>
          <DocumentPanel boardId={board.id} docKind={docKind} setDocKind={setDocKind} proposal={docProposal} clearProposal={() => setDocProposal(null)} />
        </div>
        <div hidden={panel !== "ai"}>
          <AIPanel boardId={board.id} enabled={me.ai_enabled} recording={recording} beforeGenerate={persist} onApply={applyProposal} />
        </div>
      </aside>
    </div>
  );
}

export default function BoardPage() {
  const { id } = useParams();
  const { me } = useSession();
  const [board, setBoard] = useState<BoardRow | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get<BoardRow>(`/api/boards/${id}`).then(setBoard).catch((e) => setError(e.message)); }, [id]);
  if (error) return <div className="center-card"><p className="error">{error}</p><Link to="/maps">Back to maps</Link></div>;
  if (!board || !me) return <div className="loading">Loading map…</div>;
  return <ReactFlowProvider><Canvas board={board} me={me} /></ReactFlowProvider>;
}

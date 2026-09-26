import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "@xyflow/react/dist/style.css";
import "../design-system/styles.css";
import "./styles.css";
import { SessionProvider, useSession } from "./lib/session";
import Shell from "./components/Shell";
import Login from "./pages/Login";
import Verify from "./pages/Verify";
import Home from "./pages/Home";
import Share from "./pages/Share";
import Library from "./pages/Library";
import Boards from "./pages/Boards";
import BoardPage from "./pages/BoardPage";
import CoveragePage from "./pages/Coverage";
import ProcessList from "./pages/ProcessList";
import Retention from "./pages/Retention";
import People from "./pages/People";
import Terms from "./pages/Terms";
import Pipeline from "./pages/Pipeline";

const RANK = { contributor: 0, analyst: 1, admin: 2 } as const;

// The server enforces every role check; this only keeps people off pages that would refuse them.
function Protected({ children, role = "contributor" }: { children: React.ReactNode; role?: keyof typeof RANK }) {
  const { me, loading } = useSession();
  if (loading) return <div className="gw-loading">Loading…</div>;
  if (!me) return <Navigate to="/login" replace />;
  if (RANK[me.role] < RANK[role]) return <Navigate to="/" replace />;
  return <>{children}</>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/auth/verify" element={<Verify />} />
          <Route element={<Protected><Shell /></Protected>}>
            <Route index element={<Home />} />
            <Route path="share" element={<Share />} />
            <Route path="library" element={<Library />} />
            <Route path="maps" element={<Boards />} />
            <Route path="coverage" element={<Protected role="analyst"><CoveragePage /></Protected>} />
            <Route path="processes" element={<Protected role="analyst"><ProcessList /></Protected>} />
            <Route path="retention" element={<Protected role="admin"><Retention /></Protected>} />
            <Route path="people" element={<Protected role="admin"><People /></Protected>} />
            <Route path="terms" element={<Protected role="analyst"><Terms /></Protected>} />
            <Route path="pipeline" element={<Protected role="admin"><Pipeline /></Protected>} />
          </Route>
          <Route path="/maps/:id" element={<Protected><BoardPage /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  </StrictMode>,
);

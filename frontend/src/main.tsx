import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "@xyflow/react/dist/style.css";
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

function Protected({ children }: { children: React.ReactNode }) {
  const { me, loading } = useSession();
  if (loading) return <div className="loading">Loading…</div>;
  if (!me) return <Navigate to="/login" replace />;
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
          </Route>
          <Route path="/maps/:id" element={<Protected><BoardPage /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  </StrictMode>,
);

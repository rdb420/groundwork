import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useSession } from "../lib/session";
import ProfilePrompt from "./ProfilePrompt";

export default function Shell() {
  const { me } = useSession();
  const nav = useNavigate();
  const signOut = async () => {
    await api.send("POST", "/api/auth/logout");
    nav("/login");
    location.reload();
  };
  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label="Home">
          <Mark /> {me?.app_name}
        </NavLink>
        <nav aria-label="Main">
          <NavLink to="/share">Share files</NavLink>
          <NavLink to="/library">{me && me.role !== "contributor" ? "Library" : "My files"}</NavLink>
          <NavLink to="/maps">Process maps</NavLink>
          {me && me.role !== "contributor" && <NavLink to="/coverage">Coverage</NavLink>}
          {me && me.role !== "contributor" && <NavLink to="/processes">Process list</NavLink>}
          {me?.role === "admin" && <NavLink to="/retention">Retention</NavLink>}
        </nav>
        <div className="who">
          <span>{me?.display_name || me?.email}</span>
          <button className="link" onClick={signOut}>Sign out</button>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
      {me && !me.display_name && <ProfilePrompt />}
    </div>
  );
}

export function Mark() {
  return (
    <svg width="26" height="18" viewBox="0 0 34 22" aria-hidden="true">
      <circle cx="7" cy="11" r="5.5" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <path d="M12.5 11H19" stroke="currentColor" strokeWidth="2.5" />
      <rect x="19" y="3" width="14" height="16" rx="3" fill="currentColor" />
    </svg>
  );
}

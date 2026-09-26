import { Outlet, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useSession } from "../lib/session";
import { Topbar } from "../ui";
import ProfilePrompt from "./ProfilePrompt";

export default function Shell() {
  const { me } = useSession();
  const nav = useNavigate();
  const signOut = async () => {
    await api.send("POST", "/api/auth/logout");
    nav("/login");
    location.reload();
  };
  const analyst = !!me && me.role !== "contributor";
  const admin = me?.role === "admin";
  const links: [string, string][] = [
    ["/share", "Share files"],
    ["/library", analyst ? "Library" : "My files"],
    ["/maps", "Process maps"],
    ...(analyst ? [["/coverage", "Coverage"], ["/processes", "Process list"], ["/terms", "Terms"]] as [string, string][] : []),
    ...(admin ? [["/pipeline", "Pipeline"], ["/people", "People"], ["/retention", "Retention"]] as [string, string][] : []),
  ];
  return (
    <div>
      <Topbar appName={me?.app_name} links={links} who={me?.display_name || me?.email} onSignOut={signOut} />
      <main className="gw-page">
        <Outlet />
      </main>
      {me && !me.display_name && <ProfilePrompt />}
    </div>
  );
}

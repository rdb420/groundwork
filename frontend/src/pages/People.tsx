import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../lib/session";
import { Button, Status, Table } from "../ui";

type Person = { id: string; email: string; display_name: string; team: string; role: string; blocked: boolean; last_seen_at: string | null; sessions: number };
const ROLE: Record<string, string> = { contributor: "Staff", analyst: "Analyst", admin: "Admin" };

// Who has signed in. Roles come from the server settings; here an admin can sign someone out
// everywhere or remove their access, for example when they leave.
export default function People() {
  const { me } = useSession();
  const [rows, setRows] = useState<Person[] | null>(null);
  const [error, setError] = useState("");
  const load = () => api.get<Person[]>("/api/admin/users").then(setRows).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const act = async (fn: () => Promise<unknown>) => {
    setError("");
    try { await fn(); await load(); } catch (e) { setError((e as Error).message); }
  };
  const signOut = (p: Person) => act(() => api.send("POST", `/api/admin/users/${p.id}/sign-out`));
  const access = (p: Person, blocked: boolean) => {
    if (blocked && !confirm(`Remove ${p.display_name || p.email}'s access? They'll be signed out and can't sign in again until you restore it.`)) return;
    return act(() => api.send("POST", `/api/admin/users/${p.id}/access`, { blocked }));
  };

  if (!rows) return error ? <p className="error">{error}</p> : <p className="quiet">Loading…</p>;
  return (
    <div>
      <h1>People</h1>
      <p className="lede">Everyone who has signed in. Admins and analysts are set in the server settings (GW_ADMIN_EMAILS, GW_ANALYST_EMAILS).</p>
      {error && <p className="error" role="alert">{error}</p>}
      <Table>
          <thead><tr><th scope="col">Person</th><th scope="col">Role</th><th scope="col">Last seen</th><th scope="col">Signed in on</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id}>
                <th scope="row">{p.display_name || p.email}<div className="quiet">{p.display_name ? p.email : ""}{p.team ? ` · ${p.team}` : ""}</div></th>
                <td>{p.blocked ? <Status tone="error">Access removed</Status> : ROLE[p.role] ?? p.role}</td>
                <td>{p.last_seen_at ? new Date(p.last_seen_at).toLocaleString("en-AU") : "Never"}</td>
                <td className="num">{p.sessions} device{p.sessions === 1 ? "" : "s"}</td>
                <td className="gw-row-actions">
                  {p.sessions > 0 && <Button onClick={() => signOut(p)}>Sign out everywhere</Button>}
                  {p.id !== me?.id && (p.blocked
                    ? <Button onClick={() => access(p, false)}>Restore access</Button>
                    : <Button onClick={() => access(p, true)}>Remove access</Button>)}
                </td>
              </tr>
            ))}
          </tbody>
      </Table>
    </div>
  );
}

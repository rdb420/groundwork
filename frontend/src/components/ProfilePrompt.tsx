import { useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../lib/session";

// First sign-in: ask for a name and team so uploads and maps carry a person, not an address.
export default function ProfilePrompt() {
  const { refresh } = useSession();
  const [name, setName] = useState("");
  const [team, setTeam] = useState("");
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.send("PUT", "/api/auth/me", { display_name: name, team });
    await refresh();
  };
  return (
    <div className="scrim" role="dialog" aria-modal="true" aria-labelledby="pp-title">
      <form className="dialog" onSubmit={save}>
        <h2 id="pp-title">Before you start</h2>
        <p>Tell us who you are so we know who to thank, and who to ask when a file needs explaining.</p>
        <label>Your name<input required value={name} onChange={(e) => setName(e.target.value)} autoFocus /></label>
        <label>Your team or role<input value={team} onChange={(e) => setTeam(e.target.value)} placeholder="For example: property manager, accounts" /></label>
        <button className="primary" type="submit">Save and continue</button>
      </form>
    </div>
  );
}

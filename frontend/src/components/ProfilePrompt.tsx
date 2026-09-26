import { useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../lib/session";
import { Button, Dialog, Field } from "../ui";

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
    <Dialog title="Before you start" onSubmit={save}>
      <p>Tell us who you are so we know who to thank, and who to ask when a file needs explaining.</p>
      <Field label="Your name" required value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      <Field label="Your team or role" value={team} onChange={(e) => setTeam(e.target.value)} placeholder="For example: property manager, accounts" />
      <Button variant="primary" type="submit">Save and continue</Button>
    </Dialog>
  );
}

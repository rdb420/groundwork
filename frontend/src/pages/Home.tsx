import { useEffect, useState } from "react";
import { api, type Artifact } from "../lib/api";
import { STATUS } from "../lib/labels";
import { useSession } from "../lib/session";
import { Door, Doors, Rows, Status, artifactTone } from "../ui";

export default function Home() {
  const { me } = useSession();
  const [mine, setMine] = useState<Artifact[] | null>(null);
  useEffect(() => { api.get<Artifact[]>("/api/artifacts?mine=true").then(setMine); }, []);
  const first = me?.display_name?.split(" ")[0];
  return (
    <div>
      <h1>{first ? `Hi ${first}.` : "Hi."} What does your week actually involve?</h1>
      <p className="lede">
        {me?.org_name} is working out how the business runs today, in detail, before changing anything.
        The quickest way to help is to share the files you work from, including the unofficial ones.
      </p>
      <Doors>
        <Door to="/share" title="Share files">
          Spreadsheets, checklists, templates, reports, photos of the whiteboard. Tell us what each one is for.
        </Door>
        <Door to="/maps" title="Map a process">
          Draw how a piece of work flows, on your own or in a session with the AI lead. You can record the conversation.
        </Door>
      </Doors>
      <section>
        <h2>What you've shared</h2>
        {mine === null ? <p className="quiet">Loading…</p> : mine.length === 0 ? (
          <p className="quiet">Nothing yet. Your first file is the most useful one, because it shows us where to look next.</p>
        ) : (
          <Rows items={mine.slice(0, 8).map((a) => [
            a.title,
            a.processes.map((p) => p.name).join(", ") || "No process yet",
            <Status tone={artifactTone(a.status)}>{STATUS[a.status] ?? a.status}</Status>,
          ])} />
        )}
      </section>
    </div>
  );
}

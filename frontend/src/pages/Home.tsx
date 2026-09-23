import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Artifact } from "../lib/api";
import { STATUS } from "../lib/labels";
import { useSession } from "../lib/session";

export default function Home() {
  const { me } = useSession();
  const [mine, setMine] = useState<Artifact[] | null>(null);
  useEffect(() => { api.get<Artifact[]>("/api/artifacts?mine=true").then(setMine); }, []);
  const first = me?.display_name?.split(" ")[0];
  return (
    <div className="home">
      <h1>{first ? `Hi ${first}.` : "Hi."} What does your week actually involve?</h1>
      <p className="lede">
        {me?.org_name} is working out how the business runs today, in detail, before changing anything.
        The quickest way to help is to share the files you work from, including the unofficial ones.
      </p>
      <div className="doors">
        <Link to="/share" className="door">
          <strong>Share files</strong>
          <span>Spreadsheets, checklists, templates, reports, photos of the whiteboard. Tell us what each one is for.</span>
        </Link>
        <Link to="/maps" className="door">
          <strong>Map a process</strong>
          <span>Draw how a piece of work flows, on your own or in a session with the AI lead. You can record the conversation.</span>
        </Link>
      </div>
      <section>
        <h2>What you've shared</h2>
        {mine === null ? <p className="quiet">Loading…</p> : mine.length === 0 ? (
          <p className="quiet">Nothing yet. Your first file is the most useful one, because it shows us where to look next.</p>
        ) : (
          <ul className="rows">
            {mine.slice(0, 8).map((a) => (
              <li key={a.id}>
                <span>{a.title}</span>
                <span className="quiet">{a.processes.map((p) => p.name).join(", ") || "No process yet"}</span>
                <span className={`status s-${a.status}`}>{STATUS[a.status] ?? a.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

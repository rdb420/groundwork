import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { Button, Card, LinkButton } from "../ui";

// The emailed link lands here. Signing in needs a click so mail scanners that pre-open
// links can't use up the one-time token.
export default function Verify() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      await api.send("POST", "/api/auth/verify", { token });
      location.href = "/";
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };
  return (
    <Card variant="center">
      <h1>Sign in to Groundwork</h1>
      {error ? (
        <>
          <p className="error" role="alert">{error}</p>
          <LinkButton variant="primary" href="/login">Request a new link</LinkButton>
        </>
      ) : (
        <Button variant="primary" onClick={go} disabled={!token || busy} autoFocus>
          {busy ? "Signing in…" : "Continue"}
        </Button>
      )}
    </Card>
  );
}

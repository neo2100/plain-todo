import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Loader2 } from "lucide-react";

export default function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUser } = useAuth();
  const processed = useRef(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = location.hash || "";
    const sessionId = new URLSearchParams(hash.replace(/^#/, "")).get("session_id");
    if (!sessionId) {
      navigate("/login", { replace: true });
      return;
    }

    (async () => {
      try {
        const { data } = await api.post(
          "/auth/session",
          { session_id: sessionId },
          { headers: { "X-Session-ID": sessionId } }
        );
        setUser(data);
        window.history.replaceState(null, "", "/");
        navigate("/", { replace: true });
      } catch (e) {
        setError("Sign-in failed. Please try again.");
        setTimeout(() => navigate("/login", { replace: true }), 1500);
      }
    })();
  }, [location.hash, navigate, setUser]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-background">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" strokeWidth={1.5} />
      <p className="font-mono text-sm text-muted-foreground">
        {error || "Signing you in\u2026"}
      </p>
    </div>
  );
}

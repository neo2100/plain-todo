import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CheckSquare, Loader2 } from "lucide-react";

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "signin") await login(email, password);
      else await register(email, password, name);
      navigate("/", { replace: true });
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setBusy(false);
    }
  };

  const googleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background relative z-10">
      {/* Left: hero */}
      <div className="hidden lg:flex flex-col justify-between p-12 border-r border-border bg-card relative overflow-hidden">
        <div className="flex items-center gap-2">
          <CheckSquare className="h-5 w-5" strokeWidth={1.5} />
          <span className="font-cabinet font-extrabold text-lg tracking-tight">Plain Todo</span>
        </div>
        <div className="relative">
          <img
            src="https://images.unsplash.com/photo-1587522384446-64daf3e2689a?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200"
            alt="Minimal workspace"
            className="w-full h-72 object-cover grayscale contrast-125 border border-border"
          />
        </div>
        <div className="max-w-md">
          <h1 className="font-cabinet font-extrabold text-4xl leading-[1.05] tracking-tight">
            One plain page for the day.
          </h1>
          <p className="mt-4 text-muted-foreground font-mono text-sm leading-relaxed">
            Type tasks as <span className="text-foreground">[ ] checkboxes</span>, add
            <span className="text-foreground"> - bullets</span> and links. Unfinished tasks roll
            over automatically. Park the rest in your backlog.
          </p>
        </div>
      </div>

      {/* Right: form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm animate-fade-up">
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <CheckSquare className="h-5 w-5" strokeWidth={1.5} />
            <span className="font-cabinet font-extrabold text-lg tracking-tight">Plain Todo</span>
          </div>

          <h2 className="font-cabinet font-bold text-2xl tracking-tight">
            {mode === "signin" ? "Welcome back" : "Create your canvas"}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {mode === "signin" ? "Sign in to your todo canvas." : "Start a fresh, private canvas."}
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            {mode === "signup" && (
              <div className="space-y-1.5">
                <Label htmlFor="name" className="text-xs font-mono uppercase tracking-wide text-muted-foreground">Name</Label>
                <Input id="name" data-testid="name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ada Lovelace" className="rounded-none font-mono" />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs font-mono uppercase tracking-wide text-muted-foreground">Email</Label>
              <Input id="email" data-testid="email-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" className="rounded-none font-mono" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-xs font-mono uppercase tracking-wide text-muted-foreground">Password</Label>
              <Input id="password" data-testid="password-input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="rounded-none font-mono" />
            </div>

            {error && (
              <p data-testid="auth-error" className="text-sm text-destructive font-mono">{error}</p>
            )}

            <Button type="submit" data-testid="auth-submit-btn" disabled={busy} className="w-full rounded-none h-11 font-mono">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : mode === "signin" ? "Sign in" : "Sign up"}
            </Button>
          </form>

          <div className="flex items-center gap-3 my-6">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs font-mono text-muted-foreground uppercase">or</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <Button type="button" data-testid="google-login-btn" onClick={googleLogin} variant="outline" className="w-full rounded-none h-11 font-mono gap-2">
            <svg className="h-4 w-4" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.76h3.57c2.08-1.92 3.28-4.74 3.28-8.09Z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.76c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"/><path fill="#FBBC05" d="M5.84 14.11a6.6 6.6 0 0 1 0-4.22V7.05H2.18a11 11 0 0 0 0 9.9l3.66-2.84Z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.05l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38Z"/></svg>
            Continue with Google
          </Button>

          <p className="mt-8 text-sm text-muted-foreground text-center">
            {mode === "signin" ? "No account yet?" : "Already have an account?"}{" "}
            <button
              type="button"
              data-testid="toggle-auth-mode"
              onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); }}
              className="text-foreground underline underline-offset-4 hover:opacity-70 transition-opacity"
            >
              {mode === "signin" ? "Sign up" : "Sign in"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}

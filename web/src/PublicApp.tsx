import { ArrowRight, Bot, Check, GitBranch, LockKeyhole, MailCheck, ShieldCheck, UsersRound } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "./auth";

type Navigate = (path: string, replace?: boolean) => void;

function Brand({ navigate }: { navigate: Navigate }) {
  return <button className="beta-brand" onClick={() => navigate("/")}><span><GitBranch size={19} /></span>PairPilot</button>;
}

export function LandingPage({ navigate }: { navigate: Navigate }) {
  return <div className="public-page">
    <header className="public-nav"><Brand navigate={navigate} /><div><button className="text-button" onClick={() => navigate("/sign-in")}>Sign in</button><button className="primary-button" onClick={() => navigate("/sign-up")}>Create your agent</button></div></header>
    <main className="hero">
      <div className="hero-copy"><span className="eyebrow">REAL PEOPLE · USER-OWNED AGENTS · DUAL APPROVAL</span><h1>Tell your Agent what you need. Let Agents find the right people.</h1><p>Publish a privacy-safe request, let your Personal Agent compare and coordinate with other real users’ Agents, then decide together before anything becomes a match.</p><div className="hero-actions"><button className="primary-button large" onClick={() => navigate("/sign-up")}>Start with your own Agent <ArrowRight size={17} /></button><button className="secondary-button large" onClick={() => navigate("/demo")}>See the synthetic demo</button></div><div className="trust-row"><span><ShieldCheck size={16} /> Private details stay private</span><span><UsersRound size={16} /> Both humans must approve</span><span><LockKeyhole size={16} /> Rooms unlock after a match</span></div></div>
      <div className="hero-product-card"><div className="agent-orb"><Bot size={28} /></div><small>YOUR PERSONAL AGENT</small><h2>“I’m looking for an ICML roommate in Seoul, July 6–10.”</h2><div className="agent-progress"><span><Check size={15} /> Private request created</span><span><Check size={15} /> Public post ready for review</span><span className="active"><span className="pulse" /> Waiting for your approval</span></div></div>
    </main>
  </div>;
}

export function AuthPage({ mode, navigate }: { mode: "sign-in" | "sign-up" | "forgot"; navigate: Navigate }) {
  const auth = useAuth();
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [confirmation, setConfirmation] = useState("");
  const [terms, setTerms] = useState(false); const [privacy, setPrivacy] = useState(false); const [adult, setAdult] = useState(false);
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState(""); const [localError, setLocalError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setLocalError("");
    try {
      if (mode === "forgot") { await auth.resetPassword(email); setNotice("Password reset email sent. Check your inbox."); }
      else if (mode === "sign-up") { if (password !== confirmation) throw new Error("Passwords do not match."); if (!terms || !privacy || !adult) throw new Error("Accept the Terms, Privacy Policy, and adult eligibility confirmation."); await auth.signUp(email, password); navigate("/verify-email"); }
      else { await auth.signIn(email, password); navigate("/app/agent"); }
    } catch (reason) { setLocalError(reason instanceof Error ? reason.message : "Could not continue."); }
    finally { setBusy(false); }
  }
  const title = mode === "sign-up" ? "Create your Personal Agent" : mode === "forgot" ? "Reset your password" : "Welcome back";
  return <div className="auth-page"><div className="auth-top"><Brand navigate={navigate} /></div><form className="auth-card" onSubmit={submit}><div className="auth-icon">{mode === "forgot" ? <MailCheck /> : <Bot />}</div><h1>{title}</h1><p>{mode === "sign-up" ? "One verified account, one persistent user-owned Agent." : mode === "forgot" ? "We’ll send a secure reset link to your email." : "Continue to your private Agent workspace."}</p>{!auth.configured && !auth.loading ? <div className="setup-warning">Authentication setup is being finalized. Registration will open as soon as Firebase is connected.</div> : null}<label>Email<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>{mode !== "forgot" ? <label>Password<input type="password" autoComplete={mode === "sign-up" ? "new-password" : "current-password"} minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required /></label> : null}{mode === "sign-up" ? <><label>Confirm password<input type="password" autoComplete="new-password" minLength={8} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required /></label><label className="check-label"><input type="checkbox" checked={terms} onChange={(event) => setTerms(event.target.checked)} /> I accept the <button type="button" onClick={() => navigate("/terms")}>Terms</button>.</label><label className="check-label"><input type="checkbox" checked={privacy} onChange={(event) => setPrivacy(event.target.checked)} /> I accept the <button type="button" onClick={() => navigate("/privacy")}>Privacy Policy</button>.</label><label className="check-label"><input type="checkbox" checked={adult} onChange={(event) => setAdult(event.target.checked)} /> I am 18 or older for travel/accommodation matching.</label></> : null}{localError || auth.error ? <div className="form-error">{localError || auth.error}</div> : null}{notice ? <div className="form-notice">{notice}</div> : null}<button className="primary-button full" disabled={busy || !auth.configured}>{busy ? "Working…" : mode === "sign-up" ? "Create account" : mode === "forgot" ? "Send reset email" : "Sign in"}</button>{mode === "sign-in" ? <button type="button" className="text-button" onClick={() => navigate("/forgot-password")}>Forgot password?</button> : null}<div className="auth-switch">{mode === "sign-up" ? <>Already have an account? <button type="button" onClick={() => navigate("/sign-in")}>Sign in</button></> : <>New to PairPilot? <button type="button" onClick={() => navigate("/sign-up")}>Create an account</button></>}</div></form></div>;
}

export function VerifyEmailPage({ navigate }: { navigate: Navigate }) {
  const auth = useAuth(); const [status, setStatus] = useState("Check your inbox and open the verification link."); const [resendAfter, setResendAfter] = useState(0);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search); const code = params.get("oobCode");
    if (code) void auth.verifyEmailCode(code).then(() => setStatus("Email verified. Your Personal Agent is ready.")).catch(() => setStatus("This verification link is invalid or expired."));
  }, [auth]);
  useEffect(() => { if (!resendAfter) return; const timer = window.setInterval(() => setResendAfter((value) => Math.max(0, value - 1)), 1000); return () => window.clearInterval(timer); }, [resendAfter]);
  return <div className="auth-page"><div className="auth-top"><Brand navigate={navigate} /></div><div className="auth-card centered"><div className="auth-icon"><MailCheck /></div><h1>Verify your email</h1><p>{status}</p><button className="primary-button full" onClick={async () => { await auth.refreshUser(); navigate(auth.user?.emailVerified ? "/onboarding" : "/verify-email"); }}>I’ve verified — continue</button><button className="text-button" disabled={resendAfter > 0 || !auth.user} onClick={() => { void auth.resendVerification().then(() => { setStatus("A new verification email was sent."); setResendAfter(60); }).catch((reason: Error) => setStatus(reason.message)); }}>{resendAfter ? `Resend in ${resendAfter}s` : "Resend verification email"}</button><button className="text-button" onClick={() => navigate("/sign-in")}>Back to sign in</button></div></div>;
}

export function LegalPage({ kind, navigate }: { kind: "privacy" | "terms"; navigate: Navigate }) {
  return <div className="public-page legal"><header className="public-nav"><Brand navigate={navigate} /></header><main><h1>{kind === "privacy" ? "Privacy" : "Terms"}</h1><p>PairPilot is an early public beta. It helps users discover and coordinate with other users through personal Agents. It does not verify identity, guarantee compatibility, make bookings, process payments, or provide safety guarantees.</p><h2>Human control</h2><p>Publishing, disclosure of identity, commitments, and matches require explicit user action. Both participants must independently approve the same current proposal.</p><h2>Safety</h2><p>Use your judgment before meeting or sharing personal information. You can block or report another participant at any time.</p></main></div>;
}

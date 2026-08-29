import DemoApp from "./App";
import { AuthProvider, useAuth } from "./auth";
import { BetaApp } from "./BetaApp";
import { AuthPage, LandingPage, LegalPage, VerifyEmailPage } from "./PublicApp";
import { useRouter } from "./router";

function Routes() {
  const { path, navigate } = useRouter(); const auth = useAuth();
  if (path.startsWith("/app/") || path === "/onboarding") return <BetaApp />;
  if (path === "/sign-up") return <AuthPage mode="sign-up" navigate={navigate} />;
  if (path === "/sign-in") return <AuthPage mode="sign-in" navigate={navigate} />;
  if (path === "/forgot-password") return <AuthPage mode="forgot" navigate={navigate} />;
  if (path === "/verify-email") return <VerifyEmailPage navigate={navigate} />;
  if (path === "/privacy" || path === "/terms") return <LegalPage kind={path === "/privacy" ? "privacy" : "terms"} navigate={navigate} />;
  if (path === "/demo") return <div className="demo-frame"><div className="demo-banner"><strong>Synthetic product demo</strong><span>Qi, Maya, Lena, and all activity below are demonstration data—not real users.</span><button onClick={() => navigate("/")}>Exit demo</button></div><DemoApp /></div>;
  if (auth.user?.emailVerified) return <LandingPage navigate={navigate} />;
  return <LandingPage navigate={navigate} />;
}

export default function RootApp() { return <AuthProvider><Routes /></AuthProvider>; }

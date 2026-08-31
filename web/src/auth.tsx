/* eslint-disable react-refresh/only-export-components */
import {
  applyActionCode,
  createUserWithEmailAndPassword,
  getAuth,
  onAuthStateChanged,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signOut,
  type User,
} from "firebase/auth";
import { getApps, initializeApp } from "firebase/app";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, authenticatedApi } from "./api";

interface BrowserAuthConfig {
  firebaseConfigured: boolean;
  firebase: {
    apiKey: string;
    authDomain: string;
    projectId: string;
    appId: string;
    messagingSenderId: string;
    storageBucket: string;
  };
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  configured: boolean;
  error: string;
  signUp: (email: string, password: string) => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signOutUser: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  resendVerification: () => Promise<void>;
  verifyEmailCode: (code: string) => Promise<void>;
  refreshUser: () => Promise<void>;
  request: <T>(path: string, init?: RequestInit) => Promise<T>;
  streamRequest: (path: string, init?: RequestInit) => Promise<Response>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function messageFrom(reason: unknown): string {
  if (reason instanceof Error) return reason.message.replace(/^Firebase:\s*/i, "");
  return "Authentication failed. Please try again.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [configured, setConfigured] = useState(false);
  const [error, setError] = useState("");
  const [authReady, setAuthReady] = useState<ReturnType<typeof getAuth> | null>(null);

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;
    void api<BrowserAuthConfig>("/api/auth/config")
      .then((config) => {
        if (!config.firebaseConfigured) {
          setConfigured(false);
          setLoading(false);
          return;
        }
        const app = getApps()[0] || initializeApp(config.firebase);
        const auth = getAuth(app);
        setAuthReady(auth);
        setConfigured(true);
        unsubscribe = onAuthStateChanged(auth, (nextUser) => {
          setUser(nextUser);
          setLoading(false);
        });
      })
      .catch((reason) => {
        setError(messageFrom(reason));
        setLoading(false);
      });
    return () => unsubscribe?.();
  }, []);

  const requireAuth = useCallback(() => {
    if (!authReady) throw new Error("Authentication is not configured yet.");
    return authReady;
  }, [authReady]);

  const signUp = useCallback(async (email: string, password: string) => {
    setError("");
    try {
      const credential = await createUserWithEmailAndPassword(requireAuth(), email, password);
      await sendEmailVerification(credential.user, { url: `${window.location.origin}/verify-email` });
    } catch (reason) {
      const message = messageFrom(reason); setError(message); throw new Error(message);
    }
  }, [requireAuth]);

  const signIn = useCallback(async (email: string, password: string) => {
    setError("");
    try { await signInWithEmailAndPassword(requireAuth(), email, password); }
    catch (reason) { const message = messageFrom(reason); setError(message); throw new Error(message); }
  }, [requireAuth]);

  const signOutUser = useCallback(async () => {
    setError("");
    await signOut(requireAuth());
    setUser(null);
  }, [requireAuth]);

  const resetPassword = useCallback(async (email: string) => {
    setError("");
    await sendPasswordResetEmail(requireAuth(), email, { url: `${window.location.origin}/sign-in` });
  }, [requireAuth]);

  const resendVerification = useCallback(async () => {
    const current = requireAuth().currentUser;
    if (!current) throw new Error("Sign in before requesting another verification email.");
    await sendEmailVerification(current, { url: `${window.location.origin}/verify-email` });
  }, [requireAuth]);

  const verifyEmailCode = useCallback(async (code: string) => {
    await applyActionCode(requireAuth(), code);
    if (requireAuth().currentUser) await requireAuth().currentUser?.reload();
    setUser(requireAuth().currentUser);
  }, [requireAuth]);

  const refreshUser = useCallback(async () => {
    await requireAuth().currentUser?.reload();
    setUser(requireAuth().currentUser);
  }, [requireAuth]);

  const request = useCallback(async <T,>(path: string, init?: RequestInit) => {
    const current = requireAuth().currentUser;
    if (!current) throw new Error("Your session ended. Sign in again.");
    const token = await current.getIdToken(true);
    return authenticatedApi<T>(path, token, init);
  }, [requireAuth]);

  const streamRequest = useCallback(async (path: string, init?: RequestInit) => {
    const current = requireAuth().currentUser;
    if (!current) throw new Error("Your session ended. Sign in again.");
    const token = await current.getIdToken(true);
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        Authorization: `Bearer ${token}`,
        ...init?.headers,
      },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string };
      throw new Error(body.detail || `Request failed (${response.status})`);
    }
    return response;
  }, [requireAuth]);

  const value = useMemo(() => ({
    user, loading, configured, error, signUp, signIn, signOutUser,
    resetPassword, resendVerification, verifyEmailCode, refreshUser, request,
    streamRequest,
  }), [configured, error, loading, refreshUser, request, resendVerification, resetPassword, signIn, signOutUser, signUp, streamRequest, user, verifyEmailCode]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

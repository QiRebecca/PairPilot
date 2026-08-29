import { Bot, LoaderCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, post } from "./api";
import { AppShell } from "./components/AppShell";
import type { ReviewForm } from "./components/ProductComponents";
import { AgentHomePage } from "./pages/AgentHomePage";
import { ExplorePage } from "./pages/ExplorePage";
import { AuditPage, MatchesPage, MemoryPage, NetworkPage, RequestsPage } from "./pages/OtherPages";
import { RequestWorkspacePage } from "./pages/RequestWorkspacePage";
import { CoordinationRoomPage, RoomsPage } from "./pages/RoomsPages";
import { useRouter } from "./router";
import type { DraftReview, IntentPost, OSBootstrap, PresentationDirective } from "./types";

const allowedDirectiveActions = new Set([
  "OPEN_TASK", "SHOW_TASK_STATUS", "SHOW_POST", "SHOW_RELATED_POSTS",
  "SHOW_CANDIDATE_COMPARISON", "OPEN_COORDINATION_ROOM", "SHOW_PROPOSAL",
  "SHOW_APPROVAL", "SHOW_NETWORK_PATH", "SHOW_RELATIONSHIP", "SHOW_MEMORY",
  "FILTER_EXPLORE", "CREATE_POST_DRAFT",
]);

export default function App() {
  const { path, navigate } = useRouter();
  const [data, setData] = useState<OSBootstrap | null>(null);
  const [review, setReview] = useState<DraftReview | null>(null);
  const [reviewTaskId, setReviewTaskId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const next = await api<OSBootstrap>("/api/os/bootstrap");
    setData(next);
    return next;
  }, []);

  useEffect(() => {
    if (path === "/") navigate("/agent", true);
  }, [navigate, path]);

  useEffect(() => {
    void refresh().catch((reason: Error) => setError(reason.message));
  }, [refresh]);

  const taskId = path.startsWith("/requests/") ? path.split("/")[2] : "";
  const currentTask = useMemo(() => data?.tasks.find((task) => task.task_id === taskId), [data?.tasks, taskId]);

  useEffect(() => {
    if (!currentTask || currentTask.status !== "DRAFT") {
      setReview(null);
      setReviewTaskId("");
      return;
    }
    if (reviewTaskId === currentTask.task_id) return;
    void api<DraftReview>(`/api/intents/${currentTask.intent_id}/review`)
      .then((next) => { setReview(next); setReviewTaskId(currentTask.task_id); })
      .catch((reason: Error) => setError(reason.message));
  }, [currentTask, reviewTaskId]);

  const act = useCallback(async (work: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await work(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Something went wrong"); }
    finally { setBusy(false); }
  }, []);

  const handleDirective = useCallback((directive: PresentationDirective) => {
    if (!allowedDirectiveActions.has(directive.action)) {
      setError("Qi requested an unsupported presentation action.");
      return;
    }
    if (directive.presentation !== "NAVIGATE") return;
    if (directive.action === "OPEN_TASK" && directive.task_id) navigate(`/requests/${directive.task_id}`);
    else if (directive.action === "OPEN_COORDINATION_ROOM" && directive.entity_ids[0]) navigate(`/rooms/${directive.entity_ids[0]}`);
    else if (directive.action === "FILTER_EXPLORE") navigate(`/explore?task=${directive.task_id || ""}`);
    else if (["SHOW_MEMORY"].includes(directive.action)) navigate("/memory");
    else if (["SHOW_NETWORK_PATH", "SHOW_RELATIONSHIP"].includes(directive.action)) navigate("/network");
  }, [navigate]);

  const sendMessage = useCallback((content: string, scopedTaskId?: string) => {
    void act(async () => {
      const response = await post<{ task?: { task_id: string }; directive?: PresentationDirective }>("/api/os/messages", { content, task_id: scopedTaskId || null });
      const next = await refresh();
      if (response.task?.task_id) navigate(`/requests/${response.task.task_id}`);
      else if (response.directive?.presentation === "NAVIGATE") handleDirective(response.directive);
      else if (scopedTaskId && !next.tasks.some((task) => task.task_id === scopedTaskId)) navigate("/agent");
    });
  }, [act, handleDirective, navigate, refresh]);

  const startForIntent = useCallback((intentId: string) => {
    setBusy(true); setError("");
    const stream = new EventSource(`/api/demo/run/stream?intent_id=${encodeURIComponent(intentId)}`);
    stream.addEventListener("snapshot", (event) => {
      const demoState = JSON.parse((event as MessageEvent).data) as OSBootstrap["demoState"];
      setData((current) => current ? { ...current, demoState } : current);
    });
    stream.addEventListener("complete", () => { stream.close(); setBusy(false); void refresh(); });
    stream.onerror = () => { stream.close(); setBusy(false); setError("The live agent stream ended unexpectedly. Current state is preserved."); void refresh(); };
  }, [refresh]);

  const publish = useCallback((form: ReviewForm) => {
    void act(async () => {
      const result = await post<{ intent: IntentPost }>("/api/intents/publish", {
        intent_id: form.intentId, public_title: form.title, public_summary: form.summary,
        event: form.event, location: form.location, date_start: form.dateStart,
        date_end: form.dateEnd, roommate_gender_preference: form.gender,
        public_requirements: form.publicRequirements.split(",").map((item) => item.trim()).filter(Boolean),
        quiet_overnight_compatibility_importance: form.quietImportance,
        maximum_additional_cost_usd: form.maximumCost,
        partial_date_overlap_allowed: form.partialOverlap,
      });
      setReview(null); setReviewTaskId(""); await refresh();
      startForIntent(result.intent.intent_id || form.intentId);
    });
  }, [act, refresh, startForIntent]);

  const approvalPayload = useMemo(() => {
    const request = data?.demoState?.approvalRequests?.at(-1);
    const run = data?.demoState?.run;
    return request && run ? { run_id: run.runId, proposal_id: request.proposalId, proposal_version: request.proposalVersion } : null;
  }, [data]);
  const approve = useCallback(() => { void act(async () => { if (!approvalPayload) return; await post("/api/demo/approve", { ...approvalPayload, confirmation: `APPROVE VERSION ${approvalPayload.proposal_version}` }); await refresh(); }); }, [act, approvalPayload, refresh]);
  const reject = useCallback(() => { void act(async () => { if (!approvalPayload) return; await post("/api/demo/reject", approvalPayload); await refresh(); }); }, [act, approvalPayload, refresh]);

  const roomId = path.startsWith("/rooms/") ? path.split("/")[2] : "";
  const currentRoom = data?.rooms.find((room) => room.room_id === roomId);
  const roomMode = (mode: string) => { if (!currentRoom) return; void act(async () => { await post(`/api/os/rooms/${currentRoom.room_id}/mode`, { mode }); await refresh(); }); };
  const roomSend = (action: string, content: string) => { if (!currentRoom) return; void act(async () => { await post(`/api/os/rooms/${currentRoom.room_id}/messages`, { action, content }); await refresh(); }); };
  const memoryAction = (id: string, action: string) => void act(async () => {
    await post(`/api/os/memories/${id}`, {
      action,
      ...(action === "RESTRICT_SCOPE" ? { scope: "hotel-sharing-only" } : {}),
    });
    await refresh();
  });
  const evaluate = (postIntent: IntentPost) => {
    const task = data?.tasks.find((item) => !["COMPLETED", "CANCELLED"].includes(item.status));
    const message = `Evaluate this active post for my request: ${postIntent.public_title} (${postIntent.intent_id}).`;
    sendMessage(message, task?.task_id);
    if (task) navigate(`/requests/${task.task_id}`);
    else navigate("/agent");
  };

  let page = <div className="loading-page"><LoaderCircle className="spin" size={25} /><span>Loading your Personal Agent…</span></div>;
  if (data) {
    if (path === "/agent" || path === "/") page = <AgentHomePage data={data} busy={busy} onSend={(content) => sendMessage(content)} onNavigate={navigate} onDirective={handleDirective} onApprove={approve} onReject={reject} />;
    else if (path === "/requests") page = <RequestsPage data={data} onNavigate={navigate} />;
    else if (currentTask) page = <RequestWorkspacePage data={data} task={currentTask} review={reviewTaskId === currentTask.task_id ? review : null} busy={busy} onSend={(content) => sendMessage(content, currentTask.task_id)} onPublish={publish} onNavigate={navigate} onDirective={handleDirective} onApprove={approve} onReject={reject} />;
    else if (path === "/explore") page = <ExplorePage data={data} onNavigate={navigate} onEvaluate={evaluate} />;
    else if (path === "/rooms") page = <RoomsPage data={data} onNavigate={navigate} />;
    else if (currentRoom) page = <CoordinationRoomPage data={data} room={currentRoom} busy={busy} onNavigate={navigate} onMode={roomMode} onSend={roomSend} />;
    else if (path === "/matches") page = <MatchesPage data={data} onNavigate={navigate} />;
    else if (path === "/network") page = <NetworkPage data={data} />;
    else if (path === "/memory") page = <MemoryPage data={data} onAction={memoryAction} />;
    else if (path === "/audit") page = <AuditPage data={data} />;
    else page = <div className="not-found"><Bot size={27} /><h1>That workspace doesn’t exist.</h1><button onClick={() => navigate("/agent")}>Return to Qi Agent</button></div>;
  }

  return <AppShell data={data} path={path} error={error} busy={busy} onNavigate={navigate} onNewRequest={() => navigate("/agent")} onDismissError={() => setError("")}>{page}</AppShell>;
}

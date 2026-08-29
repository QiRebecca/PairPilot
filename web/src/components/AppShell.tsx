import {
  Bot,
  CheckCircle2,
  Compass,
  GitBranch,
  Inbox,
  LayoutList,
  MemoryStick,
  MessageSquareMore,
  Network,
  Plus,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import type { ReactNode } from "react";
import type { OSBootstrap, TaskWorkspace } from "../types";

const statusLabel: Record<string, string> = {
  NEEDS_DECISION: "Decision",
  ACTIVE_NEGOTIATION: "Active",
  SEARCHING: "Searching",
  DRAFT: "Draft",
  COMPLETED: "Done",
  CANCELLED: "Cancelled",
};

function NavItem({
  active,
  icon: Icon,
  label,
  badge,
  onClick,
}: {
  active: boolean;
  icon: typeof Bot;
  label: string;
  badge?: number;
  onClick: () => void;
}) {
  return (
    <button className={`side-nav-item ${active ? "active" : ""}`} onClick={onClick}>
      <Icon size={17} />
      <span>{label}</span>
      {badge ? <b>{badge}</b> : null}
    </button>
  );
}

function TaskLink({
  task,
  active,
  onClick,
}: {
  task: TaskWorkspace;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`task-link ${active ? "active" : ""}`} onClick={onClick}>
      <span className={`task-dot state-${task.status.toLowerCase()}`} />
      <span>
        <strong>{task.title}</strong>
        <small>{statusLabel[task.status] || task.status}</small>
      </span>
      {task.status === "NEEDS_DECISION" ? <b>1</b> : null}
    </button>
  );
}

export function AppShell({
  data,
  path,
  error,
  busy,
  onNavigate,
  onNewRequest,
  onDismissError,
  children,
}: {
  data: OSBootstrap | null;
  path: string;
  error: string;
  busy: boolean;
  onNavigate: (path: string) => void;
  onNewRequest: () => void;
  onDismissError: () => void;
  children: ReactNode;
}) {
  const tasks = data?.tasks || [];
  const decisionTasks = tasks.filter((task) => task.status === "NEEDS_DECISION");
  const activeTasks = tasks.filter((task) =>
    ["ACTIVE_NEGOTIATION", "SEARCHING", "DRAFT"].includes(task.status),
  );
  const completedTasks = tasks.filter((task) => task.status === "COMPLETED");
  const taskId = path.startsWith("/requests/") ? path.split("/")[2] : "";

  return (
    <div className="os-shell">
      <aside className="sidebar">
        <button className="os-brand" onClick={() => onNavigate("/agent")}>
          <span><GitBranch size={19} /></span>
          <strong>PairPilot</strong>
        </button>
        <button className="new-task" onClick={onNewRequest} disabled={busy}>
          <Plus size={17} /> New request
        </button>

        <nav aria-label="PairPilot navigation">
          <div className="nav-section">
            <label>My agent</label>
            <NavItem
              active={path === "/agent"}
              icon={Bot}
              label="Home"
              onClick={() => onNavigate("/agent")}
            />
            <NavItem
              active={path === "/requests"}
              icon={LayoutList}
              label="All requests"
              badge={tasks.length}
              onClick={() => onNavigate("/requests")}
            />
          </div>

          {decisionTasks.length ? (
            <div className="nav-section attention-section">
              <label>Needs your decision</label>
              {decisionTasks.map((task) => (
                <TaskLink
                  key={task.task_id}
                  task={task}
                  active={task.task_id === taskId}
                  onClick={() => onNavigate(`/requests/${task.task_id}`)}
                />
              ))}
            </div>
          ) : null}

          {activeTasks.length ? (
            <div className="nav-section">
              <label>Active requests</label>
              {activeTasks.map((task) => (
                <TaskLink
                  key={task.task_id}
                  task={task}
                  active={task.task_id === taskId}
                  onClick={() => onNavigate(`/requests/${task.task_id}`)}
                />
              ))}
            </div>
          ) : null}

          {completedTasks.length ? (
            <div className="nav-section">
              <label>Completed</label>
              {completedTasks.map((task) => (
                <TaskLink
                  key={task.task_id}
                  task={task}
                  active={task.task_id === taskId}
                  onClick={() => onNavigate(`/requests/${task.task_id}`)}
                />
              ))}
            </div>
          ) : null}

          <div className="nav-section destinations">
            <label>Discover & coordinate</label>
            <NavItem active={path === "/explore"} icon={Compass} label="Explore" onClick={() => onNavigate("/explore")} />
            <NavItem active={path.startsWith("/rooms")} icon={MessageSquareMore} label="Rooms" badge={data?.rooms.length} onClick={() => onNavigate("/rooms")} />
            <NavItem active={path === "/matches"} icon={CheckCircle2} label="Matches" badge={data?.demoState.matches.length} onClick={() => onNavigate("/matches")} />
            <NavItem active={path === "/network"} icon={Network} label="Network" onClick={() => onNavigate("/network")} />
            <NavItem active={path === "/memory"} icon={MemoryStick} label="Memory" badge={data?.demoState.memories.length} onClick={() => onNavigate("/memory")} />
          </div>
        </nav>

        <button className="developer-proof" onClick={() => onNavigate("/audit")}>
          <ShieldCheck size={15} /> Developer proof
        </button>
        <div className="agent-presence">
          <span className="agent-avatar"><Bot size={17} /></span>
          <span><strong>Qi Agent</strong><small>Personal agent · online</small></span>
          <i />
        </div>
      </aside>

      <section className="app-body">
        <header className="mobile-topbar">
          <button className="mobile-brand" onClick={() => onNavigate("/agent")}><GitBranch size={17} /> PairPilot</button>
          <div className="mobile-nav">
            <button onClick={() => onNavigate("/requests")} aria-label="Requests"><Inbox size={18} /></button>
            <button onClick={() => onNavigate("/explore")} aria-label="Explore"><Compass size={18} /></button>
            <button onClick={() => onNavigate("/rooms")} aria-label="Rooms"><UsersRound size={18} /></button>
          </div>
        </header>
        {error ? <div className="os-error">{error}<button onClick={onDismissError}>Dismiss</button></div> : null}
        <main className="os-main">{children}</main>
      </section>
    </div>
  );
}


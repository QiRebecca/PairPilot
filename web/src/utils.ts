export function formatAgent(value: string) {
  const names: Record<string, string> = {
    "qi-agent": "Qi Agent",
    "alice-agent": "Alice Agent",
    "maya-agent": "Maya Agent",
    "lena-agent": "Lena Agent",
    "nora-demo-agent": "Nora Agent",
    "min-demo-agent": "Min Agent",
    "sam-demo-agent": "Sam Agent",
    "zoe-demo-agent": "Zoe Agent",
  };
  return names[value] || value;
}

export function formatDate(value?: string) {
  if (!value) return "—";
  const date = new Date(value.includes("T") ? value : `${value}T12:00:00Z`);
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(date);
}


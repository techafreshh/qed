// Vendored beUI-compatible surface for the QED demo shell.
//
// Lightweight React function components with no third-party dependencies
// beyond `react`. They mirror the beUI agents/motion/blocks API used by the
// views (Card, AnimatedBadge, Number, Table, StreamingResponse,
// AgentActivity, ToolResult, LoadingStates, CodeBlock, Tabs, Alert,
// Collapsible) so the demo renders credential-free and offline.
import React from "react";

type DivProps = React.HTMLAttributes<HTMLDivElement>;

function cx(...parts: Array<string | undefined | false>): string {
  return parts.filter(Boolean).join(" ");
}

/* ---------------------------------- blocks --------------------------------- */

export function Card({
  title,
  children,
  className,
}: DivProps & { title?: React.ReactNode }): JSX.Element {
  return (
    <div
      className={cx("beui-card", className)}
      style={{
        border: "1px solid #e2e8f0",
        borderRadius: 12,
        padding: 16,
        background: "#fff",
        boxShadow: "0 1px 2px rgba(15,23,42,0.06)",
      }}
    >
      {title != null && (
        <div style={{ fontWeight: 700, marginBottom: 8 }}>{title}</div>
      )}
      <div>{children}</div>
    </div>
  );
}

export function Alert({
  tone = "info",
  children,
  className,
}: DivProps & { tone?: "info" | "warn" | "error" | "ok" }): JSX.Element {
  const tones: Record<string, { bg: string; border: string }> = {
    info: { bg: "#eff6ff", border: "#bfdbfe" },
    warn: { bg: "#fffbeb", border: "#fde68a" },
    error: { bg: "#fef2f2", border: "#fecaca" },
    ok: { bg: "#f0fdf4", border: "#bbf7d0" },
  };
  const t = tones[tone] ?? tones.info;
  return (
    <div
      role="alert"
      className={cx("beui-alert", `beui-alert-${tone}`, className)}
      style={{
        background: t.bg,
        border: `1px solid ${t.border}`,
        borderRadius: 8,
        padding: "10px 12px",
      }}
    >
      {children}
    </div>
  );
}

export function Table({
  columns,
  rows,
  className,
}: {
  columns: string[];
  rows: Array<Record<string, React.ReactNode>>;
  className?: string;
}): JSX.Element {
  return (
    <table
      className={cx("beui-table", className)}
      style={{ borderCollapse: "collapse", width: "100%" }}
    >
      <thead>
        <tr>
          {columns.map((c) => (
            <th
              key={c}
              style={{
                textAlign: "left",
                borderBottom: "2px solid #e2e8f0",
                padding: "6px 8px",
                fontSize: 13,
                color: "#475569",
              }}
            >
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            {columns.map((c) => (
              <td
                key={c}
                style={{
                  borderBottom: "1px solid #f1f5f9",
                  padding: "6px 8px",
                  fontSize: 13,
                }}
              >
                {row[c]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CodeBlock({
  code,
  language,
  className,
}: {
  code: string;
  language?: string;
  className?: string;
}): JSX.Element {
  return (
    <pre
      className={cx("beui-code-block", className)}
      data-language={language ?? ""}
      style={{
        background: "#0f172a",
        color: "#e2e8f0",
        borderRadius: 8,
        padding: 12,
        overflowX: "auto",
        fontSize: 12.5,
      }}
    >
      <code>{code}</code>
    </pre>
  );
}

export function Tabs({
  tabs,
  defaultTab,
  className,
}: {
  tabs: Array<{ id: string; label: string; content: React.ReactNode }>;
  defaultTab?: string;
  className?: string;
}): JSX.Element {
  const [active, setActive] = React.useState(defaultTab ?? tabs[0]?.id);
  const current = tabs.find((t) => t.id === active) ?? tabs[0];
  return (
    <div className={cx("beui-tabs", className)}>
      <div role="tablist" style={{ display: "flex", gap: 4, marginBottom: 8 }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={t.id === current?.id}
            onClick={() => setActive(t.id)}
            style={{
              border: "1px solid #e2e8f0",
              borderBottom:
                t.id === current?.id
                  ? "2px solid #2563eb"
                  : "1px solid #e2e8f0",
              background: t.id === current?.id ? "#eff6ff" : "#fff",
              borderRadius: "8px 8px 0 0",
              padding: "6px 12px",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">{current?.content}</div>
    </div>
  );
}

export function Collapsible({
  title,
  children,
  defaultOpen = false,
  className,
}: DivProps & {
  title: React.ReactNode;
  defaultOpen?: boolean;
}): JSX.Element {
  return (
    <details
      className={cx("beui-collapsible", className)}
      open={defaultOpen}
      style={{
        border: "1px solid #e2e8f0",
        borderRadius: 8,
        padding: "8px 12px",
      }}
    >
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>{title}</summary>
      <div style={{ marginTop: 8 }}>{children}</div>
    </details>
  );
}

/* ---------------------------------- motion --------------------------------- */

export function AnimatedBadge({
  verdict,
  className,
}: {
  verdict?: string | null;
  className?: string;
}): JSX.Element {
  const v = (verdict ?? "PENDING").toUpperCase();
  const color =
    v === "REPLICATED"
      ? "#16a34a"
      : v === "FAILED" || v === "REFUTED"
        ? "#dc2626"
        : "#d97706";
  return (
    <span
      className={cx("beui-animated-badge", className)}
      data-verdict={v}
      style={{
        display: "inline-block",
        border: `2px solid ${color}`,
        color,
        borderRadius: 999,
        padding: "2px 12px",
        fontWeight: 800,
        letterSpacing: 1,
        animation: "beui-pulse 1.6s ease-in-out infinite",
      }}
    >
      {v}
      <style>{`@keyframes beui-pulse{0%,100%{opacity:1}50%{opacity:.55}}`}</style>
    </span>
  );
}

export function Number({
  label,
  value,
  className,
}: {
  label: string;
  value: React.ReactNode;
  className?: string;
}): JSX.Element {
  return (
    <div className={cx("beui-number", className)} style={{ textAlign: "center" }}>
      <div style={{ fontSize: 28, fontWeight: 800 }}>{value}</div>
      <div style={{ fontSize: 12, color: "#64748b" }}>{label}</div>
    </div>
  );
}

export function StreamingResponse({
  text,
  streaming = false,
  className,
}: {
  text: string;
  streaming?: boolean;
  className?: string;
}): JSX.Element {
  return (
    <div
      className={cx("beui-streaming-response", className)}
      style={{
        fontFamily: "ui-serif, Georgia, serif",
        fontSize: 15,
        lineHeight: 1.6,
        whiteSpace: "pre-wrap",
      }}
    >
      {text}
      {streaming && <span aria-hidden="true">▍</span>}
    </div>
  );
}

export function LoadingStates({
  message = "Working…",
  className,
}: {
  message?: string;
  className?: string;
}): JSX.Element {
  return (
    <div
      className={cx("beui-loading-states", className)}
      role="status"
      aria-live="polite"
      style={{ display: "flex", alignItems: "center", gap: 8, color: "#475569" }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 14,
          height: 14,
          borderRadius: "50%",
          border: "2px solid #cbd5e1",
          borderTopColor: "#2563eb",
          display: "inline-block",
          animation: "beui-spin 0.9s linear infinite",
        }}
      />
      <span>{message}</span>
      <style>{`@keyframes beui-spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

/* ---------------------------------- agents --------------------------------- */

export function AgentActivity({
  stage,
  detail,
  active = false,
  className,
}: {
  stage: string;
  detail?: React.ReactNode;
  active?: boolean;
  className?: string;
}): JSX.Element {
  return (
    <div
      className={cx("beui-agent-activity", className)}
      style={{ display: "flex", gap: 10, alignItems: "flex-start" }}
    >
      <span
        aria-hidden="true"
        style={{
          marginTop: 4,
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: active ? "#2563eb" : "#16a34a",
          flexShrink: 0,
        }}
      />
      <div>
        <div style={{ fontWeight: 700, fontSize: 14 }}>{stage}</div>
        {detail != null && (
          <div style={{ fontSize: 13, color: "#475569" }}>{detail}</div>
        )}
      </div>
    </div>
  );
}

export function ToolResult({
  name,
  output,
  className,
}: {
  name: string;
  output: React.ReactNode;
  className?: string;
}): JSX.Element {
  return (
    <div
      className={cx("beui-tool-result", className)}
      style={{
        border: "1px dashed #cbd5e1",
        borderRadius: 8,
        padding: 8,
        background: "#f8fafc",
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 700, color: "#475569" }}>
        🛠 {name}
      </div>
      <div style={{ fontSize: 13, whiteSpace: "pre-wrap" }}>{output}</div>
    </div>
  );
}

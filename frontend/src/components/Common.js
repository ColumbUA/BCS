import { useState, useEffect, useMemo } from "react";
import { useAuth, can } from "../AuthContext";

export const cls = (...x) => x.filter(Boolean).join(" ");

export function StateBadge({ s }) {
  let kind = "badge-state-bad";
  if (s === "справний") kind = "badge-state-ok";
  else if (s === "потребує ремонту" || s === "у польоті/виконанні") kind = "badge-state-warn";
  return <span className={cls("badge", kind)}>{s}</span>;
}

export function Stat({ value, label, color }) {
  return (
    <div className="bg-mil border border-mil rounded-lg p-4">
      <div className="text-3xl font-bold" style={{ color, fontFamily: "JetBrains Mono" }}>{value}</div>
      <div className="text-xs uppercase tracking-wider mt-1" style={{ color: "#7A8B6C" }}>{label}</div>
    </div>
  );
}

export function NodeRow({ label, count, type, path, selected, onClick, eqCount, expandable, expanded, onToggle, suffix }) {
  const colors = {
    company: { bg: "rgba(61,90,44,.4)", border: "#A4C26A" },
    hq: { bg: "rgba(91,58,41,.4)", border: "#D4A06A" },
    platoon: { bg: "rgba(44,74,94,.4)", border: "#7AB8D8" },
    group: { bg: "rgba(74,61,92,.4)", border: "#B8A0D6" },
    workshop: { bg: "rgba(92,74,44,.4)", border: "#D8C36A" },
    squad: { bg: "rgba(31,46,34,.6)", border: "#8FAA76" },
    unit: { bg: "rgba(31,46,34,.6)", border: "#8FAA76" },
  };
  const c = colors[type] || colors.unit;
  return (
    <div data-testid={`node-${path}`} onClick={onClick}
      className={cls("group flex items-center gap-2 px-2.5 py-2 rounded cursor-pointer text-sm border transition-all", selected ? "ring-1" : "")}
      style={{ background: selected ? c.bg : "transparent",
               borderColor: selected ? c.border : "transparent",
               boxShadow: selected ? `inset 3px 0 0 ${c.border}` : undefined }}>
      {expandable ? (
        <button className="text-xs w-4 text-center" style={{ color: c.border }}
          onClick={(e) => { e.stopPropagation(); onToggle(); }}>
          {expanded ? "▾" : "▸"}
        </button>
      ) : <div className="w-4" />}
      <div className="flex-1 truncate">{label}</div>
      <div className="text-xs px-1.5 py-0.5 rounded"
           style={{ background: c.bg, color: c.border, border: `1px solid ${c.border}` }}>{count}</div>
      {eqCount > 0 && (
        <div className="text-xs px-1.5 py-0.5 rounded badge-cat">📦 {eqCount}</div>
      )}
      {suffix}
    </div>
  );
}

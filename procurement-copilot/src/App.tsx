import React, { useState } from "react";
import Overview from "./views/Overview";
import QuoteComparisonMatrix from "./views/QuoteComparisonMatrix";
import AwardScenarios from "./views/AwardScenarios";
import VendorEligibility from "./views/VendorEligibility";
import AIChatPanel from "./components/AIChatPanel";
import "./index.css";

type NavItem = "overview" | "comparison" | "scenarios" | "eligibility";

const NAV_ITEMS: Array<{ key: NavItem; label: string; icon: React.ReactNode; desc: string }> = [
  {
    key: "overview",
    label: "Overview",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
    desc: "RFx dashboard & recommendation",
  },
  {
    key: "comparison",
    label: "Quote Comparison",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
      </svg>
    ),
    desc: "Side-by-side vendor matrix",
  },
  {
    key: "scenarios",
    label: "Award Scenarios",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    desc: "Optimization & spend analytics",
  },
  {
    key: "eligibility",
    label: "Vendor Eligibility",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    desc: "Questionnaire audit & gate",
  },
];

function App() {
  const [activeNav, setActiveNav] = useState<NavItem>("overview");
  const [chatOpen, setChatOpen] = useState(true);

  const activeItem = NAV_ITEMS.find((n) => n.key === activeNav)!;

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* ── Left Sidebar ───────────────────────────────────────── */}
      <aside className="w-56 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col shadow-sm">
        {/* Logo */}
        <div className="px-5 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shadow-sm">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-bold text-slate-800 leading-tight">ProcureAI</p>
              <p className="text-xs text-slate-400 leading-tight">Co-pilot</p>
            </div>
          </div>
        </div>

        {/* Active RFx Context */}
        <div className="px-4 py-3 border-b border-slate-100 bg-blue-50">
          <p className="text-xs font-semibold text-blue-600 uppercase tracking-wider mb-1">Active RFx</p>
          <p className="text-xs font-mono font-semibold text-slate-700">RFx-CORR-2026-017</p>
          <p className="text-xs text-slate-500 mt-0.5 leading-snug">Corrugated Packaging FY2027</p>
          <div className="mt-2 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
            <span className="text-xs text-emerald-700 font-medium">5 quotes received</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const isActive = activeNav === item.key;
            return (
              <button
                key={item.key}
                onClick={() => setActiveNav(item.key)}
                className={`w-full text-left rounded-lg px-3 py-2.5 transition-all duration-150 group ${
                  isActive
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-800"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <span className={isActive ? "text-white" : "text-slate-400 group-hover:text-slate-600"}>
                    {item.icon}
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold leading-tight truncate">{item.label}</p>
                    <p className={`text-xs leading-tight mt-0.5 truncate ${isActive ? "text-blue-200" : "text-slate-400"}`}>
                      {item.desc}
                    </p>
                  </div>
                </div>
              </button>
            );
          })}
        </nav>

        {/* Footer meta */}
        <div className="px-4 py-3 border-t border-slate-100 bg-slate-50">
          <div className="text-xs text-slate-400 space-y-1">
            {[
              ["Lines", "30"],
              ["Vendors", "5 (1 DQ)"],
              ["Closing", "19-Nov-2026"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span>{k}</span>
                <span className="text-slate-600 font-medium">{v}</span>
              </div>
            ))}
          </div>
        </div>
      </aside>

      {/* ── Main Area ──────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-slate-200 shadow-sm flex-shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">
              {activeItem.icon}
            </span>
            <h1 className="text-sm font-semibold text-slate-800">{activeItem.label}</h1>
            <span className="text-slate-300 mx-1">·</span>
            <span className="text-xs text-slate-400">{activeItem.desc}</span>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg">
              <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              10-Nov-2026, 23:40 IST
            </div>

            <button
              onClick={() => setChatOpen(!chatOpen)}
              className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border font-medium transition-all ${
                chatOpen
                  ? "bg-blue-600 border-blue-600 text-white shadow-sm"
                  : "bg-white border-slate-200 text-slate-600 hover:border-blue-400 hover:text-blue-600"
              }`}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
              AI Analyst
              {chatOpen ? (
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              ) : (
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              )}
            </button>
          </div>
        </header>

        {/* Content Row */}
        <div className="flex flex-1 min-h-0">
          <main className="flex-1 overflow-y-auto p-6 min-w-0">
            {activeNav === "overview"    && <Overview />}
            {activeNav === "comparison"  && <QuoteComparisonMatrix />}
            {activeNav === "scenarios"   && <AwardScenarios />}
            {activeNav === "eligibility" && <VendorEligibility />}
          </main>

          <AIChatPanel isOpen={chatOpen} onToggle={() => setChatOpen(!chatOpen)} />
        </div>
      </div>
    </div>
  );
}

export default App;

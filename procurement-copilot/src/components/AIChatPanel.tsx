import React, { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "ai";
  text: string;
}

const SUGGESTIONS = [
  {
    chip: "Why is Vendor 5 marked unresolved for line 27?",
    response:
      "**Vendor 5 (Standard Box Corp) — Line 27 Audit Finding**\n\nVendor 5 is flagged as **UNRESOLVED** on Line 27 (`CP-027`: Export carton 650×450×400, moisture-barrier) for two critical reasons:\n\n1. **New SKU with No Historical Baseline:** In the *Historical PO Master*, Line 27 is designated as a **New SKU** (0 prior volume and blank historical unit price). Vendor 5 submitted a quotation stating *'same as last year'*. Because there is no historical PO to reference, the normalization engine cannot infer a numerical value.\n\n2. **Quality Gate Failure (Gate Q7):** In the *Questionnaire Audit & Gate*, Vendor 5 answered **NO to Q7** (Moisture-barrier coating). Line 27 explicitly mandates moisture-barrier treatment for sea-freight transit. Therefore, Vendor 5 is also **disqualified from award on Line 27**.\n\n**Buyer Action Required:** Request a fresh numeric quotation from Vendor 5 with barrier coating, or mark them excluded from this line.",
  },
  {
    chip: "What is the cost difference if we enforce the quality gate?",
    response:
      "**Cost of Compliance & Quality Gate Analysis**\n\nEnforcing the quality gate (transitioning from **Scenario A: Unconstrained L1** to **Scenario B: Quality-Gated L1**) costs exactly **+₹2,74,585 (+0.73%)** in annual spend:\n\n| Scenario | Total Spend | Net Savings vs Budget | Cost of Compliance |\n|---|---|---|---|\n| Master Budget | ₹4,00,03,750 | — | — |\n| **Scenario A: Unconstrained L1** | ₹3,77,44,605 | ₹22,59,145 (5.65%) | Baseline |\n| **Scenario B: Quality-Gated L1** | ₹3,80,19,190 | ₹19,84,560 (4.96%) | **+₹2,74,585 (+0.73%)** |\n| **Scenario C: Dual Sourced (70/30)** | ₹3,81,18,864 | ₹18,84,886 (4.71%) | +₹3,74,259 (+0.99%) |\n\n**Key Takeaway for Leadership:**\nScenario A awards multiple high-volume lines to **Vendor 4 (Sri Balaji Packaging)**, who is uncertified (expired ISO 9001:2015). For just **₹2.75 Lakhs** (0.73% premium), Scenario B completely removes all non-compliant vendor allocations, protecting quality records and audit standing.",
  },
  {
    chip: "Show me the risk profile for Vendor 4.",
    response:
      "**Comprehensive Risk Profile: Vendor 4 (Sri Balaji Packaging)**\n\n⛔ **Overall Decision: DISQUALIFIED (Failed Q1 through Q5)**\n\nVendor 4 failed every mandatory audit criterion in the *Questionnaire Audit & Gate*:\n\n* **Q1 (ISO 9001:2015):** **FAIL** — Certificate expired in October 2026 (prior to RFx closing date 19-Nov-2026).\n* **Q2 (Monthly Capacity):** **FAIL** — Declared 280 TPM against the mandatory threshold of ≥ 300 TPM.\n* **Q3 (In-house Testing Lab):** **FAIL** — No in-house laboratory for burst, ECT, Cobb, or GSM testing.\n* **Q4 (Customer Rejection Rate):** **FAIL** — Reported 2.4% rejection rate against the maximum tolerance of ≤ 1.5%.\n* **Q5 (Active Customer References):** **FAIL** — Only 2 active accounts with 12+ months history (≥ 3 required).\n\n**Impact on Award:** Even though Vendor 4 submitted competitive raw prices on several RSC lines, they are strictly locked out of all qualified award models (Scenario B and Scenario C).",
  },
];

interface AIChatProps {
  isOpen: boolean;
  onToggle: () => void;
}

export default function AIChatPanel({ isOpen, onToggle }: AIChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "ai",
      text: "👋 Hello! I am your **AI Procurement Analyst** for RFx-CORR-2026-017.\n\nI have indexed all 4 sheets from `RFx_Master_Updated.xlsx`: Historical POs, Questionnaire Audit, Normalized Quotes, and the Award Scenarios Engine. Click a suggestion below or ask me any question about quotes, conversions, and vendor compliance.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const sendMessage = (text: string) => {
    if (!text.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setIsTyping(true);

    const match = SUGGESTIONS.find((s) => s.chip === text);

    setTimeout(() => {
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          text: match
            ? match.response
            : `**Analysis for:** *"${text}"*\n\nBased on the active RFx dataset:\n\n• **Normalized Comparison:** All 30 line items reflect landed costs converted to ₹/UoM. Vendor 3 includes USD-to-INR conversions at ₹83.95/USD, and Vendor 5 includes weight-based conversions.\n• **Questionnaire Audit:** Vendor 4 is fully disqualified (expired ISO 9001 cert, 280 TPM capacity). Vendors 3 & 5 have partial line disqualifications.\n• **Award Optimization:** Scenario B (Quality-Gated L1 at ₹3.80 Cr) is the recommended path for executive approval.\n\nFeel free to click one of the suggested query chips below for an in-depth audit breakdown!`,
        },
      ]);
    }, 900);
  };

  const renderFormattedText = (raw: string) => {
    const lines = raw.split("\n");
    const elements: React.ReactNode[] = [];
    let inTable = false;
    let tableRows: string[][] = [];

    const flushTable = () => {
      if (tableRows.length > 0) {
        const headers = tableRows[0];
        const dataRows = tableRows.slice(2);
        elements.push(
          <div key={`table-${elements.length}`} className="overflow-x-auto my-3 border border-slate-200 rounded-lg shadow-sm">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 border-b border-slate-200">
                  {headers.map((h, i) => (
                    <th key={i} className="px-2.5 py-1.5 text-left font-semibold text-slate-700 border-r border-slate-200 last:border-0">
                      {h.trim()}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {dataRows.map((r, ri) => (
                  <tr key={ri} className="hover:bg-slate-50">
                    {r.map((cell, ci) => (
                      <td key={ci} className="px-2.5 py-1.5 text-slate-700 border-r border-slate-200 last:border-0">
                        {cell.trim()}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        tableRows = [];
        inTable = false;
      }
    };

    lines.forEach((line, idx) => {
      if (line.startsWith("|")) {
        inTable = true;
        tableRows.push(line.split("|").filter((_, i) => i > 0 && i < line.split("|").length - 1));
        return;
      }
      if (inTable) flushTable();

      if (line.startsWith("**") && line.endsWith("**")) {
        elements.push(
          <p key={idx} className="font-bold text-slate-900 mt-2 text-xs uppercase tracking-wide">
            {line.slice(2, -2)}
          </p>
        );
      } else if (line.startsWith("⛔ **")) {
        elements.push(
          <p key={idx} className="font-bold text-red-700 bg-red-50 border border-red-200 rounded-md p-2 mt-2 text-xs">
            {line.replace(/\*\*/g, "")}
          </p>
        );
      } else if (line.startsWith("* ")) {
        elements.push(
          <p key={idx} className="text-xs text-slate-700 ml-3 list-item">
            {line.slice(2)}
          </p>
        );
      } else if (line.trim() === "") {
        elements.push(<div key={idx} className="h-1.5" />);
      } else {
        const parts = line.split(/\*\*(.*?)\*\*/g);
        elements.push(
          <p key={idx} className="text-xs text-slate-700 leading-relaxed">
            {parts.map((p, i) =>
              i % 2 === 1 ? <strong key={i} className="text-slate-900 font-semibold">{p}</strong> : p
            )}
          </p>
        );
      }
    });

    if (inTable) flushTable();
    return elements;
  };

  return (
    <div
      className={`flex flex-col bg-white border-l border-slate-200 shadow-md transition-all duration-300 ${
        isOpen ? "w-96" : "w-0 overflow-hidden"
      }`}
    >
      {isOpen && (
        <>
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50 flex-shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold text-xs shadow-sm">
                AI
              </div>
              <div>
                <p className="text-xs font-bold text-slate-800">AI Procurement Analyst</p>
                <p className="text-[11px] text-green-700 font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                  Ground Truth Active
                </p>
              </div>
            </div>
            <button
              onClick={onToggle}
              className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 transition-colors"
              title="Close Panel"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-slate-50/50">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[92%] rounded-xl px-3.5 py-3 shadow-sm ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white text-xs font-medium"
                      : "bg-white border border-slate-200 text-slate-800"
                  }`}
                >
                  {msg.role === "ai" ? renderFormattedText(msg.text) : <p>{msg.text}</p>}
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="flex justify-start">
                <div className="bg-white border border-slate-200 rounded-xl px-4 py-3 shadow-sm flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-slate-400 animate-bounce"></div>
                  <div className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: "150ms" }}></div>
                  <div className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: "300ms" }}></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggested Queries Chips */}
          <div className="px-3.5 py-2.5 bg-white border-t border-slate-100 space-y-1.5">
            <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              Quick Audit Inquiries
            </p>
            {SUGGESTIONS.map((s, idx) => (
              <button
                key={idx}
                onClick={() => sendMessage(s.chip)}
                className="w-full text-left text-xs bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-200 rounded-lg px-2.5 py-2 text-slate-700 hover:text-blue-700 transition-colors shadow-2xs block truncate"
                title={s.chip}
              >
                💬 {s.chip}
              </button>
            ))}
          </div>

          {/* Chat Input */}
          <div className="p-3 bg-white border-t border-slate-200 flex-shrink-0">
            <div className="flex gap-2">
              <input
                className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-all shadow-inner"
                placeholder="Ask co-pilot about quotes, vendors..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
              />
              <button
                onClick={() => sendMessage(input)}
                className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-3 py-2 text-xs font-semibold shadow-sm transition-colors flex items-center justify-center"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

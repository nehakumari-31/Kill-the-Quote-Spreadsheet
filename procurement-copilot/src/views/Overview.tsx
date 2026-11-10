import React from "react";
import { LINE_ITEMS, AWARD_SCENARIOS } from "../data/rfxData";

const stats = {
  totalLines: 30,
  newSKUs: LINE_ITEMS.filter((l) => l.isNewSKU).length,
  unresolvedCells: LINE_ITEMS.flatMap((l) => [l.v1, l.v2, l.v3, l.v4, l.v5]).filter((c) => c.flag === "unresolved").length,
  inferredCells: LINE_ITEMS.flatMap((l) => [l.v1, l.v2, l.v3, l.v4, l.v5]).filter((c) => c.flag === "inferred").length,
};

export default function Overview() {
  return (
    <div className="space-y-6">
      {/* RFx Header Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="text-xs font-mono font-semibold bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-md">
                RFx-CORR-2026-017
              </span>
              <span className="text-xs font-medium bg-green-50 text-green-700 border border-green-200 px-2.5 py-1 rounded-md flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                Quotes Under Evaluation
              </span>
              <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md">
                FY2027 Annual Contract
              </span>
            </div>
            <h1 className="text-2xl font-bold text-slate-800">
              Corrugated Packaging Procurement RFx
            </h1>
            <p className="text-slate-600 text-sm mt-1">
              Category: Secondary & Tertiary Packaging · Buyer Persona: Veda Home Appliances Pvt Ltd · Closing Date: 19-Nov-2026
            </p>
          </div>
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 min-w-[220px] text-right">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Master Budget Target</p>
            <p className="text-2xl font-bold font-mono text-slate-900 mt-0.5">₹4,00,03,750</p>
            <p className="text-xs font-medium text-green-700 mt-1">
              Optimal Savings: ₹22.59 L (5.65%)
            </p>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Line Items</p>
          <p className="text-2xl font-bold font-mono text-slate-800 mt-1">{stats.totalLines}</p>
          <p className="text-xs text-slate-500 mt-0.5">Shippers, Mailers & Inserts</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Vendors Responded</p>
          <p className="text-2xl font-bold font-mono text-slate-800 mt-1">5</p>
          <p className="text-xs text-slate-500 mt-0.5">4 eligible / 1 disqualified</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <p className="text-xs font-semibold text-purple-700 uppercase tracking-wider">New SKUs</p>
          <p className="text-2xl font-bold font-mono text-purple-700 mt-1">{stats.newSKUs}</p>
          <p className="text-xs text-slate-500 mt-0.5">No historical PO baseline</p>
        </div>

        <div className="bg-white border border-amber-200 rounded-xl p-4 shadow-sm bg-amber-50/30">
          <p className="text-xs font-semibold text-amber-800 uppercase tracking-wider">Inferred Quotes</p>
          <p className="text-2xl font-bold font-mono text-amber-700 mt-1">{stats.inferredCells}</p>
          <p className="text-xs text-amber-700 mt-0.5">Converted currency / UoM</p>
        </div>

        <div className="bg-white border border-red-200 rounded-xl p-4 shadow-sm bg-red-50/30">
          <p className="text-xs font-semibold text-red-700 uppercase tracking-wider">Unresolved Quotes</p>
          <p className="text-2xl font-bold font-mono text-red-700 mt-1">{stats.unresolvedCells}</p>
          <p className="text-xs text-red-600 mt-0.5">Requires vendor clarification</p>
        </div>
      </div>

      {/* AI Recommendation Card */}
      <div className="bg-white border border-blue-200 rounded-xl p-6 shadow-sm relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-blue-600"></div>
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 font-bold flex-shrink-0">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div className="space-y-2 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-base font-bold text-slate-800">
                Strategic Recommendation: Scenario B (Quality-Gated L1)
              </h3>
              <span className="text-xs font-semibold bg-green-50 text-green-700 border border-green-200 px-2 py-0.5 rounded-full">
                Zero Compliance Risk
              </span>
              <span className="text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full">
                Savings: ₹19.85 L (4.96%)
              </span>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed">
              While Scenario A offers ₹3.77 Cr total spend, it allocates critical lines to <strong>Vendor 4 (Sri Balaji Packaging)</strong> whose ISO 9001:2015 certificate expired in October 2026. Enforcing the quality gate in <strong>Scenario B</strong> eliminates all certification, lab testing, and rejection-rate risks for a nominal compliance premium of <strong>+₹2.75 Lakhs (+0.73%)</strong>.
            </p>
            <div className="pt-2 flex items-center gap-3 text-xs text-slate-500 flex-wrap">
              <span className="font-semibold text-slate-700">Recommended Allocation:</span>
              <span>• Apex Packaging (V1): Qualified</span>
              <span>• PackTech Solutions (V2): Qualified</span>
              <span>• Global Corrugators (V3): Qualified for 3-ply/5-ply</span>
              <span>• Standard Box Corp (V5): Repeat SKUs</span>
            </div>
          </div>
        </div>
      </div>

      {/* Vendor Participation & Health Summary */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
        <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">
          Vendor Status & Eligibility Overview
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {[
            {
              id: "V1",
              name: "Apex Packaging",
              status: "Pass / Qualified",
              statusClass: "bg-green-50 text-green-700 border-green-200",
              capacity: "650 TPM",
              iso: "Valid (Exp 2028)",
              note: "Clean submission, verified landed costs.",
            },
            {
              id: "V2",
              name: "PackTech Solutions",
              status: "Pass / Qualified",
              statusClass: "bg-green-50 text-green-700 border-green-200",
              capacity: "420 TPM",
              iso: "Valid (Exp 2027)",
              note: "Competitive on mailers and retail tuck cartons.",
            },
            {
              id: "V3",
              name: "Global Corrugators",
              status: "Partial Gate",
              statusClass: "bg-amber-50 text-amber-700 border-amber-200",
              capacity: "1,200 TPM",
              iso: "Valid (Exp 2028)",
              note: "USD quote converted. Failed Q6 (no 7-ply in-house).",
            },
            {
              id: "V4",
              name: "Sri Balaji Packaging",
              status: "DISQUALIFIED",
              statusClass: "bg-red-50 text-red-700 border-red-200",
              capacity: "280 TPM (Fail)",
              iso: "Expired Oct 2026",
              note: "Failed Q1–Q5 mandatory gates. Locked out.",
            },
            {
              id: "V5",
              name: "Standard Box Corp",
              status: "Partial Gate",
              statusClass: "bg-amber-50 text-amber-700 border-amber-200",
              capacity: "380 TPM",
              iso: "Valid (Exp 2027)",
              note: "₹/kg converted quotes. Failed Q7 for moisture-barrier.",
            },
          ].map((v) => (
            <div key={v.id} className="border border-slate-200 rounded-lg p-3 bg-slate-50/50 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-slate-800">{v.id}</span>
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${v.statusClass}`}>
                    {v.status}
                  </span>
                </div>
                <p className="text-xs font-semibold text-slate-800 truncate" title={v.name}>{v.name}</p>
                <div className="mt-2 text-[11px] space-y-0.5 text-slate-600">
                  <p><span className="text-slate-400">Capacity:</span> {v.capacity}</p>
                  <p><span className="text-slate-400">ISO:</span> {v.iso}</p>
                </div>
              </div>
              <p className="mt-3 text-[11px] text-slate-500 border-t border-slate-200/60 pt-2 leading-snug">
                {v.note}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

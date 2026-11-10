import React from "react";
import { QGATE_ROWS } from "../data/rfxData";

type CellStyle = "pass" | "fail" | "partial" | "disqualified" | "qualified" | "neutral";

function getCellStyle(text: string): CellStyle {
  if (text.includes("DISQUALIFIED")) return "disqualified";
  if (text.includes("QUALIFIED") && !text.includes("PARTIAL") && !text.includes("DISQUALIFIED")) return "qualified";
  if (text.includes("PARTIAL")) return "partial";
  if (text.includes("FAIL") || text.includes("Expired") || text.includes("Disqualified")) return "fail";
  if (text.includes("Pass") || text.includes("Yes (Pass)") || text.includes("QUALIFIED") || text.includes("Yes")) return "pass";
  return "neutral";
}

const CELL_CLASSES: Record<CellStyle, string> = {
  pass: "bg-green-50 text-green-700 border-green-200",
  fail: "bg-red-50 text-red-700 border-red-200 font-semibold",
  partial: "bg-amber-50 text-amber-700 border-amber-200",
  disqualified: "bg-red-100 text-red-800 border-red-300 font-bold",
  qualified: "bg-green-100 text-green-800 border-green-300 font-bold",
  neutral: "bg-slate-50 text-slate-700 border-slate-200",
};

const ICON: Record<CellStyle, string> = {
  pass: "✓",
  fail: "✗",
  partial: "⚠",
  disqualified: "🚫",
  qualified: "✓",
  neutral: "—",
};

const VENDOR_HEADERS = [
  { label: "V1: Apex Packaging", status: "QUALIFIED", badgeClass: "bg-green-50 text-green-700 border-green-200" },
  { label: "V2: PackTech Solutions", status: "QUALIFIED", badgeClass: "bg-green-50 text-green-700 border-green-200" },
  { label: "V3: Global Corrugators", status: "PARTIAL", badgeClass: "bg-amber-50 text-amber-700 border-amber-200" },
  { label: "V4: Sri Balaji Packaging", status: "DISQUALIFIED", badgeClass: "bg-red-50 text-red-700 border-red-200" },
  { label: "V5: Standard Box Corp", status: "PARTIAL", badgeClass: "bg-amber-50 text-amber-700 border-amber-200" },
];

export default function VendorEligibility() {
  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-800">Vendor Eligibility & Questionnaire Audit Gate</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Audited directly from the <span className="font-semibold text-slate-700">Questionnaire Audit & Gate</span> tab — mandatory quality, compliance, capacity, and capability criteria.
        </p>
      </div>

      {/* Critical Disqualification Notice for Vendor 4 */}
      <div className="bg-red-50 border-2 border-red-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-red-100 text-red-700 flex items-center justify-center text-xl flex-shrink-0 font-bold">
            🚫
          </div>
          <div className="space-y-2 flex-1">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h3 className="text-base font-bold text-red-800">
                Critical Audit Finding: Vendor 4 (Sri Balaji Packaging) is DISQUALIFIED
              </h3>
              <span className="text-xs font-bold uppercase tracking-wider bg-red-100 text-red-700 border border-red-300 px-2.5 py-0.5 rounded-full">
                Locked Out of Award
              </span>
            </div>
            <p className="text-sm text-red-700 leading-relaxed">
              <strong>Why Vendor 4 is locked out:</strong> Vendor 4 failed all 5 mandatory qualification gates (Q1 through Q5). Crucially, their <strong>ISO 9001:2015 certificate expired in October 2026</strong>, prior to the RFx closing date of 19-Nov-2026. In addition, their manufacturing capacity (280 TPM) falls short of the 300 TPM minimum, they lack an in-house testing lab, and their customer rejection rate (2.4%) exceeds our 1.5% ceiling.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-1 text-xs">
              <div className="bg-white/80 border border-red-200 rounded-md p-2">
                <span className="font-semibold text-red-800 block">Q1: ISO Certificate</span>
                <span className="text-red-600">Expired Oct 2026</span>
              </div>
              <div className="bg-white/80 border border-red-200 rounded-md p-2">
                <span className="font-semibold text-red-800 block">Q2: Capacity</span>
                <span className="text-red-600">280 TPM (&lt; 300 TPM)</span>
              </div>
              <div className="bg-white/80 border border-red-200 rounded-md p-2">
                <span className="font-semibold text-red-800 block">Q3: Test Lab</span>
                <span className="text-red-600">No In-house Lab</span>
              </div>
              <div className="bg-white/80 border border-red-200 rounded-md p-2">
                <span className="font-semibold text-red-800 block">Q4: Rejection Rate</span>
                <span className="text-red-600">2.4% (&gt; 1.5% max)</span>
              </div>
              <div className="bg-white/80 border border-red-200 rounded-md p-2">
                <span className="font-semibold text-red-800 block">Q5: References</span>
                <span className="text-red-600">2 Active (&lt; 3 req.)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Summary Vendor Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
        {VENDOR_HEADERS.map((v) => (
          <div key={v.label} className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm flex flex-col justify-between">
            <div>
              <p className="text-xs font-bold text-slate-800">{v.label.split(":")[1]?.trim()}</p>
              <p className="text-[11px] text-slate-500">{v.label.split(":")[0]}</p>
            </div>
            <div className="mt-3">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border block text-center ${v.badgeClass}`}>
                {v.status}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Main Questionnaire Audit Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider">
            Detailed Gate Evaluation Matrix
          </h3>
          <span className="text-xs text-slate-500">Evaluated against RFx Qualification Criteria</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-4 py-3 text-slate-600 font-semibold uppercase tracking-wider min-w-[200px] border-r border-slate-200">
                  Question / Gate Criteria
                </th>
                {VENDOR_HEADERS.map((v) => (
                  <th key={v.label} className="text-center px-3 py-3 text-slate-700 font-semibold uppercase tracking-wider border-r border-slate-200 min-w-[130px]">
                    {v.label.split(":")[1]?.trim()}
                  </th>
                ))}
                <th className="text-left px-4 py-3 text-slate-600 font-semibold uppercase tracking-wider min-w-[220px]">
                  Evaluation Rule & Impact
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {QGATE_ROWS.map((row, idx) => {
                const isOverall = row.question.includes("Overall Quality Gate Decision");
                return (
                  <tr
                    key={idx}
                    className={`${isOverall ? "bg-slate-50/80 font-bold" : "hover:bg-slate-50/50"} transition-colors`}
                  >
                    <td className="px-4 py-3 text-slate-800 font-medium border-r border-slate-100">
                      {row.question}
                    </td>
                    {[row.v1, row.v2, row.v3, row.v4, row.v5].map((val, vi) => {
                      const style = getCellStyle(val);
                      return (
                        <td key={vi} className="px-2 py-2 text-center border-r border-slate-100">
                          <span className={`inline-flex items-center justify-center gap-1 text-[11px] px-2.5 py-1 rounded-md border w-full ${CELL_CLASSES[style]}`}>
                            <span>{ICON[style]}</span>
                            <span>{val}</span>
                          </span>
                        </td>
                      );
                    })}
                    <td className="px-4 py-3 text-slate-600 text-xs">
                      {row.rule}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Partial Gate Notes */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-amber-200 rounded-xl p-4 shadow-sm bg-amber-50/20">
          <h4 className="text-xs font-bold text-amber-800 uppercase tracking-wider flex items-center gap-1.5 mb-1.5">
            <span>⚠</span> Vendor 3 (Global Corrugators) — Line-Specific Gate Q6
          </h4>
          <p className="text-xs text-slate-600 leading-relaxed">
            Vendor 3 answered <strong>NO to Q6</strong> (In-house 7-ply capability). They are strictly banned from award recommendations on <strong>Lines 10 &amp; 30</strong> (heavy-duty and bulk bin pallet boxes), but remain eligible for all 3-ply and 5-ply cartons.
          </p>
        </div>

        <div className="bg-white border border-amber-200 rounded-xl p-4 shadow-sm bg-amber-50/20">
          <h4 className="text-xs font-bold text-amber-800 uppercase tracking-wider flex items-center gap-1.5 mb-1.5">
            <span>⚠</span> Vendor 5 (Standard Box Corp) — Line-Specific Gate Q7
          </h4>
          <p className="text-xs text-slate-600 leading-relaxed">
            Vendor 5 answered <strong>NO to Q7</strong> (Moisture-barrier coating capability). They are strictly banned from award recommendations on <strong>Lines 26 &amp; 27</strong> (sea-freight export cartons requiring barrier treatment).
          </p>
        </div>
      </div>
    </div>
  );
}

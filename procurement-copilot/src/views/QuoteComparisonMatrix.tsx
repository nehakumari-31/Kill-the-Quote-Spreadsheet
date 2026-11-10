import React, { useState } from "react";
import { LINE_ITEMS, VENDORS, VendorKey, TrustFlag, VendorCell } from "../data/rfxData";

// ── Cell styling by trust flag ──────────────────────────────────────────────
const FLAG_ROW_BG: Record<TrustFlag, string> = {
  verified:     "",
  inferred:     "bg-amber-50",
  unresolved:   "bg-red-50",
  disqualified: "bg-slate-100",
  not_quoted:   "bg-slate-50",
};

const FLAG_TEXT: Record<TrustFlag, string> = {
  verified:     "text-slate-800",
  inferred:     "text-amber-800 font-medium",
  unresolved:   "text-red-700 font-semibold",
  disqualified: "text-slate-400 line-through",
  not_quoted:   "text-slate-400 italic",
};

const FLAG_BORDER: Record<TrustFlag, string> = {
  verified:     "",
  inferred:     "border border-amber-200",
  unresolved:   "border border-red-200",
  disqualified: "border border-slate-200",
  not_quoted:   "",
};

const FLAG_LABEL: Record<TrustFlag, string> = {
  verified:     "Verified",
  inferred:     "Inferred / Converted",
  unresolved:   "Unresolved",
  disqualified: "Disqualified",
  not_quoted:   "Not Quoted",
};

const FLAG_PILL_STYLE: Record<TrustFlag, string> = {
  verified:     "bg-green-50 text-green-700 border-green-200",
  inferred:     "bg-amber-50 text-amber-700 border-amber-200",
  unresolved:   "bg-red-50 text-red-700 border-red-200",
  disqualified: "bg-slate-100 text-slate-500 border-slate-200",
  not_quoted:   "bg-slate-100 text-slate-400 border-slate-200",
};

// ── Tooltip ─────────────────────────────────────────────────────────────────
function Tooltip({ children, cell, lineNo }: { children: React.ReactNode; cell: VendorCell; lineNo: number }) {
  const [show, setShow] = useState(false);

  return (
    <div
      className="relative inline-flex items-center justify-center cursor-help w-full"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div className="tooltip-enter absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2.5 w-72 rounded-xl bg-white border border-slate-200 shadow-xl p-4 pointer-events-none text-left">
          {/* Arrow */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-8 border-r-8 border-t-8 border-l-transparent border-r-transparent border-t-white drop-shadow-sm" />

          <div className="space-y-3">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                Original Raw Quote — Line {lineNo}
              </p>
              <p className="text-sm font-mono font-semibold text-slate-800 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                {cell.originalRaw ?? "N/A"}
              </p>
            </div>

            {cell.conversionNote && (
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Normalization / Conversion
                </p>
                <p className="text-xs text-slate-600 leading-relaxed bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                  {cell.conversionNote}
                </p>
              </div>
            )}

            <div>
              <span className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border font-medium ${FLAG_PILL_STYLE[cell.flag]}`}>
                {cell.flag === "verified"     && <span>✓</span>}
                {cell.flag === "inferred"     && <span>⚠</span>}
                {cell.flag === "unresolved"   && <span>✗</span>}
                {cell.flag === "disqualified" && <span>🚫</span>}
                {FLAG_LABEL[cell.flag]}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Cell ─────────────────────────────────────────────────────────────────────
function PriceCell({ cell, lineNo, isL1 }: { cell: VendorCell; lineNo: number; isL1: boolean }) {
  const displayValue =
    cell.value !== null
      ? `₹${Number(cell.value).toFixed(2)}`
      : cell.flag === "disqualified"
      ? "DISQUAL."
      : cell.flag === "not_quoted"
      ? "—"
      : "UNRESOLVED";

  return (
    <Tooltip cell={cell} lineNo={lineNo}>
      <div className={`w-full flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-lg ${FLAG_ROW_BG[cell.flag]} ${FLAG_BORDER[cell.flag]}`}>
        <span className={`text-xs whitespace-nowrap ${FLAG_TEXT[cell.flag]}`}>
          {displayValue}
          {cell.flag === "inferred" && (
            <span className="ml-0.5 text-amber-500" title="Inferred / Converted">
              <svg className="w-3 h-3 inline" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </span>
          )}
        </span>
        {isL1 && cell.flag !== "disqualified" && cell.flag !== "unresolved" && cell.flag !== "not_quoted" && (
          <span className="text-xs font-bold text-green-700 bg-green-100 border border-green-200 px-1.5 py-0 rounded-full leading-tight">
            L1
          </span>
        )}
      </div>
    </Tooltip>
  );
}

// ── Legend item ──────────────────────────────────────────────────────────────
function LegendItem({ flag, label }: { flag: TrustFlag; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium ${FLAG_PILL_STYLE[flag]}`}>
      {flag === "verified"     && <span className="text-green-600">✓</span>}
      {flag === "inferred"     && (
        <svg className="w-3 h-3 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
      )}
      {flag === "unresolved"   && <span className="text-red-600 font-bold">!</span>}
      {flag === "disqualified" && <span>🚫</span>}
      {label}
    </span>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function QuoteComparisonMatrix() {
  const [filterNewSKU, setFilterNewSKU] = useState(false);

  const filtered = filterNewSKU ? LINE_ITEMS.filter((l) => l.isNewSKU) : LINE_ITEMS;

  const getMinVendor = (item: (typeof LINE_ITEMS)[0]) => {
    const values: Array<{ key: VendorKey; val: number }> = [];
    (["v1", "v2", "v3", "v5"] as VendorKey[]).forEach((k) => {
      const c = item[k];
      if ((c.flag === "verified" || c.flag === "inferred") && c.value !== null) {
        values.push({ key: k, val: c.value as number });
      }
    });
    if (values.length === 0) return null;
    return values.reduce((a, b) => (a.val < b.val ? a : b));
  };

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Header */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-lg font-bold text-slate-800">Quote Comparison Matrix</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              30 line items · 5 vendors · normalized landed cost (₹/UoM) ·{" "}
              <span className="text-blue-600 font-medium">hover any cell to see the original raw quote</span>
            </p>
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={filterNewSKU}
                onChange={(e) => setFilterNewSKU(e.target.checked)}
                className="accent-blue-600 w-4 h-4"
              />
              New SKUs only
            </label>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-100">
          <LegendItem flag="verified"     label="Verified" />
          <LegendItem flag="inferred"     label="Inferred / Converted" />
          <LegendItem flag="unresolved"   label="Unresolved / Missing" />
          <LegendItem flag="disqualified" label="Disqualified" />
          <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium bg-green-50 text-green-700 border-green-200">
            L1 = Lowest qualified price on this line
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto rounded-xl border border-slate-200 shadow-sm bg-white">
        <table className="w-full border-collapse min-w-[1000px] text-xs">
          {/* Sticky header */}
          <thead className="sticky top-0 z-20 bg-slate-50 border-b-2 border-slate-200">
            <tr>
              <th className="sticky left-0 bg-slate-50 text-left px-3 py-3 text-slate-500 font-semibold uppercase tracking-wider w-9 border-r border-slate-200">#</th>
              <th className="sticky left-9 bg-slate-50 text-left px-3 py-3 text-slate-500 font-semibold uppercase tracking-wider w-20 border-r border-slate-200">Code</th>
              <th className="text-left px-3 py-3 text-slate-500 font-semibold uppercase tracking-wider min-w-[200px] border-r border-slate-200">Description</th>
              <th className="text-right px-3 py-3 text-slate-500 font-semibold uppercase tracking-wider border-r border-slate-200">Qty</th>
              <th className="text-right px-3 py-3 text-slate-500 font-semibold uppercase tracking-wider border-r border-slate-200">Budget</th>
              {VENDORS.map((v) => (
                <th
                  key={v.key}
                  className={`text-center px-3 py-2 font-semibold border-r border-slate-200 min-w-[110px] ${
                    v.key === "v4" ? "text-slate-400 bg-slate-100" : "text-slate-700"
                  }`}
                >
                  <div className="text-xs font-bold">{v.short}</div>
                  {v.key === "v4" && (
                    <div className="text-xs font-semibold text-red-500 mt-0.5">DISQUALIFIED</div>
                  )}
                  {(v.key === "v3" || v.key === "v5") && (
                    <div className="text-xs font-medium text-amber-600 mt-0.5">Partial</div>
                  )}
                  {(v.key === "v1" || v.key === "v2") && (
                    <div className="text-xs font-medium text-green-600 mt-0.5">Qualified</div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.map((item) => {
              const minVendor = getMinVendor(item);
              return (
                <tr key={item.lineNo} className="hover:bg-blue-50/40 transition-colors duration-100">
                  {/* Line # */}
                  <td className="sticky left-0 bg-white hover:bg-blue-50/40 px-3 py-2.5 text-slate-400 font-mono border-r border-slate-100 text-center">
                    {item.lineNo}
                  </td>
                  {/* Code */}
                  <td className="sticky left-9 bg-white hover:bg-blue-50/40 px-3 py-2.5 font-mono text-slate-600 border-r border-slate-100">
                    <div className="flex items-center gap-1 flex-wrap">
                      {item.itemCode}
                      {item.isNewSKU && (
                        <span className="text-xs bg-purple-100 text-purple-700 border border-purple-200 px-1.5 py-0 rounded-full font-semibold leading-5">
                          NEW
                        </span>
                      )}
                    </div>
                  </td>
                  {/* Description */}
                  <td className="px-3 py-2.5 text-slate-700 border-r border-slate-100">
                    <span className="line-clamp-2 leading-snug">{item.description}</span>
                  </td>
                  {/* Qty */}
                  <td className="px-3 py-2.5 text-right text-slate-500 font-mono border-r border-slate-100 whitespace-nowrap">
                    {item.estQty.toLocaleString("en-IN")}
                  </td>
                  {/* Budget */}
                  <td className="px-3 py-2.5 text-right text-slate-700 font-semibold font-mono border-r border-slate-100 whitespace-nowrap">
                    ₹{item.budgetPrice.toFixed(2)}
                  </td>
                  {/* Vendor cells */}
                  {(["v1", "v2", "v3", "v4", "v5"] as VendorKey[]).map((vk) => {
                    const cell = item[vk];
                    const isL1 = minVendor?.key === vk;
                    return (
                      <td
                        key={vk}
                        className={`px-2 py-2 border-r border-slate-100 ${vk === "v4" ? "bg-slate-50/80" : ""}`}
                      >
                        <PriceCell cell={cell} lineNo={item.lineNo} isL1={isL1} />
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-400 flex items-center gap-1.5">
        <svg className="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Hover any price cell to view the original raw quote text, conversion methodology, and trust classification.
        L1 badge = lowest qualified landed price on that line (excludes disqualified &amp; unresolved).
      </p>
    </div>
  );
}

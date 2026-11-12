import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";
import { AWARD_SCENARIOS } from "../data/rfxData";

const SCENARIO_COLORS = {
  budget: "#94a3b8",
  scenarioA: "#2563eb",
  scenarioB: "#16a34a",
  scenarioC: "#7c3aed",
};

const chartData = [
  {
    name: "Master Budget",
    spend: 40003750,
    fill: SCENARIO_COLORS.budget,
    shortName: "Budget",
  },
  {
    name: "Scenario A: Unconstrained L1",
    spend: 37447255,
    fill: SCENARIO_COLORS.scenarioA,
    shortName: "Scenario A",
  },
  {
    name: "Scenario B: Quality-Gated L1",
    spend: 37915847,
    fill: SCENARIO_COLORS.scenarioB,
    shortName: "Scenario B",
  },
  {
    name: "Scenario C: Quality + Dual Sourcing",
    spend: 38034120,
    fill: SCENARIO_COLORS.scenarioC,
    shortName: "Scenario C",
  },
];

const formatCrore = (value: number) => `₹${(value / 10000000).toFixed(2)} Cr`;

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const item = payload[0];
    const scenario = AWARD_SCENARIOS[
      label === "Master Budget" ? "budget" :
      label.includes("Scenario A") ? "scenarioA" :
      label.includes("Scenario B") ? "scenarioB" : "scenarioC"
    ] as any;

    return (
      <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-md min-w-[240px]">
        <p className="text-xs font-bold text-slate-800 mb-1">{label}</p>
        <p className="text-xl font-bold font-mono text-blue-600">{formatCrore(item.value)}</p>
        {scenario?.savings > 0 && (
          <p className="text-xs font-semibold text-green-700 mt-1">
            Net Savings: ₹{(scenario.savings / 100000).toFixed(2)} L ({scenario.savingsPct}%)
          </p>
        )}
        {scenario?.compliance && scenario.compliance !== "Baseline" && (
          <p className="text-xs font-medium text-amber-700 mt-0.5">
            Cost of Compliance: {scenario.compliance}
          </p>
        )}
        {scenario?.takeaway && (
          <p className="text-[11px] text-slate-500 mt-2 border-t border-slate-100 pt-1.5 leading-snug">
            {scenario.takeaway}
          </p>
        )}
      </div>
    );
  }
  return null;
};

export default function AwardScenarios() {
  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-800">Award Scenarios & Optimization Analytics</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Data directly mapped from the <span className="font-semibold text-slate-700">Award Scenarios Engine</span> — evaluate total spend, compliance trade-offs, and dual-sourcing insurance.
        </p>
      </div>

      {/* Scenario Comparison Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Budget Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Internal Budget</span>
              <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2 py-0.5 rounded">Baseline</span>
            </div>
            <p className="text-2xl font-bold font-mono text-slate-800">₹4.00 Cr</p>
            <p className="text-xs text-slate-500 mt-1">₹40,003,750 ceiling</p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500">
            Internal benchmark estimate for 30 packaging items.
          </div>
        </div>

        {/* Scenario A Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col justify-between relative">
          <div className="absolute top-0 right-0 w-2 h-full bg-blue-500 rounded-r-xl"></div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-blue-700 uppercase tracking-wider">Scenario A</span>
              <span className="text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded">
                Unconstrained L1
              </span>
            </div>
            <p className="text-2xl font-bold font-mono text-slate-800">₹3.77 Cr</p>
            <p className="text-xs font-semibold text-green-700 mt-1">Saves ₹22.59 L (5.65%)</p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-red-600 font-medium">
            High Commercial Risk: Allocates lines to uncertified V4 (expired ISO cert).
          </div>
        </div>

        {/* Scenario B Card (Recommended) */}
        <div className="bg-white border-2 border-green-500/80 rounded-xl p-4 shadow-md flex flex-col justify-between relative bg-green-50/10">
          <div className="absolute top-0 right-0 w-2 h-full bg-green-600 rounded-r-xl"></div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-green-800 uppercase tracking-wider">Scenario B</span>
              <span className="text-xs font-bold bg-green-100 text-green-800 border border-green-300 px-2 py-0.5 rounded">
                Recommended ★
              </span>
            </div>
            <p className="text-2xl font-bold font-mono text-slate-900">₹3.80 Cr</p>
            <p className="text-xs font-semibold text-green-700 mt-1">Saves ₹19.85 L (4.96%)</p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-green-800 font-medium">
            Zero Quality Risk: Enforces quality gates Q1–Q7. Eliminates uncertified vendors.
          </div>
        </div>

        {/* Scenario C Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col justify-between relative">
          <div className="absolute top-0 right-0 w-2 h-full bg-purple-500 rounded-r-xl"></div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-purple-700 uppercase tracking-wider">Scenario C</span>
              <span className="text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200 px-2 py-0.5 rounded">
                Dual Sourcing
              </span>
            </div>
            <p className="text-2xl font-bold font-mono text-slate-800">₹3.81 Cr</p>
            <p className="text-xs font-semibold text-green-700 mt-1">Saves ₹18.85 L (4.71%)</p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-purple-700 font-medium">
            Supply Continuity: 70/30 dual-source split on Criticality A lines.
          </div>
        </div>
      </div>

      {/* Spend Chart */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Total Annual Spend Comparison</h3>
            <p className="text-xs text-slate-500 mt-0.5">Bar chart visualization across baseline budget and three optimization engines</p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5 text-slate-600">
              <span className="w-3 h-3 rounded bg-blue-600 inline-block"></span> Unconstrained
            </span>
            <span className="flex items-center gap-1.5 text-slate-600">
              <span className="w-3 h-3 rounded bg-green-600 inline-block"></span> Quality-Gated
            </span>
            <span className="flex items-center gap-1.5 text-slate-600">
              <span className="w-3 h-3 rounded bg-purple-600 inline-block"></span> Dual Sourcing
            </span>
          </div>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis
                dataKey="shortName"
                tick={{ fill: "#475569", fontSize: 12, fontWeight: 500 }}
                axisLine={{ stroke: "#cbd5e1" }}
                tickLine={false}
              />
              <YAxis
                tickFormatter={(v) => `₹${(v / 10000000).toFixed(2)} Cr`}
                tick={{ fill: "#64748b", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                domain={[36000000, 41000000]}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "#f8fafc" }} />
              <ReferenceLine
                y={40003750}
                stroke="#dc2626"
                strokeDasharray="4 4"
                label={{ value: "Budget Cap: ₹4.00 Cr", position: "top", fill: "#dc2626", fontSize: 11, fontWeight: 600 }}
              />
              <Bar dataKey="spend" radius={[6, 6, 0, 0]} maxBarSize={64}>
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Cost of Compliance Deep-Dive Box */}
      <div className="bg-white border border-amber-200 rounded-xl p-6 shadow-sm bg-amber-50/20">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center font-bold text-lg flex-shrink-0">
            ⚖️
          </div>
          <div className="space-y-3 flex-1">
            <div>
              <h3 className="text-base font-bold text-slate-800">
                Cost of Compliance & Risk Premium Summary
              </h3>
              <p className="text-sm text-slate-600 mt-1">
                The <strong className="text-slate-800">Cost of Compliance</strong> represents the rational premium paid above raw unconstrained L1 pricing to eliminate quality failure risks and guarantee supplier reliability.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
              <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-sm">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Quality Gate Premium</p>
                <p className="text-xl font-bold font-mono text-slate-800 mt-1">+₹4,68,592</p>
                <p className="text-xs text-amber-700 mt-0.5 font-medium">+1.25% higher than Scenario A</p>
                <p className="text-[11px] text-slate-500 mt-2">
                  Premium to eliminate uncertified Vendor 4 across all lines.
                </p>
              </div>

              <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-sm">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Dual Sourcing Insurance</p>
                <p className="text-xl font-bold font-mono text-slate-800 mt-1">+₹1,18,273</p>
                <p className="text-xs text-purple-700 mt-0.5 font-medium">+0.31% higher than Scenario B</p>
                <p className="text-[11px] text-slate-500 mt-2">
                  Additional cost to split 5 Critical SKUs 70/30 across two vendors (+₹5,86,865 / +1.57% higher than Scenario A).
                </p>
              </div>

              <div className="bg-white border border-green-200 rounded-lg p-3.5 shadow-sm bg-green-50/30">
                <p className="text-xs font-semibold text-green-700 uppercase tracking-wider">Executive Decision</p>
                <p className="text-base font-bold text-slate-800 mt-1">Award on Scenario B</p>
                <p className="text-xs text-green-700 mt-0.5 font-medium">Saves ₹20.88 Lakhs vs Budget</p>
                <p className="text-[11px] text-slate-600 mt-2">
                  Balances maximum achievable savings with 100% compliant suppliers.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

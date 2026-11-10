// ============================================================
// RFx Master Data — sourced from RFx_Master_Updated.xlsx
// ============================================================

export type TrustFlag =
  | "verified"
  | "inferred"
  | "unresolved"
  | "disqualified"
  | "not_quoted";

export interface VendorCell {
  value: number | string | null;
  flag: TrustFlag;
  originalRaw?: string; // tooltip: original quote text
  conversionNote?: string; // tooltip: conversion explanation
}

export interface LineItem {
  lineNo: number;
  itemCode: string;
  description: string;
  estQty: number;
  budgetPrice: number;
  isNewSKU: boolean;
  v1: VendorCell; // Apex
  v2: VendorCell; // PackTech
  v3: VendorCell; // Global Corrugators
  v4: VendorCell; // Sri Balaji (DISQUALIFIED)
  v5: VendorCell; // Standard Box
  normalizationNote: string;
}

export const VENDORS = [
  { key: "v1", name: "Apex Packaging", short: "Apex" },
  { key: "v2", name: "PackTech Solutions", short: "PackTech" },
  { key: "v3", name: "Global Corrugators", short: "Global" },
  { key: "v4", name: "Sri Balaji Packaging", short: "Sri Balaji" },
  { key: "v5", name: "Standard Box Corp", short: "StdBox" },
] as const;

export type VendorKey = "v1" | "v2" | "v3" | "v4" | "v5";

// ---- Helper ------------------------------------------------
function dq(value: number): VendorCell {
  return { value, flag: "disqualified", originalRaw: `₹${value} /UoM`, conversionNote: "V4 Sri Balaji is fully disqualified (ISO cert expired Oct 2026, capacity 280 TPM < 300 TPM threshold, no testing lab, rejection rate 2.4% > 1.5% — failed Q1–Q5)." };
}
function ver(value: number, raw?: string): VendorCell {
  return { value, flag: "verified", originalRaw: raw ?? `₹${value} /UoM` };
}
function inf(value: number, raw: string, note: string): VendorCell {
  return { value, flag: "inferred", originalRaw: raw, conversionNote: note };
}
function unresolved(raw?: string): VendorCell {
  return { value: null, flag: "unresolved", originalRaw: raw ?? "Not quoted / unresolvable" };
}
function notQuoted(): VendorCell {
  return { value: null, flag: "not_quoted", originalRaw: "Line omitted from vendor's submission" };
}

// ---- Line Items data (from Normalized Comparison + Historical PO Master) ---
export const LINE_ITEMS: LineItem[] = [
  {
    lineNo: 1, itemCode: "CP-001",
    description: "Shipper carton 300×200×150, 3-ply B-flute",
    estQty: 147000, budgetPrice: 6.25, isNewSKU: false,
    v1: inf(6.12, "₹6,120 per 1,000 Nos", "Converted from per-1,000 unit pricing to per-unit (÷1,000). FX: INR."),
    v2: ver(6.38, "₹6.38 /Nos"),
    v3: inf(5.94, "USD 0.0708 /Nos (FOB Shanghai)", "Converted from USD at ₹83.95/USD (RFx closing FX). Original: USD 0.0708/Nos."),
    v4: dq(5.95),
    v5: inf(6.61, "₹38/kg + ₹0.45 freight surcharge", "Converted from ₹/kg rate using est. weight 0.165 kg/Nos + freight levy."),
    normalizationNote: "V1: Converted from /1,000; V3: Converted USD; V5: ₹38/kg+freight",
  },
  {
    lineNo: 2, itemCode: "CP-002",
    description: "Shipper carton 350×250×200, 3-ply B-flute",
    estQty: 110000, budgetPrice: 10.45, isNewSKU: false,
    v1: inf(10.35, "₹10,350 per 1,000 Nos", "Converted from per-1,000 unit pricing to per-unit."),
    v2: ver(10.14, "₹10.14 /Nos"),
    v3: inf(10.03, "USD 0.1195 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(9.92),
    v5: inf(10.14, "₹38/kg + freight", "Converted from ₹/kg using est. weight 0.253 kg/Nos."),
    normalizationNote: "V1: Converted from /1,000; V5: ₹38/kg+freight",
  },
  {
    lineNo: 3, itemCode: "CP-003",
    description: "Shipper carton 400×300×250, 3-ply C-flute",
    estQty: 85500, budgetPrice: 14.55, isNewSKU: false,
    v1: ver(14.70, "₹14.70 /Nos"),
    v2: ver(14.26, "₹14.26 /Nos"),
    v3: inf(14.11, "USD 0.1681 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(15.06),
    v5: inf(14.81, "₹38/kg + freight", "Converted from ₹/kg using est. weight 0.370 kg/Nos."),
    normalizationNote: "V5: ₹38/kg+freight",
  },
  {
    lineNo: 4, itemCode: "CP-004",
    description: "Shipper carton 450×300×300, 3-ply C-flute",
    estQty: 61000, budgetPrice: 18.35, isNewSKU: false,
    v1: ver(17.80, "₹17.80 /Nos"),
    v2: ver(18.53, "₹18.53 /Nos"),
    v3: inf(17.62, "USD 0.2099 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(19.08),
    v5: inf(19.49, "₹38/kg + freight", "Converted from ₹/kg using est. weight 0.487 kg/Nos."),
    normalizationNote: "V5: ₹38/kg+freight",
  },
  {
    lineNo: 5, itemCode: "CP-005",
    description: "Master carton 500×350×300, 5-ply BC-flute",
    estQty: 73500, budgetPrice: 44.90, isNewSKU: false,
    v1: ver(45.80, "₹45.80 /Nos"),
    v2: ver(43.55, "₹43.55 /Nos"),
    v3: inf(43.10, "USD 0.5134 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(42.48),
    v5: inf(43.03, "₹42/kg + freight", "Converted from ₹/kg using est. weight 0.980 kg/Nos."),
    normalizationNote: "V5: Converted from ₹42/kg+freight",
  },
  {
    lineNo: 6, itemCode: "CP-006",
    description: "Master carton 600×400×350, 5-ply BC-flute",
    estQty: 55000, budgetPrice: 56.90, isNewSKU: false,
    v1: ver(55.76, "₹55.76 /Nos"),
    v2: ver(57.47, "₹57.47 /Nos"),
    v3: inf(54.62, "USD 0.6506 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(53.94),
    v5: inf(58.24, "₹42/kg + freight", "Converted from ₹/kg."),
    normalizationNote: "V5: Converted from ₹42/kg+freight",
  },
  {
    lineNo: 7, itemCode: "CP-007",
    description: "Master carton 600×450×400, 5-ply BC-flute",
    estQty: 43000, budgetPrice: 72.30, isNewSKU: false,
    v1: ver(73.02, "₹73.02 /Nos"),
    v2: ver(70.85, "₹70.85 /Nos"),
    v3: inf(70.13, "USD 0.8354 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(74.12),
    v5: inf(74.02, "₹42/kg + freight", "Converted from ₹/kg."),
    normalizationNote: "V5: Converted from ₹42/kg+freight",
  },
  {
    lineNo: 8, itemCode: "CP-008",
    description: "Master carton 700×500×450, 5-ply BC-flute",
    estQty: 30500, budgetPrice: 105.05, isNewSKU: false,
    v1: ver(100.85, "₹100.85 /Nos"),
    v2: ver(107.15, "₹107.15 /Nos"),
    v3: inf(99.79, "USD 1.1887 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(106.92),
    v5: inf(99.94, "₹42/kg + freight", "Converted from ₹/kg."),
    normalizationNote: "V5: Converted from ₹42/kg+freight",
  },
  {
    lineNo: 9, itemCode: "CP-009",
    description: "Master carton 800×600×500, 5-ply BC-flute",
    estQty: 14500, budgetPrice: 165.85, isNewSKU: false,
    v1: ver(164.19, "₹164.19 /Nos"),
    v2: ver(160.87, "₹160.87 /Nos"),
    v3: inf(159.21, "USD 1.8964 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(156.63),
    v5: inf(147.03, "₹42/kg + freight", "Converted from ₹/kg."),
    normalizationNote: "V5: Converted from ₹42/kg+freight",
  },
  {
    lineNo: 10, itemCode: "CP-010",
    description: "Heavy-duty carton 900×600×600, 7-ply",
    estQty: 4500, budgetPrice: 274.40, isNewSKU: false,
    v1: ver(268.91, "₹268.91 /Nos"),
    v2: ver(279.89, "₹279.89 /Nos"),
    v3: { value: null, flag: "disqualified", originalRaw: "NOT QUOTED", conversionNote: "V3 (Global Corrugators) failed Q6 — no 7-ply in-house capability. Disqualified on Line 10 & 30." },
    v4: dq(264.38),
    v5: inf(280.18, "Same as last year (resolved from FY25 PO: ₹270.40)", "Resolved from FY25 PO at ₹270.40 × 3.6% material escalation."),
    normalizationNote: "V3 omitted quote; V5 resolved from FY25 PO",
  },
  {
    lineNo: 11, itemCode: "CP-011",
    description: "E-com mailer box 250×180×60, E-flute",
    estQty: 183500, budgetPrice: 3.50, isNewSKU: false,
    v1: ver(3.50, "₹3.50 /Nos"),
    v2: ver(3.36, "₹3.36 /Nos"),
    v3: inf(3.43, "USD 0.0409 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(3.39),
    v5: inf(3.39, "Same as last year (FY25 PO: ₹3.25)", "Resolved from FY25 PO ₹3.25 + escalation."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 12, itemCode: "CP-012",
    description: "E-com mailer box 300×220×80, E-flute",
    estQty: 122500, budgetPrice: 6.00, isNewSKU: false,
    v1: ver(5.49, "₹5.49 /Nos"),
    v2: ver(5.70, "₹5.70 /Nos"),
    v3: inf(6.06, "USD 0.0722 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(5.76),
    v5: inf(5.83, "Same as last year (FY25 PO: ₹5.60)", "Resolved from FY25 PO ₹5.60 + escalation."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 13, itemCode: "CP-013",
    description: "E-com mailer box 350×250×100, B-flute",
    estQty: 98000, budgetPrice: 8.55, isNewSKU: false,
    v1: ver(8.46, "₹8.46 /Nos"),
    v2: ver(8.29, "₹8.29 /Nos"),
    v3: inf(8.21, "USD 0.0978 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(8.31),
    v5: inf(8.51, "Same as last year (FY25 PO: ₹8.15)", "Resolved from FY25 PO."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 14, itemCode: "CP-014",
    description: "Retail inner carton 200×150×90, E-flute",
    estQty: 147000, budgetPrice: 5.00, isNewSKU: false,
    v1: ver(5.10, "₹5.10 /Nos"),
    v2: ver(4.80, "₹4.80 /Nos"),
    v3: inf(4.95, "USD 0.0590 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(4.71),
    v5: inf(5.03, "Same as last year (FY25 PO: ₹4.85)", "Resolved from FY25 PO."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 15, itemCode: "CP-015",
    description: "Retail inner carton 280×200×120, E-flute",
    estQty: 110000, budgetPrice: 9.80, isNewSKU: false,
    v1: ver(4.85, "₹4.85 /Nos"),
    v2: ver(9.55, "₹9.55 /Nos"),
    v3: inf(9.60, "USD 0.1144 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(9.23),
    v5: inf(10.17, "Same as last year (FY25 PO: ₹9.85)", "Resolved from FY25 PO."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 16, itemCode: "CP-016",
    description: "Retail inner carton 320×240×180, B-flute",
    estQty: 73500, budgetPrice: 16.70, isNewSKU: false,
    v1: ver(16.37, "₹16.37 /Nos"),
    v2: ver(16.87, "₹16.87 /Nos"),
    v3: inf(16.20, "USD 0.1930 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(15.85),
    v5: inf(17.04, "Same as last year (FY25 PO: ₹16.50)", "Resolved from FY25 PO."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 17, itemCode: "CP-017",
    description: "Telescopic lid & base set 420×320×120",
    estQty: 24500, budgetPrice: 15.80, isNewSKU: false,
    v1: ver(15.96, "₹15.96 /Nos"),
    v2: ver(15.48, "₹15.48 /Nos"),
    v3: inf(15.64, "USD 0.1863 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(16.27),
    v5: inf(16.34, "Same as last year (FY25 PO: ₹15.65)", "Resolved from FY25 PO."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 18, itemCode: "CP-018",
    description: "Partition set, 12-cell for 600×400",
    estQty: 55000, budgetPrice: 10.40, isNewSKU: false,
    v1: ver(10.09, "₹10.09 /Nos"),
    v2: ver(10.50, "₹10.50 /Nos"),
    v3: inf(10.19, "USD 0.1214 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(9.89),
    v5: inf(10.43, "Same as last year (FY25 PO: ₹9.95)", "Resolved from FY25 PO."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 19, itemCode: "CP-019",
    description: "Partition set, 6-cell for 400×300",
    estQty: 49000, budgetPrice: 5.40, isNewSKU: false,
    v1: ver(5.51, "₹5.51 /Nos"),
    v2: ver(5.24, "₹5.24 /Nos"),
    v3: inf(5.35, "USD 0.0637 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(5.12),
    v5: inf(5.73, "Same as last year (FY25 PO: ₹5.50)", "Resolved from FY25 PO."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 20, itemCode: "CP-020",
    description: "Pallet layer pad 1200×1000, 5-ply BC",
    estQty: 22000, budgetPrice: 48.60, isNewSKU: false,
    v1: ver(48.11, "₹48.11 /Nos"),
    v2: ver(47.63, "₹47.63 /Nos"),
    v3: inf(47.14, "USD 0.5616 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(46.99),
    v5: inf(50.18, "₹42/kg + freight", "Converted from ₹/kg rate."),
    normalizationNote: "V5: Converted from ₹42/kg+freight",
  },
  {
    lineNo: 21, itemCode: "CP-021",
    description: "Pallet top sheet 1200×1000, 3-ply C",
    estQty: 27000, budgetPrice: 21.60, isNewSKU: false,
    v1: ver(21.17, "₹21.17 /Nos"),
    v2: ver(21.82, "₹21.82 /Nos"),
    v3: notQuoted(),
    v4: dq(21.12),
    v5: inf(21.57, "Same as last year (FY25 PO: ₹20.55)", "Resolved from FY25 PO."),
    normalizationNote: "V3 omitted quote; V5: Resolved from FY25 PO",
  },
  {
    lineNo: 22, itemCode: "CP-022",
    description: "Corrugated sheet 1000×800, 3-ply B",
    estQty: 49000, budgetPrice: 13.95, isNewSKU: false,
    v1: ver(13.81, "₹13.81 /Nos"),
    v2: ver(13.53, "₹13.53 /Nos"),
    v3: inf(13.67, "USD 0.1628 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(13.27),
    v5: inf(13.71, "Same as last year (FY25 PO: ₹13.05)", "Resolved from FY25 PO."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 23, itemCode: "CP-023",
    description: "Corrugated roll, E-flute, 1.2m wide",
    estQty: 98000, budgetPrice: 16.30, isNewSKU: false,
    v1: ver(15.97, "₹15.97 /Nos"),
    v2: ver(16.63, "₹16.63 /Nos"),
    v3: inf(15.81, "USD 0.1884 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(16.82),
    v5: inf(16.48, "Same as last year (FY25 PO: ₹15.75)", "Resolved from FY25 PO."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 24, itemCode: "CP-024",
    description: "Corrugated roll, B-flute, 1.5m wide",
    estQty: 49000, budgetPrice: 18.60, isNewSKU: false,
    v1: ver(18.41, "₹18.41 /Nos"),
    v2: ver(18.23, "₹18.23 /Nos"),
    v3: inf(18.04, "USD 0.2149 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(19.06),
    v5: inf(18.78, "Same as last year (FY25 PO: ₹17.95)", "Resolved from FY25 PO."),
    normalizationNote: "V5: Resolved from FY25 PO",
  },
  {
    lineNo: 25, itemCode: "CP-025",
    description: "Shelf-ready display tray 400×300×80",
    estQty: 36500, budgetPrice: 6.15, isNewSKU: true,
    v1: ver(6.21, "₹6.21 /Nos"),
    v2: ver(6.03, "₹6.03 /Nos"),
    v3: notQuoted(),
    v4: dq(5.95),
    v5: unresolved("'Same as last year' — but Line 25 is a New SKU with no FY25 PO history to reference."),
    normalizationNote: "V3 omitted quote; V5: New SKU (no PO history) → UNRESOLVED",
  },
  {
    lineNo: 26, itemCode: "CP-026",
    description: "Export carton 550×400×350, moisture-barrier",
    estQty: 30500, budgetPrice: 74.55, isNewSKU: false,
    v1: ver(72.31, "₹72.31 /Nos"),
    v2: ver(73.80, "₹73.80 /Nos"),
    v3: inf(71.57, "USD 0.8526 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(71.74),
    v5: { value: null, flag: "disqualified", originalRaw: "Quoted ₹58.00 /Nos (no moisture-barrier treatment)", conversionNote: "V5 Standard Box failed Q7 — cannot supply moisture-barrier treatment. Disqualified on Lines 26 & 27 specifically." },
    normalizationNote: "V5 fails Q7 (No moisture-barrier treatment) → DISQUALIFIED",
  },
  {
    lineNo: 27, itemCode: "CP-027",
    description: "Export carton 650×450×400, moisture-barrier",
    estQty: 18500, budgetPrice: 105.85, isNewSKU: true,
    v1: ver(103.73, "₹103.73 /Nos"),
    v2: ver(106.91, "₹106.91 /Nos"),
    v3: inf(102.68, "USD 1.2231 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(101.88),
    v5: unresolved("'Same as last year' — but Line 27 is a New SKU with no FY25 PO history to reference. Additionally, V5 is disqualified on this line due to Q7 failure (no moisture-barrier capability)."),
    normalizationNote: "V5: New SKU (no PO history) + fails Q7 → UNRESOLVED",
  },
  {
    lineNo: 28, itemCode: "CP-028",
    description: "Crash-lock carton 220×160×240, full print",
    estQty: 85500, budgetPrice: 9.00, isNewSKU: true,
    v1: ver(9.09, "₹9.09 /Nos"),
    v2: ver(8.73, "₹8.73 /Nos"),
    v3: inf(8.91, "USD 0.1062 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(8.50),
    v5: unresolved("'Same as last year' — but Line 28 is a New SKU with no FY25 PO history to reference."),
    normalizationNote: "V5: New SKU (no PO history) → UNRESOLVED",
  },
  {
    lineNo: 29, itemCode: "CP-029",
    description: "Corner-cap insert set (4 pcs), 5-ply BC",
    estQty: 110000, budgetPrice: 9.40, isNewSKU: true,
    v1: ver(9.31, "₹9.31 /Nos"),
    v2: ver(9.21, "₹9.21 /Nos"),
    v3: inf(9.12, "USD 0.1087 /Nos", "Converted from USD at ₹83.95/USD."),
    v4: dq(8.90),
    v5: unresolved("'Same as last year' — but Line 29 is a New SKU with no FY25 PO history to reference."),
    normalizationNote: "V5: New SKU (no PO history) → UNRESOLVED",
  },
  {
    lineNo: 30, itemCode: "CP-030",
    description: "Pallet box 1100×900×800, 7-ply BCB",
    estQty: 3000, budgetPrice: 535.30, isNewSKU: true,
    v1: ver(519.24, "₹519.24 /Nos"),
    v2: ver(540.65, "₹540.65 /Nos"),
    v3: { value: null, flag: "disqualified", originalRaw: "NOT QUOTED — V3 failed Q6 (no 7-ply in-house capability)", conversionNote: "V3 (Global Corrugators) failed Q6 — no 7-ply in-house capability. Disqualified on Lines 10 & 30." },
    v4: dq(514.98),
    v5: unresolved("New SKU with no FY25 PO history. V5 cannot reference historical price."),
    normalizationNote: "V3 fails Q6 (No 7-ply) → DISQUALIFIED; V5 has no PO history → UNRESOLVED",
  },
];

// ---- Questionnaire Audit & Gate --------------------------------
export interface QGateRow {
  question: string;
  v1: string;
  v2: string;
  v3: string;
  v4: string;
  v5: string;
  rule: string;
}

export const QGATE_ROWS: QGateRow[] = [
  {
    question: "Q1: ISO 9001:2015 Cert",
    v1: "Pass (Exp: 2028)", v2: "Pass (Exp: 2027)", v3: "Pass (Exp: 2028)",
    v4: "FAIL (Expired Oct 2026)", v5: "Pass (Exp: 2027)",
    rule: "Mandatory gate; uncertified vendor disqualified.",
  },
  {
    question: "Q2: Monthly Capacity (≥300 TPM)",
    v1: "650 TPM (Pass)", v2: "420 TPM (Pass)", v3: "1,200 TPM (Pass)",
    v4: "280 TPM (FAIL)", v5: "380 TPM (Pass)",
    rule: "Capacity threshold for supply continuity.",
  },
  {
    question: "Q3: In-House Testing Lab",
    v1: "Yes (Pass)", v2: "Yes (Pass)", v3: "Yes (Pass)",
    v4: "No (FAIL)", v5: "Yes (Pass)",
    rule: "Lab report verification.",
  },
  {
    question: "Q4: Customer Rejection (≤1.5%)",
    v1: "0.8% (Pass)", v2: "1.1% (Pass)", v3: "0.4% (Pass)",
    v4: "2.4% (FAIL)", v5: "1.2% (Pass)",
    rule: "Quality tolerance gate.",
  },
  {
    question: "Q5: Active Customers (≥3)",
    v1: "12 (Pass)", v2: "6 (Pass)", v3: "20 (Pass)",
    v4: "2 (FAIL)", v5: "5 (Pass)",
    rule: "Minimum customer references.",
  },
  {
    question: "Q6: 7-Ply In-House (Lines 10 & 30)",
    v1: "Yes (Pass)", v2: "Yes (Pass)", v3: "NO — Disqualified L10, 30",
    v4: "No (FAIL)", v5: "Yes (Pass)",
    rule: "Line-specific capability gate.",
  },
  {
    question: "Q7: Moisture-Barrier (Lines 26 & 27)",
    v1: "Yes (Pass)", v2: "Yes (Pass)", v3: "Yes (Pass)",
    v4: "No (FAIL)", v5: "NO — Disqualified L26, 27",
    rule: "Line-specific capability gate.",
  },
  {
    question: "Overall Quality Gate Decision",
    v1: "QUALIFIED", v2: "QUALIFIED", v3: "PARTIAL (Lines 10, 30 Banned)",
    v4: "DISQUALIFIED (Q1–Q5 Failed)", v5: "PARTIAL (Lines 26, 27 Banned)",
    rule: "V4 eliminated from all qualified award models.",
  },
];

// ---- Award Scenarios Engine -----------------------------------
export const AWARD_SCENARIOS = {
  budget: { label: "Master Budget", totalSpend: 40003750, savings: 0, compliance: null },
  scenarioA: { label: "Unconstrained L1", totalSpend: 37744605, savings: 2259145, savingsPct: 5.65, compliance: "Baseline", eligibleVendors: "V1, V2, V3, V4, V5", takeaway: "High commercial risk: awards to uncertified V4" },
  scenarioB: { label: "Quality-Gated L1", totalSpend: 38019190, savings: 1984560, savingsPct: 4.96, compliance: "+₹2,74,585 (+0.73%)", eligibleVendors: "V1, V2, V3 (cond.), V5 (cond.)", takeaway: "Eliminates all quality risk for an extra ₹2.75 Lakhs" },
  scenarioC: { label: "Quality-Gated + Dual Sourcing", totalSpend: 38118864, savings: 1884886, savingsPct: 4.71, compliance: "+₹3,74,259 (+0.99%)", eligibleVendors: "V1, V2, V3 (cond.), V5 (cond.)", takeaway: "Insures 5 Critical SKUs against single points of failure" },
};

/**
 * Reading the FlowScore API from server components (S4-R10). Types mirror the backend's Pydantic
 * response schemas; the frontend never sees database rows. Every figure on screen comes from
 * these responses: this app formats numbers, it computes none (S4-R2, hard rule 4).
 */
import { apiBase } from "./api-base";

export type Band = "lower" | "middle" | "higher";
export type Status = "scored" | "refused";

export interface AssessmentSummary {
  id: number;
  as_of: string;
  status: Status;
  risk_band: Band | null;
  risk_percentile: number | null;
  model_version: string;
  created_at: string;
}

export interface Borrower {
  id: string;
  display_name: string;
  synthetic: boolean;
  created_at: string;
  history_start: string | null;
  history_end: string | null;
  latest_assessment: AssessmentSummary | null;
}

export interface Month {
  month: string;
  start: string;
  end: string;
  covered: boolean;
  money_in: number | null;
  money_out: number | null;
  net: number | null;
  closing_balance: number | null;
  transaction_count: number;
}

export interface Cashflow {
  borrower_id: string;
  months: Month[];
  daily_balance: { date: string; balance: number }[];
  window: { assessment_id: number; as_of: string; start: string; end: string } | null;
}

export interface Assessment {
  id: number;
  borrower_id: string;
  snapshot_id: number;
  features_version: string;
  created_at: string;
  window_start: string;
  status: Status;
  model_version: string;
  as_of: string;
  income_denominator: number | null;
  features: Record<string, number | null>;
  missing: { feature: string; imputed_value: number }[];
  out_of_range: { feature: string; value: number; min: number; max: number }[];
  risk_percentile: number | null;
  risk_band: Band | null;
  shap: { base_value: number; contributions: Record<string, number> } | null;
  notice: string;
}

export type Unit = "coefficient" | "ratio" | "months" | "months_of_income";

export interface GlossaryEntry {
  feature: string;
  label: string;
  description: string;
  unit: Unit;
  window_months: number;
}

export interface Health {
  model_version: string;
  features: string[];
  band_cutoffs: { lower_below: number; higher_above: number };
}

/** What went wrong, in terms a page can explain (S4-R11). */
export type ApiProblem = "unreachable" | "no-database" | "not-found" | "failed";

export class ApiError extends Error {
  constructor(public readonly problem: ApiProblem, public readonly status?: number) {
    super(`FlowScore API: ${problem}${status ? ` (${status})` : ""}`);
  }
}

async function get<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${apiBase()}/api/v1${path}`, { cache: "no-store" });
  } catch {
    throw new ApiError("unreachable");
  }
  if (res.status === 404) throw new ApiError("not-found", 404);
  if (res.status === 503) throw new ApiError("no-database", 503);
  if (!res.ok) throw new ApiError("failed", res.status);
  return (await res.json()) as T;
}

export const api = {
  borrowers: () => get<Borrower[]>("/borrowers"),
  borrower: (id: string) => get<Borrower>(`/borrowers/${encodeURIComponent(id)}`),
  cashflow: (id: string) => get<Cashflow>(`/borrowers/${encodeURIComponent(id)}/cashflow`),
  assessments: (id: string) => get<Assessment[]>(`/borrowers/${encodeURIComponent(id)}/assessments`),
  assessment: (id: string) => get<Assessment>(`/assessments/${encodeURIComponent(id)}`),
  glossary: () => get<GlossaryEntry[]>("/features/glossary"),
  health: () => get<Health>("/health"),
};

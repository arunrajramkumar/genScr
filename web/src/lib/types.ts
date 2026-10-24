export type Num = number | string | null;

export interface Metrics {
  as_of: string | null;
  close: Num;
  change_pct: Num;
  high_52w: Num;
  low_52w: Num;
  pct_from_52w_high: Num;
  return_1m: Num;
  return_1y: Num;
  avg_volume_20d: Num;
  turnover: Num;
  rsi_14: Num;
  sma_50: Num;
  sma_200: Num;
  market_cap: Num;
  pe: Num;
  pb: Num;
  roe: Num;
  roce: Num;
  debt_to_equity: Num;
  net_margin: Num;
  revenue_growth_yoy: Num;
  profit_growth_yoy: Num;
  piotroski_f: Num;
  altman_z: Num;
  dividend_yield: Num;
}

export interface Stock extends Partial<Metrics> {
  symbol: string;
  name: string;
  sector: string | null;
  industry?: string | null;
  isin?: string | null;
  listing_date?: string | null;
}

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Fundamental {
  period_end: string;
  period_type: "FY" | "Q";
  revenue: Num;
  operating_profit: Num;
  net_profit: Num;
  eps: Num;
  total_assets: Num;
  total_equity: Num;
  total_debt: Num;
  cfo: Num;
}

export interface FieldMeta {
  label: string;
  unit: string;
  higher_is_better: boolean | null;
}

export interface Preset {
  id: string;
  name: string;
  description: string;
  query: string;
}

export interface ScreenResponse {
  count: number;
  results: Stock[];
}

export interface Overview {
  as_of: string | null;
  breadth: { advances: number; declines: number; unchanged: number; new_highs: number; new_lows: number } | null;
  gainers: Stock[];
  losers: Stock[];
  active: Stock[];
  sectors: { sector: string; stocks: number; avg_change: Num; avg_return_1y: Num }[];
}

export interface CompareResponse {
  stocks: Stock[];
  fields: Record<string, FieldMeta>;
  performance: Record<string, { time: string; value: number }[]>;
}

export interface ReturnSummary {
  shares: number;
  market_value: number;
  cash_dividends: number;
  total_value: number;
  gain_pct: number;
  cagr: number | null;
}

export interface ReturnEvent {
  date: string;
  kind: "dividend" | "bonus" | "split";
  per_share?: number;
  received?: number;
  detail?: string;
  shares_added?: number;
  shares_after: number;
}

export interface TotalReturnResponse {
  amount: number;
  start_date: string;
  end_date: string;
  years: number;
  available_years: number;
  buy_price: number;
  end_price: number;
  initial_shares: number;
  bonus_split_shares: number;
  dividends_received: number;
  dividend_payments: number;
  price_only: ReturnSummary;
  with_dividends: ReturnSummary;
  reinvested: ReturnSummary;
  events: ReturnEvent[];
  series: { time: string; price: number; cash: number; reinvest: number }[];
  caveats: string[];
}

export interface DividendPayment {
  ex_date: string;
  amount: number;
  adjusted_amount: number;
  yield_pct: number | null;
  subject: string | null;
}

export interface DividendYear {
  fy: number;
  declared: number;
  adjusted: number;
  payments: number;
  yield_pct: number | null;
}

export interface DividendHistoryResponse {
  payments: DividendPayment[];
  years: DividendYear[];
  stats: {
    total_payments: number;
    first_dividend: string | null;
    paying_streak_years: number;
    growth_streak_years: number;
    dps_cagr_5y: number | null;
    last_fy: DividendYear | null;
    total_adjusted_since_first: number;
  };
}

export interface TimelineEvent {
  date: string;
  kind: "listing" | "milestone" | "dividend" | "bonus" | "split" | "rights" | "buyback" | "demerger" | "high" | "drawdown";
  title: string;
  text: string;
  source: string;
}

export interface Drawdown {
  peak_date: string;
  trough_date: string;
  depth_pct: number;
  recovered_date: string | null;
  days_to_recover: number | null;
  days_underwater: number;
}

export interface RiskResponse {
  since: string;
  volatility_1y_pct: number | null;
  up_days_1y_pct: number | null;
  current_drawdown_pct: number;
  peak_date: string;
  worst_drawdowns: Drawdown[];
  underwater: { time: string; value: number }[];
  calendar_years: { year: number; return_pct: number; partial: boolean }[];
  monthly: { year: number; month: number; return_pct: number }[];
  seasonality: { month: number; avg_pct: number; up: number; years: number }[];
}

export interface RankMetric {
  field: string;
  label: string;
  value: number;
  market_percentile: number;
  market_rank: number;
  market_total: number;
  sector_percentile?: number;
  sector_rank?: number;
  sector_total?: number;
}

export interface RanksResponse {
  sector: string | null;
  sector_size: number;
  metrics: RankMetric[];
}

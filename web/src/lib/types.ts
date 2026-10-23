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

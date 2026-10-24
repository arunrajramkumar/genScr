export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const RETRY_STATUSES = new Set([502, 503, 504]); // free-tier API waking up
const RETRY_DELAYS_MS = [2000, 5000, 10000];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    let res: Response;
    try {
      res = await fetch(`${API_URL}/api${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...init?.headers },
        cache: "no-store",
      });
    } catch (e) {
      if (init?.signal?.aborted || attempt >= RETRY_DELAYS_MS.length) throw e;
      await sleep(RETRY_DELAYS_MS[attempt]);
      continue;
    }
    if (RETRY_STATUSES.has(res.status) && attempt < RETRY_DELAYS_MS.length) {
      await sleep(RETRY_DELAYS_MS[attempt]);
      continue;
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? "");
      throw new Error(detail || `Request failed (${res.status})`);
    }
    return res.json();
  }
}

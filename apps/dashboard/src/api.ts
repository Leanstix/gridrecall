import type { DemoState } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request(path: string, method = "GET"): Promise<DemoState> {
  const response = await fetch(`${API_URL}${path}`, { method });
  if (!response.ok) {
    throw new Error(`GridRecall API returned ${response.status}`);
  }
  return response.json() as Promise<DemoState>;
}

export const demoApi = {
  state: () => request("/api/demo"),
  firstIncident: () => request("/api/demo/incidents/first", "POST"),
  secondIncident: () => request("/api/demo/incidents/second", "POST"),
  reset: () => request("/api/demo/reset", "POST"),
};

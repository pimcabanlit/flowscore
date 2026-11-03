/** Where the FastAPI backend listens: FLOWSCORE_API_URL, or the uvicorn default. Read on the
 * server only; it is not a secret, but it is never sent to the browser either. */
export function apiBase(): string {
  return (process.env.FLOWSCORE_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
}

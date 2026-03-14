const BASE = "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface Envelope<T> {
  data: T;
  warnings: string[];
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<Envelope<T>> {
  const opts: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  const json = await res.json();
  if (!res.ok) {
    const err = json.error ?? { code: "UNKNOWN", message: res.statusText };
    throw new ApiError(res.status, err.code, err.message, err.detail);
  }
  return json as Envelope<T>;
}

export async function apiGet<T>(path: string): Promise<Envelope<T>> {
  return request<T>("GET", path);
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
): Promise<Envelope<T>> {
  return request<T>("POST", path, body);
}

export async function apiPut<T>(
  path: string,
  body?: unknown,
): Promise<Envelope<T>> {
  return request<T>("PUT", path, body);
}

export async function apiPatch<T>(
  path: string,
  body?: unknown,
): Promise<Envelope<T>> {
  return request<T>("PATCH", path, body);
}

export async function apiDelete<T>(path: string): Promise<Envelope<T>> {
  return request<T>("DELETE", path);
}

import axios, { AxiosError } from 'axios';
import * as vscode from 'vscode';

export interface Template {
  id: string;
  name: string;
  description: string;
  stack: string;
  files: string[];
}

export interface Pack {
  id: string;
  name: string;
  description: string;
  stack: string;
  version?: string;
  files: string[];
}

export interface MarketplaceItem {
  id: string;
  name: string;
  description: string;
  /** e.g. bundled | remote | url host */
  source: string;
  url?: string;
  download_url?: string;
}

export interface PlanResponse {
  project_name: string;
  stack?: string;
  files: string[];
  template_id?: string;
  pack_id?: string;
  description?: string;
}

export type LicenseBakein = 'mit' | 'apache-2.0' | 'none';
export type CiBakein = 'auto' | 'python' | 'node' | 'none';

export interface BakeinOptions {
  license: LicenseBakein;
  ci: CiBakein;
  include_readme?: boolean;
}

export interface BakeinChoice {
  id: string;
  name: string;
}

export interface BakeinsResponse {
  licenses: BakeinChoice[];
  ci: BakeinChoice[];
}

export interface QualityIssue {
  code: string;
  severity: string;
  message: string;
  path?: string;
}

export interface GenerateResponse {
  project_name: string;
  stack?: string;
  files: Record<string, string>;
  template_id?: string;
  pack_id?: string;
  quality?: QualityIssue[];
}

export interface GitHubCreateRepoResponse {
  html_url: string;
  clone_url: string;
  full_name: string;
}

export interface PlanOptions {
  templateId?: string;
  packId?: string;
}

export interface GenerateOptions {
  templateId?: string;
  packId?: string;
  plan?: PlanResponse;
  jobId?: string;
  bakeins?: BakeinOptions;
}

function getBackendUrl(): string {
  const config = vscode.workspace.getConfiguration('creer');
  return (config.get<string>('backendUrl') || 'http://localhost:8000').replace(/\/$/, '');
}

export function formatAxiosError(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const ax = err as AxiosError<{ detail?: string }>;
    const detail = ax.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (ax.message) {
      return ax.message;
    }
  }
  if (err instanceof Error) {
    return err.message;
  }
  return fallback;
}

export async function fetchTemplates(): Promise<Template[]> {
  const backendUrl = getBackendUrl();
  const response = await axios.get<{ templates: Template[] }>(`${backendUrl}/templates`, {
    timeout: 30_000,
  });
  return response.data.templates ?? [];
}

export async function fetchPacks(): Promise<Pack[]> {
  const backendUrl = getBackendUrl();
  const response = await axios.get<{ packs: Pack[] }>(`${backendUrl}/packs`, {
    timeout: 30_000,
  });
  return response.data.packs ?? [];
}

/**
 * GET /marketplace → { items: MarketplaceItem[] }
 * Callers should treat missing/404 endpoints as “unavailable”.
 */
export async function fetchMarketplace(): Promise<MarketplaceItem[]> {
  const backendUrl = getBackendUrl();
  const response = await axios.get<{ items: MarketplaceItem[] }>(
    `${backendUrl}/marketplace`,
    { timeout: 30_000 }
  );
  return response.data.items ?? [];
}

/**
 * Auth headers for mutating registry endpoints when a token is available.
 * Backend accepts Authorization: Bearer and/or X-Creer-Token when CREER_REGISTRY_TOKEN is set.
 */
export function registryAuthHeaders(token?: string): Record<string, string> {
  const trimmed = token?.trim();
  if (!trimmed) {
    return {};
  }
  return {
    Authorization: `Bearer ${trimmed}`,
    'X-Creer-Token': trimmed,
  };
}

export interface PackInstallOptions {
  overwrite?: boolean;
  /** Optional registry write token (from SecretStorage / setting). */
  token?: string;
}

/**
 * POST /packs/install → { url, overwrite? } → installed pack
 * Backend returns `{ installed: true, pack: {...} }` (also tolerate a bare pack body).
 */
export async function installPack(
  url: string,
  options?: PackInstallOptions
): Promise<Pack> {
  const backendUrl = getBackendUrl();
  const body: { url: string; overwrite?: boolean } = { url };
  if (options?.overwrite !== undefined) {
    body.overwrite = options.overwrite;
  }
  const response = await axios.post<{ installed?: boolean; pack?: Pack } & Pack>(
    `${backendUrl}/packs/install`,
    body,
    {
      timeout: 120_000,
      headers: registryAuthHeaders(options?.token),
    }
  );
  const data = response.data;
  if (data?.pack && typeof data.pack === 'object') {
    return data.pack;
  }
  return data as Pack;
}

export interface RegistryItem {
  id: string;
  name: string;
  description?: string;
  stack?: string;
  version?: string;
  source?: string;
  files?: string[];
  download_url?: string;
  install_url?: string;
}

export interface RegistryResponse {
  version: string;
  base_url?: string | null;
  items: RegistryItem[];
}

/**
 * GET /registry?q=&source= — searchable self-hosted pack registry.
 */
export async function fetchRegistry(options?: {
  q?: string;
  source?: 'all' | 'bundled' | 'installed';
}): Promise<RegistryResponse> {
  const backendUrl = getBackendUrl();
  const response = await axios.get<RegistryResponse>(`${backendUrl}/registry`, {
    timeout: 30_000,
    params: {
      q: options?.q || undefined,
      source: options?.source || undefined,
    },
  });
  return {
    version: response.data.version,
    base_url: response.data.base_url,
    items: response.data.items ?? [],
  };
}

/** Item from a federated registry merge; `peer` is set when sourced from a remote host. */
export interface FederatedRegistryItem extends RegistryItem {
  /** Peer base URL when the item came from a remote Creer registry. */
  peer?: string;
}

export interface FederatedRegistryPeer {
  base_url: string;
  ok?: boolean;
  count?: number;
  error?: string | null;
}

export interface FederatedRegistryResponse {
  version?: string;
  /** Local registry snapshot. */
  local: RegistryResponse | {
    version?: string;
    base_url?: string | null;
    items?: RegistryItem[];
  };
  /** Configured peer hosts (reachable or not). */
  peers: FederatedRegistryPeer[];
  /** Merged catalog; peer-sourced rows may include `peer`. */
  items: FederatedRegistryItem[];
}

/**
 * GET /registry/federated?q=&source=&peers=&discover= — local + peer registry merge.
 * `peers` is a comma-separated list of extra peer base URLs (from settings or callers).
 * When `discover` is true, the backend expands one hop of peer-of-peer URLs.
 */
export async function fetchFederatedRegistry(options?: {
  q?: string;
  source?: string;
  /** Extra peer base URLs (comma-separated string or array). */
  peers?: string | string[];
  /** One-hop peer expansion (discover=true). */
  discover?: boolean;
}): Promise<FederatedRegistryResponse> {
  const backendUrl = getBackendUrl();
  let peersParam: string | undefined;
  if (Array.isArray(options?.peers)) {
    const joined = options.peers.map((p) => p.trim()).filter(Boolean).join(',');
    peersParam = joined || undefined;
  } else if (typeof options?.peers === 'string' && options.peers.trim()) {
    peersParam = options.peers.trim();
  }
  const response = await axios.get<FederatedRegistryResponse>(
    `${backendUrl}/registry/federated`,
    {
      timeout: 60_000,
      params: {
        q: options?.q || undefined,
        source: options?.source || undefined,
        peers: peersParam,
        discover: options?.discover === true ? true : undefined,
      },
    }
  );
  return {
    version: response.data.version,
    local: response.data.local ?? { items: [] },
    peers: response.data.peers ?? [],
    items: response.data.items ?? [],
  };
}

export interface RegistryDiscoverResponse {
  /** Discovered peer base URLs (one hop). */
  peers: string[];
  /** Optional notes from the backend. */
  discovered?: string[];
}

function normalizePeerUrlList(raw: unknown): string[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const out: string[] = [];
  const seen = new Set<string>();
  for (const entry of raw) {
    let url = '';
    if (typeof entry === 'string') {
      url = entry.trim().replace(/\/$/, '');
    } else if (entry && typeof entry === 'object') {
      const obj = entry as { url?: string; base_url?: string };
      url = (obj.url || obj.base_url || '').trim().replace(/\/$/, '');
    }
    if (url && !seen.has(url)) {
      seen.add(url);
      out.push(url);
    }
  }
  return out;
}

/**
 * GET /registry/discover — one-hop peer discovery from the local backend.
 */
export async function fetchRegistryDiscover(): Promise<RegistryDiscoverResponse> {
  const backendUrl = getBackendUrl();
  const response = await axios.get<Record<string, unknown>>(
    `${backendUrl}/registry/discover`,
    { timeout: 60_000 }
  );
  const data = response.data ?? {};
  const peers = normalizePeerUrlList(data.peers ?? data.discovered ?? data.urls);
  const discovered = normalizePeerUrlList(data.discovered);
  return {
    peers: peers.length > 0 ? peers : discovered,
    discovered: discovered.length > 0 ? discovered : undefined,
  };
}

/** Live peer probe / status from GET /registry/peers or POST /registry/peers/probe. */
export interface PeerStatus {
  /** Peer base URL (preferred). */
  url?: string;
  /** Alternate field some backends may return. */
  base_url?: string;
  ok: boolean;
  latency_ms?: number | null;
  error?: string | null;
  count?: number | null;
}

export interface PeerStatusListResponse {
  peers: PeerStatus[];
  /** Backend-configured peer URLs (CREER_REGISTRY_PEERS). */
  configured: string[];
}

function normalizePeerStatus(raw: PeerStatus): PeerStatus {
  return {
    url: raw.url || raw.base_url || '',
    base_url: raw.base_url || raw.url || '',
    ok: Boolean(raw.ok),
    latency_ms: raw.latency_ms ?? null,
    error: raw.error ?? null,
    count: raw.count ?? null,
  };
}

/**
 * GET /registry/peers → `{ peers: PeerStatus[], configured: string[] }`
 */
export async function fetchPeerStatus(): Promise<PeerStatusListResponse> {
  const backendUrl = getBackendUrl();
  const response = await axios.get<PeerStatusListResponse>(
    `${backendUrl}/registry/peers`,
    { timeout: 30_000 }
  );
  return {
    peers: (response.data.peers ?? []).map(normalizePeerStatus),
    configured: response.data.configured ?? [],
  };
}

export interface RegistryMutateOptions {
  /** Optional registry write token (from SecretStorage / setting). */
  token?: string;
}

/**
 * POST /registry/peers/probe `{ url }` → PeerStatus
 */
export async function probePeer(
  url: string,
  options?: RegistryMutateOptions
): Promise<PeerStatus> {
  const backendUrl = getBackendUrl();
  const response = await axios.post<PeerStatus>(
    `${backendUrl}/registry/peers/probe`,
    { url },
    {
      timeout: 30_000,
      headers: registryAuthHeaders(options?.token),
    }
  );
  return normalizePeerStatus(response.data);
}

/**
 * DELETE /packs/{id} → delete installed pack
 */
export async function deletePack(
  id: string,
  options?: RegistryMutateOptions
): Promise<void> {
  const backendUrl = getBackendUrl();
  await axios.delete(`${backendUrl}/packs/${encodeURIComponent(id)}`, {
    timeout: 30_000,
    headers: registryAuthHeaders(options?.token),
  });
}

export async function fetchBakeins(): Promise<BakeinsResponse> {
  const backendUrl = getBackendUrl();
  const response = await axios.get<BakeinsResponse>(`${backendUrl}/bakeins`, {
    timeout: 30_000,
  });
  return {
    licenses: response.data.licenses ?? [],
    ci: response.data.ci ?? [],
  };
}

export async function postCancel(jobId: string): Promise<{ cancelled: true }> {
  const backendUrl = getBackendUrl();
  const response = await axios.post<{ cancelled: true }>(
    `${backendUrl}/generate/cancel`,
    { job_id: jobId },
    { timeout: 30_000 }
  );
  return response.data;
}

export async function postPlan(idea: string, options?: PlanOptions): Promise<PlanResponse> {
  const backendUrl = getBackendUrl();
  const body: { idea: string; template_id?: string; pack_id?: string } = { idea };
  if (options?.packId) {
    body.pack_id = options.packId;
  } else if (options?.templateId) {
    body.template_id = options.templateId;
  }
  const response = await axios.post<PlanResponse>(`${backendUrl}/plan`, body, {
    timeout: 300_000,
  });
  return response.data;
}

export async function postGenerate(
  idea: string,
  options?: GenerateOptions
): Promise<GenerateResponse> {
  const backendUrl = getBackendUrl();
  const body: {
    idea: string;
    template_id?: string;
    pack_id?: string;
    plan?: PlanResponse;
    job_id?: string;
    bakeins?: BakeinOptions;
  } = { idea };
  if (options?.packId) {
    body.pack_id = options.packId;
  } else if (options?.templateId) {
    body.template_id = options.templateId;
  }
  if (options?.plan) {
    body.plan = options.plan;
  }
  if (options?.jobId) {
    body.job_id = options.jobId;
  }
  if (options?.bakeins) {
    body.bakeins = options.bakeins;
  }
  const response = await axios.post<GenerateResponse>(`${backendUrl}/generate`, body, {
    timeout: 300_000,
  });
  return response.data;
}

/** Re-export streaming generate for callers that import from api. */
export { streamGenerate, CancelledError, isCancellationError } from './streamGenerate';
export type {
  StreamProgressEvent,
  StreamGenerateOptions,
  StreamStartEvent,
  StreamFileEvent,
  StreamDoneEvent,
  StreamErrorEvent,
  StreamCancelledEvent,
} from './streamGenerate';

export async function createGitHubRepo(
  token: string,
  name: string,
  options?: { private?: boolean; description?: string }
): Promise<GitHubCreateRepoResponse> {
  const backendUrl = getBackendUrl();
  const isPrivate = options?.private ?? true;
  const description = options?.description ?? '';
  const response = await axios.post<GitHubCreateRepoResponse>(
    `${backendUrl}/github/create-repo`,
    { name, private: isPrivate, description },
    {
      timeout: 60_000,
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return response.data;
}

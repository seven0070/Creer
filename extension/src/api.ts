import axios, { AxiosError } from 'axios';
import * as vscode from 'vscode';

export interface Template {
  id: string;
  name: string;
  description: string;
  stack: string;
  files: string[];
}

export interface PlanResponse {
  project_name: string;
  stack?: string;
  files: string[];
  template_id?: string;
  description?: string;
}

export interface GenerateResponse {
  project_name: string;
  stack?: string;
  files: Record<string, string>;
  template_id?: string;
}

export interface GitHubCreateRepoResponse {
  html_url: string;
  clone_url: string;
  full_name: string;
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

export async function postPlan(idea: string, templateId?: string): Promise<PlanResponse> {
  const backendUrl = getBackendUrl();
  const body: { idea: string; template_id?: string } = { idea };
  if (templateId) {
    body.template_id = templateId;
  }
  const response = await axios.post<PlanResponse>(`${backendUrl}/plan`, body, {
    timeout: 300_000,
  });
  return response.data;
}

export async function postGenerate(
  idea: string,
  options?: { templateId?: string; plan?: PlanResponse }
): Promise<GenerateResponse> {
  const backendUrl = getBackendUrl();
  const body: {
    idea: string;
    template_id?: string;
    plan?: PlanResponse;
  } = { idea };
  if (options?.templateId) {
    body.template_id = options.templateId;
  }
  if (options?.plan) {
    body.plan = options.plan;
  }
  const response = await axios.post<GenerateResponse>(`${backendUrl}/generate`, body, {
    timeout: 300_000,
  });
  return response.data;
}

/** Re-export streaming generate for callers that import from api. */
export { streamGenerate } from './streamGenerate';
export type {
  StreamProgressEvent,
  StreamGenerateOptions,
  StreamStartEvent,
  StreamFileEvent,
  StreamDoneEvent,
  StreamErrorEvent,
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

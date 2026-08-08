import axios from 'axios';
import * as vscode from 'vscode';
import { formatAxiosError } from './api';

export interface DoctorCheck {
  id: string;
  ok: boolean;
  detail: string;
}

export interface DoctorHealth {
  status?: string;
  version?: string;
  offline?: boolean;
  base_url_set?: boolean;
  packs_count?: number;
  peers_configured?: number;
  auth_required?: boolean;
  peer_trust_mode?: string;
  peer_trust_signing?: boolean;
  tls_server_configured?: boolean;
  mtls_client_configured?: boolean;
  [key: string]: unknown;
}

export interface DoctorReport {
  version: string;
  ok: boolean;
  checks: DoctorCheck[];
  health: DoctorHealth;
}

let outputChannel: vscode.OutputChannel | undefined;

function getBackendUrl(): string {
  const config = vscode.workspace.getConfiguration('creer');
  return (config.get<string>('backendUrl') || 'http://localhost:8000').replace(/\/$/, '');
}

function getCreerOutput(context?: vscode.ExtensionContext): vscode.OutputChannel {
  if (!outputChannel) {
    outputChannel = vscode.window.createOutputChannel('Creer');
    context?.subscriptions.push(outputChannel);
  }
  return outputChannel;
}

function formatReport(report: DoctorReport): string {
  const lines: string[] = [
    `Creer Doctor — version ${report.version}`,
    `Overall: ${report.ok ? 'OK' : 'ISSUES'}`,
    '',
  ];
  for (const check of report.checks) {
    const mark = check.ok ? '✓' : '✗';
    lines.push(`[${mark}] ${check.id}: ${check.detail}`);
  }
  if (report.health && typeof report.health === 'object') {
    lines.push('');
    lines.push('Health snapshot:');
    for (const [key, value] of Object.entries(report.health)) {
      lines.push(`  ${key}: ${JSON.stringify(value)}`);
    }
  }
  return lines.join('\n');
}

/**
 * Compose a minimal DoctorReport from GET /health when /doctor is unavailable.
 */
export function composeDoctorFromHealth(health: DoctorHealth): DoctorReport {
  const version = typeof health.version === 'string' ? health.version : 'unknown';
  const offline = Boolean(health.offline);
  const baseUrlSet = Boolean(health.base_url_set);
  const packs = typeof health.packs_count === 'number' ? health.packs_count : 0;
  const peers =
    typeof health.peers_configured === 'number' ? health.peers_configured : 0;
  const authRequired = Boolean(health.auth_required);
  const trustMode =
    typeof health.peer_trust_mode === 'string' ? health.peer_trust_mode : 'off';
  const signing = Boolean(health.peer_trust_signing);
  const tlsServer = Boolean(health.tls_server_configured);
  const mtlsClient = Boolean(health.mtls_client_configured);

  // Without OPENAI_API_KEY visibility on /health, treat offline OR base_url as llm ok.
  const llmOk = offline || baseUrlSet;
  const llmDetail = offline
    ? 'offline stubs (composed from /health)'
    : baseUrlSet
      ? 'BASE_URL set (composed from /health)'
      : 'llm config unknown from /health (no offline, no BASE_URL)';

  const checks: DoctorCheck[] = [
    {
      id: 'health',
      ok: true,
      detail: `status=${health.status ?? 'ok'} version=${version}`,
    },
    {
      id: 'offline',
      ok: true,
      detail: `CREER_OFFLINE=${offline ? 'true' : 'false'}`,
    },
    { id: 'llm', ok: llmOk, detail: llmDetail },
    { id: 'packs', ok: true, detail: `${packs} packs` },
    { id: 'peers', ok: true, detail: `${peers} configured` },
    {
      id: 'auth',
      ok: true,
      detail: authRequired
        ? 'registry write auth required'
        : 'registry write auth open',
    },
    {
      id: 'trust',
      ok: true,
      detail: `mode=${trustMode} signing=${signing ? 'on' : 'off'}`,
    },
    {
      id: 'tls',
      ok: true,
      detail: `server=${tlsServer ? 'yes' : 'no'} client_mtls=${mtlsClient ? 'yes' : 'no'}`,
    },
  ];

  return {
    version,
    ok: checks.every((c) => c.ok),
    checks,
    health,
  };
}

export async function fetchDoctorReport(): Promise<DoctorReport> {
  const backendUrl = getBackendUrl();

  try {
    const response = await axios.get<DoctorReport>(`${backendUrl}/doctor`, {
      timeout: 15_000,
    });
    const data = response.data;
    if (data && Array.isArray(data.checks)) {
      return {
        version: data.version || 'unknown',
        ok: Boolean(data.ok),
        checks: data.checks,
        health: data.health ?? {},
      };
    }
  } catch (err) {
    const is404 = axios.isAxiosError(err) && err.response?.status === 404;
    if (!is404) {
      throw err;
    }
  }

  const healthResp = await axios.get<DoctorHealth>(`${backendUrl}/health`, {
    timeout: 15_000,
  });
  return composeDoctorFromHealth(healthResp.data ?? {});
}

export async function runDoctorCommand(
  context?: vscode.ExtensionContext
): Promise<void> {
  const channel = getCreerOutput(context);
  try {
    const report = await fetchDoctorReport();
    const text = formatReport(report);
    channel.clear();
    channel.appendLine(text);
    channel.show(true);

    const failed = report.checks.filter((c) => !c.ok);
    if (report.ok) {
      void vscode.window.showInformationMessage(
        `Creer Doctor: OK (v${report.version}) — ${report.checks.length} checks passed`
      );
    } else {
      const summary = failed.map((c) => c.id).join(', ');
      void vscode.window.showWarningMessage(
        `Creer Doctor: issues — ${summary}. See Output → Creer for details.`
      );
    }
  } catch (err) {
    const msg = formatAxiosError(err, 'Doctor failed');
    channel.appendLine(`Creer Doctor failed: ${msg}`);
    channel.show(true);
    void vscode.window.showWarningMessage(`Creer Doctor failed: ${msg}`);
  }
}

/**
 * Lightweight status bar: fetch /health once on activate.
 * Click runs Doctor. Disposed via context.subscriptions.
 */
export function createDoctorStatusBar(
  context: vscode.ExtensionContext
): vscode.StatusBarItem {
  const item = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  item.text = 'Creer $(sync~spin)';
  item.tooltip = 'Creer: checking backend…';
  item.command = 'creer.doctor';
  item.show();

  const backendUrl = getBackendUrl();
  void (async () => {
    try {
      const response = await axios.get<{ version?: string; status?: string }>(
        `${backendUrl}/health`,
        { timeout: 8_000 }
      );
      const version = response.data?.version || '?';
      item.text = 'Creer $(check)';
      item.tooltip = `Creer backend v${version} — click for Doctor`;
    } catch {
      item.text = 'Creer $(warning)';
      item.tooltip = 'Creer backend unreachable — click for Doctor';
    }
  })();

  context.subscriptions.push(item);
  return item;
}

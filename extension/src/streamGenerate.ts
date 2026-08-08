import * as http from 'http';
import * as https from 'https';
import { URL } from 'url';
import * as vscode from 'vscode';
import type { GenerateResponse, PlanResponse } from './api';

export type StreamStartEvent = {
  event: 'start';
  project_name: string;
  total: number;
  stack: string;
};

export type StreamFileEvent = {
  event: 'file';
  index: number;
  total: number;
  path: string;
  status: 'generating' | 'done';
  bytes?: number;
};

export type StreamDoneEvent = {
  event: 'done';
  project_name: string;
  stack: string;
  files: Record<string, string>;
  template_id?: string;
};

export type StreamErrorEvent = {
  event: 'error';
  detail: string;
};

export type StreamProgressEvent =
  | StreamStartEvent
  | StreamFileEvent
  | StreamDoneEvent
  | StreamErrorEvent;

export interface StreamGenerateOptions {
  idea: string;
  templateId?: string;
  plan?: PlanResponse;
  onProgress?: (event: StreamProgressEvent) => void;
}

function getBackendUrl(): string {
  const config = vscode.workspace.getConfiguration('creer');
  return (config.get<string>('backendUrl') || 'http://localhost:8000').replace(/\/$/, '');
}

function parseSseChunk(
  buffer: string,
  onEvent: (data: StreamProgressEvent) => void
): string {
  // Normalize CRLF so event separators are always `\n\n` (proxies / Windows).
  let remaining = buffer.replace(/\r\n/g, '\n');
  for (;;) {
    const sep = remaining.indexOf('\n\n');
    if (sep === -1) {
      break;
    }
    const rawEvent = remaining.slice(0, sep);
    remaining = remaining.slice(sep + 2);

    for (const line of rawEvent.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) {
        continue;
      }
      const payload = trimmed.slice(5).trim();
      if (!payload || payload === '[DONE]') {
        continue;
      }
      try {
        const parsed = JSON.parse(payload) as StreamProgressEvent;
        if (parsed && typeof parsed === 'object' && 'event' in parsed) {
          onEvent(parsed);
        }
      } catch {
        // Ignore malformed JSON fragments; wait for a complete event.
      }
    }
  }
  return remaining;
}

/**
 * POST /generate/stream and parse SSE (`data: {...}\\n\\n`).
 * Uses Node http/https so streaming works in the VS Code extension CommonJS host.
 */
export function streamGenerate(options: StreamGenerateOptions): Promise<GenerateResponse> {
  const backendUrl = getBackendUrl();
  const url = new URL(`${backendUrl}/generate/stream`);
  const body: {
    idea: string;
    template_id?: string;
    plan?: PlanResponse;
  } = { idea: options.idea };
  if (options.templateId) {
    body.template_id = options.templateId;
  }
  if (options.plan) {
    body.plan = options.plan;
  }

  const payload = JSON.stringify(body);
  const lib = url.protocol === 'https:' ? https : http;

  return new Promise<GenerateResponse>((resolve, reject) => {
    let settled = false;
    let doneResult: GenerateResponse | undefined;
    let buffer = '';

    const fail = (err: Error) => {
      if (settled) {
        return;
      }
      settled = true;
      reject(err);
    };

    const succeed = (result: GenerateResponse) => {
      if (settled) {
        return;
      }
      settled = true;
      resolve(result);
    };

    let req: http.ClientRequest;

    const handleEvent = (ev: StreamProgressEvent) => {
      options.onProgress?.(ev);

      if (ev.event === 'error') {
        // Stop reading further events; destroy the socket so we do not hang.
        try {
          req.destroy();
        } catch {
          // ignore
        }
        fail(new Error(ev.detail || 'Streaming generation failed'));
        return;
      }

      if (ev.event === 'done') {
        doneResult = {
          project_name: ev.project_name,
          stack: ev.stack,
          files: ev.files,
        };
        if (ev.template_id) {
          doneResult.template_id = ev.template_id;
        }
      }
    };

    req = lib.request(
      {
        protocol: url.protocol,
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? 443 : 80),
        path: `${url.pathname}${url.search}`,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          'Content-Length': Buffer.byteLength(payload),
          Connection: 'keep-alive',
        },
        timeout: 600_000,
      },
      (res) => {
        const status = res.statusCode ?? 0;
        if (status < 200 || status >= 300) {
          const chunks: Buffer[] = [];
          res.on('data', (c: Buffer) => chunks.push(c));
          res.on('end', () => {
            const text = Buffer.concat(chunks).toString('utf8');
            let detail = text;
            try {
              const parsed = JSON.parse(text) as { detail?: string };
              if (typeof parsed.detail === 'string') {
                detail = parsed.detail;
              }
            } catch {
              // keep raw text
            }
            fail(new Error(detail || `HTTP ${status} from /generate/stream`));
          });
          return;
        }

        res.setEncoding('utf8');
        res.on('data', (chunk: string) => {
          buffer = parseSseChunk(buffer + chunk, handleEvent);
        });
        res.on('end', () => {
          if (buffer.trim()) {
            parseSseChunk(buffer + '\n\n', handleEvent);
          }
          if (doneResult) {
            succeed(doneResult);
          } else if (!settled) {
            fail(new Error('Stream ended without a done event'));
          }
        });
        res.on('error', (err) => fail(err instanceof Error ? err : new Error(String(err))));
      }
    );

    req.on('timeout', () => {
      req.destroy();
      fail(new Error('Streaming generation timed out'));
    });
    req.on('error', (err) => fail(err instanceof Error ? err : new Error(String(err))));

    req.write(payload);
    req.end();
  });
}

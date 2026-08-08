import axios from 'axios';
import * as http from 'http';
import * as https from 'https';
import { URL } from 'url';
import * as vscode from 'vscode';
import type { BakeinOptions, GenerateResponse, PlanResponse, QualityIssue } from './api';

export type StreamStartEvent = {
  event: 'start';
  project_name: string;
  total: number;
  stack: string;
  job_id?: string;
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
  quality?: QualityIssue[];
};

export type StreamErrorEvent = {
  event: 'error';
  detail: string;
};

export type StreamCancelledEvent = {
  event: 'cancelled';
  job_id: string;
  detail: string;
};

export type StreamProgressEvent =
  | StreamStartEvent
  | StreamFileEvent
  | StreamDoneEvent
  | StreamErrorEvent
  | StreamCancelledEvent;

export interface StreamGenerateOptions {
  idea: string;
  templateId?: string;
  plan?: PlanResponse;
  bakeins?: BakeinOptions;
  jobId?: string;
  signal?: AbortSignal;
  onJobId?: (jobId: string) => void;
  onProgress?: (event: StreamProgressEvent) => void;
}

/** Thrown when the user or AbortSignal cancels streaming generation. */
export class CancelledError extends Error {
  readonly jobId?: string;

  constructor(message = 'Generation cancelled', jobId?: string) {
    super(message);
    this.name = 'AbortError';
    this.jobId = jobId;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export function isCancellationError(err: unknown): boolean {
  if (!err || typeof err !== 'object') {
    return false;
  }
  const e = err as { name?: string; code?: string };
  return (
    err instanceof CancelledError ||
    e.name === 'AbortError' ||
    e.name === 'CancelledError' ||
    e.code === 'ERR_CANCELED'
  );
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
 * Supports AbortSignal: posts /generate/cancel with job_id (when known) and destroys the request.
 */
export function streamGenerate(options: StreamGenerateOptions): Promise<GenerateResponse> {
  const backendUrl = getBackendUrl();
  const url = new URL(`${backendUrl}/generate/stream`);
  const body: {
    idea: string;
    template_id?: string;
    plan?: PlanResponse;
    job_id?: string;
    bakeins?: BakeinOptions;
  } = { idea: options.idea };
  if (options.templateId) {
    body.template_id = options.templateId;
  }
  if (options.plan) {
    body.plan = options.plan;
  }
  if (options.jobId) {
    body.job_id = options.jobId;
  }
  if (options.bakeins) {
    body.bakeins = options.bakeins;
  }

  const payload = JSON.stringify(body);
  const lib = url.protocol === 'https:' ? https : http;

  return new Promise<GenerateResponse>((resolve, reject) => {
    let settled = false;
    let doneResult: GenerateResponse | undefined;
    let buffer = '';
    let jobId: string | undefined = options.jobId;
    let cancelPosted = false;
    let req: http.ClientRequest;

    const fail = (err: Error) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanupAbort();
      reject(err);
    };

    const succeed = (result: GenerateResponse) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanupAbort();
      resolve(result);
    };

    const destroyRequest = () => {
      try {
        req.destroy();
      } catch {
        // ignore
      }
    };

    const requestBackendCancel = () => {
      if (cancelPosted || !jobId) {
        return;
      }
      cancelPosted = true;
      // Inline cancel call to avoid a circular import with api.ts.
      void axios
        .post(
          `${backendUrl}/generate/cancel`,
          { job_id: jobId },
          { timeout: 30_000 }
        )
        .catch(() => {
          // Best-effort; local abort still tears down the HTTP stream.
        });
    };

    const abortNow = () => {
      requestBackendCancel();
      destroyRequest();
      fail(new CancelledError('Generation cancelled', jobId));
    };

    const onAbort = () => {
      abortNow();
    };

    const cleanupAbort = () => {
      if (options.signal) {
        options.signal.removeEventListener('abort', onAbort);
      }
    };

    if (options.signal?.aborted) {
      // No request yet — reject immediately (and cancel if we already have a job id).
      requestBackendCancel();
      fail(new CancelledError('Generation cancelled', jobId));
      return;
    }

    const handleEvent = (ev: StreamProgressEvent) => {
      options.onProgress?.(ev);

      if (ev.event === 'start') {
        if (ev.job_id) {
          jobId = ev.job_id;
          options.onJobId?.(ev.job_id);
          // Race: user may have aborted between request start and start event.
          if (options.signal?.aborted) {
            abortNow();
          }
        }
        return;
      }

      if (ev.event === 'cancelled') {
        destroyRequest();
        fail(
          new CancelledError(
            ev.detail || 'Generation cancelled',
            ev.job_id || jobId
          )
        );
        return;
      }

      if (ev.event === 'error') {
        // Stop reading further events; destroy the socket so we do not hang.
        destroyRequest();
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
        if (ev.quality) {
          doneResult.quality = ev.quality;
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
        res.on('error', (err) => {
          if (settled) {
            return;
          }
          // Destroy after abort often surfaces as a socket error — treat as cancel.
          if (options.signal?.aborted) {
            fail(new CancelledError('Generation cancelled', jobId));
            return;
          }
          fail(err instanceof Error ? err : new Error(String(err)));
        });
      }
    );

    req.on('timeout', () => {
      req.destroy();
      fail(new Error('Streaming generation timed out'));
    });
    req.on('error', (err) => {
      if (settled) {
        return;
      }
      if (options.signal?.aborted || isCancellationError(err)) {
        fail(new CancelledError('Generation cancelled', jobId));
        return;
      }
      // Node often emits Error with code after destroy(); ignore if we already aborted.
      const code = (err as NodeJS.ErrnoException).code;
      if (code === 'ECONNRESET' && cancelPosted) {
        fail(new CancelledError('Generation cancelled', jobId));
        return;
      }
      fail(err instanceof Error ? err : new Error(String(err)));
    });

    if (options.signal) {
      options.signal.addEventListener('abort', onAbort, { once: true });
    }

    req.write(payload);
    req.end();
  });
}

import * as path from 'path';
import * as vscode from 'vscode';
import { resolveSafeProjectPath, type ConflictResolution } from './writeFiles';

export const CREER_GENERATED_SCHEME = 'creer-generated';

const MAX_DIFF_FILES = 15;

/**
 * Serves generated file contents for side-by-side `vscode.diff` against on-disk files.
 * Content is keyed by the `path` query parameter (relative project path).
 */
export class CreerGeneratedContentProvider implements vscode.TextDocumentContentProvider {
  private readonly contents = new Map<string, string>();
  private readonly _onDidChange = new vscode.EventEmitter<vscode.Uri>();
  readonly onDidChange = this._onDidChange.event;

  setContent(relativePath: string, content: string): void {
    const key = normalizeRelPath(relativePath);
    this.contents.set(key, content);
    this._onDidChange.fire(generatedUri(key));
  }

  setMany(files: Record<string, string>, relativePaths: string[]): void {
    for (const rel of relativePaths) {
      this.setContent(rel, files[rel] ?? '');
    }
  }

  clear(): void {
    this.contents.clear();
  }

  provideTextDocumentContent(uri: vscode.Uri): string {
    const key = pathFromUri(uri);
    return this.contents.get(key) ?? '';
  }
}

let sharedProvider: CreerGeneratedContentProvider | undefined;

export function registerConflictDiffProvider(
  context: vscode.ExtensionContext
): CreerGeneratedContentProvider {
  const provider = new CreerGeneratedContentProvider();
  sharedProvider = provider;
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider(CREER_GENERATED_SCHEME, provider),
    { dispose: () => {
      if (sharedProvider === provider) {
        sharedProvider = undefined;
      }
      provider.clear();
    } }
  );
  return provider;
}

function getProvider(): CreerGeneratedContentProvider {
  if (!sharedProvider) {
    // Lazy fallback if activate forgot to register (tests / unexpected hosts)
    sharedProvider = new CreerGeneratedContentProvider();
  }
  return sharedProvider;
}

function normalizeRelPath(relativePath: string): string {
  return relativePath.replace(/\\/g, '/');
}

function pathFromUri(uri: vscode.Uri): string {
  const q = new URLSearchParams(uri.query);
  const fromQuery = q.get('path');
  if (fromQuery) {
    return normalizeRelPath(fromQuery);
  }
  return normalizeRelPath(uri.path.replace(/^\//, ''));
}

export function generatedUri(relativePath: string): vscode.Uri {
  const normalized = normalizeRelPath(relativePath);
  return vscode.Uri.from({
    scheme: CREER_GENERATED_SCHEME,
    path: '/' + normalized,
    query: `path=${encodeURIComponent(normalized)}`,
  });
}

/**
 * Open side-by-side diffs: existing on-disk file (left) vs generated content (right).
 * Caps at MAX_DIFF_FILES to avoid flooding the editor.
 */
export async function openConflictDiffs(
  projectPath: string,
  files: Record<string, string>,
  conflicts: string[],
  provider?: CreerGeneratedContentProvider
): Promise<number> {
  const p = provider ?? getProvider();
  const toShow = conflicts.slice(0, MAX_DIFF_FILES);
  p.setMany(files, toShow);

  for (const rel of toShow) {
    let existingUri: vscode.Uri;
    try {
      const fullPath = resolveSafeProjectPath(projectPath, rel);
      existingUri = vscode.Uri.file(fullPath);
    } catch {
      continue;
    }
    const generated = generatedUri(rel);
    const title = `${path.basename(rel)} (existing ↔ generated)`;
    await vscode.commands.executeCommand('vscode.diff', existingUri, generated, title);
  }

  return toShow.length;
}

function conflictMessage(conflicts: string[]): string {
  const preview = conflicts.slice(0, 10);
  const extra = conflicts.length > 10 ? `\n…and ${conflicts.length - 10} more` : '';
  const list = preview.map((p) => `• ${p}`).join('\n');
  return `${conflicts.length} file(s) already exist under the project folder:\n${list}${extra}`;
}

async function promptOverwriteSkipCancel(
  message: string,
  detail?: string
): Promise<ConflictResolution> {
  const choice = await vscode.window.showWarningMessage(
    message,
    { modal: true, detail },
    'Overwrite all',
    'Skip existing',
    'Cancel'
  );
  if (choice === 'Overwrite all') {
    return 'overwrite';
  }
  if (choice === 'Skip existing') {
    return 'skip';
  }
  return 'cancel';
}

/**
 * Conflict resolution with optional side-by-side review via `creer-generated` diffs.
 * When `creer.showConflictDiffs` is false, only Overwrite / Skip / Cancel are offered.
 */
export async function resolveConflictsWithDiffs(
  projectPath: string,
  files: Record<string, string>,
  conflicts: string[]
): Promise<ConflictResolution> {
  if (conflicts.length === 0) {
    return 'overwrite';
  }

  const config = vscode.workspace.getConfiguration('creer');
  const showDiffs = config.get<boolean>('showConflictDiffs') ?? true;
  const message = conflictMessage(conflicts);

  if (!showDiffs) {
    return promptOverwriteSkipCancel(message);
  }

  const choice = await vscode.window.showWarningMessage(
    message,
    { modal: true },
    'Review diffs',
    'Overwrite all',
    'Skip existing',
    'Cancel'
  );

  if (choice === 'Overwrite all') {
    return 'overwrite';
  }
  if (choice === 'Skip existing') {
    return 'skip';
  }
  if (choice !== 'Review diffs') {
    return 'cancel';
  }

  const opened = await openConflictDiffs(projectPath, files, conflicts);
  const more =
    conflicts.length > MAX_DIFF_FILES
      ? ` (showing ${opened} of ${conflicts.length})`
      : '';

  return promptOverwriteSkipCancel(
    `Reviewed ${opened} conflicted file(s)${more}. How should Creer proceed?`,
    'Overwrite all replaces existing files. Skip existing keeps them and writes only new paths.'
  );
}

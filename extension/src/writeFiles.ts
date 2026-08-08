import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

export type ConflictResolution = 'overwrite' | 'skip' | 'cancel';

/** Safe project folder name: alphanumeric start, then [a-zA-Z0-9._-], max 64. */
const SAFE_PROJECT_NAME = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/;

/**
 * Validate project_name before joining under the workspace root.
 * Rejects path separators and `..` so the folder cannot escape the workspace.
 */
export function assertSafeProjectName(name: string): void {
  if (typeof name !== 'string' || !name) {
    throw new Error(`Invalid project name: ${JSON.stringify(name)}`);
  }
  if (name.includes('\0') || name.includes('/') || name.includes('\\')) {
    throw new Error(`Unsafe project name: ${JSON.stringify(name)}`);
  }
  // Reject `.` / `..` as the whole name (path-like); substring `foo..bar` is allowed by backend SAFE_NAME
  if (name === '.' || name === '..') {
    throw new Error(`Unsafe project name: ${JSON.stringify(name)}`);
  }
  if (!SAFE_PROJECT_NAME.test(name)) {
    throw new Error(
      `Invalid project name (use 1–64 chars, alphanumeric start, [a-zA-Z0-9._-]): ${JSON.stringify(name)}`
    );
  }
}

/**
 * Resolve a relative path under projectPath and ensure it cannot escape the project root.
 * Rejects absolute paths, null bytes, and `..` traversal (defense in depth vs backend).
 */
export function resolveSafeProjectPath(projectPath: string, relativePath: string): string {
  if (typeof relativePath !== 'string' || !relativePath) {
    throw new Error(`Invalid file path: ${JSON.stringify(relativePath)}`);
  }
  if (relativePath.includes('\0')) {
    throw new Error(`Unsafe file path (null byte): ${JSON.stringify(relativePath)}`);
  }
  if (path.isAbsolute(relativePath)) {
    throw new Error(`Absolute file paths are not allowed: ${JSON.stringify(relativePath)}`);
  }
  // Windows drive / UNC when running on win32; also reject drive-like prefixes on any OS
  if (/^[a-zA-Z]:/.test(relativePath) || relativePath.startsWith('\\\\')) {
    throw new Error(`Windows drive/UNC paths are not allowed: ${JSON.stringify(relativePath)}`);
  }

  const normalizedSep = relativePath.replace(/\\/g, '/');
  const segments = normalizedSep.split('/');
  if (segments.some((s) => s === '..')) {
    throw new Error(`Path traversal ('..') is not allowed: ${JSON.stringify(relativePath)}`);
  }
  if (segments.some((s) => s === '')) {
    // Leading/trailing/double slashes → empty segment
    throw new Error(`Invalid file path: ${JSON.stringify(relativePath)}`);
  }

  const root = path.resolve(projectPath);
  const fullPath = path.resolve(root, ...segments);
  const prefix = root.endsWith(path.sep) ? root : root + path.sep;
  if (fullPath !== root && !fullPath.startsWith(prefix)) {
    throw new Error(`Path escapes project root: ${JSON.stringify(relativePath)}`);
  }
  return fullPath;
}

export function findConflicts(
  projectPath: string,
  files: Record<string, string>
): string[] {
  const conflicts: string[] = [];
  for (const relativePath of Object.keys(files)) {
    const fullPath = resolveSafeProjectPath(projectPath, relativePath);
    if (fs.existsSync(fullPath) && fs.statSync(fullPath).isFile()) {
      conflicts.push(relativePath);
    }
  }
  return conflicts.sort((a, b) => a.localeCompare(b));
}

export async function resolveConflicts(conflicts: string[]): Promise<ConflictResolution> {
  if (conflicts.length === 0) {
    return 'overwrite';
  }

  const preview = conflicts.slice(0, 10);
  const extra = conflicts.length > 10 ? `\n…and ${conflicts.length - 10} more` : '';
  const list = preview.map((p) => `• ${p}`).join('\n');

  const choice = await vscode.window.showWarningMessage(
    `${conflicts.length} file(s) already exist under the project folder:\n${list}${extra}`,
    { modal: true },
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

export function writeProjectFiles(
  projectPath: string,
  files: Record<string, string>,
  resolution: ConflictResolution
): { written: number; skipped: number } {
  if (resolution === 'cancel') {
    return { written: 0, skipped: 0 };
  }

  fs.mkdirSync(projectPath, { recursive: true });

  let written = 0;
  let skipped = 0;

  for (const relativePath of Object.keys(files)) {
    const fullPath = resolveSafeProjectPath(projectPath, relativePath);
    const exists = fs.existsSync(fullPath) && fs.statSync(fullPath).isFile();

    if (exists && resolution === 'skip') {
      skipped += 1;
      continue;
    }

    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, files[relativePath], 'utf8');
    written += 1;
  }

  return { written, skipped };
}

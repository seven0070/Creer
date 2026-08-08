import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

const MAX_FILES_SHOWN = 30;
const MAX_PREVIEW_LINES = 40;
const MAX_DIFF_LINES = 60;

function fenceLang(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  const map: Record<string, string> = {
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.js': 'javascript',
    '.jsx': 'jsx',
    '.py': 'python',
    '.json': 'json',
    '.md': 'markdown',
    '.yml': 'yaml',
    '.yaml': 'yaml',
    '.toml': 'toml',
    '.sh': 'bash',
    '.css': 'css',
    '.html': 'html',
    '.rs': 'rust',
    '.go': 'go',
    '.java': 'java',
    '.rb': 'ruby',
  };
  return map[ext] || '';
}

function byteSize(content: string): number {
  return Buffer.byteLength(content, 'utf8');
}

function formatBytes(n: number): string {
  if (n < 1024) {
    return `${n} B`;
  }
  if (n < 1024 * 1024) {
    return `${(n / 1024).toFixed(1)} KB`;
  }
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function truncateLines(text: string, maxLines: number): { text: string; truncated: boolean } {
  const lines = text.split('\n');
  if (lines.length <= maxLines) {
    return { text, truncated: false };
  }
  return {
    text: lines.slice(0, maxLines).join('\n'),
    truncated: true,
  };
}

/**
 * Simple line-based unified diff (no external deps).
 * Uses LCS on lines for moderate-sized inputs; truncates output.
 */
export function buildUnifiedDiff(
  existing: string,
  generated: string,
  maxOutputLines = MAX_DIFF_LINES
): string {
  const a = existing.split('\n');
  const b = generated.split('\n');

  // Cap LCS input to keep it snappy on huge files
  const CAP = 400;
  const aCapped = a.length > CAP;
  const bCapped = b.length > CAP;
  const aLines = aCapped ? a.slice(0, CAP) : a;
  const bLines = bCapped ? b.slice(0, CAP) : b;

  const n = aLines.length;
  const m = bLines.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      if (aLines[i] === bLines[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  const ops: Array<{ kind: 'eq' | 'del' | 'add'; line: string }> = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (aLines[i] === bLines[j]) {
      ops.push({ kind: 'eq', line: aLines[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      ops.push({ kind: 'del', line: aLines[i] });
      i++;
    } else {
      ops.push({ kind: 'add', line: bLines[j] });
      j++;
    }
  }
  while (i < n) {
    ops.push({ kind: 'del', line: aLines[i++] });
  }
  while (j < m) {
    ops.push({ kind: 'add', line: bLines[j++] });
  }

  const out: string[] = ['--- existing', '+++ generated'];
  let shown = 0;
  let skippedEq = 0;

  const flushSkipped = () => {
    if (skippedEq > 0) {
      out.push(` … ${skippedEq} unchanged line(s)`);
      skippedEq = 0;
    }
  };

  for (const op of ops) {
    if (shown >= maxOutputLines) {
      flushSkipped();
      out.push(` … diff truncated (${ops.length - shown} more op(s))`);
      break;
    }
    if (op.kind === 'eq') {
      skippedEq++;
      continue;
    }
    flushSkipped();
    if (op.kind === 'del') {
      out.push(`-${op.line}`);
    } else {
      out.push(`+${op.line}`);
    }
    shown++;
  }
  flushSkipped();

  if (aCapped || bCapped) {
    out.push(
      ` … input capped for diff (existing ${a.length} lines, generated ${b.length} lines)`
    );
  }

  return out.join('\n');
}

function buildNewFileSection(relPath: string, content: string): string {
  const size = formatBytes(byteSize(content));
  const lang = fenceLang(relPath);
  const { text, truncated } = truncateLines(content, MAX_PREVIEW_LINES);
  const note = truncated
    ? `\n_Preview truncated to ${MAX_PREVIEW_LINES} lines (${content.split('\n').length} total)._\n`
    : '';

  return [
    `### \`${relPath}\` — NEW · ${size}`,
    '',
    note,
    '```' + lang,
    text,
    '```',
    '',
  ].join('\n');
}

function buildExistingFileSection(
  relPath: string,
  existing: string,
  generated: string
): string {
  const size = formatBytes(byteSize(generated));
  if (existing === generated) {
    return [
      `### \`${relPath}\` — UNCHANGED · ${size}`,
      '',
      '_Generated content matches the existing file._',
      '',
    ].join('\n');
  }

  const diff = buildUnifiedDiff(existing, generated);
  return [
    `### \`${relPath}\` — EXISTING (will overwrite) · ${size}`,
    '',
    '```diff',
    diff,
    '```',
    '',
  ].join('\n');
}

export function buildContentPreviewMarkdown(
  projectName: string,
  projectPath: string,
  files: Record<string, string>
): string {
  const paths = Object.keys(files).sort((a, b) => a.localeCompare(b));
  const shown = paths.slice(0, MAX_FILES_SHOWN);
  const omitted = paths.length - shown.length;

  const sections: string[] = [
    `# Creer content preview`,
    '',
    `**Project:** \`${projectName}\``,
    '',
    `**Path:** \`${projectPath}\``,
    '',
    `**Files:** ${paths.length}`,
    '',
    '---',
    '',
  ];

  for (const relPath of shown) {
    const generated = files[relPath] ?? '';
    const fullPath = path.join(projectPath, relPath);
    let existing: string | undefined;
    try {
      if (fs.existsSync(fullPath) && fs.statSync(fullPath).isFile()) {
        existing = fs.readFileSync(fullPath, 'utf8');
      }
    } catch {
      existing = undefined;
    }

    if (existing === undefined) {
      sections.push(buildNewFileSection(relPath, generated));
    } else {
      sections.push(buildExistingFileSection(relPath, existing, generated));
    }
  }

  if (omitted > 0) {
    sections.push(`_…and ${omitted} more file(s) not shown in this preview._`, '');
  }

  sections.push('---', '', '_Confirm to write these files to disk._', '');
  return sections.join('\n');
}

/**
 * Open an untitled markdown preview of generated file contents and ask the user
 * to confirm writing. Returns true if the user confirms.
 * When `creer.contentPreview` is false, skips the UI and returns true.
 */
export async function showContentPreviewAndConfirm(
  projectName: string,
  projectPath: string,
  files: Record<string, string>
): Promise<boolean> {
  const config = vscode.workspace.getConfiguration('creer');
  const enabled = config.get<boolean>('contentPreview') ?? true;
  if (!enabled) {
    return true;
  }

  const markdown = buildContentPreviewMarkdown(projectName, projectPath, files);
  const doc = await vscode.workspace.openTextDocument({
    content: markdown,
    language: 'markdown',
  });
  await vscode.window.showTextDocument(doc, { preview: true, preserveFocus: false });

  const fileCount = Object.keys(files).length;
  const choice = await vscode.window.showInformationMessage(
    `Creer content ready: ${projectName} (${fileCount} files). Write files to disk?`,
    { modal: true },
    'Write files',
    'Cancel'
  );

  return choice === 'Write files';
}

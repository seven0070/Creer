import * as vscode from 'vscode';
import type { PlanResponse } from './api';

function buildFileTreeMarkdown(files: string[]): string {
  const sorted = [...files].sort((a, b) => a.localeCompare(b));
  return sorted.map((f) => `- \`${f}\``).join('\n');
}

export function buildPlanPreviewMarkdown(plan: PlanResponse, idea: string): string {
  const stack = plan.stack?.trim() || '(unspecified)';
  let sourceLine = '\n**Template:** AI plan (no template)\n';
  if (plan.pack_id) {
    sourceLine = `\n**Pack:** \`${plan.pack_id}\`\n`;
  } else if (plan.template_id) {
    sourceLine = `\n**Template:** \`${plan.template_id}\`\n`;
  }
  const description = plan.description?.trim()
    ? `\n**Description:** ${plan.description.trim()}\n`
    : '';

  return [
    `# Creer plan preview`,
    '',
    `**Idea:** ${idea}`,
    '',
    `**Project:** \`${plan.project_name}\``,
    '',
    `**Stack:** ${stack}`,
    sourceLine,
    description,
    `**Files (${plan.files.length}):**`,
    '',
    buildFileTreeMarkdown(plan.files),
    '',
    '---',
    '',
    '_Confirm generation to write these files into your workspace._',
    '',
  ].join('\n');
}

/**
 * Open an untitled markdown preview document and ask the user to confirm generation.
 * Returns true if the user confirms, false if they cancel.
 */
export async function showPlanPreviewAndConfirm(plan: PlanResponse, idea: string): Promise<boolean> {
  const markdown = buildPlanPreviewMarkdown(plan, idea);
  const doc = await vscode.workspace.openTextDocument({
    content: markdown,
    language: 'markdown',
  });
  await vscode.window.showTextDocument(doc, { preview: true, preserveFocus: false });

  const choice = await vscode.window.showInformationMessage(
    `Creer plan ready: ${plan.project_name} (${plan.files.length} files). Generate & write files?`,
    { modal: true },
    'Generate & write files',
    'Cancel'
  );

  return choice === 'Generate & write files';
}

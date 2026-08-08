import * as path from 'path';
import * as vscode from 'vscode';
import {
  createGitHubRepo,
  fetchBakeins,
  fetchPacks,
  fetchTemplates,
  formatAxiosError,
  postGenerate,
  postPlan,
  type BakeinOptions,
  type CiBakein,
  type GenerateResponse,
  type LicenseBakein,
  type Pack,
  type PlanResponse,
  type QualityIssue,
  type Template,
} from './api';
import { showContentPreviewAndConfirm } from './contentPreview';
import { addRemoteAndPush, ensureGitRepo, initGit } from './git';
import { showPlanPreviewAndConfirm } from './preview';
import { resolveGitHubToken } from './secrets';
import {
  isCancellationError,
  streamGenerate,
  type StreamProgressEvent,
} from './streamGenerate';
import { resolveConflictsWithDiffs } from './conflictDiff';
import { pickWorkspaceRoot } from './workspace';
import {
  assertSafeProjectName,
  findConflicts,
  writeProjectFiles,
} from './writeFiles';

export interface ScaffoldOptions {
  /** Extension context (required for SecretStorage). */
  context: vscode.ExtensionContext;
  /** Pre-filled idea (e.g. from chat). If omitted, prompts the user. */
  idea?: string;
  /** Use chat-style InputBox placeholder (/creer …). */
  fromChat?: boolean;
}

export type SourcePick =
  | { kind: 'ai' }
  | { kind: 'template'; id: string }
  | { kind: 'pack'; id: string };

const LICENSE_FALLBACK: Array<{ id: LicenseBakein; name: string }> = [
  { id: 'mit', name: 'MIT' },
  { id: 'apache-2.0', name: 'Apache-2.0' },
  { id: 'none', name: 'None' },
];

const CI_FALLBACK: Array<{ id: CiBakein; name: string }> = [
  { id: 'auto', name: 'Auto (detect from stack)' },
  { id: 'python', name: 'Python' },
  { id: 'node', name: 'Node' },
  { id: 'none', name: 'None' },
];

function stripCreerPrefix(raw: string): string {
  return raw.replace(/^\s*\/creer\b\s*/i, '').trim();
}

async function promptForIdea(fromChat: boolean, initial?: string): Promise<string | undefined> {
  if (initial?.trim()) {
    const stripped = stripCreerPrefix(initial);
    if (stripped) {
      return stripped;
    }
  }

  const value = await vscode.window.showInputBox({
    prompt: fromChat
      ? 'Enter a /creer prompt describing the project to scaffold'
      : 'Describe the project you want to create',
    placeHolder: fromChat
      ? '/creer Build a FastAPI todo'
      : 'Build a FastAPI todo app',
    value: initial?.trim() || undefined,
    ignoreFocusOut: true,
  });

  if (!value?.trim()) {
    return undefined;
  }
  return stripCreerPrefix(value);
}

/**
 * QuickPick: AI plan | built-in templates | packs.
 * Returns null if cancelled.
 */
async function pickSource(
  templates: Template[],
  packs: Pack[]
): Promise<SourcePick | null> {
  type Item = vscode.QuickPickItem & {
    kindSelect?: SourcePick['kind'];
    sourceId?: string;
  };

  const items: Item[] = [
    {
      label: 'AI plan (no template)',
      description: 'Let Creer choose the stack and file layout',
      kindSelect: 'ai',
    },
  ];

  if (templates.length > 0) {
    items.push({
      label: 'Built-in templates',
      kind: vscode.QuickPickItemKind.Separator,
    });
    for (const t of templates) {
      items.push({
        label: t.name,
        description: t.stack,
        detail: t.description,
        kindSelect: 'template',
        sourceId: t.id,
      });
    }
  }

  if (packs.length > 0) {
    items.push({
      label: 'Packs',
      kind: vscode.QuickPickItemKind.Separator,
    });
    for (const p of packs) {
      const versionNote = p.version ? ` v${p.version}` : '';
      items.push({
        label: `[pack] ${p.name}`,
        description: `${p.stack}${versionNote}`,
        detail: p.description,
        kindSelect: 'pack',
        sourceId: p.id,
      });
    }
  }

  const picked = await vscode.window.showQuickPick(items, {
    placeHolder: 'Select AI plan, template, or pack',
    ignoreFocusOut: true,
    matchOnDescription: true,
    matchOnDetail: true,
  });

  if (!picked || picked.kind === vscode.QuickPickItemKind.Separator) {
    return null;
  }

  if (picked.kindSelect === 'template' && picked.sourceId) {
    return { kind: 'template', id: picked.sourceId };
  }
  if (picked.kindSelect === 'pack' && picked.sourceId) {
    return { kind: 'pack', id: picked.sourceId };
  }
  return { kind: 'ai' };
}

function isLicenseBakein(v: string): v is LicenseBakein {
  return v === 'mit' || v === 'apache-2.0' || v === 'none';
}

function isCiBakein(v: string): v is CiBakein {
  return v === 'auto' || v === 'python' || v === 'node' || v === 'none';
}

/**
 * Resolve bake-in options from settings, optionally prompting via QuickPick
 * when `creer.promptBakeins` is true.
 * Returns null if the user cancels a prompt.
 */
async function resolveBakeins(): Promise<BakeinOptions | null> {
  const config = vscode.workspace.getConfiguration('creer');
  const promptBakeins = config.get<boolean>('promptBakeins') ?? true;
  const settingsLicense = config.get<string>('license') ?? 'mit';
  const settingsCi = config.get<string>('ciPreset') ?? 'auto';

  const defaultLicense: LicenseBakein = isLicenseBakein(settingsLicense)
    ? settingsLicense
    : 'mit';
  const defaultCi: CiBakein = isCiBakein(settingsCi) ? settingsCi : 'auto';

  if (!promptBakeins) {
    return { license: defaultLicense, ci: defaultCi };
  }

  let licenses: Array<{ id: string; name: string }> = LICENSE_FALLBACK.map((l) => ({
    id: l.id,
    name: l.name,
  }));
  let ciOptions: Array<{ id: string; name: string }> = CI_FALLBACK.map((c) => ({
    id: c.id,
    name: c.name,
  }));

  try {
    const remote = await fetchBakeins();
    if (remote.licenses.length > 0) {
      licenses = remote.licenses;
    }
    if (remote.ci.length > 0) {
      ciOptions = remote.ci;
    }
  } catch {
    // Use built-in fallbacks when /bakeins is unavailable.
  }

  const licenseItems: Array<vscode.QuickPickItem & { value: string }> = licenses.map(
    (l) => ({
      label: l.name,
      description: l.id,
      value: l.id,
    })
  );
  const licensePick = await vscode.window.showQuickPick(licenseItems, {
    placeHolder: `Select a license (default: ${defaultLicense})`,
    ignoreFocusOut: true,
    matchOnDescription: true,
  });
  if (!licensePick) {
    return null;
  }

  const ciItems: Array<vscode.QuickPickItem & { value: string }> = ciOptions.map((c) => ({
    label: c.name,
    description: c.id,
    value: c.id,
  }));
  const ciPick = await vscode.window.showQuickPick(ciItems, {
    placeHolder: `Select a CI preset (default: ${defaultCi})`,
    ignoreFocusOut: true,
    matchOnDescription: true,
  });
  if (!ciPick) {
    return null;
  }

  const license = isLicenseBakein(licensePick.value) ? licensePick.value : defaultLicense;
  const ci = isCiBakein(ciPick.value) ? ciPick.value : defaultCi;
  return { license, ci };
}

async function maybeCreateGitHubRemote(
  context: vscode.ExtensionContext,
  projectPath: string,
  projectName: string,
  idea: string
): Promise<void> {
  const config = vscode.workspace.getConfiguration('creer');
  const autoCreate = config.get<boolean>('createGitHubRepo') ?? false;
  const isPrivate = config.get<boolean>('githubPrivate') ?? true;

  let shouldCreate = autoCreate;
  if (!shouldCreate) {
    const answer = await vscode.window.showInformationMessage(
      'Create GitHub repository?',
      'Yes',
      'No'
    );
    shouldCreate = answer === 'Yes';
  }

  if (!shouldCreate) {
    return;
  }

  const token = await resolveGitHubToken(context);
  if (!token) {
    vscode.window.showWarningMessage('GitHub token required to create a repository. Skipped.');
    return;
  }

  try {
    const repo = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: creating GitHub repository…',
        cancellable: false,
      },
      async () =>
        createGitHubRepo(token, projectName, {
          private: isPrivate,
          description: idea.slice(0, 200),
        })
    );

    await ensureGitRepo(projectPath);
    await addRemoteAndPush(projectPath, repo.clone_url, token);

    const open = await vscode.window.showInformationMessage(
      `GitHub repo created: ${repo.html_url}`,
      'Open'
    );
    if (open === 'Open') {
      await vscode.env.openExternal(vscode.Uri.parse(repo.html_url));
    }
  } catch (err) {
    const message = formatAxiosError(err, 'GitHub create/push failed');
    vscode.window.showWarningMessage(`Project created, but GitHub step failed: ${message}`);
  }
}

function reportStreamProgress(
  progress: vscode.Progress<{ message?: string; increment?: number }>,
  ev: StreamProgressEvent
): void {
  if (ev.event === 'start') {
    const jobNote = ev.job_id ? ` · job ${ev.job_id}` : '';
    progress.report({
      message: `Starting ${ev.project_name} (${ev.total} files)${jobNote}…`,
    });
    return;
  }
  if (ev.event === 'file') {
    const status = ev.status === 'done' ? 'done' : 'generating';
    progress.report({
      message: `[${ev.index}/${ev.total}] ${ev.path} (${status})`,
    });
  }
}

function reportQualityIssues(quality: QualityIssue[] | undefined): void {
  if (!quality || quality.length === 0) {
    return;
  }

  const errors = quality.filter((q) => {
    const s = (q.severity || '').toLowerCase();
    return s === 'error' || s === 'critical' || s === 'fatal';
  });
  const warnings = quality.filter((q) => {
    const s = (q.severity || '').toLowerCase();
    return s === 'warning' || s === 'warn';
  });
  const other = quality.length - errors.length - warnings.length;

  if (errors.length > 0) {
    const sample = errors
      .slice(0, 3)
      .map((e) => (e.path ? `${e.code} (${e.path})` : e.code))
      .join(', ');
    const more = errors.length > 3 ? ` (+${errors.length - 3} more)` : '';
    void vscode.window.showErrorMessage(
      `Creer quality gates reported ${errors.length} error(s)` +
        (warnings.length ? `, ${warnings.length} warning(s)` : '') +
        `: ${sample}${more}`
    );
    return;
  }

  const parts: string[] = [];
  if (warnings.length) {
    parts.push(`${warnings.length} warning(s)`);
  }
  if (other > 0) {
    parts.push(`${other} other issue(s)`);
  }
  void vscode.window.showWarningMessage(
    `Creer quality gates: ${parts.join(', ') || `${quality.length} issue(s)`}.`
  );
}

function sourceToIds(source: SourcePick): {
  templateId?: string;
  packId?: string;
} {
  if (source.kind === 'template') {
    return { templateId: source.id };
  }
  if (source.kind === 'pack') {
    return { packId: source.id };
  }
  return {};
}

async function generateWithOptionalStream(
  idea: string,
  plan: PlanResponse,
  source: SourcePick,
  useStreaming: boolean,
  bakeins: BakeinOptions
): Promise<GenerateResponse> {
  const { templateId, packId } = sourceToIds(source);
  const resolvedTemplateId = plan.template_id ?? templateId;
  const resolvedPackId = plan.pack_id ?? packId;

  // pack_id and template_id are mutually exclusive
  const genOpts = {
    templateId: resolvedPackId ? undefined : resolvedTemplateId,
    packId: resolvedPackId,
    plan,
    bakeins,
  };

  if (!useStreaming) {
    return vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: generating project…',
        cancellable: false,
      },
      () => postGenerate(idea, genOpts)
    );
  }

  try {
    return await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: generating project…',
        cancellable: true,
      },
      async (progress, cancellationToken) => {
        const controller = new AbortController();
        const sub = cancellationToken.onCancellationRequested(() => {
          controller.abort();
        });
        try {
          return await streamGenerate({
            idea,
            templateId: genOpts.templateId,
            packId: genOpts.packId,
            plan: genOpts.plan,
            bakeins: genOpts.bakeins,
            signal: controller.signal,
            onProgress: (ev) => reportStreamProgress(progress, ev),
          });
        } finally {
          sub.dispose();
        }
      }
    );
  } catch (err) {
    if (isCancellationError(err)) {
      throw err;
    }
    const message = formatAxiosError(err, 'Streaming generate failed');
    vscode.window.showWarningMessage(
      `Streaming failed (${message}); falling back to non-streaming generate.`
    );
    return vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: generating project (fallback)…',
        cancellable: false,
      },
      () => postGenerate(idea, genOpts)
    );
  }
}

/**
 * Shared scaffold flow used by createRepo, createRepoFromChat, and the chat participant.
 */
export async function runScaffoldFlow(options: ScaffoldOptions): Promise<void> {
  const { context } = options;
  const fromChat = options.fromChat ?? false;
  const idea = await promptForIdea(fromChat, options.idea);
  if (!idea) {
    return;
  }

  const rootPath = await pickWorkspaceRoot();
  if (!rootPath) {
    vscode.window.showErrorMessage('Open a workspace folder first.');
    return;
  }

  const config = vscode.workspace.getConfiguration('creer');
  const shouldInitGit = config.get<boolean>('initGit') ?? true;
  const previewBeforeWrite = config.get<boolean>('previewBeforeWrite') ?? true;
  const useStreaming = config.get<boolean>('useStreaming') ?? true;

  try {
    // 1) Templates + packs
    let templates: Template[] = [];
    let packs: Pack[] = [];

    try {
      templates = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'Creer: loading templates…',
          cancellable: false,
        },
        () => fetchTemplates()
      );
    } catch (err) {
      const message = formatAxiosError(err, 'Failed to load templates');
      vscode.window.showWarningMessage(
        `Could not load templates (${message}). Continuing with AI plan only.`
      );
    }

    try {
      packs = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'Creer: loading packs…',
          cancellable: false,
        },
        () => fetchPacks()
      );
    } catch {
      // Backend /packs may not be ready yet — show templates only.
      packs = [];
    }

    const source = await pickSource(templates, packs);
    if (!source) {
      return;
    }
    const { templateId, packId } = sourceToIds(source);

    // 2) Plan
    const plan: PlanResponse = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: planning project…',
        cancellable: false,
      },
      () => postPlan(idea, { templateId, packId })
    );

    if (!plan.project_name || !Array.isArray(plan.files)) {
      vscode.window.showErrorMessage('Creer backend returned an invalid plan.');
      return;
    }

    if (templateId && !plan.template_id) {
      plan.template_id = templateId;
    }
    if (packId && !plan.pack_id) {
      plan.pack_id = packId;
    }

    // 3) Plan preview / confirm (tree) before generate
    if (previewBeforeWrite) {
      const confirmed = await showPlanPreviewAndConfirm(plan, idea);
      if (!confirmed) {
        return;
      }
    }

    // 4) Bake-ins (license / CI)
    const bakeins = await resolveBakeins();
    if (!bakeins) {
      return;
    }

    // 5) Generate (streaming with cancellable progress when enabled)
    let generated: GenerateResponse;
    try {
      generated = await generateWithOptionalStream(
        idea,
        plan,
        source,
        useStreaming,
        bakeins
      );
    } catch (err) {
      if (isCancellationError(err)) {
        void vscode.window.showInformationMessage('Creer generation cancelled.');
        return;
      }
      throw err;
    }

    reportQualityIssues(generated.quality);

    const projectName = generated.project_name || plan.project_name;
    const files = generated.files;

    if (!projectName || !files || typeof files !== 'object') {
      vscode.window.showErrorMessage('Creer backend returned an invalid generate response.');
      return;
    }

    try {
      assertSafeProjectName(projectName);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      vscode.window.showErrorMessage(`Creer refused unsafe project name: ${message}`);
      return;
    }

    const projectPath = path.join(rootPath, projectName);
    // Ensure the resolved project folder stays under the workspace root
    const resolvedRoot = path.resolve(rootPath);
    const resolvedProject = path.resolve(projectPath);
    const rootPrefix = resolvedRoot.endsWith(path.sep)
      ? resolvedRoot
      : resolvedRoot + path.sep;
    if (resolvedProject !== resolvedRoot && !resolvedProject.startsWith(rootPrefix)) {
      vscode.window.showErrorMessage(
        `Creer refused project path outside workspace: ${projectName}`
      );
      return;
    }

    // 6) Content preview / diff before write
    const contentConfirmed = await showContentPreviewAndConfirm(
      projectName,
      projectPath,
      files
    );
    if (!contentConfirmed) {
      return;
    }

    // 7) Conflict resolution (optional side-by-side diffs)
    const conflicts = findConflicts(projectPath, files);
    const resolution = await resolveConflictsWithDiffs(projectPath, files, conflicts);
    if (resolution === 'cancel') {
      return;
    }

    // 8) Write
    const { written, skipped } = writeProjectFiles(projectPath, files, resolution);
    if (written === 0 && skipped === 0) {
      vscode.window.showWarningMessage('No files were written.');
      return;
    }

    // 9) Git init
    if (shouldInitGit) {
      try {
        await initGit(projectPath);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        vscode.window.showWarningMessage(`Project created, but git init failed: ${message}`);
      }
    }

    // 10) GitHub remote (optional)
    await maybeCreateGitHubRemote(context, projectPath, projectName, idea);

    const skipNote = skipped > 0 ? ` (${skipped} existing skipped)` : '';
    vscode.window.showInformationMessage(
      `Project ${projectName} created at ${projectPath}${skipNote}.`
    );
  } catch (err) {
    if (isCancellationError(err)) {
      void vscode.window.showInformationMessage('Creer generation cancelled.');
      return;
    }
    const message = formatAxiosError(err, 'Creer failed');
    vscode.window.showErrorMessage(`Creer failed: ${message}`);
  }
}

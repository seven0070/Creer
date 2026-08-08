import * as path from 'path';
import * as vscode from 'vscode';
import {
  createGitHubRepo,
  fetchTemplates,
  formatAxiosError,
  postGenerate,
  postPlan,
  type PlanResponse,
  type Template,
} from './api';
import { addRemoteAndPush, ensureGitRepo, initGit } from './git';
import { showPlanPreviewAndConfirm } from './preview';
import {
  assertSafeProjectName,
  findConflicts,
  resolveConflicts,
  writeProjectFiles,
} from './writeFiles';

export interface ScaffoldOptions {
  /** Pre-filled idea (e.g. from chat). If omitted, prompts the user. */
  idea?: string;
  /** Use chat-style InputBox placeholder (/creer …). */
  fromChat?: boolean;
}

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

async function pickTemplate(templates: Template[]): Promise<string | undefined | null> {
  // null = cancelled; undefined = AI plan (no template); string = template id
  const items: Array<vscode.QuickPickItem & { templateId?: string }> = [
    {
      label: 'AI plan (no template)',
      description: 'Let Creer choose the stack and file layout',
      templateId: undefined,
    },
    ...templates.map((t) => ({
      label: t.name,
      description: t.stack,
      detail: t.description,
      templateId: t.id,
    })),
  ];

  const picked = await vscode.window.showQuickPick(items, {
    placeHolder: 'Select a template or AI plan',
    ignoreFocusOut: true,
    matchOnDescription: true,
    matchOnDetail: true,
  });

  if (!picked) {
    return null;
  }
  return picked.templateId;
}

async function resolveGitHubToken(): Promise<string | undefined> {
  const config = vscode.workspace.getConfiguration('creer');
  const configured = (config.get<string>('githubToken') || '').trim();
  if (configured) {
    return configured;
  }

  const token = await vscode.window.showInputBox({
    prompt: 'GitHub personal access token (repo scope)',
    placeHolder: 'ghp_…',
    password: true,
    ignoreFocusOut: true,
  });
  return token?.trim() || undefined;
}

async function maybeCreateGitHubRemote(
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

  const token = await resolveGitHubToken();
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

/**
 * Shared scaffold flow used by createRepo, createRepoFromChat, and the chat participant.
 */
export async function runScaffoldFlow(options: ScaffoldOptions = {}): Promise<void> {
  const fromChat = options.fromChat ?? false;
  const idea = await promptForIdea(fromChat, options.idea);
  if (!idea) {
    return;
  }

  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders) {
    vscode.window.showErrorMessage('Open a workspace folder first.');
    return;
  }

  const config = vscode.workspace.getConfiguration('creer');
  const shouldInitGit = config.get<boolean>('initGit') ?? true;
  const previewBeforeWrite = config.get<boolean>('previewBeforeWrite') ?? true;
  const rootPath = workspaceFolders[0].uri.fsPath;

  try {
    // 1) Templates
    let templates: Template[] = [];
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

    const templatePick = await pickTemplate(templates);
    if (templatePick === null) {
      return;
    }
    const templateId = templatePick; // string | undefined

    // 2) Plan
    const plan: PlanResponse = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: planning project…',
        cancellable: false,
      },
      () => postPlan(idea, templateId)
    );

    if (!plan.project_name || !Array.isArray(plan.files)) {
      vscode.window.showErrorMessage('Creer backend returned an invalid plan.');
      return;
    }

    // Ensure template_id is on the plan when selected
    if (templateId && !plan.template_id) {
      plan.template_id = templateId;
    }

    // 3) Preview / confirm
    if (previewBeforeWrite) {
      const confirmed = await showPlanPreviewAndConfirm(plan, idea);
      if (!confirmed) {
        return;
      }
    }

    // 4) Generate
    const generated = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: generating project…',
        cancellable: false,
      },
      () =>
        postGenerate(idea, {
          templateId: plan.template_id ?? templateId,
          plan,
        })
    );

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

    // 5) Conflict resolution
    const conflicts = findConflicts(projectPath, files);
    const resolution = await resolveConflicts(conflicts);
    if (resolution === 'cancel') {
      return;
    }

    // 6) Write
    const { written, skipped } = writeProjectFiles(projectPath, files, resolution);
    if (written === 0 && skipped === 0) {
      vscode.window.showWarningMessage('No files were written.');
      return;
    }

    // 7) Git init
    if (shouldInitGit) {
      try {
        await initGit(projectPath);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        vscode.window.showWarningMessage(`Project created, but git init failed: ${message}`);
      }
    }

    // 8) GitHub remote (optional)
    await maybeCreateGitHubRemote(projectPath, projectName, idea);

    const skipNote = skipped > 0 ? ` (${skipped} existing skipped)` : '';
    vscode.window.showInformationMessage(
      `Project ${projectName} created at ${projectPath}${skipNote}.`
    );
  } catch (err) {
    const message = formatAxiosError(err, 'Creer failed');
    vscode.window.showErrorMessage(`Creer failed: ${message}`);
  }
}

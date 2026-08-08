import * as vscode from 'vscode';
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

interface GenerateResponse {
  project_name: string;
  stack?: string;
  files: Record<string, string>;
}

async function initGit(projectPath: string): Promise<void> {
  await execAsync('git init', { cwd: projectPath });
  await execAsync('git add .', { cwd: projectPath });
  try {
    await execAsync('git commit -m "Initial commit"', { cwd: projectPath });
  } catch {
    // Commit can fail if git user.name/email are unset — still leave the repo initialized.
  }
}

export function activate(context: vscode.ExtensionContext) {
  const disposable = vscode.commands.registerCommand('creer.createRepo', async () => {
    const idea = await vscode.window.showInputBox({
      prompt: 'Describe the project you want to create',
      placeHolder: 'Build a FastAPI todo app',
      ignoreFocusOut: true,
    });

    if (!idea?.trim()) {
      return;
    }

    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
      vscode.window.showErrorMessage('Open a workspace folder first.');
      return;
    }

    const config = vscode.workspace.getConfiguration('creer');
    const backendUrl = (config.get<string>('backendUrl') || 'http://localhost:8000').replace(/\/$/, '');
    const shouldInitGit = config.get<boolean>('initGit') ?? true;

    const rootPath = workspaceFolders[0].uri.fsPath;

    try {
      const response = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'Creer: generating project…',
          cancellable: false,
        },
        async () =>
          axios.post<GenerateResponse>(
            `${backendUrl}/generate`,
            { idea: idea.trim() },
            { timeout: 300_000 }
          )
      );

      const projectName = response.data.project_name;
      const files = response.data.files;

      if (!projectName || !files || typeof files !== 'object') {
        vscode.window.showErrorMessage('Creer backend returned an invalid response.');
        return;
      }

      const projectPath = path.join(rootPath, projectName);

      if (fs.existsSync(projectPath)) {
        const overwrite = await vscode.window.showWarningMessage(
          `Folder "${projectName}" already exists. Overwrite files?`,
          { modal: true },
          'Overwrite'
        );
        if (overwrite !== 'Overwrite') {
          return;
        }
      }

      fs.mkdirSync(projectPath, { recursive: true });

      for (const filePath of Object.keys(files)) {
        const fullPath = path.join(projectPath, filePath);
        fs.mkdirSync(path.dirname(fullPath), { recursive: true });
        fs.writeFileSync(fullPath, files[filePath], 'utf8');
      }

      if (shouldInitGit) {
        try {
          await initGit(projectPath);
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err);
          vscode.window.showWarningMessage(`Project created, but git init failed: ${message}`);
        }
      }

      vscode.window.showInformationMessage(`Project ${projectName} created.`);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail || err.message;
        vscode.window.showErrorMessage(`Creer generation failed: ${detail}`);
        return;
      }
      const message = err instanceof Error ? err.message : String(err);
      vscode.window.showErrorMessage(`Creer failed: ${message}`);
    }
  });

  context.subscriptions.push(disposable);
}

export function deactivate() {}

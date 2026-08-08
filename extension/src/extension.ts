import * as vscode from 'vscode';
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export function activate(context: vscode.ExtensionContext) {
  const disposable = vscode.commands.registerCommand('creer.createRepo', async () => {
    // 1. Ask for idea
    const idea = await vscode.window.showInputBox({
      prompt: 'Describe the project you want to create',
      placeHolder: 'e.g. Build a FastAPI todo app with JWT auth and SQLite',
      validateInput: (v) => (v && v.trim().length >= 5 ? null : 'Please describe your idea (min 5 chars)')
    });

    if (!idea) {
      return;
    }

    const config = vscode.workspace.getConfiguration('creer');
    const backendUrl = (config.get<string>('backendUrl') || 'http://localhost:8000').replace(/\/$/, '');
    const initGit = config.get<boolean>('initGit', true);

    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
      vscode.window.showErrorMessage('Open a workspace folder first (File → Open Folder), then run Creer: Create New Repo.');
      return;
    }

    const rootPath = workspaceFolders[0].uri.fsPath;

    // Progress UI
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: Generating project...',
        cancellable: false
      },
      async (progress) => {
        progress.report({ message: 'Planning structure...' });

        let data: { project_name: string; files: Record<string, string> };
        try {
          const response = await axios.post(`${backendUrl}/generate`, { idea }, { timeout: 120000 });
          data = response.data;
        } catch (err: any) {
          const msg = err?.response?.data?.detail || err?.message || String(err);
          vscode.window.showErrorMessage(`Creer backend failed: ${msg}. Is the backend running at ${backendUrl}? (uvicorn main:app --reload --port 8000)`);
          return;
        }

        const projectName = data.project_name;
        const files = data.files;

        if (!projectName || !files || Object.keys(files).length === 0) {
          vscode.window.showErrorMessage('Backend returned empty project. Try a more detailed idea.');
          return;
        }

        const projectPath = path.join(rootPath, projectName);

        // Overwrite protection
        if (fs.existsSync(projectPath)) {
          const choice = await vscode.window.showWarningMessage(
            `Folder "${projectName}" already exists in workspace. Overwrite?`,
            { modal: true },
            'Overwrite',
            'Cancel'
          );
          if (choice !== 'Overwrite') {
            vscode.window.showInformationMessage('Creer cancelled — no files written.');
            return;
          }
        }

        progress.report({ message: `Writing ${Object.keys(files).length} files to ${projectName}/...` });

        // Write files
        try {
          fs.mkdirSync(projectPath, { recursive: true });

          for (const [filePath, content] of Object.entries(files)) {
            // basic traversal protection (also enforced backend)
            if (filePath.includes('..') || path.isAbsolute(filePath)) {
              console.warn(`[creer] skipping unsafe path: ${filePath}`);
              continue;
            }
            const fullPath = path.join(projectPath, filePath);
            // ensure still inside projectPath
            const relative = path.relative(projectPath, fullPath);
            if (relative.startsWith('..') || path.isAbsolute(relative)) {
              console.warn(`[creer] path escapes project: ${filePath}`);
              continue;
            }
            fs.mkdirSync(path.dirname(fullPath), { recursive: true });
            fs.writeFileSync(fullPath, content, 'utf8');
          }
        } catch (err: any) {
          vscode.window.showErrorMessage(`Failed to write files: ${err.message}`);
          return;
        }

        // Optional git init
        if (initGit) {
          progress.report({ message: 'Initializing git...' });
          try {
            // check if already a git repo
            const isGit = fs.existsSync(path.join(projectPath, '.git'));
            if (!isGit) {
              await execAsync('git init', { cwd: projectPath });
              await execAsync('git add .', { cwd: projectPath });
              // commit may fail if git user not configured - don't block
              try {
                await execAsync('git commit -m "Initial commit from Creer"', { cwd: projectPath });
              } catch {
                // add .git keep but no commit is okay
                console.log('[creer] git commit skipped (user.name/email missing?)');
              }
            }
          } catch (err: any) {
            vscode.window.showWarningMessage(`Project created but git init failed: ${err.message}`);
          }
        }

        vscode.window.showInformationMessage(`Project "${projectName}" created at ${projectName}/ (${Object.keys(files).length} files)`);

        // Offer to open folder
        const open = await vscode.window.showInformationMessage(`Open "${projectName}"?`, 'Open Folder', 'Show in Explorer');
        if (open === 'Open Folder') {
          const uri = vscode.Uri.file(projectPath);
          await vscode.commands.executeCommand('vscode.openFolder', uri, { forceNewWindow: false });
        } else if (open === 'Show in Explorer') {
          // reveal in explorer
          const uri = vscode.Uri.file(projectPath);
          await vscode.commands.executeCommand('revealInExplorer', uri);
        }
      }
    );
  });

  context.subscriptions.push(disposable);
}

export function deactivate() {}

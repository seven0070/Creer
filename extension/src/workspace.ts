import * as vscode from 'vscode';

/**
 * Resolve which workspace folder root to use for scaffolding.
 * - Single folder → that folder's fsPath
 * - Multiple → honor `creer.defaultWorkspaceFolder` if it matches name or fsPath;
 *   otherwise QuickPick by folder name / path
 * Returns undefined if no folders are open or the user cancels the pick.
 */
export async function pickWorkspaceRoot(): Promise<string | undefined> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    return undefined;
  }

  if (folders.length === 1) {
    return folders[0].uri.fsPath;
  }

  const config = vscode.workspace.getConfiguration('creer');
  const hint = (config.get<string>('defaultWorkspaceFolder') || '').trim();
  if (hint) {
    const matched = folders.find(
      (f) => f.name === hint || f.uri.fsPath === hint || f.uri.fsPath.endsWith(hint)
    );
    if (matched) {
      return matched.uri.fsPath;
    }
  }

  const items: Array<vscode.QuickPickItem & { fsPath: string }> = folders.map((f) => ({
    label: f.name,
    description: f.uri.fsPath,
    fsPath: f.uri.fsPath,
  }));

  const picked = await vscode.window.showQuickPick(items, {
    placeHolder: 'Select a workspace folder for the new project',
    ignoreFocusOut: true,
    matchOnDescription: true,
  });

  return picked?.fsPath;
}

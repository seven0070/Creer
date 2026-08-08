import * as vscode from 'vscode';

/** SecretStorage key for the GitHub personal access token. */
export const GITHUB_TOKEN_SECRET_KEY = 'creer.githubToken';

/** SecretStorage key for the optional Creer registry write token. */
export const REGISTRY_TOKEN_SECRET_KEY = 'creer.registryToken';

/**
 * Read GitHub token: SecretStorage first, then deprecated config fallback.
 */
export async function getGitHubToken(
  context: vscode.ExtensionContext
): Promise<string | undefined> {
  const secret = (await context.secrets.get(GITHUB_TOKEN_SECRET_KEY))?.trim();
  if (secret) {
    return secret;
  }

  // Migration path: plaintext setting (deprecated)
  const fromConfig = (
    vscode.workspace.getConfiguration('creer').get<string>('githubToken') || ''
  ).trim();
  return fromConfig || undefined;
}

export async function setGitHubToken(
  context: vscode.ExtensionContext,
  token: string
): Promise<void> {
  await context.secrets.store(GITHUB_TOKEN_SECRET_KEY, token.trim());
}

export async function clearGitHubToken(context: vscode.ExtensionContext): Promise<void> {
  await context.secrets.delete(GITHUB_TOKEN_SECRET_KEY);
}

/**
 * Prompt for a token and optionally persist it in SecretStorage.
 */
export async function promptAndStoreGitHubToken(
  context: vscode.ExtensionContext
): Promise<string | undefined> {
  const token = await vscode.window.showInputBox({
    prompt: 'GitHub personal access token (repo scope)',
    placeHolder: 'ghp_…',
    password: true,
    ignoreFocusOut: true,
  });

  const trimmed = token?.trim();
  if (!trimmed) {
    return undefined;
  }

  const saveChoice = await vscode.window.showQuickPick(
    [
      {
        label: 'Save to SecretStorage (recommended)',
        description: 'Stored securely; preferred over settings.json',
        id: 'save',
      },
      {
        label: 'Use once (do not save)',
        description: 'Token is only used for this operation',
        id: 'once',
      },
    ],
    {
      placeHolder: 'Save GitHub token?',
      ignoreFocusOut: true,
    }
  );

  if (saveChoice?.id === 'save') {
    await setGitHubToken(context, trimmed);
    void vscode.window.showInformationMessage('Creer: GitHub token saved to SecretStorage.');
  }

  return trimmed;
}

/**
 * Resolve token: SecretStorage → config fallback → prompt (offer save).
 */
export async function resolveGitHubToken(
  context: vscode.ExtensionContext
): Promise<string | undefined> {
  const existing = await getGitHubToken(context);
  if (existing) {
    return existing;
  }
  return promptAndStoreGitHubToken(context);
}

/**
 * Read registry token: SecretStorage first, then deprecated config fallback.
 * Auth is optional — only needed when the backend sets CREER_REGISTRY_TOKEN.
 */
export async function getRegistryToken(
  context: vscode.ExtensionContext
): Promise<string | undefined> {
  const secret = (await context.secrets.get(REGISTRY_TOKEN_SECRET_KEY))?.trim();
  if (secret) {
    return secret;
  }

  const fromConfig = (
    vscode.workspace.getConfiguration('creer').get<string>('registryToken') || ''
  ).trim();
  return fromConfig || undefined;
}

export async function setRegistryToken(
  context: vscode.ExtensionContext,
  token: string
): Promise<void> {
  await context.secrets.store(REGISTRY_TOKEN_SECRET_KEY, token.trim());
}

export async function clearRegistryToken(context: vscode.ExtensionContext): Promise<void> {
  await context.secrets.delete(REGISTRY_TOKEN_SECRET_KEY);
}

/**
 * Resolve registry token for mutating API calls (SecretStorage → deprecated setting).
 * Does not prompt — registry auth is optional when the server has no CREER_REGISTRY_TOKEN.
 */
export async function resolveRegistryToken(
  context: vscode.ExtensionContext
): Promise<string | undefined> {
  return getRegistryToken(context);
}

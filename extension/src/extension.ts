import * as vscode from 'vscode';
import { registerConflictDiffProvider } from './conflictDiff';
import {
  browseMarketplaceCommand,
  browseRegistryCommand,
  installPackFromUrlCommand,
} from './marketplace';
import { browseFederatedRegistryCommand, manageRegistryPeersCommand } from './registry';
import { runScaffoldFlow } from './scaffold';
import {
  clearGitHubToken,
  clearRegistryToken,
  setGitHubToken,
  setRegistryToken,
} from './secrets';

export function activate(context: vscode.ExtensionContext) {
  registerConflictDiffProvider(context);

  const createRepo = vscode.commands.registerCommand('creer.createRepo', async () => {
    await runScaffoldFlow({ context, fromChat: false });
  });

  const createRepoFromChat = vscode.commands.registerCommand(
    'creer.createRepoFromChat',
    async (idea?: string) => {
      const initial = typeof idea === 'string' ? idea : undefined;
      await runScaffoldFlow({ context, idea: initial, fromChat: true });
    }
  );

  const setToken = vscode.commands.registerCommand('creer.setGitHubToken', async () => {
    const token = await vscode.window.showInputBox({
      prompt: 'GitHub personal access token (repo scope) — stored in SecretStorage',
      placeHolder: 'ghp_…',
      password: true,
      ignoreFocusOut: true,
    });
    const trimmed = token?.trim();
    if (!trimmed) {
      return;
    }
    await setGitHubToken(context, trimmed);
    void vscode.window.showInformationMessage('Creer: GitHub token saved to SecretStorage.');
  });

  const clearToken = vscode.commands.registerCommand('creer.clearGitHubToken', async () => {
    await clearGitHubToken(context);
    void vscode.window.showInformationMessage('Creer: GitHub token cleared from SecretStorage.');
  });

  const setRegistryTok = vscode.commands.registerCommand(
    'creer.setRegistryToken',
    async () => {
      const token = await vscode.window.showInputBox({
        prompt:
          'Creer registry write token (matches CREER_REGISTRY_TOKEN) — stored in SecretStorage',
        placeHolder: 'registry token',
        password: true,
        ignoreFocusOut: true,
      });
      const trimmed = token?.trim();
      if (!trimmed) {
        return;
      }
      await setRegistryToken(context, trimmed);
      void vscode.window.showInformationMessage(
        'Creer: registry token saved to SecretStorage.'
      );
    }
  );

  const clearRegistryTok = vscode.commands.registerCommand(
    'creer.clearRegistryToken',
    async () => {
      await clearRegistryToken(context);
      void vscode.window.showInformationMessage(
        'Creer: registry token cleared from SecretStorage.'
      );
    }
  );

  const installPackFromUrl = vscode.commands.registerCommand(
    'creer.installPackFromUrl',
    () => installPackFromUrlCommand(context)
  );

  const browseMarketplace = vscode.commands.registerCommand(
    'creer.browseMarketplace',
    () => browseMarketplaceCommand(context)
  );

  const browseRegistry = vscode.commands.registerCommand(
    'creer.browseRegistry',
    () => browseRegistryCommand(context)
  );

  const browseFederatedRegistry = vscode.commands.registerCommand(
    'creer.browseFederatedRegistry',
    () => browseFederatedRegistryCommand(context)
  );

  const manageRegistryPeers = vscode.commands.registerCommand(
    'creer.manageRegistryPeers',
    () => manageRegistryPeersCommand(context)
  );

  context.subscriptions.push(
    createRepo,
    createRepoFromChat,
    setToken,
    clearToken,
    setRegistryTok,
    clearRegistryTok,
    installPackFromUrl,
    browseMarketplace,
    browseRegistry,
    browseFederatedRegistry,
    manageRegistryPeers
  );
  registerChatParticipant(context);
}

function registerChatParticipant(context: vscode.ExtensionContext): void {
  // Runtime feature-detect: chat API may be missing on older VS Code hosts.
  const create =
    typeof vscode.chat?.createChatParticipant === 'function'
      ? vscode.chat.createChatParticipant.bind(vscode.chat)
      : undefined;

  if (!create) {
    return;
  }

  try {
    const participant = create(
      'creer.participant',
      async (request, _context, stream, _token) => {
        const idea = (request.prompt || '').trim();
        if (!idea) {
          stream.markdown(
            'Provide an idea after `@creer`, for example: `@creer Build a FastAPI todo app`.\n\n' +
              'You can also run **Creer: Create from Chat Prompt** and type `/creer …`.'
          );
          return;
        }

        stream.markdown(
          `Scaffolding with Creer: **${idea}**…\n\n` +
            'Follow the prompts to pick a template, preview the plan, and confirm.'
        );
        await runScaffoldFlow({ context, idea, fromChat: true });
      }
    );

    context.subscriptions.push(participant);
  } catch {
    // Hosts without chat support — ignore registration failure.
  }
}

export function deactivate() {}

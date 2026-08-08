import * as vscode from 'vscode';
import { runScaffoldFlow } from './scaffold';

export function activate(context: vscode.ExtensionContext) {
  const createRepo = vscode.commands.registerCommand('creer.createRepo', async () => {
    await runScaffoldFlow({ fromChat: false });
  });

  const createRepoFromChat = vscode.commands.registerCommand(
    'creer.createRepoFromChat',
    async (idea?: string) => {
      const initial = typeof idea === 'string' ? idea : undefined;
      await runScaffoldFlow({ idea: initial, fromChat: true });
    }
  );

  context.subscriptions.push(createRepo, createRepoFromChat);
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
        await runScaffoldFlow({ idea, fromChat: true });
      }
    );

    context.subscriptions.push(participant);
  } catch {
    // Hosts without chat support — ignore registration failure.
  }
}

export function deactivate() {}

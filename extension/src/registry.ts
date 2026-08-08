import * as vscode from 'vscode';
import {
  fetchFederatedRegistry,
  formatAxiosError,
  type FederatedRegistryItem,
} from './api';
import {
  installFromResolvedUrl,
  isBundledSource,
} from './marketplace';

function peerHostLabel(peer: string | undefined): string | undefined {
  if (!peer?.trim()) {
    return undefined;
  }
  try {
    return new URL(peer).host || peer;
  } catch {
    return peer;
  }
}

/**
 * Creer: Browse Federated Registry — GET /registry/federated, QuickPick, install.
 */
export async function browseFederatedRegistryCommand(): Promise<void> {
  const q = await vscode.window.showInputBox({
    prompt: 'Search federated registry (leave empty for all packs)',
    placeHolder: 'fastapi, express, peer host…',
    ignoreFocusOut: true,
  });
  if (q === undefined) {
    return;
  }

  let items: FederatedRegistryItem[];
  let peerCount = 0;
  try {
    const federated = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: loading federated registry…',
        cancellable: false,
      },
      () => fetchFederatedRegistry({ q: q.trim() || undefined })
    );
    items = federated.items;
    peerCount = federated.peers?.length ?? 0;
  } catch (err) {
    const message = formatAxiosError(err, 'Federated registry unavailable');
    void vscode.window.showWarningMessage(
      `Creer: federated registry endpoint not available (${message}). ` +
        'Try “Creer: Browse Pack Registry” or configure CREER_REGISTRY_PEERS on the backend.'
    );
    return;
  }

  if (items.length === 0) {
    void vscode.window.showInformationMessage(
      peerCount > 0
        ? 'Creer: no federated packs matched (peers configured).'
        : 'Creer: no federated packs matched.'
    );
    return;
  }

  type PickItem = vscode.QuickPickItem & { fed?: FederatedRegistryItem };
  const picks: PickItem[] = items.map((item) => {
    const parts: string[] = [];
    if (item.source) {
      parts.push(item.source);
    }
    const host = peerHostLabel(item.peer);
    if (host) {
      parts.push(host);
    }
    if (item.stack) {
      parts.push(item.stack);
    }
    if (item.version) {
      parts.push(item.version);
    }
    return {
      label: item.name || item.id,
      description: parts.join(' · '),
      detail: item.description,
      fed: item,
    };
  });

  const picked = await vscode.window.showQuickPick(picks, {
    placeHolder: 'Select a federated pack to install',
    ignoreFocusOut: true,
    matchOnDescription: true,
    matchOnDetail: true,
  });

  if (!picked?.fed) {
    return;
  }

  const item = picked.fed;
  if (isBundledSource(item.source) && !item.peer) {
    const choice = await vscode.window.showInformationMessage(
      `“${item.name || item.id}” is bundled locally. Install a copy via download URL anyway?`,
      'Install copy',
      'Cancel'
    );
    if (choice !== 'Install copy') {
      return;
    }
  }

  await installFromResolvedUrl(
    item.name || item.id,
    item.install_url || item.download_url
  );
}

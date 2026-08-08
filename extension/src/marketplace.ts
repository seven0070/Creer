import * as vscode from 'vscode';
import {
  deletePack,
  fetchMarketplace,
  formatAxiosError,
  installPack,
  type MarketplaceItem,
} from './api';

/**
 * Creer: Install Pack from URL — prompt for URL, POST /packs/install.
 */
export async function installPackFromUrlCommand(): Promise<void> {
  const url = await vscode.window.showInputBox({
    prompt: 'Pack URL (JSON/YAML pack definition)',
    placeHolder: 'https://example.com/packs/fastapi-crud.json',
    ignoreFocusOut: true,
  });
  const trimmed = url?.trim();
  if (!trimmed) {
    return;
  }

  try {
    const pack = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: installing pack…',
        cancellable: false,
      },
      () => installPack(trimmed)
    );
    const name = pack.name || pack.id || 'pack';
    void vscode.window.showInformationMessage(
      `Creer: installed pack “${name}”${pack.id ? ` (${pack.id})` : ''}.`
    );
  } catch (err) {
    const message = formatAxiosError(err, 'Failed to install pack');
    void vscode.window.showErrorMessage(`Creer: could not install pack — ${message}`);
  }
}

function isBundledSource(source: string | undefined): boolean {
  if (!source) {
    return false;
  }
  const s = source.toLowerCase();
  return s === 'bundled' || s === 'builtin' || s === 'built-in' || s === 'local';
}

/**
 * Creer: Browse Pack Marketplace — GET /marketplace, QuickPick, optional install.
 */
export async function browseMarketplaceCommand(): Promise<void> {
  let items: MarketplaceItem[];
  try {
    items = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: loading marketplace…',
        cancellable: false,
      },
      () => fetchMarketplace()
    );
  } catch (err) {
    const message = formatAxiosError(err, 'Marketplace unavailable');
    void vscode.window.showWarningMessage(
      `Creer: marketplace endpoint not available (${message}). ` +
        'You can still use “Creer: Install Pack from URL” if the backend supports /packs/install.'
    );
    return;
  }

  if (items.length === 0) {
    void vscode.window.showInformationMessage('Creer: marketplace has no items.');
    return;
  }

  type PickItem = vscode.QuickPickItem & { market?: MarketplaceItem };

  const picks: PickItem[] = items.map((item) => {
    const bundled = isBundledSource(item.source);
    const hasUrl = Boolean(item.url?.trim());
    let description = item.source || '';
    if (bundled) {
      description = description ? `${description} · bundled` : 'bundled';
    } else if (hasUrl) {
      description = description ? `${description} · remote` : 'remote';
    }
    return {
      label: item.name || item.id,
      description,
      detail: item.description,
      market: item,
    };
  });

  const picked = await vscode.window.showQuickPick(picks, {
    placeHolder: 'Select a marketplace pack',
    ignoreFocusOut: true,
    matchOnDescription: true,
    matchOnDetail: true,
  });

  if (!picked?.market) {
    return;
  }

  const item = picked.market;
  if (isBundledSource(item.source)) {
    void vscode.window.showInformationMessage(
      `Creer: “${item.name || item.id}” is already available (bundled).`
    );
    return;
  }

  const url = item.url?.trim();
  if (!url) {
    void vscode.window.showInformationMessage(
      `Creer: “${item.name || item.id}” has no install URL.`
    );
    return;
  }

  const action = await vscode.window.showInformationMessage(
    `Install pack “${item.name || item.id}” from marketplace?`,
    'Install',
    'Cancel'
  );
  if (action !== 'Install') {
    return;
  }

  try {
    const pack = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `Creer: installing ${item.name || item.id}…`,
        cancellable: false,
      },
      () => installPack(url)
    );
    void vscode.window.showInformationMessage(
      `Creer: installed pack “${pack.name || pack.id || item.name}”.`
    );
  } catch (err) {
    const message = formatAxiosError(err, 'Failed to install pack');
    void vscode.window.showErrorMessage(`Creer: could not install pack — ${message}`);
  }
}

/** Optional helper for hosts that expose delete UI later. */
export async function deletePackCommand(packId?: string): Promise<void> {
  let id = packId?.trim();
  if (!id) {
    id = (
      await vscode.window.showInputBox({
        prompt: 'Pack id to delete',
        placeHolder: 'fastapi-crud',
        ignoreFocusOut: true,
      })
    )?.trim();
  }
  if (!id) {
    return;
  }

  try {
    await deletePack(id);
    void vscode.window.showInformationMessage(`Creer: deleted pack “${id}”.`);
  } catch (err) {
    const message = formatAxiosError(err, 'Failed to delete pack');
    void vscode.window.showErrorMessage(`Creer: could not delete pack — ${message}`);
  }
}

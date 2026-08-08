import * as vscode from 'vscode';
import {
  deletePack,
  fetchMarketplace,
  fetchRegistry,
  formatAxiosError,
  installPack,
  type MarketplaceItem,
  type RegistryItem,
} from './api';
import { resolveRegistryToken } from './secrets';

export function resolveInstallUrl(url: string | undefined): string | undefined {
  const trimmed = url?.trim();
  if (!trimmed) {
    return undefined;
  }
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed;
  }
  // Relative registry paths → absolute against backend
  const config = vscode.workspace.getConfiguration('creer');
  const backendUrl = (config.get<string>('backendUrl') || 'http://localhost:8000').replace(
    /\/$/,
    ''
  );
  if (trimmed.startsWith('/')) {
    return `${backendUrl}${trimmed}`;
  }
  return `${backendUrl}/${trimmed}`;
}

/**
 * Creer: Install Pack from URL — prompt for URL, POST /packs/install.
 */
export async function installPackFromUrlCommand(
  context: vscode.ExtensionContext
): Promise<void> {
  const url = await vscode.window.showInputBox({
    prompt: 'Pack URL (JSON/YAML pack definition or registry download URL)',
    placeHolder: 'http://localhost:8000/registry/packs/fastapi-crud/download',
    ignoreFocusOut: true,
  });
  const trimmed = url?.trim();
  if (!trimmed) {
    return;
  }

  const token = await resolveRegistryToken(context);
  try {
    const pack = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: installing pack…',
        cancellable: false,
      },
      () => installPack(trimmed, { token })
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

export function isBundledSource(source: string | undefined): boolean {
  if (!source) {
    return false;
  }
  const s = source.toLowerCase();
  return s === 'bundled' || s === 'builtin' || s === 'built-in' || s === 'local';
}

export async function installFromResolvedUrl(
  label: string,
  url: string | undefined,
  context?: vscode.ExtensionContext
): Promise<void> {
  const resolved = resolveInstallUrl(url);
  if (!resolved) {
    void vscode.window.showInformationMessage(`Creer: “${label}” has no install URL.`);
    return;
  }

  const action = await vscode.window.showInformationMessage(
    `Install pack “${label}”?\n${resolved}`,
    'Install',
    'Cancel'
  );
  if (action !== 'Install') {
    return;
  }

  const token = context ? await resolveRegistryToken(context) : undefined;
  try {
    const pack = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `Creer: installing ${label}…`,
        cancellable: false,
      },
      () => installPack(resolved, { token })
    );
    void vscode.window.showInformationMessage(
      `Creer: installed pack “${pack.name || pack.id || label}”.`
    );
  } catch (err) {
    const message = formatAxiosError(err, 'Failed to install pack');
    void vscode.window.showErrorMessage(`Creer: could not install pack — ${message}`);
  }
}

/**
 * Creer: Browse Pack Marketplace — GET /marketplace, QuickPick, optional install.
 */
export async function browseMarketplaceCommand(
  context: vscode.ExtensionContext
): Promise<void> {
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
        'Try “Creer: Browse Pack Registry” or “Install Pack from URL”.'
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
    const hasUrl = Boolean(item.url?.trim() || item.download_url?.trim());
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
  if (isBundledSource(item.source) && !item.url && !item.download_url) {
    void vscode.window.showInformationMessage(
      `Creer: “${item.name || item.id}” is already available (bundled).`
    );
    return;
  }

  await installFromResolvedUrl(
    item.name || item.id,
    item.url || item.download_url,
    context
  );
}

/**
 * Creer: Browse Pack Registry — searchable self-hosted /registry catalog.
 */
export async function browseRegistryCommand(
  context: vscode.ExtensionContext
): Promise<void> {
  const q = await vscode.window.showInputBox({
    prompt: 'Search registry (leave empty for all packs)',
    placeHolder: 'fastapi, express, cli…',
    ignoreFocusOut: true,
  });
  if (q === undefined) {
    return;
  }

  let items: RegistryItem[];
  try {
    const registry = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: loading registry…',
        cancellable: false,
      },
      () => fetchRegistry({ q: q.trim() || undefined })
    );
    items = registry.items;
  } catch (err) {
    const message = formatAxiosError(err, 'Registry unavailable');
    void vscode.window.showWarningMessage(
      `Creer: registry endpoint not available (${message}).`
    );
    return;
  }

  if (items.length === 0) {
    void vscode.window.showInformationMessage('Creer: no registry packs matched.');
    return;
  }

  type PickItem = vscode.QuickPickItem & { reg?: RegistryItem };
  const picks: PickItem[] = items.map((item) => ({
    label: item.name || item.id,
    description: [item.source, item.stack, item.version].filter(Boolean).join(' · '),
    detail: item.description,
    reg: item,
  }));

  const picked = await vscode.window.showQuickPick(picks, {
    placeHolder: 'Select a registry pack to install (or reinstall)',
    ignoreFocusOut: true,
    matchOnDescription: true,
    matchOnDetail: true,
  });

  if (!picked?.reg) {
    return;
  }

  const item = picked.reg;
  if (isBundledSource(item.source)) {
    const choice = await vscode.window.showInformationMessage(
      `“${item.name || item.id}” is bundled. Install a local copy via registry download anyway?`,
      'Install copy',
      'Cancel'
    );
    if (choice !== 'Install copy') {
      return;
    }
  }

  await installFromResolvedUrl(
    item.name || item.id,
    item.install_url || item.download_url,
    context
  );
}

/** Optional helper for hosts that expose delete UI later. */
export async function deletePackCommand(
  packId: string | undefined,
  context: vscode.ExtensionContext
): Promise<void> {
  let id = packId?.trim();
  if (!id) {
    id = (
      await vscode.window.showInputBox({
        prompt: 'Pack id to delete (installed packs only)',
        placeHolder: 'fastapi-crud',
        ignoreFocusOut: true,
      })
    )?.trim();
  }
  if (!id) {
    return;
  }

  const token = await resolveRegistryToken(context);
  try {
    await deletePack(id, { token });
    void vscode.window.showInformationMessage(`Creer: deleted pack “${id}”.`);
  } catch (err) {
    const message = formatAxiosError(err, 'Failed to delete pack');
    void vscode.window.showErrorMessage(`Creer: could not delete pack — ${message}`);
  }
}

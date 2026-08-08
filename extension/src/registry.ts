import * as vscode from 'vscode';
import {
  fetchFederatedRegistry,
  fetchPeerStatus,
  formatAxiosError,
  probePeer,
  type FederatedRegistryItem,
  type PeerStatus,
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

function peerUrlOf(status: PeerStatus): string {
  return (status.url || status.base_url || '').trim();
}

function formatPeerHealth(status: PeerStatus): string {
  const host = peerHostLabel(peerUrlOf(status)) || peerUrlOf(status) || 'peer';
  if (status.ok) {
    const latency =
      typeof status.latency_ms === 'number' ? ` ${Math.round(status.latency_ms)}ms` : '';
    return `$(check) ${host}${latency}`;
  }
  const err = status.error ? `: ${status.error}` : '';
  return `$(error) ${host}${err}`;
}

function parseRegistryPeersSetting(): string[] {
  const raw = vscode.workspace.getConfiguration('creer').get<string>('registryPeers') || '';
  return raw
    .split(',')
    .map((p) => p.trim().replace(/\/$/, ''))
    .filter(Boolean);
}

async function saveRegistryPeersSetting(peers: string[]): Promise<void> {
  const value = peers.join(', ');
  await vscode.workspace
    .getConfiguration('creer')
    .update('registryPeers', value, vscode.ConfigurationTarget.Global);
}

/**
 * Creer: Browse Federated Registry — GET /registry/federated, QuickPick, install.
 */
export async function browseFederatedRegistryCommand(): Promise<void> {
  const config = vscode.workspace.getConfiguration('creer');
  const showPeerStatus = config.get<boolean>('showPeerStatus') !== false;
  const registryPeers = config.get<string>('registryPeers') || '';

  const q = await vscode.window.showInputBox({
    prompt: 'Search federated registry (leave empty for all packs)',
    placeHolder: 'fastapi, express, peer host…',
    ignoreFocusOut: true,
  });
  if (q === undefined) {
    return;
  }

  let peerStatuses: PeerStatus[] | undefined;
  if (showPeerStatus) {
    try {
      const statusResp = await fetchPeerStatus();
      peerStatuses = statusResp.peers;
      const ok = peerStatuses.filter((p) => p.ok).length;
      const fail = peerStatuses.length - ok;
      if (peerStatuses.length > 0) {
        void vscode.window.showInformationMessage(
          `Creer peers: ${ok} ok, ${fail} fail` +
            (peerStatuses.some((p) => typeof p.latency_ms === 'number')
              ? ` · ${peerStatuses
                  .filter((p) => p.ok && typeof p.latency_ms === 'number')
                  .map((p) => `${peerHostLabel(peerUrlOf(p))}:${Math.round(p.latency_ms!)}ms`)
                  .slice(0, 3)
                  .join(', ')}`
              : '')
        );
      }
    } catch {
      // Soft-fail: peer status endpoints may be missing on older backends.
      peerStatuses = undefined;
    }
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
      () =>
        fetchFederatedRegistry({
          q: q.trim() || undefined,
          peers: registryPeers.trim() || undefined,
        })
    );
    items = federated.items;
    peerCount = federated.peers?.length ?? 0;
  } catch (err) {
    const message = formatAxiosError(err, 'Federated registry unavailable');
    void vscode.window.showWarningMessage(
      `Creer: federated registry endpoint not available (${message}). ` +
        'Try “Creer: Browse Pack Registry” or configure creer.registryPeers / CREER_REGISTRY_PEERS.'
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
  const picks: PickItem[] = [];

  if (showPeerStatus && peerStatuses && peerStatuses.length > 0) {
    picks.push({
      label: 'Peer health',
      kind: vscode.QuickPickItemKind.Separator,
    });
    for (const status of peerStatuses) {
      picks.push({
        label: formatPeerHealth(status),
        description: peerUrlOf(status),
        detail: status.ok
          ? typeof status.count === 'number'
            ? `${status.count} packs`
            : 'reachable'
          : status.error || 'unreachable',
      });
    }
    picks.push({
      label: 'Packs',
      kind: vscode.QuickPickItemKind.Separator,
    });
  }

  const localItems = items.filter((i) => !i.peer);
  const remoteItems = items.filter((i) => Boolean(i.peer));

  const toPick = (item: FederatedRegistryItem): PickItem => {
    const host = peerHostLabel(item.peer);
    const parts: string[] = [];
    if (host) {
      parts.push(host);
    } else {
      parts.push('local');
    }
    if (item.source) {
      parts.push(item.source);
    }
    if (item.stack) {
      parts.push(item.stack);
    }
    if (item.version) {
      parts.push(item.version);
    }
    return {
      label: host
        ? `$(cloud) ${item.name || item.id}`
        : `$(home) ${item.name || item.id}`,
      description: parts.join(' · '),
      detail: item.description,
      fed: item,
    };
  };

  for (const item of localItems) {
    picks.push(toPick(item));
  }
  for (const item of remoteItems) {
    picks.push(toPick(item));
  }

  const picked = await vscode.window.showQuickPick(picks, {
    placeHolder: 'Select a federated pack to install (peer host shown in description)',
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

/**
 * Creer: Manage Registry Peers — view/add/remove setting peers; probe via backend.
 */
export async function manageRegistryPeersCommand(): Promise<void> {
  const settingPeers = parseRegistryPeersSetting();

  let configured: string[] = [];
  let livePeers: PeerStatus[] = [];
  let peersEndpointOk = true;
  try {
    const status = await fetchPeerStatus();
    configured = status.configured ?? [];
    livePeers = status.peers ?? [];
  } catch {
    peersEndpointOk = false;
  }

  const lines: string[] = [];
  lines.push(
    settingPeers.length
      ? `Setting peers (${settingPeers.length}): ${settingPeers.join(', ')}`
      : 'Setting peers: (none)'
  );
  if (peersEndpointOk) {
    lines.push(
      configured.length
        ? `Backend configured (${configured.length}): ${configured.join(', ')}`
        : 'Backend configured: (none)'
    );
    if (livePeers.length > 0) {
      lines.push(
        'Status: ' +
          livePeers
            .map((p) => {
              const host = peerHostLabel(peerUrlOf(p)) || peerUrlOf(p);
              return p.ok
                ? `${host} ok${typeof p.latency_ms === 'number' ? ` ${Math.round(p.latency_ms)}ms` : ''}`
                : `${host} fail`;
            })
            .join('; ')
      );
    }
  } else {
    lines.push('Backend peer endpoints unavailable (soft-fail). You can still edit creer.registryPeers.');
  }

  type Action = 'add' | 'remove' | 'probe' | 'done';
  type ActionPick = vscode.QuickPickItem & { action?: Action };

  const actions: ActionPick[] = [
    {
      label: '$(info) Current peers',
      description: 'Summary',
      detail: lines.join('\n'),
    },
    {
      label: '$(add) Add peer',
      description: 'Probe URL then append to creer.registryPeers',
      action: 'add',
    },
    {
      label: '$(remove) Remove peer',
      description: 'Remove from creer.registryPeers',
      action: 'remove',
    },
    {
      label: '$(debug-alt) Probe all',
      description: peersEndpointOk
        ? 'POST /registry/peers/probe for each setting peer'
        : 'Requires backend probe endpoint',
      action: 'probe',
    },
  ];

  const picked = await vscode.window.showQuickPick(actions, {
    placeHolder: 'Creer: Manage Registry Peers',
    ignoreFocusOut: true,
    matchOnDescription: true,
    matchOnDetail: true,
  });

  if (!picked?.action) {
    if (picked && !picked.action) {
      void vscode.window.showInformationMessage(`Creer:\n${lines.join('\n')}`);
    }
    return;
  }

  if (picked.action === 'add') {
    const url = await vscode.window.showInputBox({
      prompt: 'Peer base URL (e.g. https://creer.example.com)',
      placeHolder: 'http://localhost:8001',
      ignoreFocusOut: true,
    });
    const trimmed = url?.trim().replace(/\/$/, '');
    if (!trimmed) {
      return;
    }

    let ok = true;
    let probeError: string | undefined;
    try {
      const result = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: `Creer: probing ${trimmed}…`,
          cancellable: false,
        },
        () => probePeer(trimmed)
      );
      ok = result.ok;
      probeError = result.error || undefined;
      if (ok) {
        const latency =
          typeof result.latency_ms === 'number'
            ? ` (${Math.round(result.latency_ms)}ms)`
            : '';
        void vscode.window.showInformationMessage(
          `Creer: peer reachable${latency}.`
        );
      }
    } catch (err) {
      // Soft-fail: if probe endpoint missing, still allow adding after confirm.
      const message = formatAxiosError(err, 'Probe failed');
      const choice = await vscode.window.showWarningMessage(
        `Creer: could not probe peer (${message}). Add anyway?`,
        'Add',
        'Cancel'
      );
      if (choice !== 'Add') {
        return;
      }
      ok = true;
    }

    if (!ok) {
      void vscode.window.showErrorMessage(
        `Creer: peer probe failed${probeError ? ` — ${probeError}` : ''}. Not added.`
      );
      return;
    }

    const next = parseRegistryPeersSetting();
    if (!next.includes(trimmed)) {
      next.push(trimmed);
      await saveRegistryPeersSetting(next);
    }
    void vscode.window.showInformationMessage(
      `Creer: added peer ${trimmed} to creer.registryPeers.`
    );
    return;
  }

  if (picked.action === 'remove') {
    const current = parseRegistryPeersSetting();
    if (current.length === 0) {
      void vscode.window.showInformationMessage('Creer: no setting peers to remove.');
      return;
    }
    const toRemove = await vscode.window.showQuickPick(
      current.map((url) => ({ label: url, description: peerHostLabel(url) })),
      {
        placeHolder: 'Select peer to remove from creer.registryPeers',
        ignoreFocusOut: true,
        canPickMany: true,
      }
    );
    if (!toRemove || toRemove.length === 0) {
      return;
    }
    const removeSet = new Set(toRemove.map((p) => p.label));
    const remaining = current.filter((u) => !removeSet.has(u));
    await saveRegistryPeersSetting(remaining);
    void vscode.window.showInformationMessage(
      `Creer: removed ${toRemove.length} peer(s) from creer.registryPeers.`
    );
    return;
  }

  if (picked.action === 'probe') {
    const current = parseRegistryPeersSetting();
    const targets =
      current.length > 0
        ? current
        : configured.length > 0
          ? configured
          : [];
    if (targets.length === 0) {
      void vscode.window.showInformationMessage(
        'Creer: no peers to probe. Add peers via this command or CREER_REGISTRY_PEERS.'
      );
      return;
    }

    const results: string[] = [];
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Creer: probing peers…',
        cancellable: false,
      },
      async (progress) => {
        for (let i = 0; i < targets.length; i++) {
          const url = targets[i];
          progress.report({
            message: `${i + 1}/${targets.length} ${peerHostLabel(url) || url}`,
          });
          try {
            const status = await probePeer(url);
            results.push(formatPeerHealth(status).replace(/\$\([^)]+\)\s*/g, ''));
          } catch (err) {
            results.push(
              `${peerHostLabel(url) || url}: ${formatAxiosError(err, 'probe failed')}`
            );
          }
        }
      }
    );

    void vscode.window.showInformationMessage(
      `Creer probe results:\n${results.join('\n')}`
    );
  }
}

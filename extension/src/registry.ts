import * as vscode from 'vscode';
import {
  fetchFederatedRegistry,
  fetchPeerStatus,
  fetchRegistryDiscover,
  formatAxiosError,
  isPeerPolicyBlockMessage,
  probePeer,
  type FederatedRegistryItem,
  type FederatedRegistryPeer,
  type PeerStatus,
  type RegistryDiscoverPeer,
} from './api';
import {
  installFromResolvedUrl,
  isBundledSource,
} from './marketplace';
import { resolveRegistryToken } from './secrets';

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
  if (status.blocked || isPeerPolicyBlockMessage(status.error) || isPeerPolicyBlockMessage(status.policy)) {
    const reason = status.error || status.policy || 'policy';
    return `$(circle-slash) ${host}: blocked (${reason})`;
  }
  if (status.ok) {
    const latency =
      typeof status.latency_ms === 'number' ? ` ${Math.round(status.latency_ms)}ms` : '';
    return `$(check) ${host}${latency}`;
  }
  const err = status.error ? `: ${status.error}` : '';
  return `$(error) ${host}${err}`;
}

/**
 * Heuristic: localhost / loopback / RFC1918 / link-local / .local hosts.
 * Used only for client-side warnPrivatePeers UX (backend enforces real policy).
 */
export function looksLikePrivateOrLocalhostHost(urlOrHost: string): boolean {
  let host = (urlOrHost || '').trim().toLowerCase();
  if (!host) {
    return false;
  }
  try {
    if (host.includes('://') || host.includes('/')) {
      host = new URL(host.includes('://') ? host : `http://${host}`).hostname.toLowerCase();
    }
  } catch {
    // fall through with raw host
  }
  // Strip IPv6 brackets
  if (host.startsWith('[') && host.endsWith(']')) {
    host = host.slice(1, -1);
  }

  if (
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host === '0.0.0.0' ||
    host === '::1' ||
    host === '::' ||
    host.endsWith('.localhost') ||
    host.endsWith('.local')
  ) {
    return true;
  }

  // IPv4 private / loopback / link-local
  if (/^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(host)) {
    return true;
  }
  if (/^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(host)) {
    return true;
  }
  if (/^192\.168\.\d{1,3}\.\d{1,3}$/.test(host)) {
    return true;
  }
  if (/^172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}$/.test(host)) {
    return true;
  }
  if (/^169\.254\.\d{1,3}\.\d{1,3}$/.test(host)) {
    return true;
  }

  // IPv6 ULA (fc00::/7) / link-local (fe80::/10) — simple prefix check
  const bare = host.replace(/%.*$/, '');
  if (/^(fc|fd)[0-9a-f]*:/i.test(bare) || /^fe[89ab][0-9a-f]*:/i.test(bare)) {
    return true;
  }

  return false;
}

async function confirmPrivatePeerIfNeeded(url: string): Promise<boolean> {
  const warn = vscode.workspace.getConfiguration('creer').get<boolean>('warnPrivatePeers') !== false;
  if (!warn || !looksLikePrivateOrLocalhostHost(url)) {
    return true;
  }
  const host = peerHostLabel(url) || url;
  const choice = await vscode.window.showWarningMessage(
    `Creer: “${host}” looks like localhost or a private IP. ` +
      'Backend peer policy may block it (SSRF / private IP). Add or probe anyway?',
    { modal: true },
    'Continue',
    'Cancel'
  );
  return choice === 'Continue';
}

function readFederationMaxHops(): number {
  const raw = vscode.workspace.getConfiguration('creer').get<number>('federationMaxHops');
  if (typeof raw !== 'number' || !Number.isFinite(raw)) {
    return 1;
  }
  return Math.max(0, Math.min(2, Math.trunc(raw)));
}

function isFederatedPeerBlocked(peer: FederatedRegistryPeer): boolean {
  return (
    peer.blocked === true ||
    isPeerPolicyBlockMessage(peer.error) ||
    isPeerPolicyBlockMessage(peer.policy)
  );
}

function summarizeFederatedPeerPolicy(peers: FederatedRegistryPeer[]): string | undefined {
  if (!peers.length) {
    return undefined;
  }
  const blocked = peers.filter(isFederatedPeerBlocked);
  const ok = peers.filter((p) => p.ok && !isFederatedPeerBlocked(p));
  const fail = peers.length - ok.length - blocked.length;
  const parts: string[] = [];
  parts.push(`${ok.length} peer${ok.length === 1 ? '' : 's'} ok`);
  if (blocked.length > 0) {
    parts.push(`${blocked.length} blocked by policy`);
  }
  if (fail > 0) {
    parts.push(`${fail} fail`);
  }
  return parts.join(', ');
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
export async function browseFederatedRegistryCommand(
  context: vscode.ExtensionContext
): Promise<void> {
  const config = vscode.workspace.getConfiguration('creer');
  const showPeerStatus = config.get<boolean>('showPeerStatus') !== false;
  const registryPeers = config.get<string>('registryPeers') || '';
  const federatedDiscover = config.get<boolean>('federatedDiscover') === true;
  const maxHops = readFederationMaxHops();

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
      const ok = peerStatuses.filter((p) => p.ok && !p.blocked).length;
      const blocked = peerStatuses.filter((p) => p.blocked).length;
      const fail = peerStatuses.length - ok - blocked;
      if (peerStatuses.length > 0) {
        const parts = [`${ok} ok`];
        if (blocked > 0) {
          parts.push(`${blocked} blocked by policy`);
        }
        if (fail > 0) {
          parts.push(`${fail} fail`);
        }
        void vscode.window.showInformationMessage(
          `Creer peers: ${parts.join(', ')}` +
            (peerStatuses.some((p) => p.ok && typeof p.latency_ms === 'number')
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
  let federatedPeers: FederatedRegistryPeer[] = [];
  try {
    const federated = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: federatedDiscover
          ? `Creer: loading federated registry (discover, max_hops=${maxHops})…`
          : 'Creer: loading federated registry…',
        cancellable: false,
      },
      () =>
        fetchFederatedRegistry({
          q: q.trim() || undefined,
          peers: registryPeers.trim() || undefined,
          discover: federatedDiscover || undefined,
          maxHops,
        })
    );
    items = federated.items;
    federatedPeers = federated.peers ?? [];
    peerCount = federatedPeers.length;
    const policySummary = summarizeFederatedPeerPolicy(federatedPeers);
    const hasPeerErrors = federatedPeers.some(
      (p) => !p.ok || Boolean(p.error) || isFederatedPeerBlocked(p)
    );
    if (policySummary && (federated.policy || hasPeerErrors)) {
      void vscode.window.showInformationMessage(`Creer federation: ${policySummary}`);
    }
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
        detail: status.blocked
          ? status.error || status.policy || 'blocked by policy'
          : status.ok
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
    item.install_url || item.download_url,
    context
  );
}

/**
 * Discover peers via GET /registry/discover, falling back to federated?discover=true.
 * Returns structured entries so policy-blocked suggestions can be shown grayed.
 */
async function discoverPeerDetails(): Promise<RegistryDiscoverPeer[]> {
  try {
    const discovered = await fetchRegistryDiscover();
    if (discovered.peerDetails.length > 0) {
      return discovered.peerDetails;
    }
  } catch {
    // Soft-fail: try federated discover instead.
  }

  const registryPeers = vscode.workspace
    .getConfiguration('creer')
    .get<string>('registryPeers') || '';
  const maxHops = readFederationMaxHops();
  const federated = await fetchFederatedRegistry({
    peers: registryPeers.trim() || undefined,
    discover: true,
    maxHops,
  });
  const fromPeers = (federated.peers ?? []).map((p) => {
    const url = (p.base_url || '').trim().replace(/\/$/, '');
    const blocked = isFederatedPeerBlocked(p);
    return {
      url,
      error: p.error ?? null,
      blocked,
      policy: p.policy ?? null,
    } satisfies RegistryDiscoverPeer;
  }).filter((p) => Boolean(p.url));

  const discoveredExtra = (federated.discovered_peers ?? [])
    .map((u) => (typeof u === 'string' ? u.trim().replace(/\/$/, '') : ''))
    .filter(Boolean)
    .map((url) => ({ url } satisfies RegistryDiscoverPeer));

  const seen = new Set<string>();
  const out: RegistryDiscoverPeer[] = [];
  for (const peer of [...fromPeers, ...discoveredExtra]) {
    if (seen.has(peer.url)) {
      continue;
    }
    seen.add(peer.url);
    out.push(peer);
  }
  return out;
}

/**
 * Creer: Manage Registry Peers — view/add/remove setting peers; probe via backend.
 */
export async function manageRegistryPeersCommand(
  context: vscode.ExtensionContext
): Promise<void> {
  const settingPeers = parseRegistryPeersSetting();
  const token = await resolveRegistryToken(context);

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
              if (p.blocked) {
                return `${host} blocked`;
              }
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

  type Action = 'add' | 'remove' | 'probe' | 'discover' | 'done';
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
    {
      label: '$(search) Discover peers',
      description: 'GET /registry/discover or federated?discover=true — offer to add (policy-aware)',
      action: 'discover',
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

    if (!(await confirmPrivatePeerIfNeeded(trimmed))) {
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
        () => probePeer(trimmed, { token })
      );
      ok = result.ok && !result.blocked;
      probeError = result.error || result.policy || undefined;
      if (result.blocked || isPeerPolicyBlockMessage(probeError)) {
        void vscode.window.showErrorMessage(
          `Creer: peer blocked by policy${probeError ? ` — ${probeError}` : ''}. Not added.`
        );
        return;
      }
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
      if (isPeerPolicyBlockMessage(message)) {
        void vscode.window.showErrorMessage(
          `Creer: peer blocked by policy — ${message}. Not added.`
        );
        return;
      }
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

    // Warn once if any target looks private
    const privateTargets = targets.filter(looksLikePrivateOrLocalhostHost);
    if (privateTargets.length > 0) {
      const warn =
        vscode.workspace.getConfiguration('creer').get<boolean>('warnPrivatePeers') !== false;
      if (warn) {
        const choice = await vscode.window.showWarningMessage(
          `Creer: ${privateTargets.length} peer(s) look like localhost/private IPs. Probe anyway?`,
          { modal: true },
          'Continue',
          'Cancel'
        );
        if (choice !== 'Continue') {
          return;
        }
      }
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
            const status = await probePeer(url, { token });
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
    return;
  }

  if (picked.action === 'discover') {
    let discovered: RegistryDiscoverPeer[] = [];
    try {
      discovered = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'Creer: discovering peers…',
          cancellable: false,
        },
        () => discoverPeerDetails()
      );
    } catch (err) {
      const message = formatAxiosError(err, 'Discovery unavailable');
      void vscode.window.showWarningMessage(
        `Creer: peer discovery not available (${message}).`
      );
      return;
    }

    if (discovered.length === 0) {
      void vscode.window.showInformationMessage('Creer: no peers discovered.');
      return;
    }

    const existing = new Set(parseRegistryPeersSetting());
    type DiscoverPick = vscode.QuickPickItem & {
      peerUrl?: string;
      blocked?: boolean;
    };

    const picks: DiscoverPick[] = discovered.map((peer) => {
      const blocked =
        peer.blocked === true ||
        isPeerPolicyBlockMessage(peer.error) ||
        isPeerPolicyBlockMessage(peer.policy);
      if (blocked) {
        return {
          label: `$(circle-slash) ${peer.url}`,
          description: 'blocked',
          detail: peer.error || peer.policy || 'blocked by policy',
          peerUrl: peer.url,
          blocked: true,
        };
      }
      return {
        label: peer.url,
        description: existing.has(peer.url)
          ? 'already in creer.registryPeers'
          : peerHostLabel(peer.url),
        peerUrl: peer.url,
        blocked: false,
        picked: !existing.has(peer.url),
      };
    });

    const selected = await vscode.window.showQuickPick(picks, {
      placeHolder:
        'Select discovered peers to add (blocked suggestions are shown grayed and skipped)',
      ignoreFocusOut: true,
      canPickMany: true,
    });
    if (!selected || selected.length === 0) {
      return;
    }

    const next = parseRegistryPeersSetting();
    let added = 0;
    let skippedBlocked = 0;
    for (const item of selected) {
      if (item.blocked) {
        skippedBlocked += 1;
        continue;
      }
      const url = (item.peerUrl || item.label).trim().replace(/\/$/, '');
      if (!url) {
        continue;
      }
      if (!(await confirmPrivatePeerIfNeeded(url))) {
        continue;
      }
      if (!next.includes(url)) {
        next.push(url);
        added += 1;
      }
    }
    if (added > 0) {
      await saveRegistryPeersSetting(next);
    }
    const suffix =
      skippedBlocked > 0
        ? ` Skipped ${skippedBlocked} blocked by policy.`
        : '';
    void vscode.window.showInformationMessage(
      added > 0
        ? `Creer: added ${added} discovered peer(s) to creer.registryPeers.${suffix}`
        : `Creer: selected peers were already in creer.registryPeers or blocked.${suffix}`
    );
  }
}

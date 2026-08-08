import { execFile } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

async function git(
  cwd: string,
  args: string[],
  env?: NodeJS.ProcessEnv
): Promise<void> {
  await execFileAsync('git', args, {
    cwd,
    env: env ?? process.env,
  });
}

export async function isGitRepo(projectPath: string): Promise<boolean> {
  return fs.existsSync(path.join(projectPath, '.git'));
}

export async function initGit(projectPath: string): Promise<void> {
  await git(projectPath, ['init']);
  await git(projectPath, ['add', '.']);
  try {
    await git(projectPath, ['commit', '-m', 'Initial commit']);
  } catch {
    // Commit can fail if git user.name/email are unset — still leave the repo initialized.
  }
}

export async function ensureGitRepo(projectPath: string): Promise<void> {
  if (!(await isGitRepo(projectPath))) {
    await initGit(projectPath);
  }
}

/**
 * Write a temporary GIT_ASKPASS helper that reads the token from CREER_GITHUB_TOKEN.
 * Never put the token in the remote URL or argv.
 */
function writeAskpassScript(): string {
  const isWin = process.platform === 'win32';
  const askpassPath = path.join(
    os.tmpdir(),
    `creer-askpass-${process.pid}-${Date.now()}${isWin ? '.cmd' : '.sh'}`
  );

  if (isWin) {
    // Git asks with prompts containing "Username" / "Password".
    const script = [
      '@echo off',
      'setlocal EnableExtensions',
      'echo(%* | findstr /I "Username" >nul',
      'if not errorlevel 1 (',
      '  echo x-access-token',
      ') else (',
      '  echo(%CREER_GITHUB_TOKEN%',
      ')',
      '',
    ].join('\r\n');
    fs.writeFileSync(askpassPath, script, { encoding: 'utf8' });
  } else {
    const script = [
      '#!/bin/sh',
      'case "$1" in',
      '  *[Uu]sername*) printf "%s" "x-access-token" ;;',
      '  *) printf "%s" "$CREER_GITHUB_TOKEN" ;;',
      'esac',
      '',
    ].join('\n');
    fs.writeFileSync(askpassPath, script, { encoding: 'utf8', mode: 0o700 });
  }

  return askpassPath;
}

export async function addRemoteAndPush(
  projectPath: string,
  cloneUrl: string,
  token?: string
): Promise<void> {
  try {
    await git(projectPath, ['remote', 'remove', 'origin']);
  } catch {
    // No existing origin — fine.
  }

  // Always store a clean clone URL (no embedded credentials).
  await git(projectPath, ['remote', 'add', 'origin', cloneUrl]);

  // Ensure we have a branch name for -u push.
  try {
    await git(projectPath, ['rev-parse', '--verify', 'HEAD']);
  } catch {
    await git(projectPath, ['add', '.']);
    try {
      await git(projectPath, ['commit', '-m', 'Initial commit']);
    } catch {
      throw new Error('Cannot push: repository has no commits (set git user.name/email).');
    }
  }

  let askpassPath: string | undefined;
  try {
    const pushEnv: NodeJS.ProcessEnv = { ...process.env };

    if (token) {
      askpassPath = writeAskpassScript();
      pushEnv.GIT_ASKPASS = askpassPath;
      pushEnv.GIT_TERMINAL_PROMPT = '0';
      pushEnv.CREER_GITHUB_TOKEN = token;
      // Prefer askpass over interactive prompts / GUI helpers for this child only.
      pushEnv.SSH_ASKPASS = askpassPath;
      pushEnv.SSH_ASKPASS_REQUIRE = 'never';
    }

    // Push to the clean clone URL — credentials come from askpass/env only.
    try {
      await git(projectPath, ['push', '-u', cloneUrl, 'HEAD'], pushEnv);
    } catch {
      await git(projectPath, ['push', '-u', cloneUrl, 'HEAD:main'], pushEnv);
    }
  } finally {
    if (askpassPath) {
      try {
        fs.unlinkSync(askpassPath);
      } catch {
        // Best-effort cleanup.
      }
    }
  }

  // Keep origin pointing at the clean clone URL.
  await git(projectPath, ['remote', 'set-url', 'origin', cloneUrl]);
}

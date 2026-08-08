import { execFile } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

async function git(cwd: string, args: string[]): Promise<void> {
  await execFileAsync('git', args, { cwd });
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

export async function addRemoteAndPush(
  projectPath: string,
  cloneUrl: string,
  token?: string
): Promise<void> {
  // Prefer authenticated HTTPS URL when a token is available so push works non-interactively.
  // Args are passed via execFile (no shell) so tokens/URLs cannot inject commands.
  let pushUrl = cloneUrl;
  if (token && cloneUrl.startsWith('https://')) {
    pushUrl = cloneUrl.replace(
      'https://',
      `https://x-access-token:${encodeURIComponent(token)}@`
    );
  }

  try {
    await git(projectPath, ['remote', 'remove', 'origin']);
  } catch {
    // No existing origin — fine.
  }

  await git(projectPath, ['remote', 'add', 'origin', cloneUrl]);

  // Ensure we have a branch name for -u push.
  try {
    await git(projectPath, ['rev-parse', '--verify', 'HEAD']);
  } catch {
    // No commits yet — stage and commit if possible.
    await git(projectPath, ['add', '.']);
    try {
      await git(projectPath, ['commit', '-m', 'Initial commit']);
    } catch {
      throw new Error('Cannot push: repository has no commits (set git user.name/email).');
    }
  }

  // Push using authenticated URL without rewriting the stored remote (keep clone_url clean).
  try {
    await git(projectPath, ['push', '-u', pushUrl, 'HEAD']);
  } catch {
    // Fallback: try main explicitly
    await git(projectPath, ['push', '-u', pushUrl, 'HEAD:main']);
  }

  // Keep origin pointing at the clean clone URL (without embedded token).
  await git(projectPath, ['remote', 'set-url', 'origin', cloneUrl]);
}

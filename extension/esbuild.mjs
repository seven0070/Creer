#!/usr/bin/env node
/**
 * Bundle the Creer VS Code extension into a single CommonJS file.
 * vscode is external (provided by the host).
 */
import * as esbuild from 'esbuild';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const watch = process.argv.includes('--watch');

const options = {
  entryPoints: [path.join(__dirname, 'src/extension.ts')],
  bundle: true,
  outfile: path.join(__dirname, 'dist/extension.js'),
  external: ['vscode'],
  format: 'cjs',
  platform: 'node',
  target: 'node18',
  sourcemap: true,
  minify: process.env.CREER_MINIFY === '1',
  logLevel: 'info',
};

async function main() {
  if (watch) {
    const ctx = await esbuild.context(options);
    await ctx.watch();
    console.log('watching…');
  } else {
    await esbuild.build(options);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

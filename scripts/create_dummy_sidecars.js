import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

// Get host target triple
let triple = '';
try {
  const output = execSync('rustc -vV', { encoding: 'utf8' });
  const match = output.match(/^host:\s+([^\s]+)/m);
  if (match) {
    triple = match[1].trim();
  }
} catch (e) {
  console.warn('Could not determine rustc host target triple, defaulting to x86_64-unknown-linux-gnu');
  triple = 'x86_64-unknown-linux-gnu';
}

const binariesDir = path.resolve('src-tauri', 'binaries');
if (!fs.existsSync(binariesDir)) {
  fs.mkdirSync(binariesDir, { recursive: true });
}

const sidecars = ['hunter', 'rag', 'gap-engine', 'worker'];
const isWindows = process.platform === 'win32' || triple.includes('windows');

sidecars.forEach((name) => {
  const binaryName = isWindows ? `${name}-${triple}.exe` : `${name}-${triple}`;
  const binaryPath = path.join(binariesDir, binaryName);

  if (!fs.existsSync(binaryPath)) {
    console.log(`Creating dummy sidecar for CI/Build verification: ${binaryName}`);
    if (isWindows) {
      fs.writeFileSync(binaryPath, 'Dummy Windows Sidecar Bin');
    } else {
      fs.writeFileSync(binaryPath, '#!/bin/sh\necho "Dummy sidecar"\nexit 0\n');
      fs.chmodSync(binaryPath, 0o755);
    }
  }
});

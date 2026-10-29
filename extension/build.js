// BlockTrace Verifier - Extension Packager
// Creates blocktrace-verifier.zip with manifest.json at the root of the archive.
// Validates that API_BASE_URL is HTTPS (localhost permitted only for development).

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const EXT_DIR = path.resolve(__dirname);
const CONFIG_FILE = path.join(EXT_DIR, 'config.json');
const MANIFEST_FILE = path.join(EXT_DIR, 'manifest.json');
const ZIP_NAME = 'blocktrace-verifier.zip';
const ZIP_OUTPUT = path.join(EXT_DIR, ZIP_NAME);

console.log('=== Building BlockTrace Verifier Extension Package ===');

// 1. Verify and read config.json
if (!fs.existsSync(CONFIG_FILE)) {
  console.error('ERROR: config.json not found at', CONFIG_FILE);
  process.exit(1);
}

const config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
const apiUrl = config.API_BASE_URL || '';

console.log(`Config API_BASE_URL: ${apiUrl}`);

// Validate HTTPS constraint
const isLocalhost = apiUrl.includes('localhost') || apiUrl.includes('127.0.0.1');
if (!isLocalhost && !apiUrl.startsWith('https://')) {
  console.error(`ERROR: API_BASE_URL must use HTTPS protocol. Found: "${apiUrl}"`);
  console.error('(Localhost is allowed only for development). Build aborted.');
  process.exit(1);
}

// 2. Validate manifest.json exists
if (!fs.existsSync(MANIFEST_FILE)) {
  console.error('ERROR: manifest.json not found at', MANIFEST_FILE);
  process.exit(1);
}

// 3. Remove old zip if it exists
if (fs.existsSync(ZIP_OUTPUT)) {
  fs.unlinkSync(ZIP_OUTPUT);
  console.log(`Removed existing ${ZIP_NAME}`);
}

// 4. Files to include in the package
const filesToInclude = [
  'manifest.json',
  'config.json',
  'background.js',
  'popup.html',
  'popup.css',
  'popup.js',
  'options.html',
  'options.js',
  'PRIVACY.md',
  'README.md',
  path.join('icons', 'icon-16.png'),
  path.join('icons', 'icon-32.png'),
  path.join('icons', 'icon-48.png'),
  path.join('icons', 'icon-128.png'),
];

// Check all files exist
for (const file of filesToInclude) {
  const fullPath = path.join(EXT_DIR, file);
  if (!fs.existsSync(fullPath)) {
    console.error(`ERROR: Required package file missing: ${file}`);
    process.exit(1);
  }
}

// 5. Create ZIP using PowerShell script file to avoid escaping issues
console.log('Creating ZIP archive...');

const tempDistDir = path.join(EXT_DIR, '.temp_dist');
if (fs.existsSync(tempDistDir)) {
  fs.rmSync(tempDistDir, { recursive: true, force: true });
}
fs.mkdirSync(tempDistDir, { recursive: true });
fs.mkdirSync(path.join(tempDistDir, 'icons'), { recursive: true });

for (const file of filesToInclude) {
  const src = path.join(EXT_DIR, file);
  const dest = path.join(tempDistDir, file);
  fs.copyFileSync(src, dest);
}

const psScriptPath = path.join(EXT_DIR, '.zip_helper.ps1');
const psScriptContent = `
$src = '${tempDistDir.replace(/'/g, "''")}'
$dest = '${ZIP_OUTPUT.replace(/'/g, "''")}'
Compress-Archive -Path "$src\\*" -DestinationPath "$dest" -Force
`;
fs.writeFileSync(psScriptPath, psScriptContent, 'utf8');

try {
  execSync(`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "${psScriptPath}"`, { stdio: 'inherit' });
} finally {
  if (fs.existsSync(psScriptPath)) fs.unlinkSync(psScriptPath);
  if (fs.existsSync(tempDistDir)) fs.rmSync(tempDistDir, { recursive: true, force: true });
}

if (!fs.existsSync(ZIP_OUTPUT)) {
  console.error('ERROR: Failed to create ZIP archive.');
  process.exit(1);
}

const stats = fs.statSync(ZIP_OUTPUT);
console.log('\nPackage build SUCCESSFUL!');
console.log(`ZIP Path: ${ZIP_OUTPUT}`);
console.log(`ZIP Size: ${(stats.size / 1024).toFixed(1)} KB`);
console.log('Ready for Chrome Web Store & Microsoft Edge Add-ons upload.');

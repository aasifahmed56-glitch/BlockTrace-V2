// BlockTrace Verifier - Options Logic
const browserApi = (typeof browser !== 'undefined') ? browser : chrome;

const apiBaseUrlInput = document.getElementById('api-base-url');
const webUrlInput = document.getElementById('web-url');
const extVersionEl = document.getElementById('ext-version');
const btnTest = document.getElementById('btn-test-connection');
const statusDiv = document.getElementById('connection-status');

let currentApiUrl = 'https://blocktrace-v2.onrender.com';

async function init() {
  // Read version from manifest
  const manifest = browserApi.runtime.getManifest();
  extVersionEl.textContent = manifest.version || '1.0.0';

  // Read config from config.json or storage
  try {
    const resp = await fetch(browserApi.runtime.getURL('config.json'));
    const config = await resp.json();
    currentApiUrl = config.API_BASE_URL || currentApiUrl;
    apiBaseUrlInput.value = currentApiUrl;
    webUrlInput.value = config.WEB_URL || 'https://blocktrace-v2.vercel.app';
  } catch (err) {
    apiBaseUrlInput.value = currentApiUrl;
    webUrlInput.value = 'https://blocktrace-v2.vercel.app';
  }
}

btnTest.addEventListener('click', async () => {
  btnTest.disabled = true;
  btnTest.textContent = 'Testing...';
  statusDiv.style.display = 'block';
  statusDiv.className = 'status-msg';
  statusDiv.textContent = 'Connecting to ' + currentApiUrl + '/health...';

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    const resp = await fetch(`${currentApiUrl}/health`, {
      signal: controller.signal
    });
    clearTimeout(timeout);

    if (resp.ok) {
      const data = await resp.json();
      statusDiv.className = 'status-msg status-ok';
      statusDiv.textContent = `Connection successful! Status: ${data.status}, Public Mode: ${data.public_mode}`;
    } else {
      statusDiv.className = 'status-msg status-err';
      statusDiv.textContent = `Server responded with HTTP ${resp.status}`;
    }
  } catch (err) {
    statusDiv.className = 'status-msg status-err';
    statusDiv.textContent = `Connection failed: ${err.message || 'Network error'}. Note: If Render is asleep, this may take up to a minute to wake.`;
  } finally {
    btnTest.disabled = false;
    btnTest.textContent = 'Test Connection (/health)';
  }
});

document.addEventListener('DOMContentLoaded', init);


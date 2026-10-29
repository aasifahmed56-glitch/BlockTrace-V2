// BlockTrace Verifier - Popup Logic
// Manifest V3 compliant: no remote code, no inline scripts, no eval.

const browserApi = (typeof browser !== 'undefined') ? browser : chrome;

// Default configuration fallback (mirrors config.json)
let CONFIG = {
  API_BASE_URL: 'https://blocktrace-v2.onrender.com',
  WEB_URL: 'https://blocktrace-v2.vercel.app'
};

// UI Elements
const wakeupBanner = document.getElementById('wakeup-banner');
const tabBtnVerify = document.getElementById('tab-btn-verify');
const tabBtnAddress = document.getElementById('tab-btn-address');
const panelVerify = document.getElementById('panel-verify');
const panelAddress = document.getElementById('panel-address');

// Verify form elements
const verifyForm = document.getElementById('verify-form');
const pdfFileInput = document.getElementById('pdf-file');
const fileDropzone = document.getElementById('file-dropzone');
const dropzoneText = document.getElementById('dropzone-text');
const fileSelectedInfo = document.getElementById('file-selected-info');
const selectedFileName = document.getElementById('selected-file-name');
const selectedFileSize = document.getElementById('selected-file-size');
const fileError = document.getElementById('file-error');
const investigationHashInput = document.getElementById('investigation-hash');
const hashError = document.getElementById('hash-error');
const btnVerify = document.getElementById('btn-verify');
const verifyResult = document.getElementById('verify-result');
const resultBadge = document.getElementById('result-badge');
const resultMessage = document.getElementById('result-message');
const resultMeta = document.getElementById('result-meta');
const resultLinks = document.getElementById('result-links');

// Address form elements
const addressForm = document.getElementById('address-form');
const walletAddressInput = document.getElementById('wallet-address');
const addressError = document.getElementById('address-error');
const btnCheckAddress = document.getElementById('btn-check-address');
const addressResult = document.getElementById('address-result');
const addressBadge = document.getElementById('address-badge');
const addressDetails = document.getElementById('address-details');
const linkOpenBlocktrace = document.getElementById('link-open-blocktrace');

// Client-side file validation constants
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB
const PDF_MAGIC = '%PDF';

// ==================== Validation Helpers ====================

function validateEthereumAddress(address) {
  if (!address || typeof address !== 'string') return false;
  return /^0x[a-fA-F0-9]{40}$/.test(address.trim());
}

function normalizeHash(hash) {
  if (!hash) return '';
  let cleaned = hash.trim().toLowerCase();
  if (cleaned.startsWith('0x')) {
    cleaned = cleaned.slice(2);
  }
  return cleaned;
}

function validateInvestigationHash(hash) {
  if (!hash) return true; // optional in form if present in PDF
  const cleaned = normalizeHash(hash);
  return /^[a-f0-9]{64}$/.test(cleaned);
}

async function validatePdfFile(file) {
  if (!file) {
    return { valid: false, error: 'A PDF file is required.' };
  }
  if (file.size > MAX_FILE_SIZE) {
    return { valid: false, error: 'File size exceeds 25 MB limit.' };
  }

  // Read first 10 bytes to verify %PDF magic header
  try {
    const slice = file.slice(0, 10);
    const buffer = await slice.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    const header = String.fromCharCode(...bytes.slice(0, 4));
    if (header !== PDF_MAGIC) {
      return { valid: false, error: 'File does not appear to be a valid PDF (missing %PDF header).' };
    }
  } catch (err) {
    return { valid: false, error: 'Could not read file header.' };
  }

  return { valid: true };
}

// ==================== Tab Switching ====================

function switchTab(tabName) {
  if (tabName === 'address') {
    tabBtnAddress.classList.add('active');
    tabBtnAddress.setAttribute('aria-selected', 'true');
    tabBtnVerify.classList.remove('active');
    tabBtnVerify.setAttribute('aria-selected', 'false');

    panelAddress.classList.remove('hidden');
    panelVerify.classList.add('hidden');
    walletAddressInput.focus();
  } else {
    tabBtnVerify.classList.add('active');
    tabBtnVerify.setAttribute('aria-selected', 'true');
    tabBtnAddress.classList.remove('active');
    tabBtnAddress.setAttribute('aria-selected', 'false');

    panelVerify.classList.remove('hidden');
    panelAddress.classList.add('hidden');
  }
}

tabBtnVerify.addEventListener('click', () => switchTab('verify'));
tabBtnAddress.addEventListener('click', () => switchTab('address'));

// ==================== Dropzone & File Selection ====================

function handleFileChosen(file) {
  fileError.classList.add('hidden');
  fileError.textContent = '';

  if (!file) {
    dropzoneText.classList.remove('hidden');
    fileSelectedInfo.classList.add('hidden');
    return;
  }

  selectedFileName.textContent = file.name;
  selectedFileSize.textContent = `(${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
  dropzoneText.classList.add('hidden');
  fileSelectedInfo.classList.remove('hidden');
}

pdfFileInput.addEventListener('change', (e) => {
  const file = e.target.files && e.target.files[0];
  handleFileChosen(file);
});

// Drag and drop handling
['dragenter', 'dragover'].forEach((eventName) => {
  fileDropzone.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
    fileDropzone.classList.add('dragover');
  });
});

['dragleave', 'drop'].forEach((eventName) => {
  fileDropzone.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
    fileDropzone.classList.remove('dragover');
  });
});

fileDropzone.addEventListener('drop', (e) => {
  const dt = e.dataTransfer;
  const file = dt.files && dt.files[0];
  if (file) {
    pdfFileInput.files = dt.files;
    handleFileChosen(file);
  }
});

// ==================== Wakeup & Network Fetch ====================

// Fetch with Render wake-up handling:
// - 90s timeout
// - Shows wake-up banner if taking longer than 5 seconds
// - Retries once on network failure
async function fetchWithWakeup(url, options = {}) {
  let wakeupTimer = null;

  const runAttempt = async () => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 90000); // 90-second timeout

    wakeupTimer = setTimeout(() => {
      wakeupBanner.classList.remove('hidden');
    }, 5000);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });
      return response;
    } finally {
      clearTimeout(timeoutId);
      clearTimeout(wakeupTimer);
      wakeupBanner.classList.add('hidden');
    }
  };

  try {
    return await runAttempt();
  } catch (err) {
    // If network error / timeout, retry once
    console.warn('Initial request failed, retrying once for server wakeup...', err);
    try {
      return await runAttempt();
    } catch (retryErr) {
      wakeupBanner.classList.add('hidden');
      throw retryErr;
    }
  }
}

// Background wake-up call on popup open
async function wakeServerInBackground() {
  try {
    await fetch(`${CONFIG.API_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      cache: 'no-store'
    });
  } catch (err) {
    // Silent fail; actual user action will show UI if sleeping
  }
}

// ==================== Verify Report ====================

function setVerifyLoading(isLoading) {
  btnVerify.disabled = isLoading;
  const btnText = btnVerify.querySelector('.btn-text');
  const btnSpinner = btnVerify.querySelector('.btn-spinner');
  if (isLoading) {
    btnText.textContent = 'Verifying with Sepolia...';
    btnSpinner.classList.remove('hidden');
  } else {
    btnText.textContent = 'Verify Report On-Chain';
    btnSpinner.classList.add('hidden');
  }
}

function renderMetaRow(label, value, allowCopy = false) {
  if (!value) return '';
  const copyHtml = allowCopy
    ? `<button type="button" class="copy-btn" data-copy="${escapeHtml(value)}">Copy</button>`
    : '';
  return `
    <div class="meta-row">
      <dt class="meta-label">${escapeHtml(label)}</dt>
      <div class="meta-value-container">
        <dd class="meta-value">${escapeHtml(value)}</dd>
        ${copyHtml}
      </div>
    </div>
  `;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

verifyForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  fileError.classList.add('hidden');
  hashError.classList.add('hidden');
  verifyResult.classList.add('hidden');

  const file = pdfFileInput.files && pdfFileInput.files[0];
  const fileCheck = await validatePdfFile(file);
  if (!fileCheck.valid) {
    fileError.textContent = fileCheck.error;
    fileError.classList.remove('hidden');
    return;
  }

  const rawHash = investigationHashInput.value.trim();
  if (rawHash && !validateInvestigationHash(rawHash)) {
    hashError.textContent = 'Must be 64 hexadecimal characters (optional 0x prefix).';
    hashError.classList.remove('hidden');
    return;
  }
  const cleanHash = rawHash ? normalizeHash(rawHash) : '';

  setVerifyLoading(true);

  try {
    const formData = new FormData();
    formData.append('file', file);
    if (cleanHash) {
      formData.append('investigation_hash', cleanHash);
    }

    const response = await fetchWithWakeup(`${CONFIG.API_BASE_URL}/report/verify`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `Server returned error (${response.status})`);
    }

    displayVerifyResult(data);
  } catch (err) {
    displayVerifyError(err);
  } finally {
    setVerifyLoading(false);
  }
});

function displayVerifyResult(data) {
  verifyResult.classList.remove('hidden');
  resultBadge.className = 'badge';

  const status = (data.status || 'unavailable').toLowerCase();

  let message = '';
  let metaRows = '';
  let linkRows = '';

  if (status === 'authentic') {
    resultBadge.classList.add('badge-authentic');
    resultBadge.textContent = 'AUTHENTIC';
    message = 'Cryptographic integrity verified. The uploaded PDF matches the on-chain IPFS artifact recorded on Sepolia.';
  } else if (status === 'tampered') {
    resultBadge.classList.add('badge-tampered');
    resultBadge.textContent = 'TAMPERED';
    message = 'Verification failure: The uploaded file has been modified or does not match the on-chain recorded artifact.';
  } else if (status === 'not_found') {
    resultBadge.classList.add('badge-notfound');
    resultBadge.textContent = 'NOT FOUND';
    message = data.message || 'No on-chain record found for this investigation hash on Sepolia.';
  } else {
    resultBadge.classList.add('badge-unavailable');
    resultBadge.textContent = 'UNAVAILABLE';
    message = data.message || 'Verification could not be completed at this time.';
  }

  resultMessage.textContent = message;

  // Metadata rows
  if (data.investigation_hash) {
    metaRows += renderMetaRow('Investigation Hash', data.investigation_hash, true);
  }
  if (data.submitter) {
    metaRows += renderMetaRow('Anchored By (Submitter)', data.submitter, true);
  }
  if (data.timestamp_utc) {
    metaRows += renderMetaRow('Recorded Timestamp (UTC)', data.timestamp_utc, false);
  }
  if (data.uploaded_sha256) {
    metaRows += renderMetaRow('Uploaded PDF SHA-256', data.uploaded_sha256, true);
  }
  if (data.stored_sha256) {
    metaRows += renderMetaRow('On-Chain IPFS SHA-256', data.stored_sha256, true);
  }
  if (data.ipfs_cid) {
    metaRows += renderMetaRow('IPFS CID', data.ipfs_cid, true);
  }

  resultMeta.innerHTML = metaRows;

  // Action links
  if (data.explorer_url) {
    linkRows += `
      <a href="${escapeHtml(data.explorer_url)}" target="_blank" rel="noopener noreferrer" class="ext-link">
        View On Sepolia Explorer &rarr;
      </a>
    `;
  }
  if (data.gateway_url) {
    linkRows += `
      <a href="${escapeHtml(data.gateway_url)}" target="_blank" rel="noopener noreferrer" class="ext-link">
        View Archived PDF On IPFS &rarr;
      </a>
    `;
  }

  resultLinks.innerHTML = linkRows;

  // Attach copy listeners
  resultMeta.querySelectorAll('.copy-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const textToCopy = btn.getAttribute('data-copy');
      navigator.clipboard.writeText(textToCopy).then(() => {
        const orig = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = orig; }, 1500);
      });
    });
  });
}

function displayVerifyError(err) {
  verifyResult.classList.remove('hidden');
  resultBadge.className = 'badge badge-unavailable';
  resultBadge.textContent = 'ERROR';
  resultMessage.textContent = err.message || 'Failed to reach verification service.';
  resultMeta.innerHTML = '';
  resultLinks.innerHTML = '';
}

// ==================== Check Address ====================

function setAddressLoading(isLoading) {
  btnCheckAddress.disabled = isLoading;
  const btnText = btnCheckAddress.querySelector('.btn-text');
  const btnSpinner = btnCheckAddress.querySelector('.btn-spinner');
  if (isLoading) {
    btnText.textContent = 'Checking list...';
    btnSpinner.classList.remove('hidden');
  } else {
    btnText.textContent = 'Check Sanctions List';
    btnSpinner.classList.add('hidden');
  }
}

async function performAddressCheck(address) {
  addressError.classList.add('hidden');
  addressResult.classList.add('hidden');

  const cleanAddr = (address || '').trim();
  if (!validateEthereumAddress(cleanAddr)) {
    addressError.textContent = 'Invalid Ethereum address. Must be 0x followed by 40 hex characters.';
    addressError.classList.remove('hidden');
    return;
  }

  setAddressLoading(true);

  try {
    const url = `${CONFIG.API_BASE_URL}/sanctions/check?address=${encodeURIComponent(cleanAddr)}`;
    const response = await fetchWithWakeup(url);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `Server error (${response.status})`);
    }

    displayAddressResult(data);
  } catch (err) {
    addressResult.classList.remove('hidden');
    addressBadge.className = 'badge badge-unavailable';
    addressBadge.textContent = 'ERROR';
    addressDetails.innerHTML = `<p class="address-note">${escapeHtml(err.message || 'Check failed.')}</p>`;
  } finally {
    setAddressLoading(false);
  }
}

function displayAddressResult(data) {
  addressResult.classList.remove('hidden');
  addressBadge.className = 'badge';

  if (data.sanctioned) {
    addressBadge.classList.add('badge-tampered');
    addressBadge.textContent = 'SANCTIONED';
    addressDetails.innerHTML = `
      <div class="address-label-badge">${escapeHtml(data.label || 'Identified Sanctioned Entity')}</div>
      <p class="meta-value">${escapeHtml(data.address)}</p>
      <p class="address-note">Source: ${escapeHtml(data.source || 'built-in OFAC list')}</p>
      <p class="address-note">${escapeHtml(data.note || 'Indicator only; list may be outdated.')}</p>
    `;
  } else {
    addressBadge.classList.add('badge-authentic');
    addressBadge.textContent = 'NOT ON LIST';
    addressDetails.innerHTML = `
      <p class="meta-value">${escapeHtml(data.address)}</p>
      <p class="address-note">${escapeHtml(data.note || 'Indicator only; list may be outdated. Verify with official OFAC sources.')}</p>
    `;
  }

  linkOpenBlocktrace.href = CONFIG.WEB_URL;
}

addressForm.addEventListener('submit', (e) => {
  e.preventDefault();
  performAddressCheck(walletAddressInput.value);
});

// ==================== Initialize Popup ====================

async function init() {
  // Load config from storage or config.json
  try {
    const stored = await browserApi.storage.local.get(['API_BASE_URL', 'WEB_URL']);
    if (stored.API_BASE_URL) CONFIG.API_BASE_URL = stored.API_BASE_URL;
    if (stored.WEB_URL) CONFIG.WEB_URL = stored.WEB_URL;
  } catch (err) {
    // Use fallback CONFIG
  }

  // Wake Render in background
  wakeServerInBackground();

  // Read URL query parameters (from context menu open)
  const urlParams = new URLSearchParams(window.location.search);
  const targetTab = urlParams.get('tab');
  const targetAddress = urlParams.get('address');
  const rawText = urlParams.get('raw');
  const isInvalid = urlParams.get('invalid');

  if (targetTab === 'address') {
    switchTab('address');
    if (targetAddress) {
      walletAddressInput.value = targetAddress;
      performAddressCheck(targetAddress);
    } else if (isInvalid && rawText) {
      walletAddressInput.value = rawText;
      addressError.textContent = `Selected text "${rawText}" is not a valid 42-character Ethereum address.`;
      addressError.classList.remove('hidden');
    }
  }
}

document.addEventListener('DOMContentLoaded', init);


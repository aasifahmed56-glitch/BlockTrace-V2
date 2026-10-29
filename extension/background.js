// BlockTrace Verifier - Service Worker (Manifest V3)
// Cross-browser compatibility shim (Firefox / Chrome / Edge)
const browserApi = (typeof browser !== 'undefined') ? browser : chrome;

const CONTEXT_MENU_ID = 'blocktrace-check-address';

// Setup context menu on extension install/update
browserApi.runtime.onInstalled.addListener(() => {
  browserApi.contextMenus.create({
    id: CONTEXT_MENU_ID,
    title: 'Check address with BlockTrace',
    contexts: ['selection']
  });
});

// Helper: check if a text contains or looks like an Ethereum address
function extractEthereumAddress(text) {
  if (!text) return null;
  const cleaned = text.trim();
  const match = cleaned.match(/\b(0x[a-fA-F0-9]{40})\b/);
  return match ? match[1] : null;
}

// Handle context menu click
browserApi.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === CONTEXT_MENU_ID) {
    const selectedText = (info.selectionText || '').trim();
    const address = extractEthereumAddress(selectedText);
    
    // Construct target URL for the popup
    const popupUrl = address
      ? browserApi.runtime.getURL(`popup.html?tab=address&address=${encodeURIComponent(address)}`)
      : browserApi.runtime.getURL(`popup.html?tab=address&raw=${encodeURIComponent(selectedText.slice(0, 50))}&invalid=1`);

    // Open a small popup window (380x540)
    browserApi.windows.create({
      url: popupUrl,
      type: 'popup',
      width: 396,
      height: 560
    });
  }
});

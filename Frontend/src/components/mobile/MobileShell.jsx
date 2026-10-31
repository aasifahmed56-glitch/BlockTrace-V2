import React, { useEffect, useRef, useState } from 'react';
import { useInvestigation } from '../../context/InvestigationContext';
import { ConfirmModal } from '../ConfirmModal';
import { Sheet } from './Sheet';
import { copyText } from '../../utils/useCompact';

const EXPLORERS = {
  Ethereum: { name: 'Etherscan', base: 'https://etherscan.io' },
  'BNB Smart Chain': { name: 'BscScan', base: 'https://bscscan.com' },
  Polygon: { name: 'PolygonScan', base: 'https://polygonscan.com' },
};
export const explorerFor = (chain) => EXPLORERS[chain] || EXPLORERS.Ethereum;

export const MOBILE_NAV = [
  { id: 'investigate', label: 'Investigate', icon: 'search_insights' },
  { id: 'findings', label: 'Findings', icon: 'rule' },
  { id: 'certificates', label: 'Certs', icon: 'verified_user' },
  { id: 'cases-reports', label: 'Cases', icon: 'folder_shared' },
  { id: 'verify-report', label: 'Verify', icon: 'fact_check' },
];

const MenuRow = ({ icon, label, hint, onClick, disabled, danger, children }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    className={`w-full min-h-[52px] flex items-center gap-3 px-2 py-2 rounded-lg text-left hover:bg-surface-container disabled:opacity-50 ${
      danger ? 'text-error' : 'text-on-surface'
    }`}
  >
    <span className="material-symbols-outlined text-[22px] shrink-0">{icon}</span>
    <span className="flex-1 min-w-0">
      <span className="block text-[15px] font-medium">{label}</span>
      {hint && <span className="block text-xs text-on-surface-variant leading-snug">{hint}</span>}
    </span>
    {children}
  </button>
);

const Switch = ({ on }) => (
  <span
    aria-hidden="true"
    className={`w-11 h-6 rounded-full shrink-0 relative transition-colors ${on ? 'bg-primary' : 'bg-outline-variant'}`}
  >
    <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-[left] ${on ? 'left-[22px]' : 'left-0.5'}`} />
  </span>
);

// Phone/tablet top bar: logo, compact counter, sanctions badge and one overflow menu.
export const MobileTopBar = () => {
  const {
    setActiveTab,
    summary,
    sanctions,
    edges,
    showZeroValue,
    setShowZeroValue,
    includeInternal,
    setIncludeInternal,
    exportGraph,
    clearSession,
    refreshGraphAndSummary,
    refreshFindings,
    isLoadingGraph,
    actionLoading,
    serverWaking,
  } = useInvestigation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const sync = async () => {
    setMenuOpen(false);
    await refreshGraphAndSummary();
    await refreshFindings();
  };

  return (
    <>
      <header
        className={`lg:hidden fixed ${serverWaking ? 'top-[36px]' : 'top-0'} inset-x-0 z-40 bg-surface/95 backdrop-blur-md border-b border-outline-variant`}
        style={{ paddingTop: 'env(safe-area-inset-top)' }}
      >
        <div className="h-14 flex items-center gap-2 pl-[max(8px,env(safe-area-inset-left))] pr-[max(8px,env(safe-area-inset-right))]">
          <button
            type="button"
            onClick={() => setActiveTab('landing')}
            className="w-11 h-11 flex items-center justify-center shrink-0 rounded-lg"
            aria-label="BlockTrace: product overview"
          >
            <span className="w-9 h-9 rounded-lg bg-primary-container flex items-center justify-center text-white shadow-md">
              <span className="material-symbols-outlined text-[22px]">hub</span>
            </span>
          </button>

          <div
            className="flex items-center gap-1.5 h-8 px-2.5 rounded-full bg-surface-container border border-outline-variant/60 min-w-0"
            aria-label={`${summary.wallets_traced} wallets, ${summary.transactions_mapped} transactions`}
          >
            <span className={`w-2 h-2 rounded-full shrink-0 ${summary.wallets_traced > 0 ? 'bg-primary' : 'bg-secondary'}`} />
            <span className="font-address-md text-xs text-on-surface whitespace-nowrap truncate">
              {summary.wallets_traced} wallets · {summary.transactions_mapped} txs
            </span>
          </div>

          {sanctions && sanctions.length > 0 && (
            <button
              type="button"
              onClick={() => setActiveTab('findings')}
              className="flex items-center gap-1 h-8 px-2.5 rounded-full bg-error/10 text-error border border-error/30 shrink-0"
              aria-label={`${sanctions.length} sanctioned hit${sanctions.length > 1 ? 's' : ''}, open Findings`}
            >
              <span className="material-symbols-outlined text-[16px]">warning</span>
              <span className="text-xs font-label-caps font-bold">{sanctions.length}</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            className="ml-auto w-11 h-11 flex items-center justify-center rounded-lg text-on-surface hover:bg-surface-container shrink-0"
            aria-label="More actions"
            aria-haspopup="dialog"
          >
            <span className="material-symbols-outlined text-[24px]">more_vert</span>
          </button>
        </div>
      </header>

      <Sheet open={menuOpen} onClose={() => setMenuOpen(false)} title="Graph actions" initial="auto" draggable={false}>
        <div className="flex flex-col gap-1">
          <MenuRow
            icon="money_off"
            label="Show 0-ETH contract calls"
            hint="Changes what every count includes."
            onClick={() => setShowZeroValue(!showZeroValue)}
            disabled={actionLoading}
          >
            <Switch on={showZeroValue} />
          </MenuRow>
          <MenuRow
            icon="swap_horiz"
            label="Include internal transfers"
            hint="ETH moved by smart contracts. Applies to the next trace."
            onClick={() => setIncludeInternal(!includeInternal)}
            disabled={actionLoading}
          >
            <Switch on={includeInternal} />
          </MenuRow>
          <div className="h-px bg-outline-variant/60 my-1" />
          <MenuRow
            icon="download"
            label="Export graph (JSON)"
            onClick={() => {
              setMenuOpen(false);
              exportGraph();
            }}
            disabled={edges.length === 0}
          />
          <MenuRow
            icon="sync"
            label="Sync graph and findings"
            onClick={sync}
            disabled={isLoadingGraph}
          />
          <MenuRow
            icon="delete_sweep"
            label="Clear graph"
            danger
            onClick={() => {
              setMenuOpen(false);
              setConfirmClear(true);
            }}
            disabled={edges.length === 0 || actionLoading}
          />
        </div>
      </Sheet>

      <ConfirmModal
        isOpen={confirmClear}
        title="Clear Forensic Graph?"
        message="This action will delete all wallets and transactions in the current graph session. Any unsaved investigation state will be lost."
        confirmText="Clear Graph"
        confirmVariant="danger"
        onConfirm={() => {
          setConfirmClear(false);
          clearSession();
        }}
        onCancel={() => setConfirmClear(false)}
      />
    </>
  );
};

// Bottom navigation: the five sections plus "More" (Product Overview, Privacy).
export const BottomNav = () => {
  const { activeTab, setActiveTab, sanctions } = useInvestigation();
  const [moreOpen, setMoreOpen] = useState(false);

  const item = (active) =>
    `relative flex-1 min-w-0 h-16 flex flex-col items-center justify-center gap-0.5 text-[11px] max-[399px]:text-[10px] max-[399px]:tracking-tight font-medium transition-colors ${
      active ? 'text-primary' : 'text-on-surface-variant'
    }`;

  return (
    <>
      <nav
        data-nav="bottom"
        aria-label="Main navigation"
        className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-surface/95 backdrop-blur-md border-t border-outline-variant flex"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)', paddingLeft: 'env(safe-area-inset-left)', paddingRight: 'env(safe-area-inset-right)' }}
      >
        {MOBILE_NAV.map((n) => {
          const active = activeTab === n.id;
          return (
            <button key={n.id} type="button" onClick={() => setActiveTab(n.id)} aria-current={active ? 'page' : undefined} className={item(active)}>
              {active && <span className="absolute top-0 inset-x-3 h-[3px] rounded-b bg-primary" aria-hidden="true" />}
              <span className={`material-symbols-outlined text-[24px] ${active ? 'fill' : ''}`}>{n.icon}</span>
              <span className="max-w-full truncate px-0.5">{n.label}</span>
              {n.id === 'findings' && sanctions?.length > 0 && (
                <span className="absolute top-2 right-[calc(50%-18px)] w-2.5 h-2.5 rounded-full bg-error ring-2 ring-surface" aria-hidden="true" />
              )}
            </button>
          );
        })}
        <button type="button" onClick={() => setMoreOpen(true)} className={item(false)} aria-haspopup="dialog">
          <span className="material-symbols-outlined text-[24px]">more_horiz</span>
          <span>More</span>
        </button>
      </nav>

      <Sheet open={moreOpen} onClose={() => setMoreOpen(false)} title="More" initial="auto" draggable={false}>
        <div className="flex flex-col gap-1">
          <MenuRow
            icon="info"
            label="Product overview"
            onClick={() => {
              setMoreOpen(false);
              setActiveTab('landing');
            }}
          />
          <a
            href="/privacy"
            className="w-full min-h-[52px] flex items-center gap-3 px-2 py-2 rounded-lg text-on-surface hover:bg-surface-container"
          >
            <span className="material-symbols-outlined text-[22px]">shield_lock</span>
            <span className="text-[15px] font-medium">Privacy</span>
          </a>
        </div>
      </Sheet>
    </>
  );
};

// Full value of a long address or hash, with copy and the block explorer.
export const AddressSheet = () => {
  const { addressSheet, closeAddressSheet, traceScope } = useInvestigation();
  const [copied, setCopied] = useState(false);
  useEffect(() => setCopied(false), [addressSheet]);
  if (!addressSheet) return null;
  const { address, label } = addressSheet;
  const explorer = explorerFor(traceScope?.chain);
  const isHash = /^0x[0-9a-fA-F]{64}$/.test(address);
  const isAddress = /^0x[0-9a-fA-F]{40}$/.test(address);
  return (
    <Sheet open onClose={closeAddressSheet} title={label || (isHash ? 'Transaction hash' : 'Address')} initial="auto" draggable={false}>
      <p className="font-address-md text-sm text-on-surface break-all bg-surface-container rounded-lg p-3 border border-outline-variant select-all">
        {address}
      </p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={async () => setCopied(await copyText(address))}
          className="min-h-[48px] rounded-lg border border-outline-variant bg-surface-container text-on-surface font-label-caps text-xs uppercase font-bold flex items-center justify-center gap-1.5"
        >
          <span className="material-symbols-outlined text-[18px]">{copied ? 'check' : 'content_copy'}</span>
          {copied ? 'Copied' : 'Copy'}
        </button>
        {(isAddress || isHash) ? (
          <a
            href={`${explorer.base}/${isHash ? 'tx' : 'address'}/${address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="min-h-[48px] rounded-lg bg-primary text-white font-label-caps text-xs uppercase font-bold flex items-center justify-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[18px]">open_in_new</span>
            {explorer.name}
          </a>
        ) : <span />}
      </div>
      <span className="sr-only" aria-live="polite">{copied ? 'Copied to clipboard' : ''}</span>
    </Sheet>
  );
};

// Dismissal is remembered per browser for the banner's current mode, so the banner
// comes back when the mode changes.
const BANNER_KEY = 'bt_demo_banner_dismissed';
const readDismissed = () => {
  try {
    return localStorage.getItem(BANNER_KEY);
  } catch {
    return null;
  }
};

// Compact public-demo notice. Its height is published as --bt-banner-h so the
// full-height Investigate layout can subtract it.
export const PublicDemoBanner = () => {
  const { publicMode } = useInvestigation();
  const ref = useRef(null);
  const mode = publicMode ? 'public' : null;
  const [dismissedMode, setDismissedMode] = useState(readDismissed);
  const [expanded, setExpanded] = useState(false);
  const visible = Boolean(mode) && dismissedMode !== mode;

  useEffect(() => {
    const root = document.documentElement;
    if (!visible || !ref.current) {
      root.style.removeProperty('--bt-banner-h');
      return undefined;
    }
    const set = () => root.style.setProperty('--bt-banner-h', `${ref.current?.offsetHeight || 0}px`);
    set();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(set) : null;
    ro?.observe(ref.current);
    return () => {
      ro?.disconnect();
      root.style.removeProperty('--bt-banner-h');
    };
  }, [visible]);

  const dismiss = () => {
    try {
      localStorage.setItem(BANNER_KEY, mode);
    } catch {
      // Storage blocked: hidden for this page view only.
    }
    setDismissedMode(mode);
  };

  if (!visible) return null;
  return (
    <div
      ref={ref}
      role="note"
      className="flex-none flex items-center gap-2 px-4 py-1.5 bg-tertiary/10 border-b border-tertiary/30 text-[12px] leading-snug text-on-surface max-lg:px-3 max-lg:gap-1.5 max-lg:text-[11.5px]"
    >
      <span className="material-symbols-outlined text-[16px] text-tertiary shrink-0 max-sm:hidden">public</span>
      {/* Phones/tablets: a short line; "More" shows the full text */}
      <span id="demo-banner-text" className="flex-1 min-w-0">
        <span className={expanded ? '' : 'max-lg:hidden'}>
          <span className="font-bold">Public demo:</span> your traces stay in a private workspace in this browser. Publishing to
          IPFS + Sepolia is limited to 5 per hour.
        </span>
        {!expanded && (
          <span className="lg:hidden block truncate">
            <span className="font-bold">Public demo</span> · private workspace · 5 publishes/hour
          </span>
        )}
      </span>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-controls="demo-banner-text"
        className="lg:hidden shrink-0 -my-2.5 px-1 !min-w-0 font-bold text-tertiary underline underline-offset-2"
      >
        {expanded ? 'Less' : 'More'}
      </button>
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss public demo notice"
        title="Dismiss"
        className="shrink-0 -my-1 w-6 h-6 flex items-center justify-center rounded text-on-surface-variant hover:text-on-surface hover:bg-tertiary/10 max-lg:-my-2.5 max-lg:-mr-2"
      >
        <span className="material-symbols-outlined text-[16px]">close</span>
      </button>
    </div>
  );
};

import React, { useEffect, useRef, useState } from 'react';
import { useInvestigation } from '../context/InvestigationContext';
import { GraphCanvas } from '../components/GraphCanvas';
import { ConfirmModal } from '../components/ConfirmModal';
import {
  loadCuratedCase,
  expandWallet,
  findPath,
  getErrorMessage,
} from '../api/client';
import { describeScope, describeCap, describeDataQuality, describeFailedSkipped } from '../utils/scope';
import { midTruncate } from '../utils/useCompact';

const INTERNAL_HELP =
  "Internal transfers are ETH moved by smart contracts (Etherscan's Internal Transactions tab). Turn on for bridges, mixers and exchanges.";

const CURATED_CASE_CARDS = [
  { name: 'Ronin Bridge Hack ($600M, 2022)', badge: '$600M', sub: 'Lazarus Group OFAC' },
  { name: 'Poly Network Hack ($611M, 2021)', badge: '$611M', sub: 'Cross-chain DeFi' },
  { name: 'Wormhole Bridge Hack ($321M, 2022)', badge: '$321M', sub: 'Solana-ETH Bridge' },
];

const inputClass =
  'w-full bg-surface text-on-surface text-xs p-2 rounded-lg border border-outline-variant focus:outline-none focus:ring-1 focus:ring-primary font-medium';
const labelClass = 'font-label-caps text-[10px] uppercase text-on-surface-variant font-bold block mb-1 max-lg:text-xs';

// Today in the user's local time zone, as YYYY-MM-DD for <input type="date" max>.
const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

// From / To date + order fields; used by both the wallet trace and the path search.
const DateWindowFields = ({ idPrefix, fromDate, toDate, sortOrder, onFromDate, onToDate, onSortOrder }) => {
  const today = todayIso();
  const invalid = Boolean(fromDate && toDate && fromDate > toDate);
  return (
    <div className="flex flex-col gap-2 bg-surface-container-low p-2.5 rounded-lg border border-outline-variant/40 max-lg:p-3 max-lg:gap-3">
      <div className="grid grid-cols-2 gap-2 max-[399px]:grid-cols-1">
        <div>
          <label htmlFor={`${idPrefix}-from-date`} className={labelClass}>From date</label>
          <input
            id={`${idPrefix}-from-date`}
            type="date"
            value={fromDate}
            min="2015-07-30"
            max={today}
            onChange={(e) => onFromDate(e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor={`${idPrefix}-to-date`} className={labelClass}>To date</label>
          <input
            id={`${idPrefix}-to-date`}
            type="date"
            value={toDate}
            min="2015-07-30"
            max={today}
            onChange={(e) => onToDate(e.target.value)}
            className={inputClass}
          />
        </div>
      </div>
      <div>
        <label htmlFor={`${idPrefix}-order`} className={labelClass}>Order</label>
        <select
          id={`${idPrefix}-order`}
          value={sortOrder}
          onChange={(e) => onSortOrder(e.target.value)}
          className={inputClass}
        >
          <option value="desc">Newest first</option>
          <option value="asc">Oldest first</option>
        </select>
      </div>
      {invalid && (
        <p className="text-[11px] text-error font-medium" role="alert">
          "From date" must be on or before "To date".
        </p>
      )}
      <p className="text-[10px] text-on-surface-variant leading-snug max-lg:text-xs">
        Investigators: set the window around the incident date. Oldest-first within the window shows the earliest activity.
      </p>
    </div>
  );
};

const walletsVisited = (n) => `${n} ${n === 1 ? 'wallet' : 'wallets'} visited`;

// Trace toast: the counted total, then the same breakdown as the Data quality box.
const describeFetch = (q) => {
  if (!q || q.transactions_shown == null) return '';
  return `${q.transactions_shown} transactions counted: ${describeDataQuality(q)}.`;
};

// The same numbers the PDF dossier prints under "Data quality".
const DataQualityBox = ({ quality, graphTotals }) => {
  const [open, setOpen] = useState(false);
  const n = (v) => (v == null ? '—' : v);
  const items = [
    ['Fetched', quality.transactions_fetched, 'Transactions taken into the graph by the last trace (normal + internal, after the cap).'],
    ['Shown', quality.transactions_shown, 'Transactions counted everywhere: successful ETH transfers, 0-ETH calls only if shown.'],
    [
      'Failed skipped',
      quality.failed_skipped == null ? null : describeFailedSkipped(quality).replace('Failed skipped ', ''),
      'Failed transactions (isError = 1) left out of the graph, split into normal and internal when both occur.',
    ],
    ['0-ETH hidden', quality.zero_value_hidden, '0-ETH contract calls stored but hidden. Turn on "Show 0-ETH contract calls" to include them.'],
    ['Internal', quality.internal_counted ? quality.internal_shown : 'off', 'Internal ETH transfers (sent by contracts); counted only when the trace included them.'],
    ['Capped wallets', quality.capped_wallets, 'Wallets with more transactions than the per-wallet cap.'],
  ];
  return (
    <div className="flex-none bg-surface border-b border-outline-variant/60 px-4 py-1.5 text-xs z-10 max-lg:px-3 max-lg:py-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-on-surface-variant hover:text-on-surface max-lg:w-full max-lg:text-left"
      >
        <span className="material-symbols-outlined text-[16px] text-primary">fact_check</span>
        <span className="font-label-caps uppercase text-[10px] font-bold max-lg:shrink-0">Data quality</span>
        <span className={`font-mono text-[11px] max-lg:flex-1 max-lg:min-w-0 ${open ? '' : 'max-lg:truncate'}`}>
          {describeDataQuality(quality)}
          {graphTotals.total > graphTotals.returned && ` · showing ${graphTotals.returned} of ${graphTotals.total} in the graph`}
        </span>
        <span className="material-symbols-outlined text-[14px]">{open ? 'expand_less' : 'expand_more'}</span>
      </button>
      {open && (
        <dl className="mt-1.5 grid grid-cols-3 sm:grid-cols-6 gap-1.5 max-lg:mb-2">
          {items.map(([label, value, help]) => (
            <div key={label} className="bg-surface-container rounded px-2 py-1" title={help}>
              <dt className="text-[9px] font-label-caps uppercase text-on-surface-variant font-bold">{label}</dt>
              <dd className="font-mono text-[12px] font-semibold text-on-surface">{n(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
};

export const InvestigateScreen = () => {
  const {
    chains,
    curatedCases,
    edges,
    summary,
    startWallet,
    setStartWallet,
    activePathEdges,
    setActivePathEdges,
    pathBannerMessage,
    setPathBannerMessage,
    resetPathView,
    refreshGraphAndSummary,
    refreshFindings,
    showToast,
    actionLoading,
    setActionLoading,
    traceScope,
    limitedWallets,
    dataQuality,
    graphTotals,
    showZeroValue,
    setShowZeroValue,
    includeInternal,
    setIncludeInternal,
    clearSession,
    exportGraph,
  } = useInvestigation();

  // Phones and tablets: "Setup" (forms) or "Graph"; desktop shows both side by side
  const [mobileTab, setMobileTab] = useState(edges.length > 0 ? 'graph' : 'setup');
  const [scopeOpen, setScopeOpen] = useState(false);

  // Filter input state
  const [filterQuery, setFilterQuery] = useState('');

  // Expand Wallet Form
  const [selectedChain, setSelectedChain] = useState('Ethereum');
  const [targetWallet, setTargetWallet] = useState(
    startWallet || '0x098B716B8Aaf21512996dC57EB0615e2383E2f96'
  );
  const [hops, setHops] = useState(2);
  const [txPerWallet, setTxPerWallet] = useState(15);

  // Date window + order for "Investigate a Wallet"
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [sortOrder, setSortOrder] = useState('desc');
  const dateRangeInvalid = Boolean(fromDate && toDate && fromDate > toDate);
  const traceWindow = { from_date: fromDate || undefined, to_date: toDate || undefined, sort: sortOrder };

  // Separate date window + order for "Trace a Specific Path"
  const [pathFromDate, setPathFromDate] = useState('');
  const [pathToDate, setPathToDate] = useState('');
  const [pathSortOrder, setPathSortOrder] = useState('desc');
  // Path search fetches more per wallet by default: a low cap is the usual reason a path is missed
  const [pathTxPerWallet, setPathTxPerWallet] = useState(30);
  // Scope returned by the last path search, so the banner can tell it apart from a wallet trace
  const [pathScopeKey, setPathScopeKey] = useState(null);
  const pathRangeInvalid = Boolean(pathFromDate && pathToDate && pathFromDate > pathToDate);

  const [showCapped, setShowCapped] = useState(false);

  // "Include internal transfers" (context state, off by default: match Etherscan's Transactions tab)
  // What the loaded graph was traced with; old scopes without the field included them
  const graphIncludesInternal = traceScope ? traceScope.include_internal !== false : null;

  // When a new scope arrives (curated case, reopened saved case), mirror it in the form
  const appliedScopeKey = useRef(null);
  useEffect(() => {
    if (!traceScope) return;
    const key = JSON.stringify(traceScope);
    if (appliedScopeKey.current === key) return;
    appliedScopeKey.current = key;
    setFromDate(traceScope.from_date || '');
    setToDate(traceScope.to_date || '');
    setSortOrder(traceScope.sort === 'asc' ? 'asc' : 'desc');
    setIncludeInternal(traceScope.include_internal !== false);
    if (traceScope.tx_per_wallet) setTxPerWallet(Math.min(30, Math.max(5, Number(traceScope.tx_per_wallet))));
    if (traceScope.hops) setHops(Math.min(3, Math.max(1, Number(traceScope.hops))));
    if (traceScope.chain && chains.includes(traceScope.chain)) setSelectedChain(traceScope.chain);
  }, [traceScope, chains]);

  const isPathScope = Boolean(traceScope && pathScopeKey === JSON.stringify(traceScope));
  const scopeLine = describeScope(traceScope, { maxHops: isPathScope });
  const capWarning = describeCap(limitedWallets, traceScope?.tx_per_wallet ?? txPerWallet);

  // Path Finder Form
  const [pathSource, setPathSource] = useState('0x098B716B8Aaf21512996dC57EB0615e2383E2f96');
  const [pathDestination, setPathDestination] = useState('');
  const [maxHops, setMaxHops] = useState(4);

  // Confirm Modal for Clear Graph
  const [isClearModalOpen, setIsClearModalOpen] = useState(false);

  // Handle Load Curated Case
  const handleLoadCuratedCase = async (caseName) => {
    setActionLoading(true);
    try {
      showToast(`Loading curated case: ${caseName}...`, 'info');
      const data = await loadCuratedCase(caseName);
      setStartWallet(data.start_wallet);
      setTargetWallet(data.start_wallet);
      resetPathView();
      await refreshGraphAndSummary();
      await refreshFindings(data.start_wallet);
      setMobileTab('graph');
      showToast(`Loaded ${caseName}: ${walletsVisited(data.wallets_visited)}. ${describeFetch(data.data_quality)}`, 'success');
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Expand Wallet
  const handleExpandWallet = async (e) => {
    e.preventDefault();
    if (!targetWallet.trim()) {
      showToast('Please enter a target wallet address.', 'warning');
      return;
    }
    if (dateRangeInvalid) {
      showToast('"From date" must be on or before "To date".', 'warning');
      return;
    }
    setActionLoading(true);
    try {
      showToast(`Tracing wallet ${targetWallet.slice(0, 8)}...`, 'info');
      const data = await expandWallet({
        wallet: targetWallet.trim(),
        hops: Number(hops),
        tx_per_wallet: Number(txPerWallet),
        chain: selectedChain,
        include_internal: includeInternal,
        ...traceWindow,
      });
      setStartWallet(data.start_wallet);
      resetPathView();
      await refreshGraphAndSummary();
      await refreshFindings(data.start_wallet);
      setMobileTab('graph');
      showToast(`Trace complete: ${walletsVisited(data.wallets_visited)}. ${describeFetch(data.data_quality)}`, 'success');
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Find Path
  const handleFindPath = async (e) => {
    e.preventDefault();
    if (!pathSource.trim() || !pathDestination.trim()) {
      showToast('Enter both a source and destination wallet.', 'warning');
      return;
    }
    if (pathRangeInvalid) {
      showToast('"From date" must be on or before "To date".', 'warning');
      return;
    }
    setActionLoading(true);
    try {
      showToast('Searching for transaction route...', 'info');
      const data = await findPath({
        source: pathSource.trim(),
        destination: pathDestination.trim(),
        max_hops: Number(maxHops),
        tx_per_wallet: Number(pathTxPerWallet),
        chain: selectedChain,
        include_internal: includeInternal,
        from_date: pathFromDate || undefined,
        to_date: pathToDate || undefined,
        sort: pathSortOrder,
      });
      // The path search's own window shouldn't be copied into the wallet-trace form.
      if (data.scope) {
        appliedScopeKey.current = JSON.stringify(data.scope);
        setPathScopeKey(JSON.stringify(data.scope));
      }

      if (!data.found || !data.paths || data.paths.length === 0) {
        setActivePathEdges(null);
        setPathBannerMessage(
          `No path found between ${pathSource.slice(0, 6)}... and ${pathDestination.slice(0, 6)}... within ${maxHops} hops limit.`
        );
        showToast('No path found within the hop limit.', 'warning');
      } else {
        // Collect union of rels across all returned paths
        const relsMap = new Map();
        data.paths.forEach((p) => {
          p.rels.forEach((r) => {
            // Keyed on the transaction, so two transfers of the same amount stay two
            const key = r.hash || `${r.from.toLowerCase()}-${r.to.toLowerCase()}-${r.value}`;
            if (!relsMap.has(key)) {
              relsMap.set(key, { from: r.from, to: r.to, value: r.value, hash: r.hash, timestamp: r.timestamp, kind: r.kind });
            }
          });
        });
        const isolatedEdges = Array.from(relsMap.values());
        setActivePathEdges(isolatedEdges);
        setPathBannerMessage(
          `Showing isolated route from ${pathSource.slice(0, 6)}... to ${pathDestination.slice(0, 6)}... (${data.paths.length} path(s) found)`
        );
        showToast(`Route found! Displaying ${data.paths.length} path(s).`, 'success');
      }
      await refreshGraphAndSummary();
      setMobileTab('graph');
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Clear Graph
  const handleConfirmClear = async () => {
    setIsClearModalOpen(false);
    await clearSession();
  };

  // Export graph as JSON
  const handleExportGraph = () => exportGraph();

  // Paste a wallet address from the clipboard (phones: no long-press fiddling)
  const handlePaste = async (setter) => {
    try {
      const text = (await navigator.clipboard.readText()).trim();
      if (text) setter(text);
      else showToast('Clipboard is empty.', 'warning');
    } catch {
      showToast('Clipboard access was blocked. Long-press the field and paste instead.', 'warning');
    }
  };

  const pasteButton = (setter, label) => (
    <button
      type="button"
      onClick={() => handlePaste(setter)}
      className="lg:hidden shrink-0 px-3 rounded-lg border border-outline-variant bg-surface-container text-on-surface font-label-caps text-xs uppercase font-bold flex items-center gap-1"
      aria-label={label}
    >
      <span className="material-symbols-outlined text-[18px]">content_paste</span>
      Paste
    </button>
  );

  // Node selection callback
  const handleSelectWallet = (address) => {
    setTargetWallet(address);
    if (!pathSource) {
      setPathSource(address);
    } else if (!pathDestination) {
      setPathDestination(address);
    }
  };

  return (
    <div className="flex flex-col w-full bt-investigate-h overflow-hidden bg-surface-bright relative">
      {/* Phones and tablets: Setup / Graph switch */}
      <div className="lg:hidden flex-none px-3 py-2 bg-surface border-b border-outline-variant/50 z-10">
        <div role="tablist" aria-label="Investigate view" className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-surface-container">
          {[
            ['setup', 'tune', 'Setup'],
            ['graph', 'hub', 'Graph'],
          ].map(([id, icon, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              data-mobile-tab={id}
              aria-selected={mobileTab === id}
              aria-controls={`investigate-${id}-panel`}
              onClick={() => setMobileTab(id)}
              className={`flex items-center justify-center gap-1.5 rounded-lg text-sm font-semibold transition-colors ${
                mobileTab === id ? 'bg-surface text-primary shadow-sm' : 'text-on-surface-variant'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">{icon}</span>
              {label}
              {id === 'graph' && summary.wallets_traced > 0 && (
                <span className="font-mono text-[11px] px-1.5 rounded-full bg-primary/10 text-primary">{summary.wallets_traced}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Top Action Bar (desktop; on small screens these live in the top bar's menu) */}
      <div className="max-lg:hidden flex-none flex flex-wrap items-center justify-between px-xl py-sm bg-surface shadow-xs z-10 border-b border-outline-variant/50 gap-4">
        {/* Filter Input */}
        <div className="flex items-center gap-md w-full max-w-xl">
          <div className="relative w-full">
            <span className="material-symbols-outlined absolute left-sm top-1/2 -translate-y-1/2 text-on-surface-variant/50 text-[18px]">
              filter_list
            </span>
            <input
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              className="w-full bg-surface-container text-on-surface font-address-md text-xs rounded-lg py-2 pl-9 pr-8 focus:outline-none focus:ring-1 focus:ring-primary transition-all border border-outline-variant/60"
              placeholder="Filter rendered nodes by address or entity tag..."
              type="text"
            />
            {filterQuery && (
              <button
                onClick={() => setFilterQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-on-surface text-xs"
              >
                <span className="material-symbols-outlined text-[14px]">close</span>
              </button>
            )}
          </div>
        </div>

        {/* Status & Actions */}
        <div className="flex items-center gap-md">
          {/* Active status indicator */}
          <div className="flex items-center gap-1.5 bg-primary/10 px-3 py-1.5 rounded-full border border-primary/20">
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="font-label-caps text-[11px] uppercase tracking-wider text-primary font-bold">
              {summary.wallets_traced > 0 ? 'Live Trace Active' : 'Session Ready'}
            </span>
          </div>

          {/* Show 0-ETH contract calls */}
          <label className="flex items-center gap-1.5 text-[11px] font-label-caps uppercase text-on-surface-variant cursor-pointer select-none">
            <input
              id="show-zero-value"
              type="checkbox"
              checked={showZeroValue}
              onChange={(e) => setShowZeroValue(e.target.checked)}
              disabled={actionLoading}
              className="accent-primary"
            />
            <span>Show 0-ETH contract calls</span>
          </label>

          {/* Include internal transfers (applies to the next trace) */}
          <label
            className="flex items-center gap-1.5 text-[11px] font-label-caps uppercase text-on-surface-variant cursor-pointer select-none"
            title={INTERNAL_HELP}
          >
            <input
              id="include-internal"
              type="checkbox"
              checked={includeInternal}
              onChange={(e) => setIncludeInternal(e.target.checked)}
              disabled={actionLoading}
              aria-describedby="include-internal-help"
              className="accent-primary"
            />
            <span>Include internal transfers</span>
            <span id="include-internal-help" className="sr-only">{INTERNAL_HELP}</span>
          </label>

          {/* Export Graph */}
          <button
            onClick={handleExportGraph}
            disabled={edges.length === 0}
            className="bg-surface-container hover:bg-surface-variant text-on-surface px-3.5 py-1.5 rounded-lg font-label-caps text-[11px] uppercase border border-outline-variant transition-colors flex items-center gap-1 disabled:opacity-50"
            title="Export Graph JSON"
          >
            <span className="material-symbols-outlined text-[16px]">download</span>
            <span>Export</span>
          </button>

          {/* Clear Graph */}
          <button
            onClick={() => setIsClearModalOpen(true)}
            disabled={edges.length === 0}
            className="bg-transparent hover:bg-error/10 text-error px-3.5 py-1.5 rounded-lg font-label-caps text-[11px] uppercase border border-error/30 transition-colors flex items-center gap-1 disabled:opacity-50"
            title="Clear Graph"
          >
            <span className="material-symbols-outlined text-[16px]">delete_sweep</span>
            <span>Clear</span>
          </button>
        </div>
      </div>

      {/* Path Isolation Banner if active */}
      {pathBannerMessage && (
        <div className="bg-primary-container text-on-primary px-xl py-2 flex items-center justify-between text-xs font-medium z-10 max-lg:px-3 max-lg:gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="material-symbols-outlined text-[16px]">route</span>
            <span>{pathBannerMessage}</span>
          </div>
          {activePathEdges && (
            <button
              onClick={resetPathView}
              className="bg-black/20 hover:bg-black/40 text-white px-2.5 py-1 rounded font-label-caps uppercase text-[10px] transition-colors"
            >
              Show Full Graph
            </button>
          )}
        </div>
      )}

      {/* Main Workspace Area */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Panel: Investigation Tools Sidebar */}
        <div
          id="investigate-setup-panel"
          className={`w-[360px] bg-surface flex flex-col border-r border-outline-variant/60 shadow-lg z-10 overflow-y-auto max-lg:w-full max-lg:border-r-0 max-lg:shadow-none ${
            mobileTab !== 'setup' ? 'max-lg:hidden' : ''
          }`}
        >
          {/* Section 1: Example Investigations */}
          <div className="p-4 bg-surface-container-low border-b border-outline-variant/40 max-lg:px-0">
            <div className="flex items-center justify-between mb-3 max-lg:px-4">
              <h3 className="font-label-caps text-xs uppercase tracking-wider text-on-surface-variant font-bold flex items-center gap-1.5">
                <span className="material-symbols-outlined text-[16px] text-primary">book</span>
                <span>Example Investigations</span>
              </h3>
            </div>

            <div className="flex flex-col gap-2 max-lg:flex-row max-lg:overflow-x-auto max-lg:snap-x max-lg:snap-mandatory max-lg:px-4 max-lg:pb-1 max-lg:scroll-px-4 bt-no-scrollbar">
              {CURATED_CASE_CARDS.map((card) => ({
                ...card,
                ...(curatedCases.find((cc) => cc.name === card.name) || {}),
              })).map((c) => (
                <button
                  key={c.name}
                  onClick={() => handleLoadCuratedCase(c.name)}
                  disabled={actionLoading}
                  title={c.date_note || c.description || ''}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-surface hover:bg-primary/10 border border-outline-variant/50 group transition-all text-left shadow-xs disabled:opacity-50 max-lg:shrink-0 max-lg:w-[78%] max-lg:max-w-[300px] max-lg:snap-start max-lg:items-start max-lg:p-3"
                >
                  <div className="flex flex-col max-lg:gap-0.5">
                    <span className="font-body-sm text-xs text-on-surface font-semibold group-hover:text-primary transition-colors max-lg:text-sm">
                      {c.name}
                    </span>
                    <span className="text-[10px] text-on-surface-variant font-address-md max-lg:text-xs">
                      {c.sub}
                      {c.incident_date && <> · Incident {c.incident_date}</>}
                    </span>
                    {c.from_date && (
                      <span className="text-[10px] text-on-surface-variant/80 max-lg:text-xs">
                        Traces {c.from_date} to {c.to_date}, oldest first
                        {c.include_internal ? ', incl. internal transfers' : ''}
                      </span>
                    )}
                  </div>
                  <span className="material-symbols-outlined text-on-surface-variant/40 group-hover:text-primary text-[18px] transition-transform group-hover:translate-x-0.5">
                    arrow_forward
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Section 2: Investigate a Wallet Form */}
          <div className="p-4 border-b border-outline-variant/40">
            <h3 className="font-headline-md text-sm font-bold text-on-surface mb-3 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-primary text-[18px]">search</span>
              <span>Investigate a Wallet</span>
            </h3>

            <form onSubmit={handleExpandWallet} className="flex flex-col gap-3">
              {/* Chain selector */}
              <div>
                <label htmlFor="trace-chain" className="font-label-caps text-[10px] uppercase text-on-surface-variant font-bold block mb-1 max-lg:text-xs">
                  Blockchain Network
                </label>
                <select
                  id="trace-chain"
                  value={selectedChain}
                  onChange={(e) => setSelectedChain(e.target.value)}
                  className="w-full bg-surface-container text-on-surface text-xs p-2 rounded-lg border border-outline-variant focus:outline-none focus:ring-1 focus:ring-primary font-medium"
                >
                  {chains.map((chain) => (
                    <option key={chain} value={chain}>
                      {chain}
                    </option>
                  ))}
                </select>
              </div>

              {/* Wallet Address Input */}
              <div>
                <label htmlFor="trace-wallet" className="font-label-caps text-[10px] uppercase text-on-surface-variant font-bold block mb-1 max-lg:text-xs">
                  Target Wallet Address
                </label>
                <div className="flex gap-2">
                  <input
                    id="trace-wallet"
                    type="text"
                    value={targetWallet}
                    onChange={(e) => setTargetWallet(e.target.value)}
                    placeholder="0x..."
                    className="w-full bg-surface text-on-surface font-address-md text-xs p-2.5 rounded-lg border border-outline-variant focus:outline-none focus:ring-1 focus:ring-primary shadow-xs font-mono max-lg:min-w-0"
                    spellCheck="false"
                    autoCapitalize="off"
                    autoCorrect="off"
                    required
                  />
                  {pasteButton(setTargetWallet, 'Paste wallet address')}
                </div>
              </div>

              {/* Date window + order */}
              <DateWindowFields
                idPrefix="trace"
                fromDate={fromDate}
                toDate={toDate}
                sortOrder={sortOrder}
                onFromDate={setFromDate}
                onToDate={setToDate}
                onSortOrder={setSortOrder}
              />

              {/* Sliders: Hops and Tx per wallet */}
              <div className="grid grid-cols-2 gap-3 bg-surface-container-low p-2.5 rounded-lg border border-outline-variant/40 max-lg:p-3 max-lg:gap-5">
                <div>
                  <div className="flex justify-between text-[10px] font-label-caps uppercase text-on-surface-variant font-bold mb-1 max-lg:text-xs">
                    <label htmlFor="trace-hops">Hops Deep</label>
                    <span className="text-primary font-mono">{hops}</span>
                  </div>
                  <input
                    id="trace-hops"
                    type="range"
                    min="1"
                    max="3"
                    value={hops}
                    onChange={(e) => setHops(Number(e.target.value))}
                    className="w-full accent-primary h-1 bg-outline-variant rounded-lg cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-[10px] font-label-caps uppercase text-on-surface-variant font-bold mb-1 max-lg:text-xs">
                    <label htmlFor="trace-tx-per-wallet">Tx / Wallet</label>
                    <span className="text-primary font-mono">{txPerWallet}</span>
                  </div>
                  <input
                    id="trace-tx-per-wallet"
                    type="range"
                    min="5"
                    max="30"
                    step="5"
                    value={txPerWallet}
                    onChange={(e) => setTxPerWallet(Number(e.target.value))}
                    className="w-full accent-primary h-1 bg-outline-variant rounded-lg cursor-pointer"
                  />
                </div>
              </div>

              {/* Expand Graph Action Button (sticky at the bottom of the form on small screens) */}
              <div className="max-lg:sticky max-lg:bottom-0 max-lg:-mx-4 max-lg:px-4 max-lg:py-3 max-lg:bg-surface max-lg:border-t max-lg:border-outline-variant/50 max-lg:z-10">
                <button
                  type="submit"
                  disabled={actionLoading || dateRangeInvalid}
                  className="w-full bg-primary text-white hover:bg-primary-container py-2.5 rounded-lg font-label-caps text-xs uppercase shadow-md transition-all font-bold flex items-center justify-center gap-1.5 active:scale-98 disabled:opacity-50 max-lg:text-sm max-lg:min-h-[48px]"
                >
                  <span className="material-symbols-outlined text-[16px]">account_tree</span>
                  <span>Expand Graph</span>
                </button>
              </div>
            </form>
          </div>

          {/* Section 3: Trace a Specific Path */}
          <div className="p-4 flex-1">
            <h3 className="font-headline-md text-sm font-bold text-on-surface mb-3 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-primary text-[18px]">alt_route</span>
              <span>Trace a Specific Path</span>
            </h3>

            <form onSubmit={handleFindPath} className="flex flex-col gap-3">
              <div className="flex flex-col gap-2">
                <div>
                  <label htmlFor="path-source" className="font-label-caps text-[10px] uppercase text-on-surface-variant font-bold block mb-1 max-lg:text-xs">
                    Source Wallet
                  </label>
                  <div className="flex gap-2">
                    <input
                      id="path-source"
                      type="text"
                      value={pathSource}
                      onChange={(e) => setPathSource(e.target.value)}
                      placeholder="0x... Source"
                      className="w-full bg-surface text-on-surface font-address-md text-[11px] p-2 rounded border border-outline-variant focus:outline-none focus:ring-1 focus:ring-primary font-mono max-lg:min-w-0 max-lg:rounded-lg"
                      spellCheck="false"
                      autoCapitalize="off"
                      autoCorrect="off"
                      required
                    />
                    {pasteButton(setPathSource, 'Paste source wallet')}
                  </div>
                </div>

                <div>
                  <label htmlFor="path-destination" className="font-label-caps text-[10px] uppercase text-on-surface-variant font-bold block mb-1 max-lg:text-xs">
                    Destination Wallet
                  </label>
                  <div className="flex gap-2">
                    <input
                      id="path-destination"
                      type="text"
                      value={pathDestination}
                      onChange={(e) => setPathDestination(e.target.value)}
                      placeholder="0x... Destination"
                      className="w-full bg-surface text-on-surface font-address-md text-[11px] p-2 rounded border border-outline-variant focus:outline-none focus:ring-1 focus:ring-primary font-mono max-lg:min-w-0 max-lg:rounded-lg"
                      spellCheck="false"
                      autoCapitalize="off"
                      autoCorrect="off"
                      required
                    />
                    {pasteButton(setPathDestination, 'Paste destination wallet')}
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-2 bg-surface-container-low p-2.5 rounded-lg border border-outline-variant/40 max-lg:p-3">
                <div className="grid grid-cols-2 gap-3 max-lg:gap-5">
                  <div>
                    <div className="flex justify-between text-[10px] font-label-caps uppercase text-on-surface-variant font-bold mb-1 max-lg:text-xs">
                      <label htmlFor="path-max-hops">Max hops (1–6)</label>
                      <span className="text-primary font-mono">{maxHops}</span>
                    </div>
                    <input
                      id="path-max-hops"
                      type="range"
                      min="1"
                      max="6"
                      value={maxHops}
                      onChange={(e) => setMaxHops(Number(e.target.value))}
                      className="w-full accent-primary h-1 bg-outline-variant rounded-lg cursor-pointer"
                    />
                  </div>
                  <div>
                    <div className="flex justify-between text-[10px] font-label-caps uppercase text-on-surface-variant font-bold mb-1 max-lg:text-xs">
                      <label htmlFor="path-tx-per-wallet">Tx per wallet</label>
                      <span className="text-primary font-mono">{pathTxPerWallet}</span>
                    </div>
                    <input
                      id="path-tx-per-wallet"
                      type="range"
                      min="5"
                      max="30"
                      step="5"
                      value={pathTxPerWallet}
                      onChange={(e) => setPathTxPerWallet(Number(e.target.value))}
                      className="w-full accent-primary h-1 bg-outline-variant rounded-lg cursor-pointer"
                    />
                  </div>
                </div>
                <p className="text-[10px] text-on-surface-variant leading-snug max-lg:text-xs">
                  Hops = how many wallet-to-wallet steps outward the search may go. Tx per wallet = the most transactions fetched for each wallet visited; raise it if a path is missing.
                </p>
              </div>

              <DateWindowFields
                idPrefix="path"
                fromDate={pathFromDate}
                toDate={pathToDate}
                sortOrder={pathSortOrder}
                onFromDate={setPathFromDate}
                onToDate={setPathToDate}
                onSortOrder={setPathSortOrder}
              />

              <div className="max-lg:sticky max-lg:bottom-0 max-lg:-mx-4 max-lg:px-4 max-lg:py-3 max-lg:bg-surface max-lg:border-t max-lg:border-outline-variant/50 max-lg:z-10">
                <button
                  type="submit"
                  disabled={actionLoading || pathRangeInvalid}
                  className="w-full bg-surface-container hover:bg-surface-variant text-on-surface py-2 rounded font-label-caps text-[11px] uppercase border border-outline-variant transition-colors font-bold flex items-center justify-center gap-1 shadow-xs disabled:opacity-50 max-lg:text-sm max-lg:min-h-[48px] max-lg:rounded-lg"
                >
                  <span className="material-symbols-outlined text-[16px]">route</span>
                  <span>Find Path</span>
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Main Graph Visualization Canvas */}
        <div
          id="investigate-graph-panel"
          className={`flex-1 h-full relative flex flex-col min-w-0 ${mobileTab !== 'graph' ? 'max-lg:hidden' : ''}`}
        >
          {/* Small screens: scope as one tappable line; cap warning stays visible */}
          {edges.length > 0 && (
            <div className="lg:hidden flex-none bg-surface border-b border-outline-variant/60 px-3 flex flex-col z-10 text-xs text-on-surface">
              <button
                type="button"
                onClick={() => setScopeOpen((v) => !v)}
                aria-expanded={scopeOpen}
                className="w-full flex items-center gap-1.5 text-left"
              >
                <span className="material-symbols-outlined text-[16px] text-primary shrink-0">date_range</span>
                <span className="font-label-caps uppercase text-[10px] text-on-surface-variant font-bold shrink-0">
                  {isPathScope ? 'Path scope' : 'Scope'}
                </span>
                <span className={`flex-1 min-w-0 font-medium ${scopeOpen ? '' : 'truncate'}`}>
                  {scopeLine || 'Not recorded for this graph (traced before scopes were saved).'}
                </span>
                <span className="material-symbols-outlined text-[18px] text-on-surface-variant shrink-0">
                  {scopeOpen ? 'expand_less' : 'expand_more'}
                </span>
              </button>
              {scopeOpen && (
                <div className="flex flex-col gap-2 pb-2">
                  {traceScope?.date_note && <p className="text-on-surface-variant">{traceScope.date_note}</p>}
                  {graphIncludesInternal !== null && includeInternal !== graphIncludesInternal && (
                    <p className="rounded-lg border border-primary/40 bg-primary/10 px-3 py-2" role="status">
                      {graphIncludesInternal
                        ? 'Graph was loaded with internal transfers; re-run the trace to leave them out.'
                        : 'Graph was loaded without internal transfers; re-run the trace to include them.'}
                    </p>
                  )}
                </div>
              )}
              {capWarning && (
                <div className="mb-2 rounded-lg border border-[#F2A93B]/50 bg-[#F2A93B]/10 px-3 py-1.5" role="status">
                  <div className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-[16px] text-[#B7791F] mt-0.5">warning</span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium leading-snug">{capWarning}</p>
                      <button
                        type="button"
                        onClick={() => setShowCapped((v) => !v)}
                        aria-expanded={showCapped}
                        className="text-[11px] font-label-caps uppercase font-bold text-[#B7791F] flex items-center gap-0.5"
                      >
                        <span className="material-symbols-outlined text-[14px]">{showCapped ? 'expand_less' : 'expand_more'}</span>
                        {showCapped ? 'Hide' : 'Show'} capped wallets ({limitedWallets.length})
                      </button>
                      {showCapped && (
                        <ul className="max-h-40 overflow-y-auto flex flex-col">
                          {limitedWallets.map((w) => (
                            <li key={w}>
                              <button
                                type="button"
                                onClick={() => handleSelectWallet(w)}
                                className="w-full font-mono text-[13px] text-on-surface text-left"
                                title={w}
                              >
                                {midTruncate(w)} <span className="text-on-surface-variant text-[11px] font-sans">· use as target</span>
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
          {edges.length > 0 && (
            <div className="max-lg:hidden flex-none bg-surface border-b border-outline-variant/60 px-4 py-2 flex flex-col gap-2 z-10">
              <div className="flex items-start gap-2 text-xs text-on-surface">
                <span className="material-symbols-outlined text-[16px] text-primary">date_range</span>
                <span className="font-medium">
                  <span className="font-label-caps uppercase text-[10px] text-on-surface-variant font-bold mr-1.5">
                    {isPathScope ? 'Path search scope' : 'Scope'}
                  </span>
                  {scopeLine || 'Not recorded for this graph (traced before scopes were saved).'}
                </span>
              </div>
              {graphIncludesInternal !== null && includeInternal !== graphIncludesInternal && (
                <div className="rounded-lg border border-primary/40 bg-primary/10 px-3 py-2 text-xs text-on-surface flex items-start gap-2" role="status">
                  <span className="material-symbols-outlined text-[16px] text-primary">info</span>
                  <span>
                    {graphIncludesInternal
                      ? 'Graph was loaded with internal transfers; re-run the trace to leave them out.'
                      : 'Graph was loaded without internal transfers; re-run the trace to include them.'}
                    {' '}The checkbox applies to the next trace; the graph is not changed until then.
                  </span>
                </div>
              )}
              {traceScope?.date_note && (
                <p className="text-[11px] text-on-surface-variant pl-6">{traceScope.date_note}</p>
              )}
              {capWarning && (
                <div className="rounded-lg border border-[#F2A93B]/50 bg-[#F2A93B]/10 px-3 py-2 text-xs text-on-surface" role="status">
                  <div className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-[16px] text-[#B7791F]">warning</span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium">{capWarning}</p>
                      <button
                        type="button"
                        onClick={() => setShowCapped((v) => !v)}
                        aria-expanded={showCapped}
                        className="mt-1 text-[11px] font-label-caps uppercase font-bold text-[#B7791F] hover:underline flex items-center gap-0.5"
                      >
                        <span className="material-symbols-outlined text-[14px]">{showCapped ? 'expand_less' : 'expand_more'}</span>
                        {showCapped ? 'Hide' : 'Show'} capped wallets ({limitedWallets.length})
                      </button>
                      {showCapped && (
                        <ul className="mt-1.5 max-h-32 overflow-y-auto flex flex-col gap-1">
                          {limitedWallets.map((w) => (
                            <li key={w}>
                              <button
                                type="button"
                                onClick={() => handleSelectWallet(w)}
                                className="font-mono text-[11px] text-on-surface hover:text-primary break-all text-left"
                                title="Use as target wallet"
                              >
                                {w}
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
          {edges.length > 0 && dataQuality && (
            <DataQualityBox quality={dataQuality} graphTotals={graphTotals} />
          )}
          <div className="flex-1 relative min-h-0">
            {/* Small screens: the node filter floats over the graph */}
            {edges.length > 0 && (
              <div className="lg:hidden absolute top-2 left-2 right-2 z-20">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/60 text-[18px] pointer-events-none">
                  filter_list
                </span>
                <input
                  value={filterQuery}
                  onChange={(e) => setFilterQuery(e.target.value)}
                  className="w-full bg-surface/95 text-on-surface font-address-md rounded-lg pl-10 pr-11 border border-outline-variant shadow-md focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Filter by address or label"
                  type="search"
                  aria-label="Filter wallets in the graph"
                />
                {filterQuery && (
                  <button
                    type="button"
                    onClick={() => setFilterQuery('')}
                    className="absolute right-0 top-0 h-11 w-11 flex items-center justify-center text-on-surface-variant"
                    aria-label="Clear filter"
                  >
                    <span className="material-symbols-outlined text-[18px]">close</span>
                  </button>
                )}
              </div>
            )}
            <GraphCanvas filterQuery={filterQuery} onSelectWallet={handleSelectWallet} />
          </div>
        </div>
      </div>

      {/* Clear Graph Confirmation Modal */}
      <ConfirmModal
        isOpen={isClearModalOpen}
        title="Clear Forensic Graph?"
        message="This action will delete all wallets and transactions in the current graph session. Any unsaved investigation state will be lost."
        confirmText="Clear Graph"
        confirmVariant="danger"
        onConfirm={handleConfirmClear}
        onCancel={() => setIsClearModalOpen(false)}
      />
    </div>
  );
};

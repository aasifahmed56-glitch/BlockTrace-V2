import React from 'react';
import { useInvestigation } from '../context/InvestigationContext';

export const Header = ({ onToggleSidebar, isLocked = false, isMobileOpen = false }) => {
  const {
    summary, sanctions, refreshGraphAndSummary, refreshFindings, isLoadingGraph,
    serverWaking,
  } = useInvestigation();

  const handleRefresh = async () => {
    await refreshGraphAndSummary();
    await refreshFindings();
  };

  const isExpanded = isLocked || isMobileOpen;

  return (
    <>
      {/* Server waking banner */}
      {serverWaking && (
        <div className="fixed top-0 left-0 right-0 z-[60] bg-amber-500/90 text-black text-center py-2 text-sm font-medium backdrop-blur-sm">
          <span className="inline-block animate-spin mr-2">⏳</span>
          Waking up the server, this can take up to a minute...
        </div>
      )}

      <header className={`max-lg:hidden fixed ${serverWaking ? 'top-[36px]' : 'top-0'} left-0 md:left-[72px] right-0 h-16 bg-surface/80 backdrop-blur-xl z-40 flex items-center justify-between px-md sm:px-xl border-b border-outline-variant transition-[top] duration-300`}>
        {/* Left: Hamburger / Lock Toggle & Search Bar */}
        <div className="flex items-center gap-sm sm:gap-md">
          <button
            id="sidebar-hamburger-btn"
            onClick={onToggleSidebar}
            className={`p-2 rounded-lg transition-all flex items-center justify-center focus:outline-none ${
              isLocked
                ? 'bg-primary/20 text-primary'
                : 'text-on-surface-variant hover:text-white hover:bg-white/10 active:scale-95'
            }`}
            title={isLocked ? "Unlock navigation sidebar (restore auto-collapse on hover)" : "Lock navigation sidebar expanded"}
            aria-label={isLocked ? "Unlock navigation sidebar" : "Lock navigation sidebar expanded"}
            aria-expanded={isExpanded}
          >
            <span className="material-symbols-outlined text-[24px]">
              {isExpanded ? 'menu_open' : 'menu'}
            </span>
          </button>

          {/* Search Bar / Quick Lookup */}
          <div className="hidden sm:flex items-center bg-surface-container-low px-md py-xs rounded-full border border-outline-variant w-72 md:w-96">
            <span className="material-symbols-outlined text-on-surface-variant mr-sm text-[20px]">
              search
            </span>
            <input
              className="bg-transparent border-none focus:ring-0 text-body-sm w-full outline-none placeholder:text-on-surface-variant/50 font-address-md text-xs"
              placeholder="Global search address, tx, or entity..."
              type="text"
              readOnly
              onClick={() => {}}
            />
          </div>
        </div>

        {/* Right Actions & Status Badges */}
        <div className="flex items-center gap-lg">
          {/* Live Traced Status */}
          <div className="hidden sm:flex items-center gap-2 bg-surface-container px-3 py-1 rounded-full border border-outline-variant/60">
            <div className={`w-2 h-2 rounded-full ${summary.wallets_traced > 0 ? 'bg-primary animate-pulse' : 'bg-secondary'}`} />
            <span className="text-xs font-address-md text-on-surface">
              {summary.wallets_traced} wallets · {summary.transactions_mapped} txs
            </span>
          </div>

          {/* Sanctions Warning Badge if hits exist */}
          {sanctions && sanctions.length > 0 && (
            <div className="flex items-center gap-1.5 bg-error/10 text-error px-3 py-1 rounded-full border border-error/30">
              <span className="material-symbols-outlined text-[16px]">warning</span>
              <span className="text-xs font-label-caps uppercase font-bold">
                {sanctions.length} Sanctioned Hit{sanctions.length > 1 ? 's' : ''}
              </span>
            </div>
          )}

          {/* Refresh button */}
          <button
            onClick={handleRefresh}
            disabled={isLoadingGraph}
            className="p-sm text-on-surface-variant hover:text-primary transition-colors disabled:opacity-50"
            title="Refresh Graph & Findings"
          >
            <span className={`material-symbols-outlined text-[20px] ${isLoadingGraph ? 'animate-spin' : ''}`}>
              sync
            </span>
          </button>
        </div>
      </header>
    </>
  );
};

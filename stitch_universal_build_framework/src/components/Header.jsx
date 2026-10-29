import React, { useState } from 'react';
import { useInvestigation } from '../context/InvestigationContext';

export const Header = ({ onToggleSidebar, isLocked = false, isMobileOpen = false }) => {
  const {
    summary, sanctions, refreshGraphAndSummary, refreshFindings, isLoadingGraph,
    publicMode, isPublicLocked, accessCode, setAccessCode, serverWaking,
  } = useInvestigation();

  const [showCodeInput, setShowCodeInput] = useState(false);
  const [codeValue, setCodeValue] = useState('');

  const handleRefresh = async () => {
    await refreshGraphAndSummary();
    await refreshFindings();
  };

  const handleUnlock = () => {
    if (codeValue.trim()) {
      setAccessCode(codeValue.trim());
      setShowCodeInput(false);
      setCodeValue('');
      // Reload page to re-fetch all data with the new code
      window.location.reload();
    }
  };

  const handleLock = () => {
    setAccessCode('');
    window.location.reload();
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

      {/* Public mode locked banner */}
      {isPublicLocked && !serverWaking && (
        <div className="fixed top-0 left-0 md:left-[72px] right-0 z-[55] bg-amber-600/90 text-white text-center py-1.5 text-xs font-medium backdrop-blur-sm flex items-center justify-center gap-2">
          <span className="material-symbols-outlined text-[16px]">search</span>
          Public demo mode: report verification only
          <button
            onClick={() => setShowCodeInput(true)}
            className="ml-2 px-2.5 py-0.5 bg-white/20 hover:bg-white/30 rounded text-xs font-bold transition-colors"
          >
            Unlock full workspace
          </button>
        </div>
      )}

      {/* Access code modal */}
      {showCodeInput && (
        <div className="fixed inset-0 z-[70] bg-black/50 backdrop-blur-sm flex items-center justify-center">
          <div className="bg-surface-container rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl border border-outline-variant">
            <h3 className="text-lg font-bold text-on-surface mb-2">Unlock Full Workspace</h3>
            <p className="text-sm text-on-surface-variant mb-4">
              Enter the access code to use investigation, findings, and case management features.
            </p>
            <input
              type="password"
              value={codeValue}
              onChange={(e) => setCodeValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleUnlock()}
              placeholder="Access code"
              className="w-full px-3 py-2 bg-surface rounded-lg border border-outline-variant text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-2 focus:ring-primary mb-3"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={handleUnlock}
                className="flex-1 px-4 py-2 bg-primary text-on-primary rounded-lg font-medium hover:bg-primary/90 transition-colors"
              >
                Unlock
              </button>
              <button
                onClick={() => { setShowCodeInput(false); setCodeValue(''); }}
                className="px-4 py-2 bg-surface-container-high text-on-surface rounded-lg font-medium hover:bg-surface-container-highest transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <header className={`fixed ${isPublicLocked && !serverWaking ? 'top-[30px]' : serverWaking ? 'top-[36px]' : 'top-0'} left-0 md:left-[72px] right-0 h-16 bg-surface/80 backdrop-blur-xl z-40 flex items-center justify-between px-md sm:px-xl border-b border-outline-variant transition-[top] duration-300`}>
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

          {/* Unlock/Lock badge for public mode */}
          {publicMode && accessCode && (
            <button
              onClick={handleLock}
              className="flex items-center gap-1 bg-green-500/10 text-green-400 px-2.5 py-1 rounded-full border border-green-500/30 text-xs font-bold hover:bg-green-500/20 transition-colors"
              title="Click to lock workspace"
            >
              <span className="material-symbols-outlined text-[14px]">lock_open</span>
              Unlocked
            </button>
          )}
          {isPublicLocked && (
            <button
              onClick={() => setShowCodeInput(true)}
              className="flex items-center gap-1 bg-amber-500/10 text-amber-400 px-2.5 py-1 rounded-full border border-amber-500/30 text-xs font-bold hover:bg-amber-500/20 transition-colors"
              title="Click to unlock workspace"
            >
              <span className="material-symbols-outlined text-[14px]">lock</span>
              Locked
            </button>
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

          {/* Notification Bell */}
          <button className="relative p-sm text-on-surface-variant hover:text-primary transition-colors">
            <span className="material-symbols-outlined text-[20px]">notifications</span>
            {sanctions && sanctions.length > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full" />
            )}
          </button>
        </div>
      </header>
    </>
  );
};

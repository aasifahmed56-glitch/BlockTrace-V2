import React, { useState, useRef } from 'react';
import { useInvestigation } from '../context/InvestigationContext';

export const Navigation = ({
  isLocked = false,
  onToggleLock,
  isMobileOpen = false,
  onCloseMobile,
}) => {
  const { activeTab, setActiveTab, summary } = useInvestigation();
  const [isHovered, setIsHovered] = useState(false);
  const hoverTimerRef = useRef(null);

  // Expanded if hovered, locked, or opened via mobile menu
  const isExpanded = isLocked || isHovered || isMobileOpen;

  const navItems = [
    { id: 'investigate', label: 'Investigate', icon: 'search_insights' },
    { id: 'findings', label: 'Findings', icon: 'rule' },
    { id: 'certificates', label: 'Certificates', icon: 'verified_user' },
    { id: 'cases-reports', label: 'Cases & Reports', icon: 'folder_shared' },
    { id: 'verify-report', label: 'Verify Report', icon: 'fact_check' },
  ];

  const handleMouseEnter = () => {
    // Check if device supports fine hover (desktop)
    if (window.matchMedia && !window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
      return;
    }
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
    }
    hoverTimerRef.current = setTimeout(() => {
      setIsHovered(false);
    }, 180);
  };

  const handleNavClick = (tabId) => {
    setActiveTab(tabId);
    if (isMobileOpen && onCloseMobile) {
      onCloseMobile();
    }
  };

  return (
    <aside
      id="main-sidebar"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`fixed left-0 top-0 h-full bg-inverse-surface text-inverse-on-surface z-50 flex flex-col shadow-xl transition-[width,transform] duration-300 ease-in-out select-none ${
        // Mobile visibility & width
        isMobileOpen
          ? 'translate-x-0 w-[280px] shadow-2xl'
          : 'max-md:-translate-x-full md:translate-x-0'
      } ${
        // Desktop width: 72px icon-only by default, 280px when hovered or locked
        isExpanded ? 'md:w-[280px] md:shadow-2xl' : 'md:w-[72px]'
      }`}
      aria-expanded={isExpanded}
    >
      {/* Brand Header */}
      <div className="h-16 px-3 flex items-center justify-between border-b border-on-surface-variant/20 shrink-0">
        <div
          className="flex items-center cursor-pointer group overflow-hidden"
          onClick={() => handleNavClick('landing')}
          title={!isExpanded ? "BlockTrace Forensic System - Return to Homepage" : "Return to Homepage"}
        >
          {/* Hub Icon Container */}
          <div className="w-10 h-10 rounded-lg bg-primary-container flex items-center justify-center text-white shadow-md group-hover:scale-105 transition-transform shrink-0">
            <span className="material-symbols-outlined text-[24px]">hub</span>
          </div>

          {/* Brand Text (Fades in when expanded) */}
          <div
            className={`flex flex-col ml-3 overflow-hidden whitespace-nowrap transition-all duration-200 ${
              isExpanded ? 'opacity-100 max-w-[150px]' : 'opacity-0 max-w-0 pointer-events-none'
            }`}
          >
            <span className="font-headline-md text-headline-md tracking-tight uppercase text-white font-bold leading-tight">
              BlockTrace
            </span>
            <span className="text-[10px] text-outline-variant uppercase tracking-widest font-semibold leading-tight">
              Forensic System
            </span>
          </div>
        </div>

        {/* Lock/Unlock Pin Button (Desktop) & Close Button (Mobile) */}
        {isExpanded && (
          <div className="flex items-center gap-1 shrink-0">
            {/* Desktop Pin Toggle */}
            <button
              id="sidebar-pin-btn"
              onClick={(e) => {
                e.stopPropagation();
                if (onToggleLock) onToggleLock();
              }}
              className={`hidden md:flex p-1.5 rounded-lg transition-colors items-center justify-center ${
                isLocked
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-on-surface-variant/70 hover:text-white hover:bg-white/10'
              }`}
              title={isLocked ? "Unlock sidebar (auto-collapse on hover)" : "Lock sidebar expanded"}
              aria-label={isLocked ? "Unlock sidebar" : "Lock sidebar expanded"}
            >
              <span className={`material-symbols-outlined text-[18px] ${isLocked ? 'rotate-45' : ''} transition-transform`}>
                push_pin
              </span>
            </button>

            {/* Mobile Close Button */}
            <button
              id="sidebar-close-btn"
              onClick={(e) => {
                e.stopPropagation();
                if (onCloseMobile) onCloseMobile();
              }}
              className="md:hidden p-1.5 rounded-lg text-on-surface-variant/70 hover:text-white hover:bg-white/10 active:scale-95 transition-all flex items-center justify-center"
              title="Close navigation menu"
              aria-label="Close navigation menu"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>
        )}
      </div>

      {/* Main Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto overflow-x-hidden">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => handleNavClick(item.id)}
              className={`w-full flex items-center h-11 px-2.5 rounded-lg transition-all text-left group relative ${
                isActive
                  ? 'bg-primary text-on-primary shadow-md font-bold'
                  : 'text-on-surface-variant hover:bg-white/10 hover:text-white font-medium'
              }`}
              title={!isExpanded ? item.label : undefined}
            >
              {/* Icon Container (fixed width to prevent layout shift) */}
              <span
                className={`material-symbols-outlined text-[22px] w-6 h-6 flex items-center justify-center shrink-0 transition-colors ${
                  isActive ? 'text-white' : 'text-on-surface-variant group-hover:text-white'
                }`}
              >
                {item.icon}
              </span>

              {/* Text Label */}
              <span
                className={`font-label-caps text-label-caps uppercase tracking-wider overflow-hidden whitespace-nowrap transition-all duration-200 ${
                  isExpanded
                    ? 'opacity-100 max-w-[150px] ml-3'
                    : 'opacity-0 max-w-0 ml-0 pointer-events-none'
                }`}
              >
                {item.label}
              </span>

              {/* Badges */}
              {item.id === 'investigate' && summary.wallets_traced > 0 && (
                <span
                  className={`text-[10px] font-address-md rounded-full transition-all duration-200 shrink-0 ${
                    isExpanded
                      ? 'px-2 py-0.5 ml-auto opacity-100'
                      : 'opacity-0 max-w-0 overflow-hidden'
                  } ${
                    isActive ? 'bg-black/30 text-white' : 'bg-white/10 text-on-surface-variant'
                  }`}
                >
                  {summary.wallets_traced}w
                </span>
              )}
            </button>
          );
        })}

        {/* Return to Landing Page Action */}
        <div className="pt-3 mt-3 border-t border-on-surface-variant/20">
          <button
            onClick={() => handleNavClick('landing')}
            className="w-full flex items-center h-10 px-2.5 rounded-lg text-on-surface-variant/70 hover:bg-white/5 hover:text-white transition-all text-xs group"
            title={!isExpanded ? "Product Overview" : undefined}
          >
            <span className="material-symbols-outlined text-[20px] w-6 h-6 flex items-center justify-center shrink-0 text-on-surface-variant/70 group-hover:text-white">
              arrow_back
            </span>
            <span
              className={`font-label-caps uppercase tracking-wider overflow-hidden whitespace-nowrap transition-all duration-200 ${
                isExpanded
                  ? 'opacity-100 max-w-[150px] ml-3'
                  : 'opacity-0 max-w-0 ml-0 pointer-events-none'
              }`}
            >
              Product Overview
            </span>
          </button>
        </div>
      </nav>

      {/* Investigator Profile */}
      <div
        className="mt-auto h-16 px-3 border-t border-on-surface-variant/20 flex items-center bg-black/10 hover:bg-black/20 transition-colors shrink-0 overflow-hidden"
        title={!isExpanded ? "Agent Forensics - Level 4 Investigator" : undefined}
      >
        <div className="w-10 h-10 rounded-full border-2 border-primary bg-surface-variant flex items-center justify-center text-on-surface-variant font-bold text-sm shrink-0">
          AF
        </div>
        <div
          className={`flex flex-col ml-3 overflow-hidden whitespace-nowrap transition-all duration-200 ${
            isExpanded ? 'opacity-100 max-w-[170px]' : 'opacity-0 max-w-0 pointer-events-none'
          }`}
        >
          <span className="font-body-sm text-body-sm text-white font-bold leading-tight">
            Agent Forensics
          </span>
          <span className="text-[10px] uppercase text-primary-fixed-dim tracking-widest font-bold leading-tight">
            Level 4 Investigator
          </span>
        </div>
      </div>
    </aside>
  );
};

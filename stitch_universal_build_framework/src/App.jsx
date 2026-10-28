import React, { useState, useEffect, useRef } from 'react';
import { InvestigationProvider, useInvestigation } from './context/InvestigationContext';
import { Navigation } from './components/Navigation';
import { Header } from './components/Header';
import { ToastContainer } from './components/Toast';
import { LandingScreen } from './screens/LandingScreen';
import { InvestigateScreen } from './screens/InvestigateScreen';
import { FindingsScreen } from './screens/FindingsScreen';
import { CertificatesScreen } from './screens/CertificatesScreen';
import { CasesScreen } from './screens/CasesScreen';
import { VerifyReportScreen } from './screens/VerifyReportScreen';

const MainLayout = () => {
  const { activeTab } = useInvestigation();

  // Sidebar lock (desktop) and mobile drawer state
  const [isLocked, setIsLocked] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  // Toggle sidebar via hamburger button
  const handleToggleSidebar = () => {
    const isMobile = window.innerWidth < 768;
    if (isMobile) {
      setIsMobileOpen((prev) => !prev);
    } else {
      setIsLocked((prev) => !prev);
    }
  };

  const handleToggleLock = () => {
    setIsLocked((prev) => !prev);
  };

  const handleCloseMobile = () => {
    setIsMobileOpen(false);
  };

  if (activeTab === 'landing') {
    return (
      <div className="w-full min-h-screen bg-surface">
        <LandingScreen />
        <ToastContainer />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface text-on-surface flex relative overflow-x-hidden">
      {/* Backdrop overlay when locked on desktop or open on mobile */}
      {(isLocked || isMobileOpen) && (
        <div
          id="sidebar-backdrop"
          className={`fixed inset-0 z-[45] transition-opacity duration-300 ${
            isMobileOpen ? 'bg-black/50 backdrop-blur-[2px]' : 'bg-black/20 backdrop-blur-[1px]'
          }`}
          onClick={() => {
            setIsLocked(false);
            setIsMobileOpen(false);
          }}
          aria-hidden="true"
        />
      )}

      {/* Collapsible Icon-Only Sidebar Navigation (Overlay when expanded) */}
      <Navigation
        isLocked={isLocked}
        onToggleLock={handleToggleLock}
        isMobileOpen={isMobileOpen}
        onCloseMobile={handleCloseMobile}
      />

      {/* Main Content Area (Stationary 72px left padding on desktop; never shifts on hover/expand) */}
      <div className="md:pl-[72px] w-full flex flex-col min-h-screen">
        <Header
          onToggleSidebar={handleToggleSidebar}
          isLocked={isLocked}
          isMobileOpen={isMobileOpen}
        />
        <main className="relative pt-16 bg-surface min-h-[calc(100vh-64px)] flex flex-col flex-1">
          {activeTab === 'investigate' && <InvestigateScreen />}
          {activeTab === 'findings' && <FindingsScreen />}
          {activeTab === 'certificates' && <CertificatesScreen />}
          {activeTab === 'cases-reports' && <CasesScreen />}
          {activeTab === 'verify-report' && <VerifyReportScreen />}
        </main>
      </div>

      {/* Global Toast Notifications */}
      <ToastContainer />
    </div>
  );
};

export function App() {
  return (
    <InvestigationProvider>
      <MainLayout />
    </InvestigationProvider>
  );
}

export default App;

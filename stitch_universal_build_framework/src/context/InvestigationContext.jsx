import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchChains,
  fetchCuratedCases,
  fetchGraphWithTotals,
  setShowZeroValue as setClientShowZeroValue,
  fetchSummary,
  fetchSanctionsWithSnapshot,
  fetchRiskOverview,
  fetchNarrative,
  fetchHubDetections,
  fetchFanoutDetections,
  fetchPeelDetections,
  fetchRoundDetections,
  fetchCircularDetections,
  checkHealth,
  clearGraph,
  getErrorMessage,
} from '../api/client';

const InvestigationContext = createContext(null);

export const InvestigationProvider = ({ children }) => {
  // Navigation
  const [activeTab, setActiveTab] = useState('investigate'); // 'landing' | 'investigate' | 'findings' | 'certificates' | 'cases-reports'

  // Server state
  const [serverWaking, setServerWaking] = useState(false);
  const [serverReady, setServerReady] = useState(false);
  // /health reports public_mode; the UI then shows the public-demo banner
  const [publicMode, setPublicMode] = useState(false);

  // Core Data
  const [chains, setChains] = useState(['Ethereum', 'BNB Smart Chain', 'Polygon']);
  const [curatedCases, setCuratedCases] = useState([]);
  const [edges, setEdges] = useState([]);
  const [summary, setSummary] = useState({ wallets_traced: 0, transactions_mapped: 0 });
  const [startWallet, setStartWallet] = useState('');

  // What the last trace covered (dates, order, cap) and which wallets hit the cap
  const [traceScope, setTraceScope] = useState(null);
  const [limitedWallets, setLimitedWallets] = useState([]);
  // Data quality of the last trace and of the graph as shown (see /summary)
  const [dataQuality, setDataQuality] = useState(null);
  const [graphTotals, setGraphTotals] = useState({ total: 0, returned: 0 });
  // "Show 0-ETH contract calls" — off by default; changes what every count includes
  const [showZeroValue, setShowZeroValueState] = useState(false);
  // "Include internal transfers" — applies to the next trace (shared by the Investigate
  // form and the phone overflow menu)
  const [includeInternal, setIncludeInternal] = useState(false);
  // Full-value sheet for a long address or hash on small screens
  const [addressSheet, setAddressSheet] = useState(null);
  
  // Path finding isolation state
  const [activePathEdges, setActivePathEdges] = useState(null);
  const [pathBannerMessage, setPathBannerMessage] = useState(null);

  // Findings data
  const [sanctions, setSanctions] = useState([]);
  const [sanctionsSnapshot, setSanctionsSnapshot] = useState(null);
  const [riskData, setRiskData] = useState([]);
  const [narrativeParagraphs, setNarrativeParagraphs] = useState([]);
  const [hubDetections, setHubDetections] = useState([]);
  const [fanoutDetections, setFanoutDetections] = useState([]);
  const [peelDetections, setPeelDetections] = useState([]);
  const [roundDetections, setRoundDetections] = useState([]);
  const [circularDetections, setCircularDetections] = useState([]);

  // Entity label lookup map (wallet -> label)
  const [entityLabels, setEntityLabels] = useState({});

  // Loading & Error States
  const [isLoadingGraph, setIsLoadingGraph] = useState(false);
  const [isLoadingFindings, setIsLoadingFindings] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Toast notification state
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // ==================== Server health check & wake-up ====================
  useEffect(() => {
    let cancelled = false;
    const wakeTimer = setTimeout(() => {
      if (!cancelled) setServerWaking(true);
    }, 5000);

    const doHealthCheck = async () => {
      try {
        let health;
        try {
          health = await checkHealth();
        } catch {
          // Retry once on network failure (Render cold start)
          if (cancelled) return;
          health = await checkHealth();
        }
        if (!cancelled) {
          setServerReady(true);
          setPublicMode(Boolean(health?.public_mode));
        }
      } catch (err) {
        if (!cancelled) console.error('Server health check failed after retry:', err);
      } finally {
        // Stop the banner timer too: a fast response must not let it fire afterwards.
        clearTimeout(wakeTimer);
        if (!cancelled) setServerWaking(false);
      }
    };

    doHealthCheck();
    return () => {
      cancelled = true;
      clearTimeout(wakeTimer);
    };
  }, []);

  // Fetch initial setup (chains & curated cases)
  useEffect(() => {
    const initSetup = async () => {
      try {
        const [chainList, caseList] = await Promise.allSettled([
          fetchChains(),
          fetchCuratedCases(),
        ]);
        if (chainList.status === 'fulfilled' && chainList.value?.length) {
          setChains(chainList.value);
        }
        if (caseList.status === 'fulfilled' && caseList.value?.length) {
          setCuratedCases(caseList.value);
        }
      } catch (err) {
        console.error('Failed to initialize metadata:', err);
      }
    };
    initSetup();
  }, []);

  // Refresh graph and summary
  const refreshGraphAndSummary = useCallback(async () => {
    setIsLoadingGraph(true);
    try {
      const [graph, summaryStats] = await Promise.all([
        fetchGraphWithTotals(),
        fetchSummary(),
      ]);
      const graphEdges = graph.edges;
      setEdges(graphEdges || []);
      setGraphTotals({ total: graph.totalEdges, returned: graph.returnedEdges });
      setDataQuality(summaryStats?.data_quality || null);
      setSummary(summaryStats || { wallets_traced: 0, transactions_mapped: 0 });
      setTraceScope(summaryStats?.scope || null);
      setLimitedWallets(summaryStats?.limited_wallets || []);
      
      // Update startWallet if not set and edges exist
      if (graphEdges && graphEdges.length > 0) {
        setStartWallet((prev) => prev || graphEdges[0].from);
      }
      return graphEdges;
    } catch (err) {
      console.error('Error fetching graph/summary:', err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setIsLoadingGraph(false);
    }
  }, [showToast]);

  // Refresh all findings data
  const refreshFindings = useCallback(async (customStartWallet) => {
    setIsLoadingFindings(true);
    try {
      const activeStart = customStartWallet || startWallet || (edges[0] ? edges[0].from : undefined);
      const [
        narrativeRes,
        sanctionsRes,
        riskRes,
        hubRes,
        fanoutRes,
        peelRes,
        roundRes,
        circularRes,
      ] = await Promise.allSettled([
        fetchNarrative(activeStart),
        fetchSanctionsWithSnapshot(),
        fetchRiskOverview(),
        fetchHubDetections(),
        fetchFanoutDetections(),
        fetchPeelDetections(),
        fetchRoundDetections(),
        fetchCircularDetections(),
      ]);

      if (narrativeRes.status === 'fulfilled') setNarrativeParagraphs(narrativeRes.value);
      if (sanctionsRes.status === 'fulfilled') {
        setSanctions(sanctionsRes.value.matches);
        setSanctionsSnapshot(sanctionsRes.value.snapshot);
      }
      if (riskRes.status === 'fulfilled') setRiskData(riskRes.value);
      if (hubRes.status === 'fulfilled') setHubDetections(hubRes.value);
      if (fanoutRes.status === 'fulfilled') setFanoutDetections(fanoutRes.value);
      if (peelRes.status === 'fulfilled') setPeelDetections(peelRes.value);
      if (roundRes.status === 'fulfilled') setRoundDetections(roundRes.value);
      if (circularRes.status === 'fulfilled') setCircularDetections(circularRes.value);

      // Collect known entity labels from detections
      const labelsMap = {};
      [hubRes, fanoutRes, peelRes, circularRes, riskRes].forEach((res) => {
        if (res.status === 'fulfilled' && Array.isArray(res.value)) {
          res.value.forEach((item) => {
            if (item.wallet && item.label) {
              labelsMap[item.wallet.toLowerCase()] = item.label;
            }
          });
        }
      });
      setEntityLabels(labelsMap);
    } catch (err) {
      console.error('Error fetching findings:', err);
    } finally {
      setIsLoadingFindings(false);
    }
  }, [startWallet, edges]);

  // Load everything on initial app mount
  useEffect(() => {
    refreshGraphAndSummary().then(() => {
      refreshFindings();
    });
  }, []);

  // When switching to Findings tab, ensure fresh findings are fetched
  useEffect(() => {
    if (activeTab === 'findings') {
      refreshFindings();
    }
  }, [activeTab, refreshFindings]);

  // Toggle 0-ETH calls: the header goes on every request, then everything reloads
  const setShowZeroValue = useCallback(async (on) => {
    setClientShowZeroValue(on);
    setShowZeroValueState(!!on);
    const graphEdges = await refreshGraphAndSummary();
    await refreshFindings(startWallet || (graphEdges && graphEdges[0] ? graphEdges[0].from : undefined));
  }, [refreshGraphAndSummary, refreshFindings, startWallet]);

  // Reset path filter
  const resetPathView = () => {
    setActivePathEdges(null);
    setPathBannerMessage(null);
  };

  // Clear the graph (Investigate toolbar and the phone overflow menu)
  const clearSession = async () => {
    setActionLoading(true);
    try {
      await clearGraph();
      resetPathView();
      setStartWallet('');
      await refreshGraphAndSummary();
      await refreshFindings();
      showToast('Graph and trace session cleared successfully.', 'info');
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Export graph as JSON
  const exportGraph = () => {
    const dataStr = JSON.stringify(edges, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `blocktrace_graph_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Graph exported as JSON file.', 'success');
  };

  const openAddressSheet = useCallback((address, label) => setAddressSheet(address ? { address, label } : null), []);
  const closeAddressSheet = useCallback(() => setAddressSheet(null), []);

  const value = {
    activeTab,
    setActiveTab,
    chains,
    curatedCases,
    edges,
    setEdges,
    summary,
    startWallet,
    setStartWallet,
    activePathEdges,
    setActivePathEdges,
    pathBannerMessage,
    setPathBannerMessage,
    resetPathView,
    sanctions,
    sanctionsSnapshot,
    traceScope,
    limitedWallets,
    dataQuality,
    graphTotals,
    showZeroValue,
    setShowZeroValue,
    riskData,
    narrativeParagraphs,
    hubDetections,
    fanoutDetections,
    peelDetections,
    roundDetections,
    circularDetections,
    entityLabels,
    isLoadingGraph,
    isLoadingFindings,
    actionLoading,
    setActionLoading,
    toasts,
    showToast,
    removeToast,
    refreshGraphAndSummary,
    refreshFindings,
    serverWaking,
    serverReady,
    publicMode,
    includeInternal,
    setIncludeInternal,
    clearSession,
    exportGraph,
    addressSheet,
    openAddressSheet,
    closeAddressSheet,
  };

  return (
    <InvestigationContext.Provider value={value}>
      {children}
    </InvestigationContext.Provider>
  );
};

export const useInvestigation = () => {
  const context = useContext(InvestigationContext);
  if (!context) {
    throw new Error('useInvestigation must be used within an InvestigationProvider');
  }
  return context;
};

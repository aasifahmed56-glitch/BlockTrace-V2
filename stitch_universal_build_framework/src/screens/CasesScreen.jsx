import React, { useState, useEffect } from 'react';
import { useInvestigation } from '../context/InvestigationContext';
import { ConfirmModal } from '../components/ConfirmModal';
import { describeScope } from '../utils/scope';
import {
  fetchSavedCases,
  saveCase,
  loadSavedCase,
  deleteSavedCase,
  getReportUrl,
  getErrorMessage,
  publishReport,
  retryAnchorCase,
  reanchorCase,
  verifyCaseOnChain,
} from '../api/client';

export const CasesScreen = () => {
  const {
    edges,
    startWallet,
    summary,
    sanctions,
    refreshGraphAndSummary,
    refreshFindings,
    showToast,
    actionLoading,
    setActionLoading,
  } = useInvestigation();

  const [savedCases, setSavedCases] = useState([]);
  const [isLoadingCases, setIsLoadingCases] = useState(false);
  const [newCaseName, setNewCaseName] = useState('');
  const [newCaseNumber, setNewCaseNumber] = useState('');
  const [caseNumberError, setCaseNumberError] = useState(null);
  const [anchorOnChain, setAnchorOnChain] = useState(true);
  const [isSavingCase, setIsSavingCase] = useState(false);

  // Verification & Retry state
  const [verifyingCaseNumber, setVerifyingCaseNumber] = useState(null);
  const [retryingCaseNumber, setRetryingCaseNumber] = useState(null);
  const [reanchoringCaseNumber, setReanchoringCaseNumber] = useState(null);
  const [verifyModalData, setVerifyModalData] = useState(null);

  // Confirmation Modals
  const [loadTargetCase, setLoadTargetCase] = useState(null);
  const [deleteTargetCase, setDeleteTargetCase] = useState(null);

  // Publish to IPFS + Sepolia state
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState(null);
  const [publishError, setPublishError] = useState(null);
  const [copiedField, setCopiedField] = useState(null);

  // Load Saved Cases List
  const loadCasesList = async () => {
    setIsLoadingCases(true);
    try {
      const cases = await fetchSavedCases();
      setSavedCases(cases || []);
    } catch (err) {
      console.error(err);
      showToast('Failed to retrieve saved cases', 'error');
    } finally {
      setIsLoadingCases(false);
    }
  };

  useEffect(() => {
    loadCasesList();
  }, []);

  const handleCaseNumberChange = (val) => {
    setNewCaseNumber(val);
    if (!val || !val.trim()) {
      setCaseNumberError(null);
      return;
    }
    const trimmed = val.trim();
    if (trimmed.length < 3 || trimmed.length > 32) {
      setCaseNumberError('Length must be between 3 and 32 characters');
    } else if (!/^[A-Za-z0-9_-]+$/.test(trimmed)) {
      setCaseNumberError('Allowed: letters, numbers, hyphens, underscores');
    } else {
      setCaseNumberError(null);
    }
  };

  // Handle Save Current Case
  const handleSaveCurrentCase = async (e) => {
    e.preventDefault();
    if (!newCaseName.trim()) {
      showToast('Please enter a case name.', 'warning');
      return;
    }
    if (newCaseNumber && newCaseNumber.trim()) {
      const trimmed = newCaseNumber.trim();
      if (trimmed.length < 3 || trimmed.length > 32 || !/^[A-Za-z0-9_-]+$/.test(trimmed)) {
        showToast('Please correct the Case Number format before saving.', 'error');
        return;
      }
    }
    if (edges.length === 0) {
      showToast('Nothing to save — the graph is empty.', 'error');
      return;
    }

    setIsSavingCase(true);
    setActionLoading(true);
    try {
      showToast(
        anchorOnChain
          ? `Saving case "${newCaseName}" and anchoring on Sepolia...`
          : `Saving case "${newCaseName}"...`,
        'info'
      );
      const res = await saveCase({
        name: newCaseName.trim(),
        case_number: newCaseNumber.trim() || undefined,
        start_wallet: startWallet || undefined,
        anchor_on_chain: anchorOnChain,
      });

      const caseNumStr = res.case_number ? `[${res.case_number}] ` : '';
      if (res.blockchain_status === 'anchored') {
        showToast(`Case ${caseNumStr}"${res.name}" saved and anchored on Sepolia!`, 'success');
      } else if (res.blockchain_status === 'failed') {
        showToast(`Case ${caseNumStr}"${res.name}" saved locally, but Sepolia anchor failed: ${res.chain_error || 'Network error'}`, 'warning');
      } else {
        showToast(`Case ${caseNumStr}"${res.name}" saved locally.`, 'success');
      }

      setNewCaseName('');
      setNewCaseNumber('');
      setCaseNumberError(null);
      await loadCasesList();
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setIsSavingCase(false);
      setActionLoading(false);
    }
  };

  // Handle Verify Case On-Chain
  const handleVerifyCase = async (caseNumber) => {
    if (!caseNumber || caseNumber === 'Legacy') {
      showToast('Legacy cases without a case number cannot be verified on-chain.', 'warning');
      return;
    }

    setVerifyingCaseNumber(caseNumber);
    try {
      showToast(`Verifying case ${caseNumber} against Sepolia contract...`, 'info');
      const res = await verifyCaseOnChain(caseNumber);
      setVerifyModalData(res);
      if (res.valid) {
        showToast(`✓ Case ${caseNumber} verified: Local SHA-256 matches on-chain record!`, 'success');
      } else {
        showToast(`⚠ Verification warning: ${res.error || res.details || 'Hash mismatch'}`, 'error');
      }
    } catch (err) {
      console.error(err);
      const msg = getErrorMessage(err);
      showToast(msg, 'error');
      setVerifyModalData({
        case_number: caseNumber,
        valid: false,
        error: msg,
      });
    } finally {
      setVerifyingCaseNumber(null);
    }
  };

  // Handle Retry Anchor Case
  const handleRetryAnchor = async (caseNumber) => {
    if (!caseNumber || caseNumber === 'Legacy') {
      showToast('Cannot anchor legacy case without assigning a case number.', 'warning');
      return;
    }

    setRetryingCaseNumber(caseNumber);
    try {
      showToast(`Retrying Sepolia anchor for ${caseNumber}...`, 'info');
      const res = await retryAnchorCase(caseNumber);
      showToast(`✓ Case ${caseNumber} successfully anchored on Sepolia! (Tx: ${res.tx_hash.slice(0, 10)}…)`, 'success');
      await loadCasesList();
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setRetryingCaseNumber(null);
    }
  };

  // Handle Re-anchor (with client-side AES-256-GCM encryption)
  const handleReanchor = async (caseNumber) => {
    if (!caseNumber || caseNumber === 'Legacy') {
      showToast('Cannot re-anchor legacy case without a valid case number.', 'warning');
      return;
    }

    setReanchoringCaseNumber(caseNumber);
    try {
      showToast(`Encrypting snapshot & re-anchoring ${caseNumber} on Sepolia...`, 'info');
      const res = await reanchorCase(caseNumber);
      showToast(`✓ Case ${caseNumber} re-anchored with AES-256-GCM encryption! (Version v${res.version || '2'})`, 'success');
      await loadCasesList();
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setReanchoringCaseNumber(null);
    }
  };

  // Handle Confirm Load Case
  const handleConfirmLoad = async () => {
    if (!loadTargetCase) return;
    const caseName = loadTargetCase;
    setLoadTargetCase(null);
    setActionLoading(true);

    try {
      showToast(`Loading case "${caseName}"...`, 'info');
      const res = await loadSavedCase(caseName);
      await refreshGraphAndSummary();
      await refreshFindings(res.start_wallet);
      const scopeLine = describeScope(res.scope);
      showToast(
        `Case "${caseName}" loaded successfully (${res.edge_count} edges).` +
          (scopeLine ? ` Scope: ${scopeLine}. The Investigate form now uses this window.` : ''),
        'success'
      );
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Confirm Delete Case
  const handleConfirmDelete = async () => {
    if (!deleteTargetCase) return;
    const caseName = deleteTargetCase;
    setDeleteTargetCase(null);
    setActionLoading(true);

    try {
      showToast(`Deleting case "${caseName}"...`, 'info');
      await deleteSavedCase(caseName);
      showToast(`Case "${caseName}" deleted.`, 'info');
      await loadCasesList();
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Publish to IPFS + Sepolia
  const handlePublish = async () => {
    setIsPublishing(true);
    setPublishResult(null);
    setPublishError(null);
    try {
      showToast('Publishing report to IPFS & Sepolia…', 'info');
      const result = await publishReport(startWallet || undefined);
      setPublishResult(result);
      if (result.chain_error) {
        showToast(result.chain_error, 'warning');
      } else {
        showToast('Report published to IPFS and recorded on Sepolia!', 'success');
      }
    } catch (err) {
      console.error(err);
      const msg = getErrorMessage(err);
      setPublishError(msg);
      showToast(msg, 'error');
    } finally {
      setIsPublishing(false);
    }
  };

  const copyToClipboard = (text, fieldName) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedField(fieldName);
      setTimeout(() => setCopiedField(null), 2000);
    });
  };

  return (
    <div className="flex flex-col w-full px-xl py-lg gap-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="pb-4 border-b border-outline-variant/50">
        <h1 className="font-headline-lg text-3xl font-bold text-on-surface mb-2">
          Cases & Forensic Reports
        </h1>
        <p className="font-body-md text-sm text-on-surface-variant max-w-2xl">
          Archive, restore, and generate official audit-ready documentation for ongoing crypto crime investigations.
        </p>
      </div>

      {/* Investigation Report Card */}
      <section className="flex flex-col gap-3">
        <h2 className="font-headline-md text-xl font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-[22px]">description</span>
          <span>Investigation Dossier Report</span>
        </h2>

        <div className="bg-surface-container rounded-2xl shadow-md p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border border-outline-variant/60 relative overflow-hidden">
          <div className="flex flex-col gap-2 relative z-10">
            <h3 className="font-headline-md text-lg font-bold text-on-surface">
              Active Case Summary Export
            </h3>
            <p className="font-body-md text-xs text-on-surface-variant max-w-2xl leading-relaxed">
              Comprehensive report detailing tracked addresses, heuristic detection breakdown, high-risk sanctions hits, and cryptographic verification status.
            </p>

            <div className="flex items-center gap-3 mt-2">
              <span
                className={`inline-flex items-center gap-1 px-3 py-1 rounded-full font-label-caps text-xs font-bold ${
                  sanctions.length > 0
                    ? 'bg-error/15 text-error border border-error/30'
                    : 'bg-[#e8f5e9] text-[#2e682c]'
                }`}
              >
                <span className="material-symbols-outlined text-[14px]">
                  {sanctions.length > 0 ? 'warning' : 'verified'}
                </span>
                <span>{sanctions.length > 0 ? `${sanctions.length} Sanction Flags` : 'Clean Sanctions'}</span>
              </span>

              <span className="inline-flex items-center gap-1 px-3 py-1 bg-surface text-on-surface rounded-full font-label-caps text-xs font-bold border border-outline-variant/60">
                <span className="material-symbols-outlined text-[14px]">account_tree</span>
                <span>{summary.wallets_traced} Wallets · {summary.transactions_mapped} Txs</span>
              </span>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 relative z-10 shrink-0">
            <a
              href={getReportUrl(startWallet)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 px-6 py-3 bg-primary text-white hover:bg-primary-container transition-all font-label-caps text-xs uppercase rounded-xl shadow-md hover:shadow-lg font-bold"
            >
              <span className="material-symbols-outlined text-[18px]">download</span>
              <span>Download PDF Report</span>
            </a>
            <button
              onClick={handlePublish}
              disabled={isPublishing || edges.length === 0}
              className="flex items-center justify-center gap-2 px-6 py-3 bg-tertiary text-white hover:bg-tertiary/80 transition-all font-label-caps text-xs uppercase rounded-xl shadow-md hover:shadow-lg font-bold disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPublishing ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Publishing…</span>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-[18px]">cloud_upload</span>
                  <span>Publish to IPFS + Sepolia</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Publish Result Card */}
        {publishResult && (
          <div className="bg-surface-container rounded-2xl shadow-md p-5 border border-outline-variant/60 mt-4">
            <h4 className="font-headline-md text-sm font-bold text-on-surface flex items-center gap-2 mb-4">
              <span className="material-symbols-outlined text-tertiary text-[20px]">verified</span>
              Published Successfully
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Investigation Hash */}
              <div className="bg-surface rounded-lg p-3 border border-outline-variant/40">
                <span className="font-label-caps text-[10px] text-on-surface-variant uppercase block mb-1">Investigation Hash</span>
                <div className="flex items-center gap-2">
                  <span className="font-address-md text-[11px] text-on-surface font-mono truncate flex-1">{publishResult.investigation_hash}</span>
                  <button onClick={() => copyToClipboard(publishResult.investigation_hash, 'hash')} className="p-1 hover:bg-surface-variant rounded transition-colors shrink-0" title="Copy">
                    <span className="material-symbols-outlined text-[16px] text-on-surface-variant">{copiedField === 'hash' ? 'check' : 'content_copy'}</span>
                  </button>
                </div>
              </div>
              {/* IPFS CID */}
              <div className="bg-surface rounded-lg p-3 border border-outline-variant/40">
                <span className="font-label-caps text-[10px] text-on-surface-variant uppercase block mb-1">IPFS CID</span>
                <div className="flex items-center gap-2">
                  <a href={publishResult.gateway_url} target="_blank" rel="noopener noreferrer" className="font-address-md text-[11px] text-primary hover:underline font-mono truncate flex-1">{publishResult.cid}</a>
                  <button onClick={() => copyToClipboard(publishResult.cid, 'cid')} className="p-1 hover:bg-surface-variant rounded transition-colors shrink-0" title="Copy">
                    <span className="material-symbols-outlined text-[16px] text-on-surface-variant">{copiedField === 'cid' ? 'check' : 'content_copy'}</span>
                  </button>
                </div>
              </div>
              {/* Sepolia Tx */}
              {publishResult.tx_hash && (
                <div className="bg-surface rounded-lg p-3 border border-outline-variant/40 md:col-span-2">
                  <span className="font-label-caps text-[10px] text-on-surface-variant uppercase block mb-1">Sepolia Transaction</span>
                  <div className="flex items-center gap-2">
                    <a href={publishResult.explorer_url} target="_blank" rel="noopener noreferrer" className="font-address-md text-[11px] text-primary hover:underline font-mono truncate flex-1">{publishResult.tx_hash}</a>
                    <button onClick={() => copyToClipboard(publishResult.tx_hash, 'tx')} className="p-1 hover:bg-surface-variant rounded transition-colors shrink-0" title="Copy">
                      <span className="material-symbols-outlined text-[16px] text-on-surface-variant">{copiedField === 'tx' ? 'check' : 'content_copy'}</span>
                    </button>
                  </div>
                  {publishResult.block_number && (
                    <span className="font-label-caps text-[10px] text-on-surface-variant mt-1 block">Block #{publishResult.block_number}</span>
                  )}
                </div>
              )}
              {/* Chain warning (e.g. duplicate hash) */}
              {publishResult.chain_error && (
                <div className="bg-[#fff3e0] rounded-lg p-3 border border-[#ffcc80] md:col-span-2 flex items-start gap-2">
                  <span className="material-symbols-outlined text-[#e65100] text-[18px] mt-0.5 shrink-0">warning</span>
                  <span className="text-[11px] text-[#e65100] leading-relaxed">{publishResult.chain_error}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Publish Error Card */}
        {publishError && !publishResult && (
          <div className="bg-error/5 rounded-2xl shadow-md p-5 border border-error/30 mt-4 flex items-start gap-3">
            <span className="material-symbols-outlined text-error text-[20px] mt-0.5 shrink-0">error</span>
            <div>
              <h4 className="font-headline-md text-sm font-bold text-error mb-1">Publish Failed</h4>
              <p className="text-xs text-on-surface-variant leading-relaxed">{publishError}</p>
            </div>
          </div>
        )}
      </section>

      {/* Saved Investigation Cases Section */}
      <section className="flex flex-col gap-4 mt-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <h2 className="font-headline-md text-xl font-bold text-on-surface flex items-center gap-2">
              <span className="material-symbols-outlined text-tertiary text-[22px]">folder_shared</span>
              <span>Saved Investigation Cases</span>
            </h2>
            <span className="bg-surface-variant text-on-surface-variant px-2.5 py-0.5 rounded-full font-label-caps text-[10px] font-bold">
              {savedCases.length} TOTAL
            </span>
          </div>

          {/* Save Current Case Form */}
          <form onSubmit={handleSaveCurrentCase} className="flex flex-col gap-2 w-full lg:w-auto">
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={newCaseNumber}
                onChange={(e) => handleCaseNumberChange(e.target.value)}
                placeholder="Case # (e.g. BT-2026-0001, optional)"
                className={`bg-surface text-on-surface border ${caseNumberError ? 'border-error' : 'border-outline-variant'} focus:ring-1 focus:ring-primary text-xs px-3.5 py-2 rounded-lg outline-none w-full sm:w-48 font-mono shadow-xs`}
              />
              <input
                type="text"
                value={newCaseName}
                onChange={(e) => setNewCaseName(e.target.value)}
                placeholder="Enter case name..."
                className="bg-surface text-on-surface border border-outline-variant focus:ring-1 focus:ring-primary text-xs px-3.5 py-2 rounded-lg outline-none w-full sm:w-56 font-medium shadow-xs"
              />
              <button
                type="submit"
                disabled={isSavingCase || actionLoading || edges.length === 0 || !!caseNumberError}
                className="flex items-center gap-1.5 px-4 py-2 bg-primary text-white hover:bg-primary-container transition-colors font-label-caps text-xs uppercase rounded-lg shadow-sm whitespace-nowrap font-bold disabled:opacity-50"
              >
                {isSavingCase ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Saving…</span>
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-[16px]">save</span>
                    <span>Save Case</span>
                  </>
                )}
              </button>
            </div>

            <div className="flex items-center justify-between sm:justify-start gap-4 px-1">
              {caseNumberError ? (
                <span className="text-[11px] text-error font-medium flex items-center gap-1">
                  <span className="material-symbols-outlined text-[14px]">error</span>
                  {caseNumberError}
                </span>
              ) : (
                <span className="text-[10px] text-on-surface-variant italic">
                  Leave Case # empty to auto-generate (e.g. BT-2026-0001).
                </span>
              )}

              <label className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={anchorOnChain}
                  onChange={(e) => setAnchorOnChain(e.target.checked)}
                  className="rounded border-outline-variant text-primary focus:ring-primary h-3.5 w-3.5"
                />
                <span className="text-[11px] text-on-surface-variant font-medium">Anchor on Sepolia</span>
              </label>
            </div>
          </form>
        </div>

        {/* Data Table */}
        <div className="bg-surface rounded-2xl shadow-md border border-outline-variant/60 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container text-on-surface-variant border-b border-outline-variant font-label-caps text-[11px] uppercase tracking-wider">
                  <th className="p-4 font-bold">Case #</th>
                  <th className="p-4 font-bold">Case Name</th>
                  <th className="p-4 font-bold">Date Saved</th>
                  <th className="p-4 font-bold">Edges</th>
                  <th className="p-4 font-bold">Blockchain Status</th>
                  <th className="p-4 font-bold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="font-body-sm text-xs text-on-surface divide-y divide-outline-variant/40">
                {isLoadingCases ? (
                  <tr>
                    <td colSpan="6" className="p-8 text-center text-on-surface-variant">
                      <div className="inline-flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                        <span>Loading cases...</span>
                      </div>
                    </td>
                  </tr>
                ) : savedCases.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="p-8 text-center text-on-surface-variant italic">
                      No saved investigation cases found. Enter a name above to save the current session.
                    </td>
                  </tr>
                ) : (
                  savedCases.map((c) => (
                    <tr
                      key={c.case_number && c.case_number !== 'Legacy' ? c.case_number : c.name}
                      className="hover:bg-surface-container-low transition-colors group"
                    >
                      {/* Case Number */}
                      <td className="p-4 whitespace-nowrap">
                        {c.case_number === 'Legacy' ? (
                          <span className="px-2 py-0.5 rounded text-[10px] bg-surface-variant text-on-surface-variant font-mono">
                            Legacy
                          </span>
                        ) : (
                          <span className="font-mono text-primary font-bold text-xs bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                            {c.case_number}
                          </span>
                        )}
                      </td>

                      {/* Case Name */}
                      <td className="p-4 font-semibold text-on-surface">
                        <div className="flex items-center gap-2">
                          <span className="material-symbols-outlined text-primary text-[18px]">
                            folder_open
                          </span>
                          <div className="flex flex-col">
                            <span>{c.name}</span>
                            <span
                              className="text-[10px] font-normal text-on-surface-variant font-address-md"
                              title={c.scope?.date_note || ''}
                            >
                              {describeScope(c.scope) || 'Scope not recorded'}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Date */}
                      <td className="p-4 text-on-surface-variant font-address-md text-[11px] whitespace-nowrap">
                        {c.saved_at ? c.saved_at.replace('T', ' ').slice(0, 19) : 'Recently Saved'}
                      </td>

                      {/* Edges */}
                      <td className="p-4 font-address-md font-mono text-on-surface-variant whitespace-nowrap">
                        {c.edge_count} edges
                      </td>

                      {/* Blockchain Status */}
                      <td className="p-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          {c.blockchain_status === 'anchored' ? (
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-[#e8f5e9] text-[#2e682c] border border-[#a5d6a7]">
                                <span className="material-symbols-outlined text-[13px]">verified</span>
                                <span>Anchored {c.version ? `v${c.version}` : ''}</span>
                              </span>
                              {c.encrypted ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#e0f2fe] text-[#0369a1] border border-[#bae6fd]" title="Client-side AES-256-GCM encrypted snapshot">
                                  <span className="material-symbols-outlined text-[12px]">lock</span>
                                  <span>Encrypted</span>
                                </span>
                              ) : (
                                c.case_number !== 'Legacy' && (
                                  <button
                                    onClick={() => handleReanchor(c.case_number)}
                                    disabled={reanchoringCaseNumber === c.case_number}
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-tertiary/10 text-tertiary hover:bg-tertiary/20 border border-tertiary/30 transition-colors disabled:opacity-50"
                                    title="Encrypt snapshot and re-anchor new version on Sepolia"
                                  >
                                    <span className="material-symbols-outlined text-[12px]">
                                      {reanchoringCaseNumber === c.case_number ? 'sync' : 'lock_reset'}
                                    </span>
                                    <span>{reanchoringCaseNumber === c.case_number ? 'Re-anchoring…' : 'Re-anchor (encrypted)'}</span>
                                  </button>
                                )
                              )}
                            </div>
                          ) : c.blockchain_status === 'failed' ? (
                            <div className="flex items-center gap-1.5">
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-error/15 text-error border border-error/30" title={c.chain_error || 'Anchor failed'}>
                                <span className="material-symbols-outlined text-[13px]">warning</span>
                                <span>Failed</span>
                              </span>
                              {c.case_number !== 'Legacy' && (
                                <button
                                  onClick={() => handleRetryAnchor(c.case_number)}
                                  disabled={retryingCaseNumber === c.case_number}
                                  className="text-[10px] text-primary hover:underline font-bold disabled:opacity-50"
                                >
                                  {retryingCaseNumber === c.case_number ? 'Retrying…' : 'Retry'}
                                </button>
                              )}
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5">
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-surface-variant text-on-surface-variant">
                                <span>Not Anchored</span>
                              </span>
                              {c.case_number !== 'Legacy' && (
                                <button
                                  onClick={() => handleRetryAnchor(c.case_number)}
                                  disabled={retryingCaseNumber === c.case_number}
                                  className="text-[10px] text-primary hover:underline font-bold disabled:opacity-50"
                                >
                                  {retryingCaseNumber === c.case_number ? 'Anchoring…' : 'Anchor'}
                                </button>
                              )}
                            </div>
                          )}

                          {/* Quick links to IPFS & Explorer if available */}
                          {c.cid && (
                            <a
                              href={c.ipfs_gateway_url || `https://gateway.pinata.cloud/ipfs/${c.cid}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-1 hover:text-primary text-on-surface-variant rounded"
                              title="View IPFS Snapshot"
                            >
                              <span className="material-symbols-outlined text-[15px]">cloud</span>
                            </a>
                          )}
                          {c.tx_hash && (
                            <a
                              href={c.explorer_url || `https://sepolia.etherscan.io/tx/${c.tx_hash}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-1 hover:text-primary text-on-surface-variant rounded"
                              title="View on Sepolia Etherscan"
                            >
                              <span className="material-symbols-outlined text-[15px]">open_in_new</span>
                            </a>
                          )}
                        </div>
                      </td>

                      {/* Actions */}
                      <td className="p-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">
                          {c.case_number && c.case_number !== 'Legacy' && (
                            <button
                              onClick={() => handleVerifyCase(c.case_number)}
                              disabled={verifyingCaseNumber === c.case_number}
                              className="px-2.5 py-1 rounded bg-surface hover:bg-tertiary/10 text-tertiary border border-tertiary/40 font-label-caps text-[10px] uppercase font-bold transition-colors flex items-center gap-1 disabled:opacity-50"
                              title="Verify against Sepolia contract"
                            >
                              {verifyingCaseNumber === c.case_number ? (
                                <div className="w-3 h-3 border border-tertiary border-t-transparent rounded-full animate-spin" />
                              ) : (
                                <span className="material-symbols-outlined text-[14px]">shield</span>
                              )}
                              <span>Verify</span>
                            </button>
                          )}
                          <button
                            onClick={() => setLoadTargetCase(c.name)}
                            className="px-3 py-1 rounded bg-surface hover:bg-primary/10 text-primary border border-primary/40 font-label-caps text-[10px] uppercase font-bold transition-colors flex items-center gap-1"
                            title="Load this case into workspace"
                          >
                            <span className="material-symbols-outlined text-[14px]">file_open</span>
                            <span>Load</span>
                          </button>
                          <button
                            onClick={() => setDeleteTargetCase(c.name)}
                            className="p-1.5 text-error/70 hover:text-error hover:bg-error/10 rounded transition-colors"
                            title="Delete Case"
                          >
                            <span className="material-symbols-outlined text-[18px]">delete</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Verification Result Modal */}
      {verifyModalData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-surface rounded-2xl shadow-2xl border border-outline-variant max-w-lg w-full p-6 animate-scale-in">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
              <h3 className="font-headline-md text-base font-bold text-on-surface flex items-center gap-2">
                <span className={`material-symbols-outlined ${verifyModalData.valid ? 'text-[#2e682c]' : 'text-error'} text-[22px]`}>
                  {verifyModalData.valid ? 'verified' : 'warning'}
                </span>
                <span>Case Integrity Verification: {verifyModalData.case_number}</span>
              </h3>
              <button
                onClick={() => setVerifyModalData(null)}
                className="p-1 text-on-surface-variant hover:text-on-surface rounded-md"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>

            <div className="my-4">
              {verifyModalData.encrypted && (
                <div className="bg-[#e0f2fe] border border-[#bae6fd] rounded-xl p-3 text-[#0369a1] mb-3 flex items-start gap-2">
                  <span className="material-symbols-outlined text-[18px] shrink-0 mt-0.5">lock</span>
                  <div>
                    <p className="font-bold text-xs">CLIENT-SIDE AES-256-GCM ENCRYPTED</p>
                    <p className="text-[11px] leading-relaxed">
                      This snapshot was encrypted before IPFS upload using a case-derived key. Verification downloaded the payload from IPFS, decrypted it, and confirmed that the local, on-chain, and decrypted SHA-256 digests all match.
                    </p>
                  </div>
                </div>
              )}

              {verifyModalData.valid ? (
                <div className="bg-[#e8f5e9] border border-[#a5d6a7] rounded-xl p-3.5 mb-4 text-[#2e682c]">
                  <p className="font-bold text-xs flex items-center gap-1.5 mb-1">
                    <span className="material-symbols-outlined text-[16px]">check_circle</span>
                    CRYPTOGRAPHIC INTEGRITY CONFIRMED
                  </p>
                  <p className="text-[11px] leading-relaxed">
                    The SHA-256 fingerprint of the local case investigation snapshot matches the on-chain cryptographic anchor stored on Sepolia testnet.
                  </p>
                </div>
              ) : (
                <div className="bg-error/10 border border-error/30 rounded-xl p-3.5 mb-4 text-error">
                  <p className="font-bold text-xs flex items-center gap-1.5 mb-1">
                    <span className="material-symbols-outlined text-[16px]">cancel</span>
                    VERIFICATION FAILED / NOT ANCHORED
                  </p>
                  <p className="text-[11px] leading-relaxed">
                    {verifyModalData.error || verifyModalData.details || 'The local case hash does not match the record on Sepolia.'}
                  </p>
                </div>
              )}

              <div className="space-y-2.5 text-xs">
                {verifyModalData.local_hash && (
                  <div className="bg-surface-container rounded-lg p-2.5 border border-outline-variant/40">
                    <span className="font-label-caps text-[10px] text-on-surface-variant uppercase block mb-0.5">Local SHA-256 Digest</span>
                    <span className="font-mono text-[11px] text-on-surface break-all">{verifyModalData.local_hash}</span>
                  </div>
                )}
                {verifyModalData.on_chain_hash && (
                  <div className="bg-surface-container rounded-lg p-2.5 border border-outline-variant/40">
                    <span className="font-label-caps text-[10px] text-on-surface-variant uppercase block mb-0.5">Sepolia On-Chain Digest</span>
                    <span className="font-mono text-[11px] text-on-surface break-all">{verifyModalData.on_chain_hash}</span>
                  </div>
                )}
                {verifyModalData.decrypted_hash && (
                  <div className="bg-surface-container rounded-lg p-2.5 border border-[#bae6fd]">
                    <span className="font-label-caps text-[10px] text-[#0369a1] uppercase block mb-0.5">Decrypted IPFS Payload SHA-256</span>
                    <span className="font-mono text-[11px] text-[#0369a1] break-all">{verifyModalData.decrypted_hash}</span>
                  </div>
                )}
                {verifyModalData.version && (
                  <div className="flex items-center justify-between bg-surface-container rounded-lg p-2.5 border border-outline-variant/40">
                    <span className="font-label-caps text-[10px] text-on-surface-variant uppercase">Contract Version</span>
                    <span className="font-bold text-xs text-primary">v{verifyModalData.version}</span>
                  </div>
                )}
                {verifyModalData.submitter && (
                  <div className="bg-surface-container rounded-lg p-2.5 border border-outline-variant/40">
                    <span className="font-label-caps text-[10px] text-on-surface-variant uppercase block mb-0.5">Submitter Address</span>
                    <span className="font-mono text-[11px] text-on-surface break-all">{verifyModalData.submitter}</span>
                  </div>
                )}
                {verifyModalData.on_chain_cid && (
                  <div className="bg-surface-container rounded-lg p-2.5 border border-outline-variant/40">
                    <span className="font-label-caps text-[10px] text-on-surface-variant uppercase block mb-0.5">IPFS CID</span>
                    <span className="font-mono text-[11px] text-on-surface break-all">{verifyModalData.on_chain_cid}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setVerifyModalData(null)}
                className="px-4 py-2 bg-primary text-white rounded-lg font-label-caps text-xs uppercase font-bold hover:bg-primary-container transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal for Loading Case */}
      <ConfirmModal
        isOpen={!!loadTargetCase}
        title={`Load Case "${loadTargetCase}"?`}
        message="Loading this case will replace the entire current transaction graph and analysis session. Make sure you have saved any current work."
        confirmText="Load Case"
        confirmVariant="primary"
        onConfirm={handleConfirmLoad}
        onCancel={() => setLoadTargetCase(null)}
      />

      {/* Confirmation Modal for Deleting Case */}
      <ConfirmModal
        isOpen={!!deleteTargetCase}
        title={`Delete Case "${deleteTargetCase}"?`}
        message="Are you sure you want to permanently delete this saved investigation case? This cannot be undone."
        confirmText="Delete Case"
        confirmVariant="danger"
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteTargetCase(null)}
      />
    </div>
  );
};

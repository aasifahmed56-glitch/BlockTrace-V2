import React, { useState, useRef } from 'react';
import { verifyReport, getErrorMessage } from '../api/client';
import { useInvestigation } from '../context/InvestigationContext';

export const VerifyReportScreen = () => {
  const { showToast } = useInvestigation();

  const [file, setFile] = useState(null);
  const [investigationHash, setInvestigationHash] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [copiedKey, setCopiedKey] = useState(null);

  const fileInputRef = useRef(null);

  const handleCopy = (text, key) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    showToast('Copied to clipboard!', 'info');
    setTimeout(() => {
      setCopiedKey(null);
    }, 2000);
  };

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0];
    if (selected) {
      if (!selected.name.toLowerCase().endsWith('.pdf') && selected.type !== 'application/pdf') {
        showToast('Please select a valid PDF file.', 'error');
        return;
      }
      setFile(selected);
      setResult(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      if (!droppedFile.name.toLowerCase().endsWith('.pdf') && droppedFile.type !== 'application/pdf') {
        showToast('Please drop a valid PDF file.', 'error');
        return;
      }
      setFile(droppedFile);
      setResult(null);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    if (!file) {
      showToast('Please upload a PDF report to verify.', 'warning');
      return;
    }

    setIsLoading(true);
    setResult(null);

    try {
      showToast('Querying Sepolia blockchain & verifying IPFS artifact...', 'info');
      const data = await verifyReport({
        file,
        investigationHash: investigationHash.trim() || undefined,
      });
      setResult(data);

      if (data.status === 'authentic') {
        showToast('Report verified: Cryptographic integrity confirmed!', 'success');
      } else if (data.status === 'tampered') {
        showToast('Warning: Cryptographic fingerprint mismatch detected!', 'error');
      } else if (data.status === 'not_found') {
        showToast('No record found on Sepolia for this investigation hash.', 'warning');
      } else if (data.status === 'unavailable') {
        showToast('On-chain record found, but IPFS artifact was unreachable.', 'warning');
      }
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setInvestigationHash('');
    setResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="flex-1 w-full max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
            <span className="material-symbols-outlined text-[24px]">verified</span>
          </div>
          <div>
            <h1 className="font-headline-md text-2xl font-bold tracking-tight text-on-surface uppercase">
              Verify Investigation Report
            </h1>
            <p className="text-xs text-on-surface-variant font-medium">
              Public decentralized verification against Ethereum Sepolia on-chain registry &amp; IPFS storage
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Verification Form (Left Column) */}
        <div className="lg:col-span-5 space-y-6">
          <form onSubmit={handleVerify} className="bg-surface-container-lowest border border-outline-variant/60 rounded-2xl p-6 shadow-sm space-y-5">
            <div className="flex items-center justify-between border-b border-outline-variant/30 pb-3">
              <span className="font-label-caps text-xs font-bold uppercase tracking-wider text-on-surface">
                Report Document &amp; Hash
              </span>
              {file && (
                <button
                  type="button"
                  onClick={handleReset}
                  className="text-xs text-on-surface-variant hover:text-error transition-colors flex items-center gap-1 font-semibold"
                >
                  <span className="material-symbols-outlined text-[15px]">refresh</span>
                  Clear
                </button>
              )}
            </div>

            {/* Drag & Drop PDF Dropzone */}
            <div>
              <label className="block text-xs font-label-caps uppercase font-bold text-on-surface-variant mb-2">
                Forensic Report (PDF) <span className="text-primary">*</span>
              </label>

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleFileChange}
                className="hidden"
                id="pdf-upload-input"
              />

              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-2 ${
                  isDragOver
                    ? 'border-primary bg-primary/5 scale-[0.99]'
                    : file
                    ? 'border-primary/60 bg-surface-container-low'
                    : 'border-outline-variant hover:border-primary/50 hover:bg-surface-container-lowest'
                }`}
              >
                <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${
                  file ? 'bg-primary text-white' : 'bg-surface-container text-on-surface-variant'
                }`}>
                  <span className="material-symbols-outlined text-[26px]">
                    {file ? 'picture_as_pdf' : 'upload_file'}
                  </span>
                </div>

                {file ? (
                  <div className="space-y-1 mt-1 max-w-full px-2">
                    <p className="font-bold text-xs text-on-surface truncate">
                      {file.name}
                    </p>
                    <p className="text-[11px] text-on-surface-variant">
                      {(file.size / 1024 / 1024).toFixed(2)} MB &bull; Ready for verification
                    </p>
                    <span className="inline-block mt-1 text-[11px] text-primary font-bold underline">
                      Click or drop to replace
                    </span>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-xs font-bold text-on-surface">
                      Drag &amp; drop PDF report here, or <span className="text-primary underline">browse</span>
                    </p>
                    <p className="text-[11px] text-on-surface-variant">
                      Max file size: 25 MB &bull; Genuine BlockTrace PDF report
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Investigation Hash Input */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-label-caps uppercase font-bold text-on-surface-variant">
                  Investigation Hash
                </label>
                <span className="text-[10px] text-on-surface-variant/70 italic">
                  Optional (Auto-detects from PDF)
                </span>
              </div>
              <input
                type="text"
                value={investigationHash}
                onChange={(e) => setInvestigationHash(e.target.value)}
                placeholder="0fa8e52b42f3a7208143d7ad31dc235be45e5b36c2ff49594698bb3aa2c0fdc2"
                className="w-full px-3.5 py-2.5 text-xs font-mono bg-surface border border-outline-variant rounded-lg focus:outline-hidden focus:border-primary focus:ring-1 focus:ring-primary text-on-surface placeholder:text-on-surface-variant/40"
              />
              <p className="mt-1.5 text-[10px] text-on-surface-variant leading-relaxed">
                Enter the 64-character SHA-256 hex hash from your certificate or report. If left blank, the system will attempt to detect it inside the PDF text.
              </p>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={!file || isLoading}
              className={`w-full py-3 px-4 rounded-xl font-label-caps text-xs uppercase font-bold tracking-wider transition-all flex items-center justify-center gap-2 shadow-sm ${
                !file || isLoading
                  ? 'bg-outline-variant/40 text-on-surface-variant/50 cursor-not-allowed'
                  : 'bg-primary text-white hover:bg-primary-container hover:shadow-md active:scale-[0.99]'
              }`}
            >
              {isLoading ? (
                <>
                  <span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>
                  <span>Verifying On-Chain...</span>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-[18px]">verified_user</span>
                  <span>Verify Report Integrity</span>
                </>
              )}
            </button>
          </form>

          {/* Verification Protocol Explainer */}
          <div className="bg-surface-container-low border border-outline-variant/40 rounded-2xl p-5 text-xs text-on-surface-variant space-y-2.5">
            <h3 className="font-label-caps font-bold text-[11px] uppercase tracking-wider text-on-surface flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px] text-primary">security</span>
              How Verification Works
            </h3>
            <ol className="list-decimal list-inside space-y-1.5 text-[11px] leading-relaxed">
              <li>Reads the official cryptographic record anchored on Ethereum Sepolia via smart contract.</li>
              <li>Retrieves the canonical report archive pinned to IPFS.</li>
              <li>Calculates SHA-256 checksums locally and confirms zero-trust authenticity.</li>
            </ol>
          </div>
        </div>

        {/* Verification Result Display (Right Column) */}
        <div className="lg:col-span-7">
          {!result && !isLoading && (
            <div className="h-full min-h-[420px] bg-surface-container-lowest border border-dashed border-outline-variant rounded-2xl p-8 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-2xl bg-surface-container flex items-center justify-center text-on-surface-variant/60 mb-3">
                <span className="material-symbols-outlined text-[36px]">shield_with_heart</span>
              </div>
              <h2 className="font-label-caps text-sm font-bold uppercase text-on-surface mb-1">
                Awaiting Verification
              </h2>
              <p className="text-xs text-on-surface-variant max-w-sm leading-relaxed">
                Upload any BlockTrace investigation PDF report to immediately verify whether its findings remain untouched and anchored on the Sepolia blockchain.
              </p>
            </div>
          )}

          {isLoading && (
            <div className="h-full min-h-[420px] bg-surface-container-lowest border border-outline-variant/60 rounded-2xl p-8 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center text-primary mb-4 animate-pulse">
                <span className="material-symbols-outlined text-[36px] animate-spin">sync</span>
              </div>
              <h2 className="font-label-caps text-sm font-bold uppercase text-on-surface mb-1">
                Verifying Report On-Chain
              </h2>
              <p className="text-xs text-on-surface-variant max-w-sm">
                Querying Ethereum Sepolia testnet contract &amp; fetching IPFS content identifier...
              </p>
            </div>
          )}

          {result && !isLoading && (
            <div className="bg-surface-container-lowest border border-outline-variant/60 rounded-2xl p-6 shadow-sm space-y-6 animate-fade-in">
              {/* Status Header Banner */}
              {result.status === 'authentic' && (
                <div className="bg-[#e8f5e9] border border-[#a5d6a7] rounded-xl p-4 text-[#1b5e20]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-[#2e7d32] text-white flex items-center gap-1.5 shadow-xs">
                      <span className="material-symbols-outlined text-[15px]">verified</span>
                      AUTHENTIC
                    </span>
                    <span className="text-[11px] font-bold text-[#2e7d32]">100% Cryptographic Match</span>
                  </div>
                  <h3 className="font-bold text-sm text-[#1b5e20] mb-1">
                    Cryptographic Integrity Confirmed
                  </h3>
                  <p className="text-xs text-[#2e682c] leading-relaxed">
                    The uploaded document byte-for-byte matches the immutable report archived on IPFS and anchored on Ethereum Sepolia.
                  </p>
                </div>
              )}

              {result.status === 'tampered' && (
                <div className="bg-[#ffebee] border border-[#ef9a9a] rounded-xl p-4 text-[#b71c1c]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-[#c62828] text-white flex items-center gap-1.5 shadow-xs">
                      <span className="material-symbols-outlined text-[15px]">gpp_bad</span>
                      TAMPERED
                    </span>
                    <span className="text-[11px] font-bold text-[#c62828]">Digest Mismatch</span>
                  </div>
                  <h3 className="font-bold text-sm text-[#b71c1c] mb-1">
                    Document Tampering Detected
                  </h3>
                  <p className="text-xs text-[#c62828] leading-relaxed">
                    The uploaded PDF's SHA-256 hash does NOT match the stored artifact on IPFS anchored to this on-chain investigation hash. The report has been altered, re-exported, or corrupted.
                  </p>
                </div>
              )}

              {result.status === 'not_found' && (
                <div className="bg-[#fff8e1] border border-[#ffe082] rounded-xl p-4 text-[#e65100]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-[#f57f17] text-white flex items-center gap-1.5 shadow-xs">
                      <span className="material-symbols-outlined text-[15px]">search_off</span>
                      NOT FOUND
                    </span>
                    <span className="text-[11px] font-bold text-[#e65100]">No Sepolia Record</span>
                  </div>
                  <h3 className="font-bold text-sm text-[#e65100] mb-1">
                    On-Chain Record Not Found
                  </h3>
                  <p className="text-xs text-[#bf360c] leading-relaxed">
                    {result.message || 'No record exists on Ethereum Sepolia for this investigation hash. Ensure the hash was entered correctly and that the investigation was anchored.'}
                  </p>
                </div>
              )}

              {result.status === 'unavailable' && (
                <div className="bg-[#eceff1] border border-[#b0bec5] rounded-xl p-4 text-[#37474f]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-[#546e7a] text-white flex items-center gap-1.5 shadow-xs">
                      <span className="material-symbols-outlined text-[15px]">cloud_off</span>
                      UNAVAILABLE
                    </span>
                    <span className="text-[11px] font-bold text-[#455a64]">IPFS Gateway Timeout</span>
                  </div>
                  <h3 className="font-bold text-sm text-[#263238] mb-1">
                    IPFS Storage Temporarily Unreachable
                  </h3>
                  <p className="text-xs text-[#37474f] leading-relaxed">
                    {result.message || 'An on-chain record exists on Sepolia, but the IPFS gateway could not be reached to fetch the stored file. You can verify the on-chain anchor details below.'}
                  </p>
                </div>
              )}

              {/* SHA-256 Checksums Comparison Card */}
              <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/40 space-y-3">
                <span className="font-label-caps text-xs font-bold uppercase tracking-wider text-on-surface block">
                  Cryptographic Fingerprints (SHA-256)
                </span>

                {/* Uploaded File SHA-256 */}
                <div className="bg-surface-container-lowest rounded-lg p-3 border border-outline-variant/30 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-label-caps uppercase text-on-surface-variant font-bold">
                      Uploaded File SHA-256
                    </span>
                    {result.uploaded_sha256 && (
                      <button
                        onClick={() => handleCopy(result.uploaded_sha256, 'uploaded')}
                        className="text-[10px] text-primary hover:text-primary-container font-semibold flex items-center gap-1 transition-colors"
                      >
                        <span className="material-symbols-outlined text-[13px]">
                          {copiedKey === 'uploaded' ? 'done' : 'content_copy'}
                        </span>
                        {copiedKey === 'uploaded' ? 'Copied' : 'Copy'}
                      </button>
                    )}
                  </div>
                  <p className="font-mono text-xs text-on-surface break-all select-all font-semibold">
                    {result.uploaded_sha256 || 'N/A'}
                  </p>
                </div>

                {/* Stored On-Chain File SHA-256 */}
                {result.stored_sha256 && (
                  <div className="bg-surface-container-lowest rounded-lg p-3 border border-outline-variant/30 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-label-caps uppercase text-on-surface-variant font-bold">
                        Stored On-Chain (IPFS) SHA-256
                      </span>
                      <button
                        onClick={() => handleCopy(result.stored_sha256, 'stored')}
                        className="text-[10px] text-primary hover:text-primary-container font-semibold flex items-center gap-1 transition-colors"
                      >
                        <span className="material-symbols-outlined text-[13px]">
                          {copiedKey === 'stored' ? 'done' : 'content_copy'}
                        </span>
                        {copiedKey === 'stored' ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <p className="font-mono text-xs text-on-surface break-all select-all font-semibold">
                      {result.stored_sha256}
                    </p>
                  </div>
                )}
              </div>

              {/* Provenance & On-Chain Metadata Table */}
              <div className="space-y-3">
                <span className="font-label-caps text-xs font-bold uppercase tracking-wider text-on-surface block">
                  On-Chain Provenance &amp; Storage Details
                </span>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  {/* Investigation Hash */}
                  <div className="sm:col-span-2 bg-surface-container rounded-lg p-3 border border-outline-variant/40">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="font-label-caps text-[10px] text-on-surface-variant uppercase font-bold">
                        Investigation Hash
                      </span>
                      {result.investigation_hash && (
                        <button
                          onClick={() => handleCopy(result.investigation_hash, 'hash')}
                          className="text-[10px] text-primary font-semibold flex items-center gap-1"
                        >
                          <span className="material-symbols-outlined text-[12px]">content_copy</span>
                          {copiedKey === 'hash' ? 'Copied' : 'Copy'}
                        </button>
                      )}
                    </div>
                    <span className="font-mono text-xs text-on-surface break-all">
                      {result.investigation_hash}
                    </span>
                  </div>

                  {/* Submitter Address */}
                  {result.submitter && (
                    <div className="bg-surface-container rounded-lg p-3 border border-outline-variant/40">
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="font-label-caps text-[10px] text-on-surface-variant uppercase font-bold">
                          Submitter Address
                        </span>
                        <a
                          href={`https://sepolia.etherscan.io/address/${result.submitter}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] text-primary hover:underline flex items-center gap-0.5 font-bold"
                        >
                          Etherscan
                          <span className="material-symbols-outlined text-[11px]">open_in_new</span>
                        </a>
                      </div>
                      <span className="font-mono text-xs text-on-surface break-all">
                        {result.submitter}
                      </span>
                    </div>
                  )}

                  {/* Timestamp UTC */}
                  {result.timestamp_utc && (
                    <div className="bg-surface-container rounded-lg p-3 border border-outline-variant/40">
                      <span className="font-label-caps text-[10px] text-on-surface-variant uppercase font-bold block mb-0.5">
                        Anchored Timestamp (UTC)
                      </span>
                      <span className="font-mono text-xs text-on-surface">
                        {result.timestamp_utc}
                      </span>
                    </div>
                  )}

                  {/* IPFS CID with Gateway link */}
                  {result.ipfs_cid && (
                    <div className="sm:col-span-2 bg-surface-container rounded-lg p-3 border border-outline-variant/40">
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="font-label-caps text-[10px] text-on-surface-variant uppercase font-bold">
                          IPFS Content Identifier (CID)
                        </span>
                        {result.gateway_url && (
                          <a
                            href={result.gateway_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-primary hover:underline flex items-center gap-0.5 font-bold"
                          >
                            Open Gateway
                            <span className="material-symbols-outlined text-[11px]">open_in_new</span>
                          </a>
                        )}
                      </div>
                      <span className="font-mono text-xs text-on-surface break-all">
                        {result.ipfs_cid}
                      </span>
                    </div>
                  )}

                  {/* Contract Address */}
                  {result.contract_address && (
                    <div className="sm:col-span-2 bg-surface-container rounded-lg p-3 border border-outline-variant/40">
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="font-label-caps text-[10px] text-on-surface-variant uppercase font-bold">
                          Sepolia Registry Contract
                        </span>
                        {result.explorer_url && (
                          <a
                            href={result.explorer_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-primary hover:underline flex items-center gap-0.5 font-bold"
                          >
                            View Contract on Etherscan
                            <span className="material-symbols-outlined text-[11px]">open_in_new</span>
                          </a>
                        )}
                      </div>
                      <span className="font-mono text-xs text-on-surface break-all">
                        {result.contract_address}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default VerifyReportScreen;

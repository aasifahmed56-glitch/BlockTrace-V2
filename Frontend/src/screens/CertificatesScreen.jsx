import React, { useState } from 'react';
import { useInvestigation } from '../context/InvestigationContext';
import { issueCertificate, verifyCertificate, getErrorMessage } from '../api/client';

export const CertificatesScreen = () => {
  const { startWallet, summary, sanctions, showToast, actionLoading, setActionLoading } = useInvestigation();

  // Issue Certificate State
  const [issuedCert, setIssuedCert] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // Verification State
  const [verifyResult, setVerifyResult] = useState(null); // null | { valid: boolean, error?: string, filename?: string }
  const [isVerifying, setIsVerifying] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  // Handle Generate Certificate
  const handleGenerateCertificate = async () => {
    if (summary.wallets_traced === 0) {
      showToast('Nothing to certify — the graph is empty. Load or trace a case first.', 'warning');
      return;
    }
    setIsGenerating(true);
    setActionLoading(true);
    try {
      showToast('Computing cryptographic certificate hash...', 'info');
      const certData = await issueCertificate(startWallet || undefined);
      setIssuedCert(certData);
      showToast('Certificate successfully generated & chained!', 'success');
    } catch (err) {
      console.error(err);
      showToast(getErrorMessage(err), 'error');
    } finally {
      setIsGenerating(false);
      setActionLoading(false);
    }
  };

  // Handle Download Certificate JSON
  const handleDownloadCertificate = () => {
    if (!issuedCert) return;
    const jsonStr = JSON.stringify(issuedCert, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `blocktrace_cert_${issuedCert.certificate_hash.slice(0, 10)}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Certificate JSON file saved to disk.', 'success');
  };

  // Handle File Upload for Verification
  const processUploadedFile = async (file) => {
    if (!file) return;
    setIsVerifying(true);
    setVerifyResult(null);

    try {
      const text = await file.text();
      let parsed;
      try {
        parsed = JSON.parse(text);
      } catch (jsonErr) {
        throw new Error('Invalid JSON file. Please upload a valid BlockTrace certificate.');
      }

      if (!parsed.certificate_hash || !parsed.previous_hash || !parsed.payload) {
        throw new Error('Missing required certificate fields (certificate_hash, previous_hash, payload).');
      }

      const res = await verifyCertificate({
        certificate_hash: parsed.certificate_hash,
        previous_hash: parsed.previous_hash,
        payload: parsed.payload,
      });

      setVerifyResult({
        valid: res.valid,
        filename: file.name,
        hash: parsed.certificate_hash,
        payload: parsed.payload,
      });

      if (res.valid) {
        showToast('Certificate verified successfully! Hash is intact.', 'success');
      } else {
        showToast('Certificate verification failed! Payload may be tampered.', 'error');
      }
    } catch (err) {
      console.error(err);
      setVerifyResult({
        valid: false,
        filename: file.name,
        error: err.message || 'Verification error',
      });
      showToast(err.message || 'Failed to verify file', 'error');
    } finally {
      setIsVerifying(false);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      processUploadedFile(e.target.files[0]);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processUploadedFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="flex flex-col w-full p-xl gap-xl max-w-7xl mx-auto max-lg:p-4 max-lg:gap-6">
      {/* Top Title Banner */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-4 border-b border-outline-variant/50">
        <div>
          <h1 className="font-headline-lg text-3xl font-bold text-on-surface mb-2">
            Forensic Certificates
          </h1>
          <p className="font-body-md text-sm text-on-surface-variant max-w-2xl">
            Generate immutable cryptographic proofs for investigation findings, or verify the integrity of external case reports.
          </p>
        </div>

        <div className="flex items-center gap-2 bg-surface-container px-3.5 py-2 rounded-full border border-outline-variant/60">
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span className="font-label-caps text-xs text-on-surface-variant uppercase font-bold">
            Ledger Proof Engine Active
          </span>
        </div>
      </div>

      {/* Two Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Column: Issue Certificate */}
        <section className="flex flex-col gap-5 bg-surface-container rounded-2xl p-8 shadow-md border border-outline-variant/60 relative overflow-hidden max-lg:p-4">
          <div className="flex items-center gap-2 pb-2 border-b border-outline-variant/40">
            <span className="material-symbols-outlined text-primary text-[24px]">verified_user</span>
            <h2 className="font-headline-md text-xl font-bold text-on-surface">
              Issue New Certificate
            </h2>
          </div>

          <p className="font-body-sm text-xs text-on-surface-variant leading-relaxed">
            Generates a cryptographic hash of this investigation's current findings, chained to the previous certificate. Anyone holding the certificate file can later independently re-verify it.
          </p>

          {/* Current Working Set Card */}
          <div className="bg-surface p-4 rounded-xl border border-outline-variant/60 shadow-xs">
            <div className="flex justify-between items-center mb-3 pb-2 border-b border-outline-variant/40">
              <span className="font-label-caps text-[10px] text-on-surface-variant uppercase font-bold">
                Current Working Set
              </span>
              <span className="font-address-md text-xs text-primary font-bold">
                {summary.wallets_traced > 0 ? `${summary.wallets_traced} Wallets Traced` : 'Empty Graph'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="flex flex-col">
                <span className="font-label-caps text-[10px] text-on-surface-variant uppercase">
                  Transactions Mapped
                </span>
                <span className="font-address-md text-sm font-bold text-on-surface">
                  {summary.transactions_mapped}
                </span>
              </div>
              <div className="flex flex-col">
                <span className="font-label-caps text-[10px] text-on-surface-variant uppercase">
                  Sanction Flags
                </span>
                <span className={`font-address-md text-sm font-bold ${sanctions.length > 0 ? 'text-error' : 'text-[#4C8C4A]'}`}>
                  {sanctions.length > 0 ? `${sanctions.length} Detected` : '0 Clean'}
                </span>
              </div>
            </div>
          </div>

          {/* Action Button */}
          <button
            onClick={handleGenerateCertificate}
            disabled={isGenerating || actionLoading}
            className="w-full bg-primary text-white font-label-caps text-xs uppercase py-3.5 px-6 rounded-xl shadow-md hover:bg-primary-container transition-all flex items-center justify-center gap-2 font-bold active:scale-98 disabled:opacity-50"
          >
            <span className="material-symbols-outlined text-[18px]">fingerprint</span>
            <span>{isGenerating ? 'Computing Proof...' : 'Generate Certificate for Current Findings'}</span>
          </button>

          {/* Issued Result State */}
          {issuedCert && (
            <div className="flex flex-col gap-3 mt-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div className="flex items-center gap-1.5 text-xs text-[#2e682c] bg-[#e8f5e9] px-3 py-1.5 rounded-lg border border-[#4C8C4A]/30 w-fit font-bold font-label-caps uppercase">
                <span className="material-symbols-outlined text-[16px]">check_circle</span>
                <span>Certificate Issued Successfully</span>
              </div>

              <div className="bg-[#222222] text-white p-4 rounded-xl relative border border-white/10 shadow-inner">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-label-caps text-[10px] text-primary uppercase font-bold">
                    SHA-256 Checksum
                  </span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(issuedCert.certificate_hash);
                      showToast('Hash copied to clipboard!', 'info');
                    }}
                    className="text-gray-400 hover:text-white transition-colors"
                    title="Copy full hash"
                  >
                    <span className="material-symbols-outlined text-[16px]">content_copy</span>
                  </button>
                </div>
                <p className="font-address-md text-xs text-primary-fixed break-all font-mono select-all">
                  {issuedCert.certificate_hash}
                </p>
                <div className="mt-2 text-[10px] text-gray-400 font-mono">
                  Chained to: {issuedCert.previous_hash.slice(0, 16)}...
                </div>
              </div>

              <div className="flex items-center justify-between text-xs pt-1 max-lg:flex-col max-lg:items-stretch max-lg:gap-2">
                <span className="text-on-surface-variant font-address-md text-[11px]">
                  Timestamp: {issuedCert.created_at}
                </span>
                <button
                  onClick={handleDownloadCertificate}
                  className="bg-surface hover:bg-surface-variant text-primary font-label-caps text-xs uppercase px-3 py-1.5 rounded-lg border border-primary/40 flex items-center gap-1 font-bold shadow-xs transition-colors max-lg:justify-center max-lg:min-h-[48px]"
                >
                  <span className="material-symbols-outlined text-[16px]">download</span>
                  <span>Download Certificate</span>
                </button>
              </div>
            </div>
          )}
        </section>

        {/* Right Column: Verify Certificate */}
        <section className="flex flex-col gap-5 bg-surface-container rounded-2xl p-8 shadow-md border border-outline-variant/60 relative max-lg:p-4">
          <div className="flex items-center gap-2 pb-2 border-b border-outline-variant/40">
            <span className="material-symbols-outlined text-tertiary text-[24px]">policy</span>
            <h2 className="font-headline-md text-xl font-bold text-on-surface">
              Verify an Existing Certificate
            </h2>
          </div>

          <p className="font-body-sm text-xs text-on-surface-variant leading-relaxed">
            Upload a previously issued certificate JSON file to validate its cryptographic integrity against the SHA-256 Merkle chain.
          </p>

          {/* Drag & Drop Zone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`flex-1 flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-2xl p-8 cursor-pointer transition-all min-h-[220px] text-center max-lg:min-h-[180px] max-lg:p-5 ${
              dragActive
                ? 'border-primary bg-primary/5'
                : 'border-outline-variant bg-surface hover:bg-surface-container-high'
            }`}
            onClick={() => document.getElementById('cert-upload-input')?.click()}
            role="button"
            tabIndex={0}
            aria-label="Upload a certificate JSON file"
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                document.getElementById('cert-upload-input')?.click();
              }
            }}
          >
            <input
              id="cert-upload-input"
              type="file"
              accept=".json"
              className="hidden"
              onChange={handleFileInputChange}
            />

            <div className="w-14 h-14 rounded-full bg-surface-container flex items-center justify-center text-primary shadow-xs">
              <span className="material-symbols-outlined text-[28px]">upload_file</span>
            </div>

            <div>
              <span className="font-headline-md text-base font-bold text-on-surface block mb-1">
                Drop certificate JSON file here
              </span>
              <span className="font-body-sm text-xs text-on-surface-variant">
                or click to browse from computer
              </span>
            </div>
          </div>

          {/* Verification Result Card */}
          {isVerifying && (
            <div className="p-4 bg-surface rounded-xl border border-outline-variant flex items-center gap-3">
              <div className="w-4 h-4 border-2 border-tertiary border-t-transparent rounded-full animate-spin" />
              <span className="text-xs font-label-caps uppercase text-tertiary font-bold">
                Verifying hash payload integrity...
              </span>
            </div>
          )}

          {verifyResult && !isVerifying && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
              {verifyResult.valid ? (
                /* Success Card */
                <div className="bg-[#e8f5e9] border border-[#4C8C4A] rounded-xl p-5 flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-[#2e682c]">
                    <span className="material-symbols-outlined text-[22px]">verified</span>
                    <h3 className="font-headline-md text-base font-bold">
                      Certificate is Intact & Valid
                    </h3>
                  </div>
                  <p className="text-xs text-[#2e682c]/90 leading-relaxed">
                    The cryptographic signature and payload match exactly. The investigation findings have not been altered.
                  </p>
                  {verifyResult.hash && (
                    <div className="mt-2 p-2 bg-white/70 rounded font-address-md text-[10px] font-mono text-[#2e682c] break-all border border-[#4C8C4A]/30">
                      Hash: {verifyResult.hash}
                    </div>
                  )}
                </div>
              ) : (
                /* Failure Card */
                <div className="bg-[#ffebee] border border-error rounded-xl p-5 flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-error">
                    <span className="material-symbols-outlined text-[22px]">error</span>
                    <h3 className="font-headline-md text-base font-bold">
                      Verification Failed
                    </h3>
                  </div>
                  <p className="text-xs text-error/90 leading-relaxed">
                    {verifyResult.error || 'The certificate hash does not match the payload. Findings may have been altered or corrupted.'}
                  </p>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

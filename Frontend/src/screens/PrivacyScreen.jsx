import React from 'react';

export const PrivacyScreen = () => {
  return (
    <div className="min-h-screen bg-surface text-on-surface flex items-center justify-center px-4">
      <div className="max-w-2xl w-full">
        <div className="bg-surface-container rounded-2xl border border-outline-variant p-8 shadow-lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-primary-container flex items-center justify-center">
              <span className="material-symbols-outlined text-[24px] text-white">hub</span>
            </div>
            <div>
              <h1 className="text-xl font-bold">BlockTrace</h1>
              <p className="text-xs text-on-surface-variant uppercase tracking-wider font-semibold">
                Privacy Policy
              </p>
            </div>
          </div>

          <div className="space-y-4 text-sm text-on-surface-variant leading-relaxed">
            <section>
              <h2 className="text-base font-bold text-on-surface mb-2">Report Verification Service</h2>
              <p>
                The BlockTrace report verification service receives your uploaded PDF document and
                investigation hash, processes them <strong>entirely in memory</strong> to verify
                cryptographic integrity against on-chain records, and{' '}
                <strong>does not store, log, or retain</strong> the file or its contents after the
                verification response is returned.
              </p>
            </section>

            <section>
              <h2 className="text-base font-bold text-on-surface mb-2">Sanctions Screening</h2>
              <p>
                The public sanctions check endpoint validates wallet addresses against a built-in,
                static demonstration list derived from public OFAC data. No queries are made to
                external services, and no address lookups are logged or stored.
              </p>
            </section>

            <section>
              <h2 className="text-base font-bold text-on-surface mb-2">On-Chain Data</h2>
              <p>
                Investigation findings that are published or anchored are stored on the public
                Ethereum Sepolia testnet and IPFS. These records are immutable and publicly
                accessible by design — they serve as the cryptographic proof of investigation
                integrity. Anchored case snapshots are encrypted with AES-256-GCM before upload.
              </p>
            </section>

            <section>
              <h2 className="text-base font-bold text-on-surface mb-2">No Tracking</h2>
              <p>
                This application does not use cookies, analytics trackers, or advertising pixels.
                Rate-limiting counters are held in memory and are not persisted.
              </p>
            </section>

            <section>
              <h2 className="text-base font-bold text-on-surface mb-2">Contact</h2>
              <p>
                BlockTrace is an academic / demonstration project. For questions about this privacy
                policy or the service, please open an issue on the project repository.
              </p>
            </section>
          </div>

          <div className="mt-6 pt-4 border-t border-outline-variant/40 text-xs text-on-surface-variant/60 text-center">
            Last updated: {new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long' })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PrivacyScreen;


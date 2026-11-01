import React from 'react';
import { useInvestigation } from '../context/InvestigationContext';
import { loadCuratedCase } from '../api/client';

export const LandingScreen = () => {
  const {
    setActiveTab,
    curatedCases,
    refreshGraphAndSummary,
    refreshFindings,
    showToast,
    setActionLoading,
  } = useInvestigation();

  const handleOpenCuratedCase = async (caseName) => {
    setActionLoading(true);
    try {
      showToast(`Loading case: ${caseName}...`, 'info');
      await loadCuratedCase(caseName);
      await refreshGraphAndSummary();
      await refreshFindings();
      showToast(`Successfully loaded ${caseName}`, 'success');
      setActiveTab('investigate');
    } catch (err) {
      console.error(err);
      showToast('Failed to load curated case', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="w-full min-h-screen bg-surface font-body-md text-on-surface">
      {/* Top Header */}
      <header className="fixed top-0 w-full z-50 bg-surface/90 backdrop-blur-md shadow-xs border-b border-outline-variant/40 max-lg:pt-[env(safe-area-inset-top)]">
        <div className="h-20 max-w-7xl mx-auto px-lg flex items-center justify-between">
          <div className="flex items-center gap-md cursor-pointer" onClick={() => setActiveTab('landing')}>
            <div className="w-9 h-9 rounded-lg bg-primary-container flex items-center justify-center text-white shadow-md">
              <span className="material-symbols-outlined text-[22px]">hub</span>
            </div>
            <span className="font-headline-md text-headline-md text-on-surface tracking-tight uppercase font-bold">
              BlockTrace
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-xl">
            <a href="#problem" className="font-label-caps text-label-caps text-on-surface-variant hover:text-on-surface transition-colors uppercase max-lg:py-3 max-lg:inline-block">
              Product
            </a>
            <a href="#how-it-works" className="font-label-caps text-label-caps text-on-surface-variant hover:text-on-surface transition-colors uppercase max-lg:py-3 max-lg:inline-block">
              How it Works
            </a>
            <a href="#verified-cases" className="font-label-caps text-label-caps text-on-surface-variant hover:text-on-surface transition-colors uppercase max-lg:py-3 max-lg:inline-block">
              Verified Cases
            </a>
          </nav>

          <div className="flex items-center gap-md">
            <button
              onClick={() => setActiveTab('investigate')}
              className="bg-primary text-on-primary font-label-caps text-label-caps px-lg py-sm rounded-lg uppercase tracking-wider transition-all hover:bg-primary-container shadow-md active:scale-95 flex items-center gap-1.5"
            >
              <span>Launch App</span>
              <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative z-10 w-full min-h-[85vh] flex flex-col items-center justify-center px-lg py-xl pt-32 overflow-hidden">
        {/* Background Gradients */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary opacity-[0.04] rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/3 right-1/4 w-[500px] h-[500px] bg-tertiary opacity-[0.03] rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-4xl mx-auto text-center flex flex-col items-center gap-lg relative z-10">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-surface-container rounded-full border border-outline-variant/60 shadow-xs">
            <span className="material-symbols-outlined text-[18px] text-primary">verified</span>
            <span className="font-label-caps text-xs text-on-surface tracking-wider uppercase font-bold">
              Cryptographically Verifiable Findings
            </span>
          </div>

          <h1 className="font-display-lg text-4xl md:text-6xl font-bold tracking-tight text-on-surface max-w-3xl">
            Trace crypto crime.{' '}
            <span className="text-primary block sm:inline">Verify every finding.</span>
          </h1>

          <p className="font-body-lg text-lg text-on-surface-variant max-w-2xl mx-auto leading-relaxed">
            BlockTrace investigates cryptocurrency wallets, flags suspicious laundering patterns with transparent reasoning, and issues cryptographic proof that its findings cannot be silently altered.
          </p>

          <div className="flex flex-col sm:flex-row items-center gap-4 mt-6">
            <button
              onClick={() => setActiveTab('investigate')}
              className="w-full sm:w-auto bg-primary text-on-primary font-label-caps text-label-caps px-8 py-4 rounded-xl uppercase tracking-wider transition-all hover:bg-primary-container shadow-lg hover:shadow-primary/20 active:scale-95 flex items-center justify-center gap-2 font-bold"
            >
              <span>Launch App</span>
              <span className="material-symbols-outlined text-[20px]">arrow_forward</span>
            </button>
            <a
              href="#verified-cases"
              className="w-full sm:w-auto bg-transparent border-2 border-outline text-on-surface font-label-caps text-label-caps px-8 py-3.5 rounded-xl uppercase tracking-wider transition-all hover:bg-surface-container flex items-center justify-center gap-2 font-bold"
            >
              <span>See a Real Case</span>
            </a>
          </div>
        </div>
      </section>

      {/* Problem Comparison Section */}
      <section id="problem" className="w-full bg-surface-container py-24 px-lg border-y border-outline-variant/50">
        <div className="max-w-7xl mx-auto">
          <div className="mb-16 text-center md:text-left flex flex-col gap-2">
            <h2 className="font-headline-lg text-3xl font-bold text-on-surface">
              The Problem: Raw Data is Blind.
            </h2>
            <p className="font-body-lg text-base text-on-surface-variant max-w-2xl">
              Traditional block explorers offer transparency but lack context. Investigators manually trace stolen funds wallet by wallet across millions of noisy transactions.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left: Raw Data */}
            <div className="bg-surface p-8 rounded-2xl border border-outline-variant/60 shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-outline-variant pb-3 mb-4">
                  <span className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider font-bold">
                    Raw Explorer View
                  </span>
                  <span className="material-symbols-outlined text-outline">code</span>
                </div>
                <div className="font-address-md text-xs text-on-surface-variant/80 flex flex-col gap-2 font-mono max-lg:break-all">
                  <div className="p-2.5 bg-surface-container-low rounded">Tx: 0x8f7a9c3e2b1d0f5c8a6e4d7b2a9f1c3e5d7b9a2c1f4e6d8b0a2c4e6f8a0b2d4</div>
                  <div className="p-2.5 bg-surface-container-low rounded">From: 0x098B716B8Aaf21512996dC57EB0615e2383E2f96</div>
                  <div className="p-2.5 bg-surface-container-low rounded">To: 0x9D2a7C89d7A3b879C512b9148c7A512d7c9a8b1F</div>
                  <div className="p-2.5 bg-surface-container-low rounded">Value: 1,450.00 ETH</div>
                  <div className="p-2.5 bg-surface-container-low rounded">Gas: 21,000</div>
                </div>
              </div>
              <p className="font-body-sm text-xs text-error/90 mt-6 pt-4 border-t border-outline-variant text-center font-medium">
                Incomprehensible to non-technical investigators and auditors.
              </p>
            </div>

            {/* Right: BlockTrace Intelligence */}
            <div className="bg-[#222222] text-white p-8 rounded-2xl shadow-xl flex flex-col justify-between relative overflow-hidden">
              <div>
                <div className="flex items-center justify-between border-b border-white/15 pb-3 mb-4">
                  <span className="font-label-caps text-xs text-primary uppercase tracking-wider font-bold">
                    BlockTrace Forensics
                  </span>
                  <span className="material-symbols-outlined text-primary">account_tree</span>
                </div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/10">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-error/20 flex items-center justify-center text-error">
                        <span className="material-symbols-outlined text-[18px]">warning</span>
                      </div>
                      <div>
                        <div className="text-xs font-bold text-white">OFAC Sanctioned Entity Detected</div>
                        <div className="text-[10px] text-gray-400 font-mono">Lazarus Group Attribution</div>
                      </div>
                    </div>
                    <span className="bg-error text-white font-label-caps text-[9px] uppercase px-2 py-0.5 rounded-full font-bold">
                      Critical
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/10">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary">
                        <span className="material-symbols-outlined text-[18px]">hub</span>
                      </div>
                      <div>
                        <div className="text-xs font-bold text-white">Hub & Fan-Out Structure</div>
                        <div className="text-[10px] text-gray-400 font-mono">Dispersed to 48 Intermediate Wallets</div>
                      </div>
                    </div>
                    <span className="bg-primary text-white font-label-caps text-[9px] uppercase px-2 py-0.5 rounded-full font-bold">
                      Flagged
                    </span>
                  </div>
                </div>
              </div>
              <p className="font-body-sm text-xs text-primary-fixed-dim mt-6 pt-4 border-t border-white/15 text-center font-medium">
                Instant explainable forensic insights backed by cryptographic certificates.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="w-full py-24 px-lg">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="font-label-caps text-xs uppercase tracking-widest text-primary font-bold">
              Investigation Workflow
            </span>
            <h2 className="font-headline-lg text-3xl font-bold text-on-surface mt-2">
              Four Steps from Address to Evidence
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              {
                step: '01',
                title: 'Pick a Wallet',
                desc: 'Load a verified incident case or enter any Ethereum, BSC, or Polygon address.',
                icon: 'search',
              },
              {
                step: '02',
                title: 'We Trace the Network',
                desc: 'Follows money flows hop-by-hop across the graph, mapping every intermediary.',
                icon: 'account_tree',
              },
              {
                step: '03',
                title: 'Patterns Get Flagged',
                desc: 'Five independent detection heuristics highlight laundering structures with full transparency.',
                icon: 'shield',
              },
              {
                step: '04',
                title: 'Cryptographic Proof',
                desc: 'Export a chained cryptographic certificate and audit-ready PDF forensic report.',
                icon: 'verified_user',
              },
            ].map((s) => (
              <div
                key={s.step}
                className="bg-surface-container p-6 rounded-2xl border border-outline-variant/60 relative flex flex-col justify-between hover:border-primary/50 transition-colors"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="font-headline-lg text-2xl font-bold text-primary">{s.step}</span>
                    <div className="w-10 h-10 rounded-xl bg-surface flex items-center justify-center text-on-surface shadow-xs">
                      <span className="material-symbols-outlined text-[20px]">{s.icon}</span>
                    </div>
                  </div>
                  <h3 className="font-headline-md text-lg font-bold text-on-surface mb-2">{s.title}</h3>
                  <p className="font-body-md text-sm text-on-surface-variant leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="w-full bg-surface-container-low py-24 px-lg border-t border-outline-variant/40">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="font-label-caps text-xs uppercase tracking-widest text-primary font-bold">
              Capabilities
            </span>
            <h2 className="font-headline-lg text-3xl font-bold text-on-surface mt-2">
              Forensic Detection Heuristics
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                title: 'Hub Activity Detection',
                desc: 'Identifies centralized wallets orchestrating dense clustering and multi-party coordination.',
                icon: 'hub',
              },
              {
                title: 'High Fan-Out Splitting',
                desc: 'Flags high-velocity fund dispersion across many distinct intermediate wallets.',
                icon: 'call_split',
              },
              {
                title: 'Peel Chain Detection',
                desc: 'Uncovers classic layering where smaller round chunks are peeled away at each hop.',
                icon: 'schema',
              },
              {
                title: 'Round-Number Filters',
                desc: 'Identifies structured whole-integer transaction values frequently used in smurfing.',
                icon: 'tag',
              },
              {
                title: 'Circular Flow Analysis',
                desc: 'Spots cyclic routing designed to artificially inflate volume or obfuscate provenance.',
                icon: 'change_circle',
              },
              {
                title: 'Sanctions Screening',
                desc: 'Cross-checks every address against global OFAC and EU sanctions databases in real-time.',
                icon: 'policy',
              },
            ].map((feat) => (
              <div
                key={feat.title}
                className="bg-surface p-6 rounded-2xl border border-outline-variant/60 shadow-xs hover:border-primary/50 transition-all hover:shadow-md"
              >
                <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                  <span className="material-symbols-outlined text-[22px]">{feat.icon}</span>
                </div>
                <h3 className="font-headline-md text-base font-bold text-on-surface mb-2">{feat.title}</h3>
                <p className="font-body-md text-xs text-on-surface-variant leading-relaxed">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Verified Cases Showcase */}
      <section id="verified-cases" className="w-full py-24 px-lg bg-surface">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="font-label-caps text-xs uppercase tracking-widest text-primary font-bold">
              Real-World Evidence
            </span>
            <h2 className="font-headline-lg text-3xl font-bold text-on-surface mt-2">
              Tested Against Documented Incidents
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {(curatedCases.length > 0
              ? curatedCases
              : [
                  {
                    name: 'Ronin Bridge Hack ($600M, 2022)',
                    address: '0x098B716B8Aaf21512996dC57EB0615e2383E2f96',
                    description: 'Wallet linked to the Axie Infinity / Ronin Bridge exploit. Sanctioned by OFAC and attributed to Lazarus Group.',
                  },
                  {
                    name: 'Poly Network Hack ($611M, 2021)',
                    address: '0xC8a65Fadf0e0dDAf421F28FEAb69Bf6E2E589963',
                    description: 'DeFi exploit draining assets across Ethereum, BSC, and Polygon with extensive cross-chain movement.',
                  },
                  {
                    name: 'Wormhole Bridge Hack ($321M, 2022)',
                    address: '0x629e7Da20197a5429d30da36E77D06CdF796b71a',
                    description: 'Exploit of the Ethereum-Solana bridge directly labeled Wormhole Exploiter on Etherscan.',
                  },
                ]
            ).map((c) => (
              <div
                key={c.name}
                className="bg-surface-container p-6 rounded-2xl border border-outline-variant/60 flex flex-col justify-between shadow-xs hover:border-primary transition-all"
              >
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-primary text-[20px]">folder</span>
                    <h3 className="font-headline-md text-base font-bold text-on-surface">{c.name}</h3>
                  </div>
                  <p className="font-body-md text-xs text-on-surface-variant mb-4 leading-relaxed line-clamp-3">
                    {c.description}
                  </p>
                  <div className="p-2 bg-surface rounded-lg font-address-md text-[11px] text-on-surface-variant font-mono mb-4 break-all border border-outline-variant/40">
                    {c.address}
                  </div>
                </div>

                <button
                  onClick={() => handleOpenCuratedCase(c.name)}
                  className="w-full py-2.5 px-4 bg-primary text-white font-label-caps text-xs uppercase rounded-lg hover:bg-primary-container transition-colors font-bold flex items-center justify-center gap-1.5 shadow-xs"
                >
                  <span>Launch Investigation</span>
                  <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA & Footer */}
      <section className="w-full bg-[#222222] text-white py-16 px-lg">
        <div className="max-w-7xl mx-auto flex flex-col items-center text-center gap-6">
          <h2 className="font-headline-lg text-3xl font-bold">Start an Investigation in Seconds</h2>
          <p className="text-gray-400 max-w-xl text-sm leading-relaxed">
            Directly connect to blockchain nodes, visualize laundering topologies, and generate immutable cryptographic proof of findings.
          </p>
          <button
            onClick={() => setActiveTab('investigate')}
            className="bg-primary text-white font-label-caps text-xs uppercase px-8 py-3.5 rounded-xl font-bold tracking-wider hover:bg-primary-container transition-all shadow-lg active:scale-95 flex items-center gap-2"
          >
            <span>Open Investigator Console</span>
            <span className="material-symbols-outlined text-[18px]">launch</span>
          </button>
          <div className="pt-8 border-t border-white/10 w-full flex flex-col sm:flex-row items-center justify-between text-xs text-gray-500 gap-4">
            <span>© 2026 BlockTrace Forensics. All rights reserved.</span>
            <span className="italic text-gray-400">
              Note: Detection results are heuristic indicators, not definitive proof of wrongdoing.
            </span>
          </div>
        </div>
      </section>
    </div>
  );
};

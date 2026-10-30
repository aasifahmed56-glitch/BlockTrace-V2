import React, { useState } from 'react';
import { useInvestigation } from '../context/InvestigationContext';
import { getReportUrl } from '../api/client';

// The backend narrative (logic.build_narrative) marks up wallet addresses and key
// figures with two tags. Turn just those into elements and keep everything else as
// plain text, so wallet labels from external data can never inject HTML.
const NARRATIVE_TAG = /<span class='tc-mono'>(.*?)<\/span>|<strong>(.*?)<\/strong>/g;

const renderNarrative = (text) => {
  const parts = [];
  let last = 0;
  for (const match of text.matchAll(NARRATIVE_TAG)) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const [, address, emphasis] = match;
    parts.push(
      address !== undefined ? (
        <span key={match.index} className="font-mono text-[0.92em] bg-surface-variant/60 px-1 rounded">
          {address}
        </span>
      ) : (
        <strong key={match.index} className="font-semibold">{emphasis}</strong>
      ),
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
};

export const FindingsScreen = () => {
  const {
    startWallet,
    sanctions,
    sanctionsSnapshot,
    riskData,
    narrativeParagraphs,
    hubDetections,
    fanoutDetections,
    peelDetections,
    roundDetections,
    circularDetections,
    isLoadingFindings,
    setActiveTab,
  } = useInvestigation();

  // Expandable list toggles (showing 5 by default)
  const [showAllRisk, setShowAllRisk] = useState(false);
  const [showAllHub, setShowAllHub] = useState(false);
  const [showAllFanout, setShowAllFanout] = useState(false);
  const [showAllPeel, setShowAllPeel] = useState(false);
  const [showAllRound, setShowAllRound] = useState(false);
  const [showAllCircular, setShowAllCircular] = useState(false);

  // Address middle truncate helper
  const truncate = (addr) => {
    if (!addr) return '';
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  const displayedRisk = showAllRisk ? riskData : riskData.slice(0, 5);
  const displayedHub = showAllHub ? hubDetections : hubDetections.slice(0, 5);
  const displayedFanout = showAllFanout ? fanoutDetections : fanoutDetections.slice(0, 5);
  const displayedPeel = showAllPeel ? peelDetections : peelDetections.slice(0, 5);
  const displayedRound = showAllRound ? roundDetections : roundDetections.slice(0, 5);
  const displayedCircular = showAllCircular ? circularDetections : circularDetections.slice(0, 5);

  return (
    <div className="flex flex-col w-full px-xl py-lg space-y-xl max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between w-full gap-4 pb-4 border-b border-outline-variant/50">
        <div>
          <h1 className="font-display-lg text-3xl font-bold text-on-surface mb-2">
            Forensic Findings Report
          </h1>
          <p className="font-body-lg text-sm text-on-surface-variant max-w-2xl">
            Synthesized multi-heuristic forensic evaluation of the current transaction graph.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <a
            href={getReportUrl(startWallet)}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 rounded-lg border-2 border-primary text-primary font-label-caps text-xs uppercase hover:bg-primary hover:text-white transition-colors flex items-center gap-1.5 font-bold shadow-xs"
          >
            <span className="material-symbols-outlined text-[16px]">picture_as_pdf</span>
            <span>Export PDF</span>
          </a>
          <button
            onClick={() => setActiveTab('certificates')}
            className="px-4 py-2 rounded-lg bg-primary text-white font-label-caps text-xs uppercase hover:bg-primary-container transition-colors flex items-center gap-1.5 shadow-md font-bold"
          >
            <span className="material-symbols-outlined text-[16px]">verified</span>
            <span>Issue Proof</span>
          </button>
        </div>
      </div>

      {/* Loading state indicator */}
      {isLoadingFindings && (
        <div className="p-4 bg-surface-container rounded-xl flex items-center gap-3 border border-outline-variant">
          <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-label-caps uppercase text-primary font-bold">
            Evaluating detection heuristics...
          </span>
        </div>
      )}

      {/* Narrative Summary Section */}
      <section className="bg-surface-container rounded-xl p-6 border-l-4 border-l-primary shadow-sm relative overflow-hidden">
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-primary text-[22px]">auto_stories</span>
          <h2 className="font-headline-md text-xl font-bold text-on-surface">
            What This Trail Shows
          </h2>
        </div>

        <div className="font-body-md text-sm text-on-surface space-y-3 leading-relaxed">
          {narrativeParagraphs && narrativeParagraphs.length > 0 ? (
            narrativeParagraphs.map((para, index) => <p key={index}>{renderNarrative(para)}</p>)
          ) : (
            <p className="text-on-surface-variant italic">
              No active narrative generated yet. Load a case or trace an address in the Investigate tab to view detailed behavioral analysis.
            </p>
          )}
        </div>

        <div className="mt-4 pt-3 border-t border-outline-variant/60 text-xs text-on-surface-variant italic">
          Disclaimer: Detection results are heuristic indicators and analytical anomalies, not definitive proof of wrongdoing.
        </div>
      </section>

      {/* Split Grid: Sanctions Screening & Risk Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sanctions Screening (1 column) */}
        <section className="lg:col-span-1 flex flex-col space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-headline-md text-lg font-bold text-on-surface flex items-center gap-1.5">
              <span className="material-symbols-outlined text-error text-[20px]">policy</span>
              <span>Sanctions Screening</span>
            </h3>
            <span
              className={`px-2.5 py-0.5 rounded-full font-label-caps text-[11px] font-bold flex items-center gap-1 ${
                sanctions.length > 0
                  ? 'bg-error/15 text-error border border-error/30'
                  : 'bg-[#e8f5e9] text-[#2e682c]'
              }`}
            >
              <span className="material-symbols-outlined text-[14px]">
                {sanctions.length > 0 ? 'warning' : 'check'}
              </span>
              <span>{sanctions.length} {sanctions.length === 1 ? 'Hit' : 'Hits'}</span>
            </span>
          </div>

          <div className="space-y-3">
            {sanctions && sanctions.length > 0 ? (
              sanctions.map((s, idx) => (
                <div
                  key={idx}
                  className="bg-surface border border-error/40 rounded-xl p-4 shadow-sm relative overflow-hidden hover:border-error transition-colors"
                >
                  <div className="absolute inset-y-0 left-0 w-1 bg-error" />
                  <div className="flex justify-between items-start mb-2 pl-2">
                    <span
                      onClick={() => copyToClipboard(s.wallet)}
                      className="font-address-md text-xs font-mono text-on-surface hover:text-primary cursor-pointer"
                      title="Click to copy full address"
                    >
                      {truncate(s.wallet)}
                    </span>
                    <span className="bg-error text-white px-2 py-0.5 rounded-full font-label-caps text-[9px] font-bold shadow-xs">
                      SANCTIONED
                    </span>
                  </div>
                  <div className="pl-2 space-y-1">
                    <p className="font-body-sm text-xs font-bold text-on-surface">{s.name}</p>
                    <p className="font-body-sm text-[11px] text-on-surface-variant">
                      Authority: <span className="font-semibold">{s.authority}</span>
                    </p>
                    {s.note && (
                      <p className="font-body-sm text-[10px] text-on-surface-variant/80 italic">
                        {s.note}
                      </p>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="p-6 bg-surface rounded-xl border border-outline-variant/60 text-center text-on-surface-variant text-xs">
                <span className="material-symbols-outlined text-[28px] text-[#4C8C4A] mb-1">verified_user</span>
                <p>No sanctioned addresses detected in the current transaction graph.</p>
              </div>
            )}
          </div>

          <p className="text-[10px] text-on-surface-variant leading-snug">
            {sanctionsSnapshot?.label || 'OFAC list snapshot: loading…'}. A dated snapshot of the U.S. Treasury
            SDN list, not a live feed; verify any match against official OFAC sources.
          </p>
        </section>

        {/* Wallet Risk Overview (2 columns) */}
        <section className="lg:col-span-2 flex flex-col space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-headline-md text-lg font-bold text-on-surface flex items-center gap-1.5">
              <span className="material-symbols-outlined text-primary text-[20px]">shield</span>
              <span>Wallet Risk Overview</span>
            </h3>
            {riskData.length > 5 && (
              <button
                onClick={() => setShowAllRisk(!showAllRisk)}
                className="text-primary font-label-caps text-xs uppercase hover:underline font-bold"
              >
                {showAllRisk ? 'Show Less' : `Show All ${riskData.length} Flagged Wallets`}
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {displayedRisk && displayedRisk.length > 0 ? (
              displayedRisk.map((item, idx) => {
                const tier = item.tier || 'Low';
                const isHigh = tier === 'High';
                const isMedium = tier === 'Medium';
                const badgeColor = isHigh
                  ? 'bg-error/15 text-error border-error/30'
                  : isMedium
                  ? 'bg-primary/15 text-primary border-primary/30'
                  : 'bg-[#e8f5e9] text-[#2e682c] border-[#4C8C4A]/30';

                return (
                  <div
                    key={idx}
                    className="bg-surface-container rounded-xl p-3.5 border border-outline-variant/60 shadow-xs flex flex-col justify-between hover:border-on-surface-variant transition-colors"
                  >
                    <div>
                      <div className="flex justify-between items-center mb-1.5">
                        <div className="flex items-center gap-1.5">
                          <span
                            onClick={() => copyToClipboard(item.wallet)}
                            className="font-address-md text-xs font-mono font-bold text-on-surface hover:text-primary cursor-pointer"
                            title="Click to copy full address"
                          >
                            {truncate(item.wallet)}
                          </span>
                          {item.label && (
                            <span
                              className="text-primary font-bold"
                              title={`Known Entity: ${item.label}`}
                            >
                              <span className="material-symbols-outlined text-[14px]">star</span>
                            </span>
                          )}
                        </div>

                        <span
                          className={`px-2 py-0.5 rounded-full font-label-caps text-[10px] font-bold border uppercase ${badgeColor}`}
                        >
                          {tier} · {item.score} {item.score === 1 ? 'signal' : 'signals'}
                        </span>
                      </div>

                      <div className="flex flex-wrap gap-1 mt-2">
                        {item.signals && item.signals.length > 0 ? (
                          item.signals.map((sig, sIdx) => (
                            <span
                              key={sIdx}
                              className="bg-surface px-2 py-0.5 rounded text-[10px] font-medium text-on-surface-variant border border-outline-variant/40"
                            >
                              {sig}
                            </span>
                          ))
                        ) : (
                          <span className="text-[10px] text-on-surface-variant italic">
                            Baseline profile
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="col-span-2 p-6 bg-surface rounded-xl border border-outline-variant/60 text-center text-on-surface-variant text-xs">
                No risk flags triggered in the current network view.
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Detection Technique Panels (Row 1: 3 panels, Row 2: 2 panels) */}
      <section className="space-y-6 pt-4">
        <h3 className="font-headline-md text-xl font-bold text-on-surface">
          Explainable Pattern Heuristics
        </h3>

        {/* Row 1: Hub Wallets, High Fan-Out, Peel Chains */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Panel 1: Hub Wallets */}
          <div className="bg-surface rounded-xl p-5 border border-outline-variant/60 shadow-xs flex flex-col justify-between border-l-4 border-l-[#222222]">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="material-symbols-outlined text-[20px] text-on-surface">hub</span>
                <h4 className="font-headline-md text-base font-bold text-on-surface">Hub Wallets</h4>
              </div>
              <p className="text-xs text-on-surface-variant mb-4">
                Identifies high-density intermediary nodes facilitating volume concentration.
              </p>

              <div className="space-y-2">
                {displayedHub.map((h, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded-lg bg-surface-container-low text-xs"
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="font-address-md font-mono">{truncate(h.wallet)}</span>
                      {h.label && (
                        <span className="text-primary text-[12px]" title={h.label}>
                          ★
                        </span>
                      )}
                    </div>
                    <span className="font-address-md font-bold bg-surface px-2 py-0.5 rounded border border-outline-variant/40">
                      {h.total_txs} txs
                    </span>
                  </div>
                ))}
                {displayedHub.length === 0 && (
                  <div className="text-xs text-on-surface-variant italic py-2 text-center">
                    No hub clusters detected
                  </div>
                )}
              </div>
            </div>

            {hubDetections.length > 5 && (
              <button
                onClick={() => setShowAllHub(!showAllHub)}
                className="mt-4 text-xs font-label-caps text-primary uppercase font-bold text-left hover:underline"
              >
                {showAllHub ? 'Show Less' : `Show all ${hubDetections.length} matches`}
              </button>
            )}
          </div>

          {/* Panel 2: High Fan-Out */}
          <div className="bg-surface rounded-xl p-5 border border-outline-variant/60 shadow-xs flex flex-col justify-between border-l-4 border-l-error">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="material-symbols-outlined text-[20px] text-error">call_split</span>
                <h4 className="font-headline-md text-base font-bold text-on-surface">High Fan-Out</h4>
              </div>
              <p className="text-xs text-on-surface-variant mb-4">
                Detects rapid multi-party fund splitting across distinct recipient wallets.
              </p>

              <div className="space-y-2">
                {displayedFanout.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded-lg bg-surface-container-low text-xs"
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="font-address-md font-mono">{truncate(f.wallet)}</span>
                      {f.label && (
                        <span className="text-primary text-[12px]" title={f.label}>
                          ★
                        </span>
                      )}
                    </div>
                    <span className="font-address-md font-bold bg-surface text-error px-2 py-0.5 rounded border border-outline-variant/40">
                      {f.distinct_recipients} recipients
                    </span>
                  </div>
                ))}
                {displayedFanout.length === 0 && (
                  <div className="text-xs text-on-surface-variant italic py-2 text-center">
                    No fan-out splits detected
                  </div>
                )}
              </div>
            </div>

            {fanoutDetections.length > 5 && (
              <button
                onClick={() => setShowAllFanout(!showAllFanout)}
                className="mt-4 text-xs font-label-caps text-primary uppercase font-bold text-left hover:underline"
              >
                {showAllFanout ? 'Show Less' : `Show all ${fanoutDetections.length} matches`}
              </button>
            )}
          </div>

          {/* Panel 3: Peel Chains */}
          <div className="bg-surface rounded-xl p-5 border border-outline-variant/60 shadow-xs flex flex-col justify-between border-l-4 border-l-[#2E6F95]">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="material-symbols-outlined text-[20px] text-[#2E6F95]">schema</span>
                <h4 className="font-headline-md text-base font-bold text-on-surface">Peel Chains</h4>
              </div>
              <p className="text-xs text-on-surface-variant mb-4">
                Uncovers asymmetric split layering where small amounts are peeled off continuously.
              </p>

              <div className="space-y-2">
                {displayedPeel.map((p, i) => (
                  <div
                    key={i}
                    className="flex flex-col gap-1 p-2 rounded-lg bg-surface-container-low text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="font-address-md font-mono">{truncate(p.wallet)}</span>
                        {p.label && (
                          <span className="text-primary text-[12px]" title={p.label}>
                            ★
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-on-surface-variant font-label-caps uppercase font-bold">
                        Peel Ratio
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] font-address-md text-on-surface-variant">
                      <span>Main: {Number(p.main_amount).toFixed(2)} ETH</span>
                      <span className="text-[#2E6F95] font-bold">
                        Peel: {Number(p.peel_amount).toFixed(4)} ETH
                      </span>
                    </div>
                  </div>
                ))}
                {displayedPeel.length === 0 && (
                  <div className="text-xs text-on-surface-variant italic py-2 text-center">
                    No peel chains detected
                  </div>
                )}
              </div>
            </div>

            {peelDetections.length > 5 && (
              <button
                onClick={() => setShowAllPeel(!showAllPeel)}
                className="mt-4 text-xs font-label-caps text-primary uppercase font-bold text-left hover:underline"
              >
                {showAllPeel ? 'Show Less' : `Show all ${peelDetections.length} matches`}
              </button>
            )}
          </div>
        </div>

        {/* Row 2: Round-Number Transactions & Circular Flows */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Panel 4: Round-Number Transactions */}
          <div className="bg-surface rounded-xl p-5 border border-outline-variant/60 shadow-xs flex flex-col justify-between border-l-4 border-l-[#FF6D1F]">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="material-symbols-outlined text-[20px] text-[#FF6D1F]">tag</span>
                <h4 className="font-headline-md text-base font-bold text-on-surface">
                  Round-Number Transactions
                </h4>
              </div>
              <p className="text-xs text-on-surface-variant mb-4">
                Structured whole-integer transfers commonly indicative of automated mixing or smurfing.
              </p>

              <div className="space-y-2">
                {displayedRound.map((r, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded-lg bg-surface-container-low text-xs"
                  >
                    <div className="flex items-center gap-1.5 font-address-md font-mono text-[11px]">
                      <span>{truncate(r.from)}</span>
                      <span className="text-on-surface-variant">→</span>
                      <span>{truncate(r.to)}</span>
                    </div>
                    <span className="font-address-md font-bold text-[#FF6D1F] bg-surface px-2 py-0.5 rounded border border-outline-variant/40">
                      {r.value} ETH
                    </span>
                  </div>
                ))}
                {displayedRound.length === 0 && (
                  <div className="text-xs text-on-surface-variant italic py-2 text-center">
                    No round integer transactions found
                  </div>
                )}
              </div>
            </div>

            {roundDetections.length > 5 && (
              <button
                onClick={() => setShowAllRound(!showAllRound)}
                className="mt-4 text-xs font-label-caps text-primary uppercase font-bold text-left hover:underline"
              >
                {showAllRound ? 'Show Less' : `Show all ${roundDetections.length} matches`}
              </button>
            )}
          </div>

          {/* Panel 5: Circular Flows */}
          <div className="bg-surface rounded-xl p-5 border border-outline-variant/60 shadow-xs flex flex-col justify-between border-l-4 border-l-[#6B4E8E]">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="material-symbols-outlined text-[20px] text-[#6B4E8E]">change_circle</span>
                <h4 className="font-headline-md text-base font-bold text-on-surface">
                  Circular Flows
                </h4>
              </div>
              <p className="text-xs text-on-surface-variant mb-4">
                Closed loops where funds cycle back to the origin address to conceal illicit provenance.
              </p>

              <div className="space-y-2">
                {displayedCircular.map((c, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded-lg bg-surface-container-low text-xs"
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="font-address-md font-mono">{truncate(c.wallet)}</span>
                      {c.label && (
                        <span className="text-primary text-[12px]" title={c.label}>
                          ★
                        </span>
                      )}
                    </div>
                    <span className="font-address-md font-bold text-[#6B4E8E] bg-surface px-2 py-0.5 rounded border border-outline-variant/40">
                      {c.hops} hops loop
                    </span>
                  </div>
                ))}
                {displayedCircular.length === 0 && (
                  <div className="text-xs text-on-surface-variant italic py-2 text-center">
                    No circular flow loops detected
                  </div>
                )}
              </div>
            </div>

            {circularDetections.length > 5 && (
              <button
                onClick={() => setShowAllCircular(!showAllCircular)}
                className="mt-4 text-xs font-label-caps text-primary uppercase font-bold text-left hover:underline"
              >
                {showAllCircular ? 'Show Less' : `Show all ${circularDetections.length} matches`}
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
};

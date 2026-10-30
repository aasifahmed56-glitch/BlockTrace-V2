// Describes what a trace covered. Mirrors describe_scope() in logic.py, which
// writes the same line into the PDF dossier.
export const describeScope = (scope) => {
  if (!scope) return null;
  const cap = scope.tx_per_wallet;
  const oldestFirst = scope.sort === 'asc';
  const parts = [];
  if (scope.from_date || scope.to_date) {
    parts.push(`Transactions ${scope.from_date || 'start'} to ${scope.to_date || 'today'}`);
    parts.push(oldestFirst ? 'oldest first' : 'newest first');
    if (cap) parts.push(`up to ${cap} per wallet`);
  } else {
    parts.push(`All dates (${oldestFirst ? 'oldest' : 'newest'} ${cap} per wallet)`);
  }
  if (scope.hops) parts.push(`${scope.hops} hops`);
  if (scope.chain) parts.push(scope.chain);
  if (scope.incident_date) parts.push(`incident ${scope.incident_date}`);
  return parts.join(' · ');
};

// Warning shown when the per-wallet cap cut a trace short.
export const describeCap = (limitedWallets, txPerWallet) => {
  const n = limitedWallets?.length || 0;
  if (!n) return null;
  return `${n} wallet(s) have more transactions than the cap (${txPerWallet}). Older/newer activity is not shown. Narrow the date range or raise 'Tx per wallet'.`;
};

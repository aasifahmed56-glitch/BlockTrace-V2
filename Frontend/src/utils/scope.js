// Describes what a trace covered. Mirrors describe_scope() in logic.py, which
// writes the same line into the PDF dossier. For a path search, hops is the most
// the search was allowed to go, so pass { maxHops: true } to say "max N hops".
export const describeScope = (scope, { maxHops = false } = {}) => {
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
  if (scope.hops) parts.push(`${maxHops ? 'max ' : ''}${scope.hops} ${scope.hops === 1 ? 'hop' : 'hops'}`);
  if (scope.chain) parts.push(scope.chain);
  if (scope.incident_date) parts.push(`incident ${scope.incident_date}`);
  // Scopes from before the option existed fetched internal transfers.
  parts.push(scope.include_internal === false ? 'normal transactions only' : 'normal + internal transfers');
  return parts.join(' · ');
};

// "Failed skipped N", split by kind when internal transfers failed too.
// Mirrors describe_failed_skipped() in logic.py.
export const describeFailedSkipped = (q) => {
  const internal = q.failed_skipped_internal || 0;
  if (!internal) return `Failed skipped ${q.failed_skipped}`;
  const normal = q.failed_skipped_normal ?? q.failed_skipped - internal;
  return `Failed skipped ${normal} (normal) / ${internal} (internal)`;
};

// The Data quality line. Mirrors describe_data_quality() in logic.py (PDF dossier).
export const describeDataQuality = (q) => {
  if (!q) return null;
  const zeroPart = (zero) => (zero ? `, ${zero} zero-value ${q.show_zero_value ? 'shown' : 'hidden'}` : '');
  const normal = q.normal_stored || 0;
  const withEth = q.normal_with_eth || 0;
  const parts = [`Normal ${normal} (${withEth} with ETH${zeroPart(normal - withEth)})`];
  const internal = q.internal_stored || 0;
  if (q.internal_counted) parts.push(`Internal ${internal}`);
  else if (internal) parts.push(`Internal off (${internal} stored, not counted)`);
  else parts.push('Internal off');
  if (q.failed_skipped != null) parts.push(describeFailedSkipped(q));
  if (q.capped_wallets) parts.push(`Capped wallets ${q.capped_wallets}`);
  return parts.join(' · ');
};

// Warning shown when the per-wallet cap cut a trace short.
export const describeCap = (limitedWallets, txPerWallet) => {
  const n = limitedWallets?.length || 0;
  if (!n) return null;
  return `${n} wallet(s) have more transactions than the cap (${txPerWallet}). Older/newer activity is not shown. Narrow the date range or raise 'Tx per wallet'.`;
};

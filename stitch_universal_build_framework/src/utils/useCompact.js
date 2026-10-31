import { useEffect, useState } from 'react';

// Phones and tablets (< 1024 px) get the compact layout; desktop is unchanged.
export const COMPACT_QUERY = '(max-width: 1023.98px)';

const matches = () => typeof window !== 'undefined' && !!window.matchMedia?.(COMPACT_QUERY).matches;

export const useCompact = () => {
  const [compact, setCompact] = useState(matches);
  useEffect(() => {
    const mq = window.matchMedia?.(COMPACT_QUERY);
    if (!mq) return undefined;
    const onChange = () => setCompact(mq.matches);
    onChange();
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, []);
  return compact;
};

// 0x098B…2f96
export const midTruncate = (value, head = 6, tail = 4) => {
  if (!value) return '';
  const s = String(value);
  return s.length <= head + tail + 1 ? s : `${s.slice(0, head)}…${s.slice(-tail)}`;
};

// Clipboard with a fallback for WebView2 / insecure contexts.
export const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
};

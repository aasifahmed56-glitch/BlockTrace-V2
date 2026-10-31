import React, { useEffect, useId, useRef, useState } from 'react';

// Bottom sheet for phones and tablets. Drag the handle (or tap it) to switch between
// half and full height; drag down from half height, tap the backdrop or press Esc to close.
// initial='auto' sizes the sheet to its content (menus).
export const Sheet = ({ open, onClose, title, children, initial = 'half', draggable = true, id }) => {
  const [snap, setSnap] = useState(initial);
  const [dragY, setDragY] = useState(0);
  const start = useRef(null);
  const panelRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const titleId = useId();

  useEffect(() => {
    if (open) setSnap(initial);
  }, [open, initial]);

  useEffect(() => {
    if (!open) return undefined;
    const opener = document.activeElement;
    panelRef.current?.focus({ preventScroll: true });
    const onKey = (e) => {
      if (e.key === 'Escape') onCloseRef.current?.();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      if (opener && typeof opener.focus === 'function') opener.focus({ preventScroll: true });
    };
  }, [open]);

  if (!open) return null;

  const onPointerDown = (e) => {
    if (!draggable) return;
    start.current = e.clientY;
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e) => {
    if (start.current === null) return;
    setDragY(e.clientY - start.current);
  };
  const onPointerUp = () => {
    if (start.current === null) return;
    const dy = dragY;
    start.current = null;
    setDragY(0);
    if (Math.abs(dy) < 6) {
      setSnap((s) => (s === 'half' ? 'full' : 'half'));
    } else if (dy < -60) {
      setSnap('full');
    } else if (dy > 60) {
      if (snap === 'full') setSnap('half');
      else onCloseRef.current?.();
    }
  };

  const height = snap === 'full' ? 'calc(100dvh - 24px - env(safe-area-inset-top))' : '58dvh';

  return (
    <div className="fixed inset-0 z-[10000]" id={id}>
      <div className="absolute inset-0 bg-black/45" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="absolute inset-x-0 bottom-0 bg-surface rounded-t-2xl shadow-2xl border-t border-outline-variant flex flex-col outline-none"
        style={{
          height: snap === 'auto' ? 'auto' : height,
          maxHeight: 'calc(100dvh - 24px - env(safe-area-inset-top))',
          transform: dragY > 0 ? `translateY(${dragY}px)` : undefined,
          transition: start.current === null ? 'height 200ms ease, transform 200ms ease' : 'none',
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}
      >
        <div
          className="flex-none flex flex-col items-center pt-2 pb-1 touch-none select-none cursor-grab"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          {draggable && (
            <button
              type="button"
              className="w-14 h-6 flex items-center justify-center"
              aria-label={snap === 'half' ? 'Expand to full height' : 'Shrink to half height'}
              onClick={(e) => e.preventDefault()}
            >
              <span className="block w-10 h-1.5 rounded-full bg-outline-variant" aria-hidden="true" />
            </button>
          )}
        </div>
        <div className="flex-none flex items-center justify-between gap-2 px-4 pb-2 border-b border-outline-variant/60">
          <h2 id={titleId} className="font-headline-md text-base font-bold text-on-surface min-w-0 truncate">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="w-11 h-11 -mr-2 flex items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container"
            aria-label="Close"
          >
            <span className="material-symbols-outlined text-[22px]">close</span>
          </button>
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-4 py-3">{children}</div>
      </div>
    </div>
  );
};

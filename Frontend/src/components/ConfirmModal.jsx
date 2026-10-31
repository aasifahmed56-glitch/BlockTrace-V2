import React from 'react';

export const ConfirmModal = ({ isOpen, title, message, confirmText = 'Confirm', confirmVariant = 'danger', onConfirm, onCancel }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-surface border border-outline-variant rounded-xl shadow-2xl max-w-md w-full p-6 relative overflow-hidden">
        <div className="flex items-center gap-3 mb-3">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
            confirmVariant === 'danger' ? 'bg-error/15 text-error' : 'bg-primary/15 text-primary'
          }`}>
            <span className="material-symbols-outlined text-[22px]">
              {confirmVariant === 'danger' ? 'warning' : 'info'}
            </span>
          </div>
          <h3 className="font-headline-md text-lg text-on-surface font-semibold">{title}</h3>
        </div>

        <p className="font-body-md text-sm text-on-surface-variant mb-6 leading-relaxed">
          {message}
        </p>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-lg border border-outline-variant text-on-surface hover:bg-surface-container transition-colors text-sm font-medium"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg text-white font-label-caps text-xs uppercase shadow-sm transition-colors ${
              confirmVariant === 'danger'
                ? 'bg-error hover:bg-error/90'
                : 'bg-primary hover:bg-primary/90'
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

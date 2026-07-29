/**
 * Image Lightbox Modal Component
 * ==============================
 * Displays full-size images in a dark overlay modal when a thumbnail is clicked.
 */

import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, ZoomIn, Download } from 'lucide-react';

interface ImageLightboxProps {
  src: string;
  alt?: string;
  isOpen: boolean;
  onClose: () => void;
}

export function ImageLightbox({ src, alt, isOpen, onClose }: ImageLightboxProps) {
  // Listen for ESC key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen || !src || typeof document === 'undefined') return null;

  // Portalled to <body>: this component is rendered from inside a message
  // bubble that carries .glass-panel (backdrop-filter), which establishes a
  // containing block for `position: fixed` descendants and a new stacking
  // context. Without the portal, "fullscreen" resolves against the bubble,
  // not the viewport — a lightbox the size of one chat message.
  return createPortal(
    <div
      className="modal-scrim items-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative max-w-[90vw] max-h-[90vh] flex flex-col items-center justify-center"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Controls header */}
        <div className="absolute -top-12 right-0 flex items-center gap-3">
          <a
            href={src}
            target="_blank"
            rel="noopener noreferrer"
            download
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface/80 hover:bg-surface border border-border text-xs text-text transition-colors"
            title="Tải về"
          >
            <Download size={14} />
            <span>Tải ảnh</span>
          </a>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-surface/80 hover:bg-surface border border-border text-text hover:text-white transition-colors"
            title="Đóng (Esc)"
          >
            <X size={18} />
          </button>
        </div>

        {/* Full-size image */}
        <img
          src={src}
          alt={alt || 'Full size preview'}
          className="max-w-[90vw] max-h-[85vh] object-contain rounded-xl shadow-2xl border border-border/40 select-none"
        />

        {alt && (
          <p className="mt-3 text-xs text-text-muted text-center max-w-lg truncate">
            {alt}
          </p>
        )}
      </div>
    </div>,
    document.body
  );
}

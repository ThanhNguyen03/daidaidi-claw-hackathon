/**
 * AttentionField
 * ==============
 * Canvas backdrop for the welcome screen: drifting nodes that draw a link when
 * they come close, the edge fading with distance. A transformer decides which
 * tokens attend to which, and the strength of that link is a weight — this is
 * that picture, slowed down until it reads as atmosphere.
 *
 * Hand-written rather than pulled from a library. particles.js is ~25KB gzipped
 * and tsparticles ~90KB, for an effect that is 80 lines of canvas. This is the
 * first screen anyone sees, so it is the worst place to spend startup budget.
 *
 * Costs held down deliberately:
 *   - node count scales with viewport area and hard-caps at 70
 *   - links are only searched forward through the array, so each pair is tested
 *     once — O(n²/2) over at most 70 nodes, a few thousand cheap comparisons
 *   - the loop stops entirely when the tab is hidden
 *   - nothing renders at all under prefers-reduced-motion
 */

'use client';

import React, { useEffect, useRef } from 'react';

const LINK_DISTANCE = 130;
const SPEED = 0.13;

export function AttentionField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let raf = 0;
    let nodes: { x: number; y: number; vx: number; vy: number; r: number }[] = [];

    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const build = () => {
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const count = Math.min(70, Math.round((width * height) / 22000));
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * SPEED,
        vy: (Math.random() - 0.5) * SPEED,
        r: Math.random() * 1.5 + 0.7,
      }));
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        a.x += a.vx;
        a.y += a.vy;

        // Wrap rather than bounce: bouncing makes the edges feel like walls and
        // the eye starts tracking the boundary instead of the field.
        if (a.x < -20) a.x = width + 20;
        if (a.x > width + 20) a.x = -20;
        if (a.y < -20) a.y = height + 20;
        if (a.y > height + 20) a.y = -20;

        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy);
          if (dist >= LINK_DISTANCE) continue;

          // Opacity as attention weight: closer pairs bind more strongly.
          const w = (1 - dist / LINK_DISTANCE) * 0.22;
          ctx.strokeStyle = `rgba(0, 104, 255, ${w})`;
          ctx.lineWidth = 0.7;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }

        ctx.fillStyle = 'rgba(61, 148, 255, 0.55)';
        ctx.beginPath();
        ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2);
        ctx.fill();
      }

      raf = requestAnimationFrame(draw);
    };

    const start = () => {
      if (!raf) raf = requestAnimationFrame(draw);
    };
    const stop = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    };

    // A backdrop nobody is looking at should not keep a core awake.
    const onVisibility = () => (document.hidden ? stop() : start());

    build();
    start();

    const observer = new ResizeObserver(build);
    observer.observe(canvas);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      stop();
      observer.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
      style={{
        // Sits above the CSS lattice, below the card. Masked so the field thins
        // out behind the panel and never competes with the text on it.
        zIndex: 0,
        maskImage: 'radial-gradient(70% 70% at 50% 50%, transparent 18%, #000 55%)',
        WebkitMaskImage: 'radial-gradient(70% 70% at 50% 50%, transparent 18%, #000 55%)',
      }}
    />
  );
}

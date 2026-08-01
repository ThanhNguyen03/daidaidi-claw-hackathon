// AdtimaBox Wireframe — plugin main thread.
// Fetches a wireframe spec by job code from the AdtimaBox backend and draws
// low-fidelity mobile screens with the Figma Plugin API.

var DEFAULT_API = 'https://zah-28.123c.vn/api';
var STORAGE_KEY = 'adtimabox.apiBase';

var C = {
  page: '#F3F4F6',
  surface: '#FFFFFF',
  line: '#E5E7EB',
  chip: '#E5E7EB',
  stroke: '#D1D5DB',
  dash: '#9CA3AF',
  hint: '#9CA3AF',
  muted: '#6B7280',
  ink: '#111827',
  accent: '#F65009',
  onAccent: '#FFFFFF',
  // Tints derived from the single accent, so the palette stays one accent wide.
  accentSoft: '#FFEDE6',
  accentLine: '#FAC7B1',
  // Two semantic tints for `note`. Amber for warning, grey-blue for info —
  // both desaturated enough that they never compete with the accent.
  warnInk: '#92400E',
  warnSoft: '#FEF6E4',
  warnLine: '#F5DFA8',
  infoInk: '#3F4E5F',
  infoSoft: '#EFF2F6',
  infoLine: '#D3DBE4',
  scrim: '#111827'
};

var PHONE_W = 375;
var PHONE_H = 812;
var GAP = 60;
var PAD = 48;

// Nominal content width of a screen body (PHONE_W minus the body's 20px padding).
// Used where a child has to be sized as a fraction of its container — Figma
// auto-layout has no percentage widths and layoutGrow is 0/1 only, so a progress
// bar's filled portion is computed against this nominal width and the track clips
// anything that overhangs. A ZNS card body is 32px narrower; the bar reads full
// there rather than throwing, which is the right way to be wrong.
var BODY_W = PHONE_W - 40;

var FONT = 'Inter';

// ---------------------------------------------------------------- primitives

function hexToRgb(hex) {
  var h = String(hex).replace('#', '');
  return {
    r: parseInt(h.slice(0, 2), 16) / 255,
    g: parseInt(h.slice(2, 4), 16) / 255,
    b: parseInt(h.slice(4, 6), 16) / 255
  };
}

// fills/strokes are read-only arrays — always assign a freshly built one.
function paint(hex) {
  return [{ type: 'SOLID', color: hexToRgb(hex) }];
}

function str(v) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'string') return v;
  return String(v);
}

// Non-array where an array is expected degrades to empty rather than throwing.
function arr(v, max) {
  if (!Array.isArray(v)) return [];
  return max ? v.slice(0, max) : v.slice();
}

// A 0..1 fraction, or null when the spec gave something that is not a number.
// Deliberately rejects numeric strings: a caller that sends "0.5" has a bug, and
// an empty bar makes that visible instead of hiding it.
function frac(v) {
  if (typeof v !== 'number' || !isFinite(v)) return null;
  return v < 0 ? 0 : (v > 1 ? 1 : v);
}

// A user-visible label. An object or array where the spec promised a string
// degrades to the fallback instead of drawing "[object Object]".
function label(v, dflt) {
  if (v === null || v === undefined || typeof v === 'object') return dflt;
  return str(v).trim() || dflt;
}

// 0-based index into a list of `len`; anything out of range falls back to the first.
function idx(v, len) {
  if (typeof v !== 'number' || !isFinite(v)) return 0;
  var n = Math.floor(v);
  return (n < 0 || n >= len) ? 0 : n;
}

function newFrame() {
  // figma.createAutoLayout() only exists on newer API versions; a plain frame
  // with layoutMode set is the same node.
  return typeof figma.createAutoLayout === 'function' ? figma.createAutoLayout() : figma.createFrame();
}

function autoLayout(name, o) {
  o = o || {};
  var f = newFrame();
  f.name = name;
  f.layoutMode = o.dir || 'VERTICAL';
  f.itemSpacing = o.gap == null ? 0 : o.gap;
  var p = o.pad == null ? 0 : o.pad;
  f.paddingTop = o.padTop == null ? p : o.padTop;
  f.paddingBottom = o.padBottom == null ? p : o.padBottom;
  f.paddingLeft = o.padX == null ? p : o.padX;
  f.paddingRight = o.padX == null ? p : o.padX;
  // resize() resets both sizing modes to FIXED, so it has to come first. Never pass
  // the frame's own measured size back in — an empty auto-layout frame hugs to ~0.
  if (o.w || o.h) f.resize(o.w || Math.max(f.width, 1), o.h || Math.max(f.height, 1));
  f.primaryAxisSizingMode = o.primary || 'AUTO';
  f.counterAxisSizingMode = o.counter || 'AUTO';
  if (o.alignPrimary) f.primaryAxisAlignItems = o.alignPrimary;
  if (o.alignCounter) f.counterAxisAlignItems = o.alignCounter;
  f.fills = o.fillHex ? paint(o.fillHex) : [];
  if (o.strokeHex) {
    f.strokes = paint(o.strokeHex);
    f.strokeWeight = o.strokeW || 1;
    f.strokeAlign = 'INSIDE';
    if (o.dashed) f.dashPattern = [6, 4];
  }
  if (o.radius) f.cornerRadius = o.radius;
  f.clipsContent = o.clip == null ? false : o.clip;
  return f;
}

function text(chars, o) {
  o = o || {};
  var t = figma.createText();
  t.name = 'label';
  t.fontName = { family: FONT, style: o.style || 'Regular' };
  var size = o.size || 14;
  t.fontSize = size;
  t.lineHeight = { value: Math.round(size * 1.45), unit: 'PIXELS' };
  if (o.hug) {
    t.textAutoResize = 'WIDTH_AND_HEIGHT';
  } else {
    // Wrapping text collapses to a near-zero-width thread without an explicit width.
    t.textAutoResize = 'HEIGHT';
    t.resize(o.w || 280, t.height);
  }
  t.characters = str(chars);
  t.fills = paint(o.hex || C.ink);
  if (o.align) t.textAlignHorizontal = o.align;
  // Tracking stands in for a monospace family: loadFonts() only carries
  // Inter/Roboto, and adding a family there is a bigger change than a code/QR
  // string is worth.
  if (o.track) t.letterSpacing = { value: o.track, unit: 'PIXELS' };
  return t;
}

// FILL/HUG are only accepted once the node sits inside an auto-layout parent.
function place(parent, child, h, v) {
  parent.appendChild(child);
  if (h) child.layoutSizingHorizontal = h;
  if (v) child.layoutSizingVertical = v;
  return child;
}

function bottomBorder(node, hex) {
  node.strokes = paint(hex);
  node.strokeAlign = 'INSIDE';
  node.strokeWeight = 1;
  if ('strokeBottomWeight' in node) {
    node.strokeTopWeight = 0;
    node.strokeLeftWeight = 0;
    node.strokeRightWeight = 0;
    node.strokeBottomWeight = 1;
  }
}

function topBorder(node, hex) {
  node.strokes = paint(hex);
  node.strokeAlign = 'INSIDE';
  node.strokeWeight = 1;
  if ('strokeTopWeight' in node) {
    node.strokeTopWeight = 1;
    node.strokeLeftWeight = 0;
    node.strokeRightWeight = 0;
    node.strokeBottomWeight = 0;
  }
}

// A transparent, layout-occupying filler. Figma drops hidden children out of an
// auto-layout flow, so `visible = false` would collapse the gap it exists to hold —
// no fill is what makes it invisible.
function spacer(parent) {
  var sp = autoLayout('spacer', { dir: 'VERTICAL', h: 1, primary: 'FIXED', counter: 'FIXED' });
  return place(parent, sp, 'FILL', 'FIXED');
}

// A 1px-wide frame whose own dashed stroke reads as a dashed vertical rule.
function vDashLine(h) {
  var l = autoLayout('divider-dashed', {
    dir: 'VERTICAL', w: 1, h: h || 96, primary: 'FIXED', counter: 'FIXED'
  });
  l.strokes = paint(C.dash);
  l.strokeAlign = 'INSIDE';
  l.strokeWeight = 1;
  l.dashPattern = [5, 4];
  return l;
}

function vRule(h, hex) {
  return autoLayout('divider', {
    dir: 'VERTICAL', w: 1, h: h || 30, primary: 'FIXED', counter: 'FIXED', fillHex: hex || C.line
  });
}

// The track is meant to be FILLed by the caller; the filled portion is a fixed
// width computed against `w` (see BODY_W) and the track clips the overhang.
function progressBar(v, w, fillHex) {
  var nominal = Math.max(40, w || BODY_W);
  var track = autoLayout('progress-track', {
    dir: 'HORIZONTAL', h: 8, w: nominal, primary: 'FIXED', counter: 'FIXED',
    radius: 4, fillHex: C.chip, clip: true
  });
  if (v > 0) {
    // resize(0, …) throws, so a zero-value bar simply has no filled child.
    var bar = autoLayout('progress-value', {
      dir: 'HORIZONTAL', h: 8, w: Math.max(4, Math.round(nominal * v)),
      primary: 'FIXED', counter: 'FIXED', radius: 4, fillHex: fillHex || C.accent
    });
    track.appendChild(bar);
  }
  return track;
}

// A dashed image region with the emoji centred — carousel cards and grid tiles
// share it so the two read as the same family of placeholder.
function imageRegion(emoji, h, size) {
  var box = autoLayout('image', {
    dir: 'VERTICAL', h: h || 80, primary: 'FIXED',
    alignPrimary: 'CENTER', alignCounter: 'CENTER', radius: 8,
    fillHex: C.page, strokeHex: C.dash, strokeW: 1.5, dashed: true
  });
  place(box, text(emoji || '🖼️', { size: size || 24, hug: true }));
  return box;
}

// ------------------------------------------------------------------- blocks

function blockAppbar(b) {
  var bar = autoLayout('appbar', {
    dir: 'HORIZONTAL', gap: 12, padX: 16, h: 56,
    counter: 'FIXED', alignCounter: 'CENTER', fillHex: C.surface
  });
  bottomBorder(bar, C.line);
  if (b.back) place(bar, text('←', { size: 18, style: 'Medium', hug: true }));
  place(bar, text(str(b.title) || 'Tiêu đề', { size: 16, style: 'Bold' }), 'FILL', 'HUG');
  return bar;
}

function blockBanner(b) {
  var box = autoLayout('banner', {
    dir: 'HORIZONTAL', gap: 12, padX: 16, padTop: 16, padBottom: 16, h: 120,
    counter: 'FIXED', alignCounter: 'CENTER', radius: 12,
    fillHex: C.surface, strokeHex: C.dash, strokeW: 1.5, dashed: true
  });
  if (b.emoji) place(box, text(b.emoji, { size: 28, hug: true }));
  place(box, text(str(b.text) || 'Banner / KV', { size: 14, hex: C.muted }), 'FILL', 'HUG');
  return box;
}

function blockText(b) {
  var style = str(b.style) || 'body';
  var spec = { heading: { size: 20, style: 'Bold', hex: C.ink },
               caption: { size: 11, style: 'Regular', hex: C.muted },
               body: { size: 14, style: 'Regular', hex: C.ink } }[style] ||
             { size: 14, style: 'Regular', hex: C.ink };
  var t = text(str(b.text) || '…', spec);
  t.name = 'text/' + style;
  return t;
}

function blockCard(b) {
  var card = autoLayout('card', {
    dir: 'VERTICAL', gap: 8, pad: 16, radius: 12,
    fillHex: C.surface, strokeHex: C.line, strokeW: 1
  });
  if (b.title) place(card, text(b.title, { size: 15, style: 'Medium' }), 'FILL', 'HUG');
  if (b.subtitle) place(card, text(b.subtitle, { size: 12, hex: C.muted }), 'FILL', 'HUG');
  var rows = Array.isArray(b.rows) ? b.rows : [];
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i] || {};
    var row = autoLayout('row', { dir: 'HORIZONTAL', gap: 8, alignCounter: 'CENTER' });
    place(card, row, 'FILL', 'HUG');
    place(row, text(str(r.label) || '—', { size: 12, hex: C.muted }), 'FILL', 'HUG');
    place(row, text(str(r.value) || '—', { size: 12, style: 'Medium', hug: true, align: 'RIGHT' }));
  }
  if (!b.title && !b.subtitle && !rows.length) {
    place(card, text('Thẻ nội dung', { size: 12, hex: C.hint }), 'FILL', 'HUG');
  }
  return card;
}

function blockList(b) {
  var list = autoLayout('list', {
    dir: 'VERTICAL', gap: 12, pad: 16, radius: 12,
    fillHex: C.surface, strokeHex: C.line, strokeW: 1
  });
  if (b.title) place(list, text(b.title, { size: 15, style: 'Medium' }), 'FILL', 'HUG');
  var items = Array.isArray(b.items) ? b.items : [];
  for (var i = 0; i < items.length; i++) {
    var it = items[i] || {};
    var row = autoLayout('item', { dir: 'HORIZONTAL', gap: 12, alignCounter: 'CENTER' });
    place(list, row, 'FILL', 'HUG');
    place(row, text(str(it.emoji) || '▫️', { size: 20, hug: true }));
    var col = autoLayout('item-text', { dir: 'VERTICAL', gap: 2 });
    place(row, col, 'FILL', 'HUG');
    place(col, text(str(it.title) || 'Mục', { size: 13, style: 'Medium' }), 'FILL', 'HUG');
    if (it.sub) place(col, text(it.sub, { size: 11, hex: C.muted }), 'FILL', 'HUG');
    // A trailing value (price, points, date) takes the chevron's slot when present —
    // the row can only carry one trailing element without crowding.
    var meta = label(it.meta, '');
    if (meta) {
      place(row, text(meta, { size: 12, style: 'Medium', hug: true, align: 'RIGHT' }));
    } else {
      place(row, text('›', { size: 16, hex: C.hint, hug: true }));
    }
  }
  if (!items.length) place(list, text('Danh sách trống', { size: 12, hex: C.hint }), 'FILL', 'HUG');
  return list;
}

var FIELD_TYPES = { text: 1, phone: 1, select: 1, date: 1, textarea: 1 };

function blockField(b) {
  var type = str(b.type).trim().toLowerCase();
  if (!FIELD_TYPES[type]) type = 'text'; // unknown or missing behaves as a plain text input
  var tall = type === 'textarea';

  var wrap = autoLayout('field/' + type, { dir: 'VERTICAL', gap: 6 });
  place(wrap, text(str(b.label) || 'Nhãn', { size: 12, hex: C.muted }), 'FILL', 'HUG');
  var box = autoLayout('input', {
    dir: 'HORIZONTAL', gap: 8, padX: 12,
    padTop: tall ? 12 : 0, padBottom: tall ? 12 : 0,
    h: tall ? 132 : 44, counter: 'FIXED', alignCounter: tall ? 'MIN' : 'CENTER',
    radius: 10, fillHex: C.surface, strokeHex: C.stroke, strokeW: 1
  });
  place(wrap, box, 'FILL', 'FIXED');
  place(box, text(str(b.placeholder) || 'Nhập…', { size: 13, hex: C.hint }), 'FILL', 'HUG');
  // '▾' rather than '⌄': the arrowhead codepoint is missing from Inter and would
  // render as tofu.
  if (type === 'select') place(box, text('▾', { size: 12, hex: C.hint, hug: true }));
  else if (type === 'date') place(box, text('📅', { size: 14, hug: true }));
  return wrap;
}

function blockCta(b) {
  var secondary = str(b.variant) === 'secondary';
  var btn = autoLayout('cta/' + (secondary ? 'secondary' : 'primary'), {
    dir: 'HORIZONTAL', h: 48, counter: 'FIXED', radius: 12,
    alignPrimary: 'CENTER', alignCounter: 'CENTER',
    fillHex: secondary ? C.surface : C.accent,
    strokeHex: secondary ? C.accent : null, strokeW: 1.5
  });
  place(btn, text(str(b.text) || 'Tiếp tục', {
    size: 15, style: 'Bold', hug: true, hex: secondary ? C.accent : C.onAccent
  }));
  return btn;
}

function blockTabbar(b) {
  var items = Array.isArray(b.items) ? b.items.slice(0, 5) : [];
  if (!items.length) items = ['Trang chủ', 'Ưu đãi', 'Tài khoản'];
  var bar = autoLayout('tabbar', {
    dir: 'HORIZONTAL', padX: 8, padTop: 10, padBottom: 14, h: 64,
    counter: 'FIXED', fillHex: C.surface
  });
  topBorder(bar, C.line);
  for (var i = 0; i < items.length; i++) {
    var tab = autoLayout('tab', { dir: 'VERTICAL', gap: 5, alignPrimary: 'CENTER', alignCounter: 'CENTER' });
    place(bar, tab, 'FILL', 'FILL');
    var icon = autoLayout('icon', {
      dir: 'VERTICAL', w: 20, h: 20, primary: 'FIXED', counter: 'FIXED',
      radius: 6, fillHex: i === 0 ? C.accent : C.chip
    });
    tab.appendChild(icon);
    place(tab, text(str(items[i]), {
      size: 10, hug: true, align: 'CENTER', hex: i === 0 ? C.accent : C.muted
    }));
  }
  return bar;
}

function blockPlaceholder(b, label) {
  var box = autoLayout('placeholder', {
    dir: 'VERTICAL', pad: 16, h: 120, primary: 'FIXED',
    alignPrimary: 'CENTER', alignCounter: 'CENTER', radius: 12,
    fillHex: C.surface, strokeHex: C.dash, strokeW: 1.5, dashed: true
  });
  place(box, text(label || str(b.label) || 'Nội dung', {
    size: 12, hex: C.muted, align: 'CENTER'
  }), 'FILL', 'HUG');
  return box;
}

// An in-screen segmented control. Underline + weight carries the active state, which
// is what keeps it visually distinct from `tabbar` (icon tiles pinned to the bottom).
function blockTabs(b) {
  var items = arr(b.items, 4);
  if (!items.length) items = ['Tất cả', 'Đang dùng'];
  var bar = autoLayout('tabs', { dir: 'HORIZONTAL', gap: 0, fillHex: C.surface });
  bottomBorder(bar, C.line);
  for (var i = 0; i < items.length; i++) {
    var on = i === 0; // first item is the active one, by contract
    var tab = autoLayout('tab', { dir: 'VERTICAL', gap: 9, padTop: 11, alignCounter: 'CENTER' });
    place(bar, tab, 'FILL', 'HUG');
    place(tab, text(label(items[i], 'Tab'), {
      size: 13, style: on ? 'Bold' : 'Regular', hug: true, align: 'CENTER',
      hex: on ? C.ink : C.muted
    }));
    // The inactive underline is a transparent frame, not a missing one, so every
    // tab keeps the same height.
    var rule = autoLayout('underline', {
      dir: 'VERTICAL', h: 2, primary: 'FIXED', counter: 'FIXED', fillHex: on ? C.accent : null
    });
    place(tab, rule, 'FILL', 'FIXED');
  }
  return bar;
}

// Structural label, so no card background of its own.
function blockSection(b) {
  var row = autoLayout('section', { dir: 'HORIZONTAL', gap: 8, alignCounter: 'CENTER' });
  place(row, text(str(b.title) || 'Mục', { size: 15, style: 'Bold' }), 'FILL', 'HUG');
  if (str(b.action)) {
    place(row, text(str(b.action), {
      size: 12, style: 'Medium', hex: C.accent, hug: true, align: 'RIGHT'
    }));
  }
  return row;
}

// The row is given a fixed width wider than the screen and is NOT filled, so the
// last card runs past the phone frame's right edge and the frame's clipsContent
// cuts it — that cut is the whole "this scrolls sideways" signal. The wrapper does
// not clip, so the overflow reaches the frame edge instead of the body padding.
function blockCarousel(b) {
  var items = arr(b.items, 4);
  if (!items.length) return blockPlaceholder(b, 'Carousel — chưa có mục');

  var CARD_W = 200;
  var STEP = 12;
  var wrap = autoLayout('carousel', { dir: 'VERTICAL' });
  var row = autoLayout('carousel-row', {
    dir: 'HORIZONTAL', gap: STEP, w: items.length * CARD_W + (items.length - 1) * STEP,
    primary: 'FIXED'
  });
  wrap.appendChild(row);

  for (var i = 0; i < items.length; i++) {
    var it = items[i] || {};
    var card = autoLayout('carousel-card', {
      dir: 'VERTICAL', gap: 8, pad: 12, w: CARD_W, counter: 'FIXED',
      radius: 12, fillHex: C.surface, strokeHex: C.line, strokeW: 1
    });
    row.appendChild(card);
    place(card, imageRegion(str(it.emoji), 76, 24), 'FILL', 'FIXED');
    place(card, text(str(it.title) || 'Mục', { size: 13, style: 'Medium', w: CARD_W - 24 }), 'FILL', 'HUG');
    if (str(it.sub)) {
      place(card, text(str(it.sub), { size: 11, hex: C.muted, w: CARD_W - 24 }), 'FILL', 'HUG');
    }
  }
  return wrap;
}

function blockHero(b) {
  var card = autoLayout('hero', {
    dir: 'VERTICAL', gap: 14, pad: 16, radius: 16,
    fillHex: C.accentSoft, strokeHex: C.accentLine, strokeW: 1
  });

  var top = autoLayout('hero-identity', { dir: 'HORIZONTAL', gap: 12, alignCounter: 'CENTER' });
  place(card, top, 'FILL', 'HUG');
  var avatar = autoLayout('avatar', {
    dir: 'VERTICAL', w: 48, h: 48, primary: 'FIXED', counter: 'FIXED', radius: 24,
    alignPrimary: 'CENTER', alignCounter: 'CENTER',
    fillHex: C.surface, strokeHex: C.stroke, strokeW: 1.5, dashed: true
  });
  top.appendChild(avatar);
  place(avatar, text('👤', { size: 20, hug: true }));

  var who = autoLayout('hero-who', { dir: 'VERTICAL', gap: 6 });
  place(top, who, 'FILL', 'HUG');
  place(who, text(str(b.name) || 'Tên hội viên', { size: 15, style: 'Bold' }), 'FILL', 'HUG');
  if (str(b.tier)) {
    var pill = autoLayout('tier', {
      dir: 'HORIZONTAL', padX: 10, padTop: 4, padBottom: 4, radius: 999, fillHex: C.accent
    });
    who.appendChild(pill); // hugs and stays left-aligned in the column
    place(pill, text(str(b.tier), { size: 10, style: 'Bold', hug: true, hex: C.onAccent }));
  }

  var pts = autoLayout('hero-points', { dir: 'HORIZONTAL', gap: 6, alignCounter: 'CENTER' });
  place(card, pts, 'FILL', 'HUG');
  var points = str(b.points) || '0';
  place(pts, text(points, { size: 30, style: 'Bold', hug: true, hex: C.accent }));
  // Only label a bare figure — a spec that already wrote "1.250 điểm" must not get
  // the unit twice.
  if (/^[\d.,\s]+$/.test(points)) place(pts, text('điểm', { size: 12, hex: C.muted, hug: true }));

  var v = frac(b.progress);
  if (v !== null) {
    place(card, progressBar(v, BODY_W - 32), 'FILL', 'FIXED');
    if (str(b.progress_label)) {
      place(card, text(str(b.progress_label), { size: 11, hex: C.muted }), 'FILL', 'HUG');
    }
  }
  return card;
}

function blockStats(b) {
  var items = arr(b.items, 4);
  if (!items.length) return blockPlaceholder(b, 'Chỉ số — chưa có mục');
  var row = autoLayout('stats', {
    dir: 'HORIZONTAL', gap: 0, padTop: 14, padBottom: 14, alignCounter: 'CENTER',
    radius: 12, fillHex: C.surface, strokeHex: C.line, strokeW: 1
  });
  for (var i = 0; i < items.length; i++) {
    var it = items[i] || {};
    // Fixed-height rule rather than a stretched one: the row hugs its content, and a
    // counter-axis FILL inside a hugging parent is the sort of thing that measures 0.
    if (i) place(row, vRule(30, C.line), 'FIXED', 'FIXED');
    var cell = autoLayout('stat', {
      dir: 'VERTICAL', gap: 4, padX: 8, alignPrimary: 'CENTER', alignCounter: 'CENTER'
    });
    place(row, cell, 'FILL', 'HUG');
    place(cell, text(str(it.value) || '—', { size: 18, style: 'Bold', hug: true, align: 'CENTER' }));
    place(cell, text(str(it.label) || '—', { size: 11, hex: C.muted, hug: true, align: 'CENTER' }));
  }
  return row;
}

function blockProgress(b) {
  var v = frac(b.value);
  var wrap = autoLayout('progress', {
    dir: 'VERTICAL', gap: 9, pad: 16, radius: 12,
    fillHex: C.surface, strokeHex: C.line, strokeW: 1
  });
  var head = autoLayout('progress-head', { dir: 'HORIZONTAL', gap: 8, alignCounter: 'CENTER' });
  place(wrap, head, 'FILL', 'HUG');
  place(head, text(str(b.label) || 'Tiến độ', { size: 13, style: 'Medium' }), 'FILL', 'HUG');
  if (v !== null) {
    place(head, text(Math.round(v * 100) + '%', {
      size: 12, style: 'Medium', hex: C.accent, hug: true, align: 'RIGHT'
    }));
  }
  place(wrap, progressBar(v === null ? 0 : v, BODY_W - 32), 'FILL', 'FIXED');
  if (str(b.caption)) place(wrap, text(str(b.caption), { size: 11, hex: C.muted }), 'FILL', 'HUG');
  return wrap;
}

function gridTile(it) {
  it = it || {};
  var tile = autoLayout('tile', {
    dir: 'VERTICAL', gap: 8, pad: 10, radius: 12,
    fillHex: C.surface, strokeHex: C.line, strokeW: 1
  });
  place(tile, imageRegion(str(it.emoji), 84, 26), 'FILL', 'FIXED');
  place(tile, text(str(it.title) || 'Mục', { size: 13, style: 'Medium', w: 140 }), 'FILL', 'HUG');
  if (str(it.sub)) place(tile, text(str(it.sub), { size: 11, hex: C.muted, w: 140 }), 'FILL', 'HUG');
  return tile;
}

function blockGrid(b) {
  var items = arr(b.items, 6);
  if (!items.length) return blockPlaceholder(b, 'Lưới nội dung — chưa có mục');
  var col = autoLayout('grid', { dir: 'VERTICAL', gap: 12 });
  for (var i = 0; i < items.length; i += 2) {
    var row = autoLayout('grid-row', { dir: 'HORIZONTAL', gap: 12 });
    place(col, row, 'FILL', 'HUG');
    for (var j = 0; j < 2; j++) {
      // An odd final item gets a transparent partner, otherwise the lone FILL tile
      // stretches across the full width and stops looking like a grid.
      if (i + j < items.length) place(row, gridTile(items[i + j]), 'FILL', 'HUG');
      else spacer(row);
    }
  }
  return col;
}

// Overflow is intentional: the row hugs its content inside a wrapper that the screen
// body clips, exactly like `carousel`.
function blockChips(b) {
  var items = arr(b.items, 5);
  if (!items.length) return blockPlaceholder(b, 'Bộ lọc — chưa có mục');
  var active = idx(b.active, items.length);
  var wrap = autoLayout('chips', { dir: 'VERTICAL' });
  var row = autoLayout('chips-row', { dir: 'HORIZONTAL', gap: 8 });
  wrap.appendChild(row);
  for (var i = 0; i < items.length; i++) {
    var on = i === active;
    var chip = autoLayout('chip', {
      dir: 'HORIZONTAL', padX: 14, padTop: 7, padBottom: 7, radius: 999,
      fillHex: on ? C.accent : C.chip
    });
    row.appendChild(chip);
    place(chip, text(label(items[i], 'Chip'), {
      size: 12, style: on ? 'Medium' : 'Regular', hug: true, hex: on ? C.onAccent : C.muted
    }));
  }
  return wrap;
}

// The one element a loyalty app is recognised by, so it is built as a ticket: an
// accent stub, a dashed tear line, then the body.
function blockVoucher(b) {
  var H = 110;
  var t = autoLayout('voucher', {
    dir: 'HORIZONTAL', gap: 0, h: H, counter: 'FIXED', radius: 12, clip: true,
    fillHex: C.surface, strokeHex: C.line, strokeW: 1
  });

  var stub = autoLayout('voucher-stub', {
    dir: 'VERTICAL', gap: 2, padX: 8, w: 88, counter: 'FIXED',
    alignPrimary: 'CENTER', alignCounter: 'CENTER', fillHex: C.accentSoft
  });
  place(t, stub, 'FIXED', 'FILL');
  place(stub, text(str(b.value) || '—', {
    size: 22, style: 'Bold', hug: true, align: 'CENTER', hex: C.accent
  }));
  place(stub, text('VOUCHER', { size: 8, hug: true, align: 'CENTER', hex: C.muted, track: 0.8 }));

  place(t, vDashLine(H), 'FIXED', 'FILL');

  var body = autoLayout('voucher-body', {
    dir: 'VERTICAL', gap: 3, padX: 14, padTop: 12, padBottom: 12, alignPrimary: 'CENTER'
  });
  place(t, body, 'FILL', 'FILL');
  var w = PHONE_W - 40 - 89 - 28;
  place(body, text(str(b.title) || 'Ưu đãi', { size: 14, style: 'Bold', w: w }), 'FILL', 'HUG');
  if (str(b.condition)) place(body, text(str(b.condition), { size: 11, hex: C.muted, w: w }), 'FILL', 'HUG');
  if (str(b.expiry)) place(body, text(str(b.expiry), { size: 10, hex: C.hint, w: w }), 'FILL', 'HUG');
  if (str(b.code)) {
    place(body, text('MÃ ' + str(b.code), {
      size: 10, style: 'Medium', hex: C.muted, w: w, track: 0.8
    }), 'FILL', 'HUG');
  }
  return t;
}

// A synthetic pattern only — nothing is encoded. Three filled corner blocks plus a
// deterministic scatter is enough for a reviewer to read it as a QR at a glance.
function qrOn(r, c) {
  var corner = (r < 3 && c < 3) || (r < 3 && c > 5) || (r > 5 && c < 3);
  if (corner) return true;
  return ((r * 7 + c * 5 + ((r * c) % 3)) % 3) !== 0;
}

function blockQr(b) {
  var wrap = autoLayout('qr', {
    dir: 'VERTICAL', gap: 10, pad: 16, radius: 12, alignCounter: 'CENTER',
    fillHex: C.surface, strokeHex: C.line, strokeW: 1
  });
  if (str(b.label)) {
    place(wrap, text(str(b.label), { size: 13, style: 'Medium', align: 'CENTER' }), 'FILL', 'HUG');
  }

  var box = autoLayout('qr-box', {
    dir: 'VERTICAL', gap: 0, pad: 14, w: 140, h: 140, primary: 'FIXED', counter: 'FIXED',
    alignPrimary: 'CENTER', alignCounter: 'CENTER', radius: 10,
    fillHex: C.surface, strokeHex: C.dash, strokeW: 1.5, dashed: true
  });
  wrap.appendChild(box);
  var grid = autoLayout('qr-grid', { dir: 'VERTICAL', gap: 0 });
  box.appendChild(grid);
  for (var r = 0; r < 9; r++) {
    var row = autoLayout('qr-row', { dir: 'HORIZONTAL', gap: 0 });
    grid.appendChild(row);
    for (var c = 0; c < 9; c++) {
      row.appendChild(autoLayout('m', {
        dir: 'VERTICAL', w: 12, h: 12, primary: 'FIXED', counter: 'FIXED',
        fillHex: qrOn(r, c) ? C.ink : null
      }));
    }
  }

  if (str(b.code)) {
    place(wrap, text(str(b.code), {
      size: 16, style: 'Bold', align: 'CENTER', track: 2
    }), 'FILL', 'HUG');
  }
  if (str(b.caption)) {
    place(wrap, text(str(b.caption), { size: 11, hex: C.muted, align: 'CENTER' }), 'FILL', 'HUG');
  }
  return wrap;
}

function blockSteps(b) {
  var items = arr(b.items, 5);
  if (!items.length) return blockPlaceholder(b, 'Các bước — chưa có mục');
  var wrap = autoLayout('steps', {
    dir: 'VERTICAL', gap: 0, pad: 16, radius: 12,
    fillHex: C.surface, strokeHex: C.line, strokeW: 1
  });
  for (var i = 0; i < items.length; i++) {
    var it = items[i] || {};
    var done = it.done === true;
    var last = i === items.length - 1;

    var row = autoLayout('step', { dir: 'HORIZONTAL', gap: 12 });
    place(wrap, row, 'FILL', 'HUG');

    var rail = autoLayout('rail', { dir: 'VERTICAL', gap: 0, w: 20, counter: 'FIXED', alignCounter: 'CENTER' });
    row.appendChild(rail);
    var dot = autoLayout('dot', {
      dir: 'VERTICAL', w: 20, h: 20, primary: 'FIXED', counter: 'FIXED', radius: 10,
      alignPrimary: 'CENTER', alignCounter: 'CENTER',
      fillHex: done ? C.accent : C.surface, strokeHex: done ? null : C.stroke, strokeW: 1.5
    });
    rail.appendChild(dot);
    if (done) place(dot, text('✓', { size: 11, style: 'Bold', hug: true, hex: C.onAccent }));
    // The connector belongs between circles, so the last step never draws one.
    if (!last) {
      rail.appendChild(autoLayout('rail-line', {
        dir: 'VERTICAL', w: 2, h: 34, primary: 'FIXED', counter: 'FIXED', fillHex: C.line
      }));
    }

    var col = autoLayout('step-text', { dir: 'VERTICAL', gap: 2, padBottom: last ? 0 : 18 });
    place(row, col, 'FILL', 'HUG');
    place(col, text(str(it.label) || 'Bước ' + (i + 1), { size: 13, style: 'Medium' }), 'FILL', 'HUG');
    if (str(it.sub)) place(col, text(str(it.sub), { size: 11, hex: C.muted }), 'FILL', 'HUG');
  }
  return wrap;
}

function blockNote(b) {
  var warn = str(b.tone).trim().toLowerCase() === 'warning';
  var box = autoLayout('note/' + (warn ? 'warning' : 'info'), {
    dir: 'HORIZONTAL', gap: 10, padX: 12, padTop: 12, padBottom: 12, radius: 10,
    fillHex: warn ? C.warnSoft : C.infoSoft,
    strokeHex: warn ? C.warnLine : C.infoLine, strokeW: 1
  });
  place(box, text(warn ? '⚠️' : 'ℹ️', { size: 13, hug: true }));
  place(box, text(str(b.text) || 'Lưu ý', {
    size: 11, hex: warn ? C.warnInk : C.infoInk
  }), 'FILL', 'HUG');
  return box;
}

function blockEmpty(b) {
  var box = autoLayout('empty', {
    dir: 'VERTICAL', gap: 12, padX: 20, padTop: 64, padBottom: 64,
    alignPrimary: 'CENTER', alignCounter: 'CENTER'
  });
  place(box, text(str(b.emoji) || '📭', { size: 40, hug: true }));
  place(box, text(str(b.label) || 'Chưa có dữ liệu', {
    size: 12, hex: C.muted, align: 'CENTER'
  }), 'FILL', 'HUG');
  return box;
}

function blockToggle(b) {
  var on = b.on === true;
  var row = autoLayout('toggle', {
    dir: 'HORIZONTAL', gap: 12, pad: 14, radius: 12, alignCounter: 'CENTER',
    fillHex: C.surface, strokeHex: C.line, strokeW: 1
  });
  var col = autoLayout('toggle-text', { dir: 'VERTICAL', gap: 2 });
  place(row, col, 'FILL', 'HUG');
  place(col, text(str(b.label) || 'Tuỳ chọn', { size: 13, style: 'Medium' }), 'FILL', 'HUG');
  if (str(b.sub)) place(col, text(str(b.sub), { size: 11, hex: C.muted }), 'FILL', 'HUG');

  // The knob is pushed by the track's primary-axis alignment rather than by an x
  // offset, which auto-layout would overwrite anyway.
  var sw = autoLayout('switch', {
    dir: 'HORIZONTAL', gap: 0, padX: 3, padTop: 3, padBottom: 3, w: 44, h: 26,
    primary: 'FIXED', counter: 'FIXED', radius: 13,
    alignPrimary: on ? 'MAX' : 'MIN', alignCounter: 'CENTER',
    fillHex: on ? C.accent : C.stroke
  });
  row.appendChild(sw);
  sw.appendChild(autoLayout('knob', {
    dir: 'VERTICAL', w: 20, h: 20, primary: 'FIXED', counter: 'FIXED', radius: 10,
    fillHex: C.surface
  }));
  return row;
}

function blockTimeslot(b) {
  var items = arr(b.items, 12);
  var wrap = autoLayout('timeslot', {
    dir: 'VERTICAL', gap: 10, pad: 16, radius: 12,
    fillHex: C.surface, strokeHex: C.line, strokeW: 1
  });
  place(wrap, text(str(b.label) || 'Chọn thời gian', { size: 13, style: 'Medium' }), 'FILL', 'HUG');
  if (!items.length) {
    place(wrap, text('Chưa có khung giờ', { size: 12, hex: C.hint }), 'FILL', 'HUG');
    return wrap;
  }
  var active = idx(b.active, items.length);
  for (var i = 0; i < items.length; i += 3) {
    var row = autoLayout('slot-row', { dir: 'HORIZONTAL', gap: 8 });
    place(wrap, row, 'FILL', 'HUG');
    for (var j = 0; j < 3; j++) {
      if (i + j >= items.length) { spacer(row); continue; }
      var on = (i + j) === active;
      var chip = autoLayout('slot', {
        dir: 'HORIZONTAL', padX: 6, padTop: 9, padBottom: 9, radius: 8,
        alignPrimary: 'CENTER', alignCounter: 'CENTER',
        fillHex: on ? C.accentSoft : C.surface,
        strokeHex: on ? C.accent : C.stroke, strokeW: on ? 1.5 : 1
      });
      place(row, chip, 'FILL', 'HUG');
      place(chip, text(label(items[i + j], '—'), {
        size: 12, style: on ? 'Medium' : 'Regular', hug: true, hex: on ? C.accent : C.ink
      }));
    }
  }
  return wrap;
}

// A body block, not a real overlay — the scrim above the card is what sells it as
// one, since a wireframe frame has nothing to dim.
function blockSheet(b) {
  var wrap = autoLayout('sheet', { dir: 'VERTICAL', gap: 0 });

  var scrim = autoLayout('scrim', { dir: 'VERTICAL', h: 96, primary: 'FIXED', counter: 'FIXED' });
  // Alpha lives on the paint, never as an `a` channel inside color.
  scrim.fills = [{ type: 'SOLID', color: hexToRgb(C.scrim), opacity: 0.35 }];
  place(wrap, scrim, 'FILL', 'FIXED');

  var card = autoLayout('sheet-card', {
    dir: 'VERTICAL', gap: 12, padX: 16, padTop: 10, padBottom: 16, fillHex: C.surface
  });
  place(wrap, card, 'FILL', 'HUG');
  card.topLeftRadius = 18;
  card.topRightRadius = 18;

  var grip = autoLayout('handle-row', { dir: 'HORIZONTAL', alignPrimary: 'CENTER' });
  place(card, grip, 'FILL', 'HUG');
  grip.appendChild(autoLayout('handle', {
    dir: 'VERTICAL', w: 44, h: 4, primary: 'FIXED', counter: 'FIXED', radius: 2, fillHex: C.stroke
  }));

  place(card, text(str(b.title) || 'Xác nhận', { size: 16, style: 'Bold' }), 'FILL', 'HUG');

  var rows = arr(b.rows);
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i] || {};
    var row = autoLayout('row', { dir: 'HORIZONTAL', gap: 8, alignCounter: 'CENTER' });
    place(card, row, 'FILL', 'HUG');
    place(row, text(str(r.label) || '—', { size: 12, hex: C.muted }), 'FILL', 'HUG');
    place(row, text(str(r.value) || '—', { size: 12, style: 'Medium', hug: true, align: 'RIGHT' }));
  }

  place(card, blockCta({ text: str(b.cta) || 'Xác nhận' }), 'FILL', 'FIXED');
  return wrap;
}

// Every field but `kind` is optional, and an unknown kind must draw rather than throw.
function buildBlock(b) {
  if (!b || typeof b !== 'object') return null;
  var kind = str(b.kind).trim().toLowerCase();
  switch (kind) {
    case 'appbar': return blockAppbar(b);
    case 'banner': return blockBanner(b);
    case 'text': return blockText(b);
    case 'card': return blockCard(b);
    case 'list': return blockList(b);
    case 'field': return blockField(b);
    case 'cta': return blockCta(b);
    case 'tabbar': return blockTabbar(b);
    case 'placeholder': return blockPlaceholder(b);
    case 'tabs': return blockTabs(b);
    case 'section': return blockSection(b);
    case 'carousel': return blockCarousel(b);
    case 'hero': return blockHero(b);
    case 'stats': return blockStats(b);
    case 'progress': return blockProgress(b);
    case 'grid': return blockGrid(b);
    case 'chips': return blockChips(b);
    case 'voucher': return blockVoucher(b);
    case 'qr': return blockQr(b);
    case 'steps': return blockSteps(b);
    case 'note': return blockNote(b);
    case 'empty': return blockEmpty(b);
    case 'toggle': return blockToggle(b);
    case 'timeslot': return blockTimeslot(b);
    case 'sheet': return blockSheet(b);
    default: return blockPlaceholder(b, (kind || 'không rõ') + ' (khối chưa hỗ trợ)');
  }
}

// ------------------------------------------------------------------ screens

function splitChrome(blocks) {
  var out = { appbar: null, tabbar: null, body: [] };
  for (var i = 0; i < blocks.length; i++) {
    var b = blocks[i];
    var kind = b && typeof b === 'object' ? str(b.kind).trim().toLowerCase() : '';
    if (kind === 'appbar' && !out.appbar) out.appbar = b;
    else if (kind === 'tabbar' && !out.tabbar) out.tabbar = b;
    else out.body.push(b);
  }
  return out;
}

function drawAppScreen(screen, blocks) {
  var frame = autoLayout(str(screen.name) || 'Screen', {
    dir: 'VERTICAL', gap: 0, w: PHONE_W, h: PHONE_H,
    primary: 'FIXED', counter: 'FIXED', fillHex: C.page, clip: true
  });
  var chrome = splitChrome(blocks);
  if (chrome.appbar) place(frame, blockAppbar(chrome.appbar), 'FILL', 'FIXED');

  var body = autoLayout('body', { dir: 'VERTICAL', gap: 16, pad: 20 });
  place(frame, body, 'FILL', 'FILL');
  body.clipsContent = true;

  for (var i = 0; i < chrome.body.length; i++) {
    var node = buildBlock(chrome.body[i]);
    if (!node) continue;
    place(body, node, 'FILL', node.type === 'TEXT' ? 'HUG' : null);
  }
  // tabbar as the last child reads as pinned to the bottom without absolute positioning.
  if (chrome.tabbar) place(frame, blockTabbar(chrome.tabbar), 'FILL', 'FIXED');
  return frame;
}

// A ZNS is a notification template, not a screen: it has no navigation, no inputs
// and no horizontal scrolling, so these kinds are dropped from a ZNS body rather
// than drawn as something a template cannot actually contain. Everything else
// (text, card, voucher, qr, steps, note, cta, banner, progress, stats, section,
// placeholder) is legitimate ZNS content.
var ZNS_DROP = {
  tabbar: 1, tabs: 1, list: 1, field: 1, grid: 1, carousel: 1,
  chips: 1, timeslot: 1, toggle: 1, sheet: 1, empty: 1, hero: 1
};

function znsBody(blocks) {
  var out = [];
  for (var i = 0; i < blocks.length; i++) {
    var b = blocks[i];
    if (!b || typeof b !== 'object') continue;
    if (ZNS_DROP[str(b.kind).trim().toLowerCase()]) continue;
    out.push(b);
  }
  return out;
}

function drawZnsScreen(screen, blocks, meta) {
  var frame = autoLayout(str(screen.name) || 'ZNS', {
    dir: 'VERTICAL', gap: 0, padX: 20, padTop: 40, padBottom: 20, w: PHONE_W, h: PHONE_H,
    primary: 'FIXED', counter: 'FIXED', fillHex: C.page, clip: true
  });

  var card = autoLayout('zns-template', {
    dir: 'VERTICAL', gap: 0, radius: 12, fillHex: C.surface,
    strokeHex: C.line, strokeW: 1, clip: true
  });
  place(frame, card, 'FILL', 'HUG');

  var chrome = splitChrome(blocks); // the appbar becomes the sender strip below.
  var allowed = znsBody(chrome.body);
  var strip = autoLayout('zns-header', {
    dir: 'HORIZONTAL', gap: 10, padX: 14, padTop: 12, padBottom: 12,
    alignCounter: 'CENTER', fillHex: C.chip
  });
  place(card, strip, 'FILL', 'HUG');
  var avatar = autoLayout('avatar', {
    dir: 'VERTICAL', w: 26, h: 26, primary: 'FIXED', counter: 'FIXED',
    radius: 13, fillHex: C.stroke
  });
  strip.appendChild(avatar);
  var sender = (chrome.appbar && str(chrome.appbar.title)) || str(meta.brand) || 'Zalo Official Account';
  place(strip, text(sender, { size: 12, style: 'Medium' }), 'FILL', 'HUG');
  place(strip, text('ZNS', { size: 10, hug: true, hex: C.muted }));

  var body = autoLayout('zns-body', { dir: 'VERTICAL', gap: 14, pad: 16 });
  place(card, body, 'FILL', 'HUG');
  for (var i = 0; i < allowed.length; i++) {
    var node = buildBlock(allowed[i]);
    if (!node) continue;
    place(body, node, 'FILL', node.type === 'TEXT' ? 'HUG' : null);
  }
  if (!allowed.length) {
    place(body, text('Nội dung thông báo', { size: 12, hex: C.hint }), 'FILL', 'HUG');
  }
  return frame;
}

function drawScreenColumn(screen, index, meta) {
  var col = autoLayout('Screen ' + (index + 1), { dir: 'VERTICAL', gap: 10 });
  var name = str(screen.name) || 'Màn hình ' + (index + 1);
  var platform = str(screen.platform).trim().toLowerCase() || 'miniapp';

  place(col, text(name + '  ·  ' + platform, {
    size: 14, style: 'Bold', w: PHONE_W
  }), 'FIXED', 'HUG');
  if (screen.note) {
    place(col, text(screen.note, { size: 11, hex: C.muted, w: PHONE_W }), 'FIXED', 'HUG');
  }

  var blocks = Array.isArray(screen.blocks) ? screen.blocks : [];
  var frame = platform === 'zns' ? drawZnsScreen(screen, blocks, meta) : drawAppScreen(screen, blocks);
  col.appendChild(frame);
  col.name = name;
  return col;
}

function pageBounds() {
  var kids = figma.currentPage.children;
  var right = null, top = null;
  for (var i = 0; i < kids.length; i++) {
    var n = kids[i];
    var box = n.absoluteBoundingBox || (('width' in n) ? { x: n.x, y: n.y, width: n.width, height: n.height } : null);
    if (!box) continue;
    var r = box.x + box.width;
    if (right === null || r > right) right = r;
    if (top === null || box.y < top) top = box.y;
  }
  return { right: right === null ? 0 : right, top: top === null ? 0 : top };
}

function createContainer(name) {
  if (typeof figma.createSection === 'function') {
    var s = figma.createSection();
    s.name = name;
    try { s.fills = paint(C.surface); } catch (e) { /* section fills are version-dependent */ }
    return s;
  }
  var f = figma.createFrame();
  f.name = name;
  f.fills = paint(C.surface);
  f.clipsContent = false;
  return f;
}

function sizeContainer(node, w, h) {
  if (typeof node.resizeWithoutConstraints === 'function') node.resizeWithoutConstraints(w, h);
  else node.resize(w, h);
}

async function loadFonts() {
  var families = ['Inter', 'Roboto'];
  for (var i = 0; i < families.length; i++) {
    try {
      await figma.loadFontAsync({ family: families[i], style: 'Regular' });
      await figma.loadFontAsync({ family: families[i], style: 'Medium' });
      await figma.loadFontAsync({ family: families[i], style: 'Bold' });
      FONT = families[i];
      return;
    } catch (e) { /* try the next family */ }
  }
  throw new Error('Không tải được font Inter/Roboto trong Figma.');
}

// -------------------------------------------------------------------- fetch

async function fetchSpec(apiBase, code) {
  var base = str(apiBase).trim().replace(/\/+$/, '') || DEFAULT_API;
  var url = base + '/figma/job/' + encodeURIComponent(code);
  var res;
  try {
    res = await fetch(url);
  } catch (e) {
    throw new Error('Không kết nối được tới backend (' + base + '). Kiểm tra địa chỉ API, mạng, ' +
      'và đảm bảo tên miền đã được khai báo trong manifest.json.');
  }
  if (res.status === 404) throw new Error('Mã job "' + code + '" không tồn tại hoặc đã hết hạn.');
  if (!res.ok) throw new Error('Backend trả về lỗi HTTP ' + res.status + '.');
  var json;
  try {
    json = await res.json();
  } catch (e) {
    throw new Error('Backend trả về dữ liệu không phải JSON hợp lệ.');
  }
  // Tolerate a wrapped payload ({data:…}/{spec:…}) as well as the bare spec.
  if (json && !Array.isArray(json.screens)) {
    if (json.data && Array.isArray(json.data.screens)) json = json.data;
    else if (json.spec && Array.isArray(json.spec.screens)) json = json.spec;
  }
  if (!json || typeof json !== 'object') throw new Error('Spec rỗng.');
  return json;
}

// --------------------------------------------------------------------- draw

async function draw(code, apiBase) {
  figma.ui.postMessage({ type: 'status', text: 'Đang tải spec cho mã ' + code + '…' });
  var spec = await fetchSpec(apiBase, code);

  var screens = Array.isArray(spec.screens) ? spec.screens.filter(function (s) { return s && typeof s === 'object'; }) : [];
  if (!screens.length) throw new Error('Spec không chứa màn hình nào để vẽ.');

  var meta = spec.meta && typeof spec.meta === 'object' ? spec.meta : {};

  figma.ui.postMessage({ type: 'status', text: 'Đang tải font…' });
  await loadFonts();

  // Read existing content BEFORE creating nodes, so we never draw over the rep's work.
  var bounds = pageBounds();

  figma.ui.postMessage({ type: 'status', text: 'Đang vẽ ' + screens.length + ' màn hình…' });

  var title = 'AdtimaBox — ' + (str(meta.brand) || 'Khách hàng') + ' — ' + (str(meta.product) || 'Wireframe');
  var container = createContainer(title);

  var columns = [];
  var tallest = 0;
  for (var i = 0; i < screens.length; i++) {
    var col = drawScreenColumn(screens[i], i, meta);
    container.appendChild(col);
    col.x = PAD + i * (PHONE_W + GAP);
    col.y = PAD;
    columns.push(col);
    if (col.height > tallest) tallest = col.height;
  }

  var w = PAD * 2 + screens.length * PHONE_W + (screens.length - 1) * GAP;
  sizeContainer(container, w, PAD * 2 + tallest);
  // Positioned last: moving the container carries its children along either way.
  container.x = Math.round(bounds.right + 120);
  container.y = Math.round(bounds.top);

  figma.currentPage.selection = [container];
  figma.viewport.scrollAndZoomIntoView([container]);

  var note = str(meta.note);
  var msg = 'Đã vẽ ' + columns.length + ' màn hình cho "' + (str(meta.brand) || code) + '".' +
    (note ? '\n' + note : '');
  figma.notify('AdtimaBox: đã vẽ ' + columns.length + ' màn hình wireframe.');
  figma.ui.postMessage({ type: 'done', text: msg, frames: columns.length });
}

// ------------------------------------------------------------------ plumbing

figma.showUI(__html__, { width: 340, height: 330 });

figma.ui.onmessage = async function (msg) {
  if (!msg || !msg.type) return;

  if (msg.type === 'ready') {
    var saved = null;
    try { saved = await figma.clientStorage.getAsync(STORAGE_KEY); } catch (e) { /* first run */ }
    figma.ui.postMessage({ type: 'config', apiBase: saved || DEFAULT_API });
    return;
  }

  if (msg.type === 'draw') {
    var code = str(msg.code).trim().toUpperCase();
    if (!/^[A-Z0-9]{8}$/.test(code)) {
      figma.ui.postMessage({ type: 'error', text: 'Mã job phải gồm đúng 8 ký tự chữ và số.' });
      return;
    }
    try { await figma.clientStorage.setAsync(STORAGE_KEY, str(msg.apiBase).trim() || DEFAULT_API); } catch (e) {}
    try {
      await draw(code, msg.apiBase);
    } catch (e) {
      var text = (e && e.message) ? e.message : 'Lỗi không xác định khi vẽ wireframe.';
      figma.notify('AdtimaBox: ' + text, { error: true });
      figma.ui.postMessage({ type: 'error', text: text });
    }
  }
};

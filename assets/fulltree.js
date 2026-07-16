/* The Bloodline — whole tree on one page, explorer card design.
   Era-banded layout: cards sit in generation rows ordered & spaced by real birth
   years; every row reserves a clear band beneath it so connector lines route
   through empty space and never pass behind a card. Vanilla, no CDN. */
(function () {
  const D = window.BL_DATA, P = D.people, HOUSES = D.houses;
  const marr = {}, birth = {};
  D.unions.forEach(u => {
    u.parents.forEach(p => (marr[p] = marr[p] || []).push(u));
    u.children.forEach(c => { birth[c] = u; });
  });
  const ids = Object.keys(P);
  const lines = pid => (P[pid].label || pid).split('<br/>');
  const accOf = pid => (HOUSES[P[pid].house] || {}).accent || '#cbb98a';
  const spousesOf = pid => (marr[pid] || []).map(u => u.parents.find(x => x !== pid)).filter(Boolean);
  const parentsOf = pid => (birth[pid] ? birth[pid].parents : []);
  const kidsOf = pid => { const o = []; (marr[pid] || []).forEach(u => u.children.forEach(c => o.push(c))); return o; };

  // ---- relatives (for the detail panel) ----
  const ANC = {};                                    // per person: ancestor -> generations up (min)
  ids.forEach(p => {
    const dist = { [p]: 0 }; let frontier = [p], d = 0;
    while (frontier.length) {
      d++; const nx = [];
      frontier.forEach(x => parentsOf(x).forEach(par => { if (dist[par] === undefined) { dist[par] = d; nx.push(par); } }));
      frontier = nx;
    }
    ANC[p] = dist;
  });
  const ancAt = (p, d) => Object.keys(ANC[p]).filter(a => ANC[p][a] === d);      // d gens up
  function descAt(p, depth) {                                                     // depth gens down
    const dist = { [p]: 0 }; let frontier = [p], d = 0;
    while (frontier.length && d < depth) {
      d++; const nx = [];
      frontier.forEach(x => kidsOf(x).forEach(c => { if (dist[c] === undefined) { dist[c] = d; nx.push(c); } }));
      frontier = nx;
    }
    return Object.keys(dist).filter(k => dist[k] === depth);
  }
  const siblingsOf = p => [...new Set(parentsOf(p).flatMap(par => kidsOf(par)))].filter(x => x !== p);
  function cousinsByDegree(p) {                     // classify by NEAREST common ancestor -> no double-listing
    const A = ANC[p], excl = new Set([p, ...spousesOf(p), ...siblingsOf(p)]), groups = {};
    ids.forEach(x => {
      if (excl.has(x)) return;
      const B = ANC[x]; let dp = 0, dx = 0, best = Infinity, sum = Infinity, found = false;
      for (const c in A) {
        const bx = B[c];
        if (bx !== undefined) { const ap = A[c], mx = Math.max(ap, bx), sm = ap + bx; if (mx < best || (mx === best && sm < sum)) { best = mx; sum = sm; dp = ap; dx = bx; found = true; } }
      }
      if (!found || dp === 0 || dx === 0) return;    // unrelated, or direct ancestor/descendant
      if (dp === dx && dp >= 2) (groups[dp - 1] = groups[dp - 1] || []).push(x);   // nth cousin, n = dp-1
    });
    return groups;
  }

  // ---- 1. birth years (drive the time axis) ----
  const parseYear = pid => {
    if (P[pid].byear != null) return P[pid].byear;     // explicit birth-year correction
    const lab = (P[pid].label || '').toLowerCase();
    let m = lab.match(/(\d{1,4})\s*[-–—]\s*\d{1,4}\s*bc/);   // "382-336 bc" -> -382
    if (m) return -(+m[1]);
    m = lab.match(/(\d{1,4})\s*bc/);                          // "48 bc"
    if (m) return -(+m[1]);
    m = lab.match(/\b(\d{3,4})\s*[-–—]\s*\d{2,4}\b/);         // AD range "466-511"
    if (m) { const y = +m[1]; if (y >= 100 && y <= 1750) return y; }
    for (const s of (lab.match(/\b\d{3,4}\b/g) || [])) { const y = +s; if (y >= 100 && y <= 1750) return y; }
    return null;
  };
  const year = {}; ids.forEach(p => year[p] = parseYear(p));
  for (let it = 0; it < 16; it++) ids.forEach(p => {          // estimate undated from relatives
    if (year[p] != null) return;
    const par = parentsOf(p).map(q => year[q]).filter(v => v != null);
    const sp = spousesOf(p).map(q => year[q]).filter(v => v != null);
    const kid = kidsOf(p).map(q => year[q]).filter(v => v != null);
    if (par.length) year[p] = Math.max(...par) + 28;
    else if (sp.length) year[p] = Math.round(sp.reduce((a, b) => a + b, 0) / sp.length);
    else if (kid.length) year[p] = Math.min(...kid) - 28;
  });
  const median = a => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : null; };
  const gMed = median(ids.map(p => year[p]).filter(v => v != null)) || 1100;
  ids.forEach(p => { if (year[p] == null) year[p] = gMed; });
  const minYear = Math.min(...ids.map(p => year[p]));

  // ---- 2. lanes (era rows): seed by 24-yr buckets, then force couples level & children below ----
  const GEN = 24;
  const lane = {}; ids.forEach(p => lane[p] = Math.round((year[p] - minYear) / GEN));
  for (let changed = true, g = 0; changed && g < 3000; g++) {
    changed = false;
    for (const u of D.unions) {
      let pl = 0; u.parents.forEach(p => pl = Math.max(pl, lane[p]));
      u.parents.forEach(p => { if (lane[p] < pl) { lane[p] = pl; changed = true; } });
      u.children.forEach(c => { if (lane[c] < pl + 1) { lane[c] = pl + 1; changed = true; } });
    }
  }
  const maxLane = Math.max(...Object.values(lane));
  const byLane = Array.from({ length: maxLane + 1 }, () => []);
  ids.forEach(p => byLane[lane[p]].push(p));
  // ---- 3. couple-aware crossing reduction ----
  // Each person is grouped with their primary same-lane spouse into a BLOCK (singles are
  // their own block). Ordering runs on blocks, so couples stay together AND crossings drop.
  const blockOf = {};
  const laneBlocks = byLane.map(() => []);
  byLane.forEach((row, r) => {
    const placed = new Set();
    row.forEach(p => {
      if (placed.has(p)) return;
      const sp = spousesOf(p).find(s => lane[s] === r && !placed.has(s));
      const blk = { members: sp ? [p, sp] : [p], i: 0, x: 0 };
      blk.members.forEach(m => { placed.add(m); blockOf[m] = blk; });
      laneBlocks[r].push(blk);
    });
  });
  const bidx = () => laneBlocks.forEach(row => row.forEach((b, i) => b.i = i));
  bidx();
  for (let pass = 0; pass < 14; pass++) {
    const down = pass % 2 === 0;
    const seq = down ? laneBlocks.map((_, r) => r) : laneBlocks.map((_, r) => r).reverse();
    for (const r of seq) {
      const row = laneBlocks[r];
      row.forEach(b => {
        const nb = [];
        b.members.forEach(p => (down ? parentsOf(p) : kidsOf(p)).forEach(q => { const g = blockOf[q]; if (g && lane[q] === r + (down ? -1 : 1)) nb.push(g.i); }));
        b.key = nb.length ? nb.reduce((a, c) => a + c, 0) / nb.length : b.i;
      });
      row.sort((a, b) => (a.key - b.key) || (a.i - b.i));
      bidx();
    }
  }
  laneBlocks.forEach((row, r) => { byLane[r] = row.flatMap(b => b.members); });

  // ---- 4. era year per lane (vertical placement waits until card heights are measured) ----
  const CW = 182, HGAP = 30;
  const laneYear = byLane.map(row => median(row.map(p => year[p]).filter(v => v != null)));
  for (let r = 0; r < laneYear.length; r++) if (laneYear[r] == null) laneYear[r] = (r ? laneYear[r - 1] + GEN : minYear);
  for (let r = 1; r < laneYear.length; r++) if (laneYear[r] <= laneYear[r - 1]) laneYear[r] = laneYear[r - 1] + 2;

  // ---- 5. horizontal positions (block-based; height-independent) ----
  const pos = {};
  ids.forEach(p => pos[p] = { x: 0, y: 0 });
  const blkW = b => b.members.length * CW + (b.members.length - 1) * HGAP;
  const blkCenter = b => b.x + blkW(b) / 2;
  const BG = HGAP + 10;
  laneBlocks.forEach(row => {
    const total = row.reduce((s, b) => s + blkW(b), 0) + Math.max(0, row.length - 1) * BG;
    let cur = -total / 2;
    row.forEach(b => { b.x = cur; cur += blkW(b) + BG; });
  });
  for (let pass = 0; pass < 12; pass++) {
    const down = pass % 2 === 0;
    const seq = down ? laneBlocks.map((_, r) => r) : laneBlocks.map((_, r) => r).reverse();
    for (const r of seq) {
      const row = laneBlocks[r];
      row.forEach(b => {
        const cs = [];
        b.members.forEach(p => {
          (down ? parentsOf(p) : kidsOf(p)).forEach(q => { const g = blockOf[q]; if (g && lane[q] === r + (down ? -1 : 1)) cs.push(blkCenter(g)); });
          spousesOf(p).forEach(q => { const g = blockOf[q]; if (g && g !== b && lane[q] === r) cs.push(blkCenter(g)); });  // pull toward far-off spouses
        });
        if (cs.length) b.x = cs.reduce((a, c) => a + c, 0) / cs.length - blkW(b) / 2;
      });
      const s = [...row].sort((a, b) => a.x - b.x);
      for (let i = 1; i < s.length; i++) { const need = s[i - 1].x + blkW(s[i - 1]) + BG; if (s[i].x < need) s[i].x = need; }
    }
  }
  laneBlocks.forEach(row => row.forEach(b => b.members.forEach((m, i) => pos[m].x = b.x + i * (CW + HGAP))));

  // ---- 6. render: build cards, MEASURE real heights, then place rows & draw connectors ----
  const stage = document.getElementById('stage'), svg = document.getElementById('links');
  const cardEls = {};
  const frag = document.createDocumentFragment();
  ids.forEach(pid => {
    const L = lines(pid), sub = L.slice(1, 3).join(' · ');
    const el = document.createElement('div');
    el.className = 'pcard'; el.id = 'c_' + pid;
    el.style.left = pos[pid].x + 'px'; el.style.width = CW + 'px'; el.style.setProperty('--acc', accOf(pid));
    el.innerHTML = `<div class="pc-name">${L[0]}</div>` + (sub ? `<div class="pc-sub">${sub}</div>` : '') +
      `<div class="pc-house">${(HOUSES[P[pid].house] || {}).title || ''}</div>`;
    el.addEventListener('click', e => { e.stopPropagation(); if (moved) return; focusFamily(pid); });
    el.addEventListener('mouseenter', () => traceHover(pid));
    el.addEventListener('mouseleave', clearTrace);
    cardEls[pid] = el; frag.appendChild(el);
  });
  stage.appendChild(frag);
  const cardH = {}; ids.forEach(p => cardH[p] = cardEls[p].offsetHeight);   // measured, variable per card

  // vertical: each row is as tall as its tallest card, with a routing band below it
  // Vertical placement: each PERSON sits at their own ERA (birth year), in compact time-bands.
  // Positioning by person-year (not by graph-depth lane, and not by a lane's mixed median)
  // is essential — long legendary chains (Heracles -> the Macedonian kings) otherwise push
  // their descendants (the Hellenistic/Roman houses) far below their true era. Missing years
  // are interpolated from kin; sparse ages compact so the tree doesn't stretch.
  const rowH = byLane.map(row => row.length ? Math.max(...row.map(p => cardH[p])) : 0);
  const GAPB = 46;
  const yr2 = {}; ids.forEach(p => yr2[p] = year[p]);
  for (let pass = 0; pass < 6; pass++) ids.forEach(p => {
    if (yr2[p] != null) return;
    let v = null;
    parentsOf(p).forEach(q => { if (yr2[q] != null) v = (v == null) ? yr2[q] + 20 : Math.max(v, yr2[q] + 20); });
    kidsOf(p).forEach(q => { if (yr2[q] != null) v = (v == null) ? yr2[q] - 20 : Math.min(v, yr2[q] - 20); });
    if (v != null) yr2[p] = v;
  });
  ids.forEach(p => { if (yr2[p] == null) yr2[p] = minYear; });
  const BAND = 15, PITCH = 130;
  const bandKey = y => Math.round(y / BAND);
  const bands = [...new Set(ids.map(p => bandKey(yr2[p])))].sort((a, b) => a - b);
  const bandY = {}; bands.forEach((b, i) => bandY[b] = i * PITCH);
  const laneY = laneYear.map(y => y == null ? 0 : (bandY[bandKey(y)] || 0));   // per-lane era Y, for the axis/routing
  ids.forEach(p => pos[p].y = bandY[bandKey(yr2[p])]);

  // ---- separate disconnected bloodlines ----
  // Adam's line is the main tree. Large unconnected king-lists (Sumer, China, ...) each
  // get their own temporal column to the left. The many TINY islands (lone prophets,
  // philosophers, generals) are tiled into a compact GALLERY so they don't spread the
  // canvas to the horizon. mainSet lets the opening view center on the main tree.
  let compOf = {}, mainSet = null;
  (() => {
    const adj = {};
    const link = (a, b) => { (adj[a] = adj[a] || []).push(b); (adj[b] = adj[b] || []).push(a); };
    D.unions.forEach(u => {
      const ps = u.parents.filter(Boolean);
      for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) link(ps[i], ps[j]);
      u.children.forEach(c => ps.forEach(p => link(p, c)));
    });
    ids.forEach(p => { if (compOf[p] !== undefined) return; const c = p; compOf[p] = c; const st = [p]; while (st.length) { const n = st.pop(); (adj[n] || []).forEach(m => { if (compOf[m] === undefined) { compOf[m] = c; st.push(m); } }); } });
    const size = {}; ids.forEach(p => size[compOf[p]] = (size[compOf[p]] || 0) + 1);
    const comps = Object.keys(size).sort((a, b) => size[b] - size[a]);
    mainSet = new Set(ids.filter(p => compOf[p] == comps[0]));
    if (comps.length <= 1) return;
    const BIG = 8, COLGAP = 130;
    let leftEdge = Math.min(...ids.map(p => pos[p].x));
    const compact = members => {                          // repack an island's rows from x=0; return its width
      const rows = {}; members.forEach(p => (rows[lane[p]] = rows[lane[p]] || []).push(p));
      let w = 0;
      Object.values(rows).forEach(row => { row.sort((a, b) => pos[a].x - pos[b].x); row.forEach((p, i) => { pos[p].x = i * (CW + HGAP); w = Math.max(w, pos[p].x + CW); }); });
      return w;
    };
    // large islands -> their own temporal column (rows stay at true era height)
    comps.slice(1).filter(c => size[c] >= BIG).forEach(c => {
      const members = ids.filter(p => compOf[p] == c);
      const w = compact(members);
      const off = (leftEdge - COLGAP) - w;
      members.forEach(p => pos[p].x += off);
      leftEdge = Math.min(...members.map(p => pos[p].x));
    });
    // small islands -> gallery: compact each, stack several per column, wrap leftwards
    const smallComps = comps.slice(1).filter(c => size[c] < BIG);
    if (smallComps.length) {
      const galTop = Math.min(...ids.map(p => pos[p].y)), COLH = 3200;
      let colRight = leftEdge - COLGAP, yCur = galTop, colW = 0;
      smallComps.forEach(c => {
        const members = ids.filter(p => compOf[p] == c);
        const w = compact(members);
        const yTop = Math.min(...members.map(p => pos[p].y));
        const islH = Math.max(...members.map(p => pos[p].y + cardH[p])) - yTop;
        if (yCur + islH > galTop + COLH && yCur > galTop) { colRight -= colW + COLGAP; yCur = galTop; colW = 0; }
        members.forEach(p => { pos[p].x = (colRight - w) + pos[p].x; pos[p].y = yCur + (pos[p].y - yTop); });
        yCur += islH + 40; colW = Math.max(colW, w);
      });
    }
  })();

  const PAD = 130;
  const minX = Math.min(...ids.map(p => pos[p].x)) - PAD, minY = Math.min(...ids.map(p => pos[p].y)) - PAD;
  const W = Math.max(...ids.map(p => pos[p].x)) + CW + PAD - minX, H = Math.max(...ids.map(p => pos[p].y + cardH[p])) + PAD - minY;
  ids.forEach(p => { pos[p].x -= minX; pos[p].y -= minY; cardEls[p].style.left = pos[p].x + 'px'; cardEls[p].style.top = pos[p].y + 'px'; });
  const _main = ids.filter(p => mainSet && mainSet.has(p));
  const _mx = _main.map(p => pos[p].x);
  const mainCx = _mx.length ? (Math.min(..._mx) + Math.max(..._mx) + CW) / 2 : W / 2;   // horizontal center of the main tree
  const mainCy = _main.length ? _main.reduce((a, p) => a + pos[p].y, 0) / _main.length : H / 2;  // vertical center of MASS (lands in a dense era, not the sparse antediluvian top)
  stage.style.width = W + 'px'; stage.style.height = H + 'px';
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('width', W); svg.setAttribute('height', H);

  const cx = p => pos[p].x + CW / 2, top = p => pos[p].y, bot = p => pos[p].y + cardH[p], cyv = p => pos[p].y + cardH[p] / 2;
  const rowBottom = r => (laneY[r] - minY) + rowH[r];       // shifted Y of the row's floor

  const fmtYear = y => y < 0 ? (-y + ' BC') : (y < 1000 ? y + ' AD' : y);
  let axis = '';
  // Draw era-year labels from the clean time-bands (sane years), sampled so they don't crowd.
  // (The old lane-year source extrapolated across empty lanes into phantom 5-digit years.)
  let lastLabelY = -1e9;
  bands.forEach(b => {
    const gy = (bandY[b] - minY) - 12;
    if (gy - lastLabelY < 58) return;
    lastLabelY = gy;
    axis += `<text x="16" y="${gy}" fill="#c7a24f" fill-opacity="0.7" font-size="15" font-family="-apple-system,sans-serif">c.&#8202;${fmtYear(b * BAND)}</text>`;
  });

  const blockedAt = (X, lanesArr) => lanesArr.some(L => (byLane[L] || []).some(card => X > pos[card].x - 10 && X < pos[card].x + CW + 10));
  function clearColumn(targetX, lanesArr) {
    if (!blockedAt(targetX, lanesArr)) return targetX;
    for (let dlt = 12; dlt < 8000; dlt += 12) { if (!blockedAt(targetX + dlt, lanesArr)) return targetX + dlt; if (!blockedAt(targetX - dlt, lanesArr)) return targetX - dlt; }
    return targetX;
  }

  const svgParts = [axis];
  D.unions.forEach((u, ui) => {
    const ps = u.parents;
    const a = ps[0], b = ps[1] || ps[0];
    const twoP = ps.length > 1 && a !== b;
    // The union point sits just beneath the lower parent card, anchored to REAL card
    // positions (not lane coordinates) so bars/drops stay glued to their cards.
    const adjacent = twoP && Math.abs(pos[a].y - pos[b].y) < 40 && Math.abs(pos[a].x - pos[b].x) <= CW + HGAP + 8;
    const p = [];
    let mx, my;
    if (!twoP) {                                                        // single recorded parent
      my = cyv(a); mx = cx(a);
    } else if (adjacent) {                                              // spouses side by side: short bar in the gap between cards
      my = (cyv(a) + cyv(b)) / 2;
      const Lx = Math.min(pos[a].x, pos[b].x) + CW, Rx = Math.max(pos[a].x, pos[b].x);
      mx = (Lx + Rx) / 2;
      p.push(`M ${Lx} ${my} L ${Rx} ${my}`);
    } else {                                                            // far-apart spouses: drop both stems to a bar just below them
      my = Math.max(bot(a), bot(b)) + 18;
      mx = (cx(a) + cx(b)) / 2;
      p.push(`M ${cx(a)} ${bot(a)} L ${cx(a)} ${my}`);
      p.push(`M ${cx(b)} ${bot(b)} L ${cx(b)} ${my}`);
      p.push(`M ${cx(a)} ${my} L ${cx(b)} ${my}`);
    }
    if (u.children.length) {
      const kids = u.children.filter(c => pos[c]);
      // "near" kids form a normal sibling set just below the union; the rest are
      // deep/summary descendants routed individually. Split by REAL vertical distance.
      const isNear = c => top(c) >= my - PITCH && top(c) <= my + PITCH * 2.4;
      const near = kids.filter(isNear), far = kids.filter(c => !isNear(c));
      if (near.length) {                                               // sibling bar just above the children
        const sibY = Math.min(...near.map(top)) - 20;
        const xs = near.map(cx).concat([mx]);
        p.push(`M ${mx} ${my} L ${mx} ${sibY}`);
        p.push(`M ${Math.min(...xs)} ${sibY} L ${Math.max(...xs)} ${sibY}`);
        near.forEach(c => p.push(`M ${cx(c)} ${sibY} L ${cx(c)} ${top(c)}`));
      }
      if (far.length) {                                                // deep descendants: bus just below the union, own drop each
        const busY = my + 22;
        p.push(`M ${mx} ${my} L ${mx} ${busY}`);
        far.forEach(c => {
          const colX = cx(c), dropY = top(c) - 18;
          p.push(`M ${mx} ${busY} L ${colX} ${busY} L ${colX} ${dropY} L ${cx(c)} ${dropY} L ${cx(c)} ${top(c)}`);
        });
      }
    }
    const conc = u.kind === 'concubine';
    // A link whose parents and children sit centuries apart is a telescoped / sparsely
    // documented span (dynasty summaries: Edom's kings, the Kassites, gens Julia -> Caesar).
    // Draw it like a bridge (thin, dashed, dim) so it recedes instead of streaking bold.
    const ys = [my, bot(a)]; if (twoP) ys.push(bot(b));
    u.children.forEach(c => { if (pos[c]) ys.push(top(c)); });
    const longspan = Math.max(...ys) - Math.min(...ys) > 1000;
    const bridge = u.kind === 'bridge' || (!conc && longspan);          // "unrecorded span" summary link
    if (conc && u.mistress != null && pos[u.mistress]) {                // faint dotted tie from a servant/concubine union back to the mistress
      svgParts.push(`<path class="mtie" d="M ${mx} ${my} L ${cx(u.mistress)} ${cyv(u.mistress)}" fill="none" stroke="#9b7d54" stroke-width="1" stroke-dasharray="1 4" opacity="0.65"/>`);
    }
    const dash = conc ? ' stroke-dasharray="5 3"' : bridge ? ' stroke-dasharray="2 7"' : '';
    const stroke = conc ? '#9b7d54' : bridge ? '#565039' : '#7d6f4d';
    svgParts.push(`<path class="conn-hit" data-u="${ui}" d="${p.join(' ')}" fill="none" stroke="rgba(0,0,0,0)" stroke-width="12" pointer-events="stroke"/>`);
    svgParts.push(`<path class="conn${conc ? ' conc' : ''}${bridge ? ' bridge' : ''}" data-u="${ui}" d="${p.join(' ')}" fill="none" stroke="${stroke}" stroke-width="${bridge ? 1 : 1.4}"${dash}${bridge ? ' opacity="0.5"' : ''}/>`);
    svgParts.push(`<circle class="dot${conc ? ' conc' : ''}${bridge ? ' bridge' : ''}" data-u="${ui}" cx="${mx}" cy="${my}" r="${bridge ? 4 : 5}" fill="${conc || bridge ? '#12162e' : '#a87f2e'}" stroke="${bridge ? '#6b6045' : '#a87f2e'}" stroke-width="1.5"/>`);
  });
  svg.innerHTML = svgParts.join('');

  // ---- 7. pan / zoom ----
  const wrap = document.getElementById('explore-wrap');
  let scale = 1, tx = 0, ty = 0;
  let _onApply = null;
  const apply = () => {
    scale = Math.max(0.05, Math.min(3, scale));
    stage.style.transform = `translate(${tx}px,${ty}px) scale(${scale})`;
    wrap.classList.toggle('zfar', scale < 0.22);    // drop fine text when zoomed out
    wrap.classList.toggle('zvfar', scale < 0.1);    // very far: cards become house-colored blocks
    if (_onApply) _onApply();
  };
  function fit() {
    const cw = wrap.clientWidth, ch = wrap.clientHeight;
    if (!cw || !ch) { requestAnimationFrame(fit); return; }
    // A ~200-generation tree is far taller than wide; fitting the whole height
    // collapses cards to slivers. Floor the zoom so the overview stays legible and
    // start at the top (the earliest people) when the tree overflows the viewport.
    scale = Math.max(Math.min(cw / W, ch / H) * 0.94, 0.18);
    tx = cw / 2 - mainCx * scale;                          // center on the MAIN tree, not the island gallery
    ty = (H * scale <= ch) ? (ch - H * scale) / 2 : (ch / 2 - mainCy * scale);  // center on the dense middle, not the empty top
    apply();
  }
  function focusPerson(pid, highlight) {
    const cw = wrap.clientWidth, ch = wrap.clientHeight;
    const s = Math.max(scale, 0.85);
    scale = s;
    tx = cw / 2 - (pos[pid].x + CW / 2) * s;
    ty = ch / 2 - (pos[pid].y + (cardH[pid] || 60) / 2) * s;
    apply();
    if (highlight) {
      document.querySelectorAll('.pcard.focal').forEach(e => e.classList.remove('focal'));
      const el = document.getElementById('c_' + pid);
      if (el) { el.classList.add('focal'); updatePanel(pid); }
    }
  }
  // click a person -> spotlight their line of descent (them + all descendants, down only), fade the rest
  function focusFamily(pid) {
    focusPerson(pid, true);
    const desc = new Set([pid]); let f = [pid];
    while (f.length) { const nx = []; f.forEach(x => kidsOf(x).forEach(c => { if (!desc.has(c)) { desc.add(c); nx.push(c); } })); f = nx; }
    const litCards = new Set(desc), litU = new Set();
    D.unions.forEach((u, ui) => { if (u.children.length && u.parents.some(pp => desc.has(pp))) { litU.add(ui); u.parents.forEach(pp => litCards.add(pp)); } });
    wrap.classList.remove('tracing'); wrap.classList.add('focusing');
    document.querySelectorAll('.pcard').forEach(el => el.classList.toggle('lit', litCards.has(el.id.slice(2))));
    svg.querySelectorAll('.conn,.dot').forEach(el => el.classList.toggle('lit', litU.has(+el.dataset.u)));
  }
  function clearFocus() {
    wrap.classList.remove('focusing');
    document.querySelectorAll('.pcard.lit, .conn.lit, .dot.lit, .pcard.focal').forEach(el => el.classList.remove('lit', 'focal'));
    const p = document.getElementById('panel'); if (p) p.hidden = true;
  }
  // hover a person -> trace their whole bloodline (ancestors + descendants), fade the rest.
  // Skipped while a click-focus is active so a pinned spotlight isn't disturbed.
  function traceHover(pid) {
    if (wrap.classList.contains('focusing')) return;
    const line = new Set([pid]);
    let f = [pid];
    while (f.length) { const nx = []; f.forEach(x => parentsOf(x).forEach(p => { if (!line.has(p)) { line.add(p); nx.push(p); } })); f = nx; }
    f = [pid];
    while (f.length) { const nx = []; f.forEach(x => kidsOf(x).forEach(c => { if (!line.has(c)) { line.add(c); nx.push(c); } })); f = nx; }
    const litU = new Set();
    D.unions.forEach((u, ui) => { if (u.parents.some(p => line.has(p)) && u.children.some(c => line.has(c))) { litU.add(ui); u.parents.forEach(p => line.add(p)); } });
    wrap.classList.add('tracing');
    document.querySelectorAll('.pcard').forEach(el => el.classList.toggle('lit', line.has(el.id.slice(2))));
    svg.querySelectorAll('.conn,.dot').forEach(el => el.classList.toggle('lit', litU.has(+el.dataset.u)));
  }
  function clearTrace() {
    if (!wrap.classList.contains('tracing') || wrap.classList.contains('focusing')) return;
    wrap.classList.remove('tracing');
    document.querySelectorAll('.pcard.lit, .conn.lit, .dot.lit').forEach(el => el.classList.remove('lit'));
  }
  // hover a LINE -> light up just that connector + the two cards it joins, fade the rest,
  // so a single line is easy to follow where many lines cross.
  function hoverConn(ui) {
    if (wrap.classList.contains('focusing')) return;
    const u = D.unions[ui]; if (!u) return;
    const lit = new Set([...u.parents, ...u.children]);
    wrap.classList.add('tracing');
    document.querySelectorAll('.pcard').forEach(el => el.classList.toggle('lit', lit.has(el.id.slice(2))));
    svg.querySelectorAll('.conn,.dot').forEach(el => el.classList.toggle('lit', +el.dataset.u === ui));
  }
  svg.addEventListener('mouseover', e => { const h = e.target.closest && e.target.closest('.conn-hit'); if (h) hoverConn(+h.dataset.u); });
  svg.addEventListener('mouseout', e => { const h = e.target.closest && e.target.closest('.conn-hit'); if (!h) return; const to = e.relatedTarget; if (to && to.closest && to.closest('.conn-hit')) return; clearTrace(); });
  let drag = false, lx = 0, ly = 0, moved = false;
  wrap.addEventListener('mousedown', e => { drag = true; moved = false; lx = e.clientX; ly = e.clientY; });
  window.addEventListener('mousemove', e => { if (!drag) return; if (Math.abs(e.clientX - lx) + Math.abs(e.clientY - ly) > 3) moved = true; tx += e.clientX - lx; ty += e.clientY - ly; lx = e.clientX; ly = e.clientY; apply(); });
  window.addEventListener('mouseup', () => drag = false);
  wrap.addEventListener('click', e => { if (!moved && !e.target.closest('.pcard')) clearFocus(); });
  wrap.addEventListener('wheel', e => { e.preventDefault(); const r = wrap.getBoundingClientRect(); const px = e.clientX - r.left, py = e.clientY - r.top; const f = e.deltaY < 0 ? 1.12 : 1 / 1.12; const ns = Math.max(0.05, Math.min(3, scale * f)); const k = ns / scale; tx = px - (px - tx) * k; ty = py - (py - ty) * k; scale = ns; apply(); }, { passive: false });

  // ---- touch: one-finger pan, two-finger pinch-zoom (mobile) ----
  let tMode = null, pinchD0 = 0, pinchS0 = 1, pinchMx = 0, pinchMy = 0;
  wrap.addEventListener('touchstart', e => {
    if (e.touches.length === 1) { tMode = 'pan'; moved = false; lx = e.touches[0].clientX; ly = e.touches[0].clientY; }
    else if (e.touches.length >= 2) {
      tMode = 'pinch'; moved = true;
      const [a, b] = e.touches, r = wrap.getBoundingClientRect();
      pinchD0 = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY) || 1;
      pinchS0 = scale; pinchMx = (a.clientX + b.clientX) / 2 - r.left; pinchMy = (a.clientY + b.clientY) / 2 - r.top;
    }
  }, { passive: true });
  wrap.addEventListener('touchmove', e => {
    if (tMode === 'pan' && e.touches.length === 1) {
      const t = e.touches[0];
      if (Math.abs(t.clientX - lx) + Math.abs(t.clientY - ly) > 3) moved = true;
      tx += t.clientX - lx; ty += t.clientY - ly; lx = t.clientX; ly = t.clientY; apply(); e.preventDefault();
    } else if (tMode === 'pinch' && e.touches.length >= 2) {
      const [a, b] = e.touches;
      const d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      const ns = Math.max(0.05, Math.min(3, pinchS0 * d / pinchD0)), k = ns / scale;
      tx = pinchMx - (pinchMx - tx) * k; ty = pinchMy - (pinchMy - ty) * k; scale = ns; apply(); e.preventDefault();
    }
  }, { passive: false });
  wrap.addEventListener('touchend', e => {
    if (e.touches.length === 0) { tMode = null; if (!moved) clearTrace(); }
    else if (e.touches.length === 1) { tMode = 'pan'; lx = e.touches[0].clientX; ly = e.touches[0].clientY; }
  });
  document.getElementById('zoomIn').onclick = () => { scale *= 1.2; apply(); };
  document.getElementById('zoomOut').onclick = () => { scale /= 1.2; apply(); };
  document.getElementById('fitBtn').onclick = fit;
  window.addEventListener('resize', fit);

  // ---- 8. detail panel + search ----
  const panel = document.getElementById('panel');
  const nameOf = pid => lines(pid)[0];
  const chip = pid => `<button class="chip" data-pid="${pid}" style="--acc:${accOf(pid)}">${nameOf(pid)}</button>`;
  const CAP = 40;
  const sect = (lab, arr) => {
    if (!arr || !arr.length) return '';
    const uniq = [...new Set(arr)];
    const shown = uniq.slice(0, CAP), extra = uniq.length - shown.length;
    return `<div class="pn-sec"><div class="pn-lab">${lab} <span class="pn-ct">${uniq.length}</span></div>` +
      `<div class="pn-chips">${shown.map(chip).join('')}${extra > 0 ? `<span class="pn-more">+${extra} more</span>` : ''}</div></div>`;
  };
  const ORD = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th'];
  function updatePanel(pid) {
    const L = lines(pid);
    panel.hidden = false;
    const cous = cousinsByDegree(pid);
    let cousHtml = '';
    Object.keys(cous).map(Number).sort((a, b) => a - b).forEach(n => { cousHtml += sect(`${ORD[n - 1] || n + 'th'} cousins`, cous[n]); });
    panel.innerHTML = `<button class="pn-close" title="Close">&times;</button>` +
      `<div class="pn-name">${L[0]}</div><div class="pn-meta">${L.slice(1).join('<br>')}</div>` +
      `<div class="pn-house" style="--acc:${accOf(pid)}">${(HOUSES[P[pid].house] || {}).title || ''}</div>` +
      sect('Great-grandparents', ancAt(pid, 3)) +
      sect('Grandparents', ancAt(pid, 2)) +
      sect('Parents', parentsOf(pid)) +
      sect('Siblings', siblingsOf(pid)) +
      sect('Married', spousesOf(pid)) +
      sect('Children', [...new Set(kidsOf(pid))]) +
      sect('Grandchildren', descAt(pid, 2)) +
      sect('Great-grandchildren', descAt(pid, 3)) +
      cousHtml;
    panel.querySelectorAll('.chip').forEach(b => b.onclick = () => focusFamily(b.dataset.pid));
    const close = panel.querySelector('.pn-close'); if (close) close.onclick = clearFocus;
  }
  const search = document.getElementById('search'), results = document.getElementById('results');
  const ALL = ids.map(pid => ({ pid, n: nameOf(pid).toLowerCase() }));
  function runSearch() {
    const q = search.value.trim().toLowerCase();
    if (!q) { results.hidden = true; return; }
    const hits = ALL.filter(p => p.n.includes(q)).sort((a, b) => a.n.length - b.n.length).slice(0, 8);
    results.innerHTML = hits.map(h => `<button data-pid="${h.pid}">${nameOf(h.pid)}<span>${(HOUSES[P[h.pid].house] || {}).title || ''}</span></button>`).join('');
    results.hidden = !hits.length;
    results.querySelectorAll('button').forEach(b => b.onclick = () => { focusFamily(b.dataset.pid); search.value = ''; results.hidden = true; });
  }
  search.addEventListener('input', runSearch);
  search.addEventListener('keydown', e => { if (e.key === 'Enter') { const b = results.querySelector('button'); if (b) b.click(); } });
  document.addEventListener('click', e => { if (!e.target.closest('.searchbox')) results.hidden = true; });

  // ---- era navigation: a jump-rail down the left + a live "current era" label ----
  (() => {
    const rail = document.getElementById('era-rail'), now = document.getElementById('era-now');
    if (!rail) return;
    const ERAS = [['Creation', -3800], ['Patriarchs', -1900], ['Exodus', -1300], ['Judges', -1150],
      ['Kings', -950], ['Exile', -600], ['Classical', -460], ['Alexander', -330],
      ['Rome', -60], ['Christ', 1], ['Franks', 700], ['Crusades', 1150], ['Tudors', 1600]];
    // map year <-> stage-y using the populated era rows
    const marks = bands.filter(b => b * BAND > -4200 && b * BAND < 1850).map(b => [b * BAND, bandY[b] - minY]);
    marks.sort((a, b) => a[0] - b[0]);
    if (!marks.length) return;
    const near = (arr, i, v) => arr.reduce((best, m) => Math.abs(m[i] - v) < Math.abs(best[i] - v) ? m : best, arr[0]);
    const yForYear = yr => near(marks, 0, yr)[1];
    const yearForY = y => near(marks, 1, y)[0];
    const fmtY = yr => yr < 0 ? (-yr) + ' BC' : (yr < 1000 ? yr + ' AD' : '' + yr);
    const jumpToYear = yr => {
      const cw = wrap.clientWidth, ch = wrap.clientHeight;
      scale = Math.max(scale, 0.42);
      tx = cw / 2 - mainCx * scale;
      ty = ch / 2 - (yForYear(yr) + 60) * scale;
      apply();
    };
    const btns = ERAS.map(([label, yr]) => {
      const b = document.createElement('button');
      b.className = 'era-chip'; b.textContent = label;
      b.style.top = (yForYear(yr) / H * 100) + '%';
      b.title = 'Jump to c. ' + fmtY(yr);
      b.onclick = () => jumpToYear(yr);
      rail.appendChild(b);
      return b;
    });
    _onApply = () => {
      const yr = yearForY((wrap.clientHeight / 2 - ty) / scale);
      if (now) now.textContent = 'c. ' + fmtY(yr);
      let bi = 0, bd = Infinity;
      ERAS.forEach(([, y], i) => { const d = Math.abs(y - yr); if (d < bd) { bd = d; bi = i; } });
      btns.forEach((b, i) => b.classList.toggle('here', i === bi));
    };
  })();

  fit();
})();

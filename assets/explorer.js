/* The Bloodline — person-centric explorer (vanilla, no CDN).
   Renders an hourglass around a focal person: ancestors above, descendants below,
   clean aligned generations, click any card to re-center. Data = window.BL_DATA. */
(function () {
  const D = window.BL_DATA;
  const P = D.people, HOUSES = D.houses;

  // ---- indexes ----
  const marriagesOf = {};   // pid -> [union,...] where pid is a parent
  const birthUnionOf = {};  // pid -> the union where pid is a child
  D.unions.forEach(u => {
    u.parents.forEach(p => (marriagesOf[p] = marriagesOf[p] || []).push(u));
    u.children.forEach(c => { birthUnionOf[c] = u; });
  });
  const nameOf = pid => (P[pid].label || pid).split('<br/>')[0];
  const linesOf = pid => (P[pid].label || pid).split('<br/>');
  const houseOf = pid => P[pid].house;
  const accOf = pid => (HOUSES[houseOf(pid)] || {}).accent || '#cbb98a';
  const spousesOf = pid => (marriagesOf[pid] || []).map(u => u.parents.find(p => p !== pid)).filter(Boolean);
  function childrenOf(pid) {
    const seen = new Set(), out = [];
    (marriagesOf[pid] || []).forEach(u => u.children.forEach(c => { if (!seen.has(c)) { seen.add(c); out.push(c); } }));
    return out;
  }

  // ---- geometry ----
  const CW = 194, CH = 68, HGAP = 26, ROW = 150;
  let focal = D.root, upGens = 3, downGens = 2;
  const history = [], future = [];

  // ---- layout ----
  function buildUp(pid, gen) {
    const n = { pid, gen, y: -gen * ROW, x: 0, parents: null };
    if (gen < upGens) {
      const bu = birthUnionOf[pid];
      if (bu && bu.parents.length) n.parents = bu.parents.map(p => buildUp(p, gen + 1));
    }
    return n;
  }
  function buildDown(pid, gen) {
    const n = { pid, gen, y: gen * ROW, x: 0, kids: [] };
    if (gen < downGens) n.kids = childrenOf(pid).map(c => buildDown(c, gen + 1));
    return n;
  }
  function place(node, kidsKey, cursor) {
    const kids = node[kidsKey];
    if (kids && kids.length) {
      kids.forEach(k => place(k, kidsKey, cursor));
      node.x = (kids[0].x + kids[kids.length - 1].x) / 2;
    } else { node.x = cursor.v; cursor.v += CW + HGAP; }
    return node;
  }
  function walk(node, kidsKey, out) { out.push(node); (node[kidsKey] || []).forEach(k => walk(k, kidsKey, out)); return out; }

  // ---- render ----
  const stage = document.getElementById('stage');
  const svg = document.getElementById('links');
  let scale = 1, tx = 0, ty = 0;

  function render() {
    // build both trees, align focal to x=0
    const up = place(buildUp(focal, 0), 'parents', { v: 0 });
    const down = place(buildDown(focal, 0), 'kids', { v: 0 });
    const upNodes = walk(up, 'parents', []);
    const downNodes = walk(down, 'kids', []).slice(1); // drop duplicate focal
    const ux = up.x, dx = down.x;
    upNodes.forEach(n => n.x -= ux);
    downNodes.forEach(n => n.x -= dx);

    // focal spouse(s) as a couple row beside focal
    const spouses = spousesOf(focal);
    const nodes = upNodes.concat(downNodes);
    const spouseNodes = spouses.slice(0, 3).map((sp, i) => ({ pid: sp, gen: 0, y: 0, x: (i + 1) * (CW + HGAP), spouse: true }));
    nodes.push(...spouseNodes);

    // normalize to positive coords with padding
    const PAD = 80;
    const minX = Math.min(...nodes.map(n => n.x)) - PAD;
    const minY = Math.min(...nodes.map(n => n.y)) - PAD;
    const maxX = Math.max(...nodes.map(n => n.x)) + CW + PAD;
    const maxY = Math.max(...nodes.map(n => n.y)) + CH + PAD;
    const W = maxX - minX, H = maxY - minY;
    nodes.forEach(n => { n.px = n.x - minX; n.py = n.y - minY; });

    stage.style.width = W + 'px'; stage.style.height = H + 'px';
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W); svg.setAttribute('height', H);

    // ---- connectors ----
    const paths = [];
    const cx = n => n.px + CW / 2, top = n => n.py, bot = n => n.py + CH, cy = n => n.py + CH / 2;
    // ancestor couples: marriage bar + drop to child
    upNodes.forEach(n => {
      if (n.parents) {
        const a = n.parents[0], b = n.parents[1] || n.parents[0];
        const barY = cy(a);
        paths.push(`M ${cx(a)} ${barY} L ${cx(b)} ${barY}`);         // marriage bar
        const midX = (cx(a) + cx(b)) / 2;
        const my = (barY + top(n)) / 2;
        paths.push(`M ${midX} ${barY} L ${midX} ${my} L ${cx(n)} ${my} L ${cx(n)} ${top(n)}`); // elbow down to child
      }
    });
    // focal couple bar (focal + first spouse)
    if (spouseNodes.length) {
      const f = nodes.find(n => n.pid === focal && !n.spouse) || up;
      const s = spouseNodes[0];
      paths.push(`M ${cx(f)} ${cy(f)} L ${cx(s)} ${cy(s)}`);
    }
    // descendants: focal -> each child, and each shown parent -> its kids
    function drawKids(n) {
      if (!n.kids || !n.kids.length) return;
      const busY = (bot(n) + top(n.kids[0])) / 2;
      paths.push(`M ${cx(n)} ${bot(n)} L ${cx(n)} ${busY}`);
      n.kids.forEach(k => {
        paths.push(`M ${cx(n)} ${busY} L ${cx(k)} ${busY} L ${cx(k)} ${top(k)}`);
        drawKids(k);
      });
    }
    drawKids(down);
    svg.innerHTML = `<path d="${paths.join(' ')}" fill="none" stroke="#8a7a55" stroke-width="1.6"/>`;

    // ---- cards ----
    stage.querySelectorAll('.pcard').forEach(e => e.remove());
    nodes.forEach(n => stage.appendChild(cardEl(n)));

    updatePanel();
    fit(true);
  }

  function cardEl(n) {
    const pid = n.pid;
    const el = document.createElement('div');
    el.className = 'pcard' + (pid === focal && !n.spouse ? ' focal' : '') + (n.spouse ? ' spouse' : '');
    el.style.left = n.px + 'px'; el.style.top = n.py + 'px';
    el.style.setProperty('--acc', accOf(pid));
    const lines = linesOf(pid);
    const sub = lines.slice(1, 3).join(' · ');
    el.innerHTML =
      `<div class="pc-name">${lines[0]}</div>` +
      (sub ? `<div class="pc-sub">${sub}</div>` : '') +
      `<div class="pc-house">${(HOUSES[houseOf(pid)] || {}).title || ''}</div>`;
    el.addEventListener('click', e => { e.stopPropagation(); setFocal(pid); });
    return el;
  }

  // ---- detail panel ----
  function chip(pid) { return `<button class="chip" data-pid="${pid}" style="--acc:${accOf(pid)}">${nameOf(pid)}</button>`; }
  function updatePanel() {
    const panel = document.getElementById('panel');
    const lines = linesOf(focal);
    const bu = birthUnionOf[focal];
    const parents = bu ? bu.parents : [];
    const sp = spousesOf(focal);
    const ch = childrenOf(focal);
    panel.innerHTML =
      `<div class="pn-name">${lines[0]}</div>` +
      `<div class="pn-meta">${lines.slice(1).join('<br>')}</div>` +
      `<div class="pn-house" style="--acc:${accOf(focal)}">${(HOUSES[houseOf(focal)] || {}).title || ''}</div>` +
      section('Parents', parents) + section('Married', sp) + section('Children', ch);
    panel.querySelectorAll('.chip').forEach(b => b.addEventListener('click', () => setFocal(b.dataset.pid)));
  }
  function section(label, ids) {
    if (!ids || !ids.length) return '';
    return `<div class="pn-sec"><div class="pn-lab">${label}</div><div class="pn-chips">${ids.map(chip).join('')}</div></div>`;
  }

  // ---- navigation ----
  function setFocal(pid, noHistory) {
    if (pid === focal) return;
    if (!noHistory) { history.push(focal); future.length = 0; }
    focal = pid; render();
  }

  // ---- pan / zoom ----
  const wrap = document.getElementById('explore-wrap');
  function apply() { scale = Math.max(0.15, Math.min(3, scale)); stage.style.transform = `translate(${tx}px,${ty}px) scale(${scale})`; }
  function fit(soft) {
    const cw = wrap.clientWidth, ch = wrap.clientHeight;
    if (!cw || !ch) { requestAnimationFrame(() => fit(soft)); return; }
    const sw = stage.offsetWidth, sh = stage.offsetHeight;
    scale = Math.min(cw / sw, ch / sh, 1) * 0.92;
    // center horizontally on the focal card, keep top of tree comfortable
    const f = stage.querySelector('.pcard.focal');
    tx = (cw - sw * scale) / 2;
    ty = (ch - sh * scale) / 2;
    apply();
  }
  let drag = false, lx = 0, ly = 0, moved = false;
  wrap.addEventListener('mousedown', e => { drag = true; moved = false; lx = e.clientX; ly = e.clientY; });
  window.addEventListener('mousemove', e => { if (!drag) return; if (Math.abs(e.clientX - lx) + Math.abs(e.clientY - ly) > 3) moved = true; tx += e.clientX - lx; ty += e.clientY - ly; lx = e.clientX; ly = e.clientY; apply(); });
  window.addEventListener('mouseup', () => { drag = false; });
  wrap.addEventListener('wheel', e => { e.preventDefault(); const r = wrap.getBoundingClientRect(); const px = e.clientX - r.left, py = e.clientY - r.top; const f = e.deltaY < 0 ? 1.12 : 1 / 1.12; const ns = Math.max(0.15, Math.min(3, scale * f)); const k = ns / scale; tx = px - (px - tx) * k; ty = py - (py - ty) * k; scale = ns; apply(); }, { passive: false });

  // ---- controls ----
  document.getElementById('zoomIn').onclick = () => { scale *= 1.2; apply(); };
  document.getElementById('zoomOut').onclick = () => { scale /= 1.2; apply(); };
  document.getElementById('fitBtn').onclick = () => fit();
  document.getElementById('homeBtn').onclick = () => setFocal(D.root);
  document.getElementById('backBtn').onclick = () => { if (history.length) { future.push(focal); focal = history.pop(); render(); } };
  document.getElementById('upMore').onclick = () => { upGens = Math.min(6, upGens + 1); render(); };
  document.getElementById('upLess').onclick = () => { upGens = Math.max(0, upGens - 1); render(); };
  document.getElementById('downMore').onclick = () => { downGens = Math.min(6, downGens + 1); render(); };
  document.getElementById('downLess').onclick = () => { downGens = Math.max(0, downGens - 1); render(); };

  // ---- search ----
  const search = document.getElementById('search'), results = document.getElementById('results');
  const ALL = Object.keys(P).map(pid => ({ pid, n: nameOf(pid).toLowerCase() }));
  function runSearch() {
    const q = search.value.trim().toLowerCase();
    if (!q) { results.hidden = true; return; }
    const hits = ALL.filter(p => p.n.includes(q)).sort((a, b) => a.n.length - b.n.length).slice(0, 8);
    results.innerHTML = hits.map(h => `<button data-pid="${h.pid}">${nameOf(h.pid)}<span>${(HOUSES[houseOf(h.pid)] || {}).title || ''}</span></button>`).join('');
    results.hidden = hits.length === 0;
    results.querySelectorAll('button').forEach(b => b.onclick = () => { setFocal(b.dataset.pid); search.value = ''; results.hidden = true; });
  }
  search.addEventListener('input', runSearch);
  search.addEventListener('keydown', e => { if (e.key === 'Enter') { const b = results.querySelector('button'); if (b) b.click(); } });
  document.addEventListener('click', e => { if (!e.target.closest('.searchbox')) results.hidden = true; });
  window.addEventListener('resize', () => fit());

  render();
})();

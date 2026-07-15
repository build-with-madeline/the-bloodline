// Self-contained pan/zoom -- no external library, so nothing can fail to load.
// Runs Mermaid, then drives the rendered SVG with a CSS transform.
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  securityLevel: 'loose',
  maxEdges: 5000,
  maxTextSize: 900000,
  flowchart: {
    curve: 'linear',
    nodeSpacing: 46,
    rankSpacing: 130,
    diagramPadding: 40,
    useMaxWidth: false,
    htmlLabels: true
  }
});

mermaid.run({ querySelector: '.mermaid' }).then(function () {
  initInteractions();
}).catch(function (err) {
  var wrap = document.getElementById('diagram-wrap');
  var msg = document.createElement('div');
  msg.style.cssText = 'position:absolute;top:0;left:0;right:0;bottom:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;color:#232b46;font-size:0.9rem;line-height:1.5;';
  msg.innerHTML = 'The diagram could not finish rendering in this viewer.<br>Try opening this file in a desktop browser.';
  wrap.appendChild(msg);
  console.error('Mermaid render failed:', err);
});

function initInteractions() {
  var svgEl = document.querySelector('#graphDiv svg');
  var wrap = document.getElementById('diagram-wrap');
  if (!svgEl || !wrap) { return; }

  var W, H;
  var vb = svgEl.viewBox && svgEl.viewBox.baseVal;
  if (vb && vb.width && vb.height) { W = vb.width; H = vb.height; }
  else { var b = svgEl.getBBox(); W = b.width; H = b.height; }

  svgEl.style.transformOrigin = '0 0';
  svgEl.style.position = 'absolute';
  svgEl.style.top = '0';
  svgEl.style.left = '0';
  svgEl.style.width = W + 'px';
  svgEl.style.height = H + 'px';
  svgEl.style.maxWidth = 'none';

  var scale = 1, tx = 0, ty = 0;
  var MIN = 0.05, MAX = 25;

  function apply() {
    scale = Math.max(MIN, Math.min(MAX, scale));
    svgEl.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + scale + ')';
  }
  function fit() {
    var cw = wrap.clientWidth, ch = wrap.clientHeight;
    // If the container hasn't been laid out yet (0x0), defer until it has size
    // so we never bake in a broken transform.
    if (!cw || !ch) { requestAnimationFrame(fit); return; }
    scale = Math.min(cw / W, ch / H) * 0.95;
    tx = (cw - W * scale) / 2;
    ty = (ch - H * scale) / 2;
    apply();
  }
  function zoomAt(cx, cy, factor) {
    var ns = Math.max(MIN, Math.min(MAX, scale * factor));
    var k = ns / scale;
    tx = cx - (cx - tx) * k;
    ty = cy - (cy - ty) * k;
    scale = ns;
    apply();
  }
  function rel(e) {
    var r = wrap.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  fit();

  wrap.addEventListener('wheel', function (e) {
    e.preventDefault();
    var p = rel(e);
    zoomAt(p.x, p.y, e.deltaY < 0 ? 1.15 : 1 / 1.15);
  }, { passive: false });

  // Mouse drag to pan. Ignore drags that start on a bridge link so clicks navigate.
  var dragging = false, moved = false, lx = 0, ly = 0;
  wrap.addEventListener('mousedown', function (e) {
    dragging = true; moved = false; lx = e.clientX; ly = e.clientY;
  });
  window.addEventListener('mousemove', function (e) {
    if (!dragging) return;
    if (Math.abs(e.clientX - lx) + Math.abs(e.clientY - ly) > 2) moved = true;
    tx += e.clientX - lx; ty += e.clientY - ly; lx = e.clientX; ly = e.clientY; apply();
  });
  window.addEventListener('mouseup', function () { dragging = false; });

  wrap.addEventListener('dblclick', function (e) { var p = rel(e); zoomAt(p.x, p.y, 1.5); });

  // Robust bridge navigation: follow a node's link on a genuine (non-drag) click.
  // Native SVG <a> from an HTML foreignObject label doesn't reliably navigate, so
  // we resolve the nearest anchor ourselves. `moved` keeps pans from navigating.
  wrap.addEventListener('click', function (e) {
    if (moved) return;
    var el = e.target;
    var a = el && el.closest ? el.closest('a') : null;
    if (!a) return;
    var href = a.getAttribute('href') || a.getAttributeNS('http://www.w3.org/1999/xlink', 'href');
    if (href) { window.location.href = href; }
  });

  var pinch = 0;
  function tdist(t) { var dx = t[0].clientX - t[1].clientX, dy = t[0].clientY - t[1].clientY; return Math.hypot(dx, dy); }
  wrap.addEventListener('touchstart', function (e) {
    if (e.touches.length === 1) { lx = e.touches[0].clientX; ly = e.touches[0].clientY; }
    else if (e.touches.length === 2) { pinch = tdist(e.touches); }
  }, { passive: false });
  wrap.addEventListener('touchmove', function (e) {
    e.preventDefault();
    var r = wrap.getBoundingClientRect();
    if (e.touches.length === 1) {
      tx += e.touches[0].clientX - lx; ty += e.touches[0].clientY - ly;
      lx = e.touches[0].clientX; ly = e.touches[0].clientY; apply();
    } else if (e.touches.length === 2) {
      var nd = tdist(e.touches);
      var cx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - r.left;
      var cy = (e.touches[0].clientY + e.touches[1].clientY) / 2 - r.top;
      if (pinch) zoomAt(cx, cy, nd / pinch);
      pinch = nd;
    }
  }, { passive: false });

  document.getElementById('zoomIn').addEventListener('click', function () { zoomAt(wrap.clientWidth / 2, wrap.clientHeight / 2, 1.3); });
  document.getElementById('zoomOut').addEventListener('click', function () { zoomAt(wrap.clientWidth / 2, wrap.clientHeight / 2, 1 / 1.3); });
  document.getElementById('zoomReset').addEventListener('click', fit);

  window.addEventListener('keydown', function (e) {
    if (e.key === '+' || e.key === '=') zoomAt(wrap.clientWidth / 2, wrap.clientHeight / 2, 1.3);
    else if (e.key === '-' || e.key === '_') zoomAt(wrap.clientWidth / 2, wrap.clientHeight / 2, 1 / 1.3);
    else if (e.key === '0') fit();
  });

  window.addEventListener('resize', fit);
  setTimeout(function () { var h = document.getElementById('hint'); if (h) h.style.opacity = '0'; }, 3500);

  // ---- breadcrumb: "arrived from House X" ----
  var params = new URLSearchParams(window.location.search);
  var from = params.get('from');
  var crumb = document.getElementById('crumb');
  if (from && crumb && window.BL_HOUSES && window.BL_HOUSES[from]) {
    crumb.textContent = '← from ' + window.BL_HOUSES[from];
    crumb.setAttribute('href', './' + from + '.html');
    crumb.hidden = false;
  }

  // ---- focus + highlight the deep-linked person (#PERSONID) ----
  function findNode(pid) {
    var gs = document.querySelectorAll('#graphDiv svg g.node');
    for (var i = 0; i < gs.length; i++) {
      var mid = (gs[i].id || '').replace(/^flowchart-/, '').replace(/-\d+$/, '');
      if (mid === pid) return gs[i];
    }
    return null;
  }
  function focusNode(pid) {
    var g = findNode(pid);
    if (!g) return;
    var gr = g.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
    // pan so the node's center sits at the wrap center (at current fit scale)
    tx += (wr.width / 2) - (gr.left + gr.width / 2 - wr.left);
    ty += (wr.height / 2) - (gr.top + gr.height / 2 - wr.top);
    apply();
    // then zoom in on the centered node to a readable scale
    var target = Math.max(scale, 1.5);
    zoomAt(wr.width / 2, wr.height / 2, target / scale);
    g.classList.add('bl-focus');
    setTimeout(function () { g.classList.remove('bl-focus'); }, 6000);
  }
  var hash = decodeURIComponent((window.location.hash || '').replace(/^#/, ''));
  if (hash) { requestAnimationFrame(function () { focusNode(hash); }); }

  // ---- search box (full-tree page only): jump to + highlight a person ----
  var searchEl = document.getElementById('search');
  if (searchEl && window.BL_PEOPLE) {
    function doSearch() {
      var q = searchEl.value.trim().toLowerCase();
      if (!q) return;
      var hit = window.BL_PEOPLE.filter(function (p) {
        return p.n.toLowerCase().indexOf(q) !== -1;
      });
      // prefer an exact name match, else the shortest matching name
      hit.sort(function (a, b) { return a.n.length - b.n.length; });
      var exact = hit.find(function (p) { return p.n.toLowerCase() === q; });
      var pick = exact || hit[0];
      if (pick) { fit(); requestAnimationFrame(function () { focusNode(pick.id); }); searchEl.classList.remove('miss'); }
      else { searchEl.classList.add('miss'); }
    }
    searchEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); doSearch(); } });
    searchEl.addEventListener('search', doSearch); // type=search fires this on Enter/clear
    searchEl.addEventListener('input', function () { searchEl.classList.remove('miss'); });
    var go = document.getElementById('searchGo');
    if (go) go.addEventListener('click', doSearch);
  }
}

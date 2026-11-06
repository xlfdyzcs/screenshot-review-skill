'use strict';
const $ = id => document.getElementById(id);
const data = JSON.parse($('review-data').textContent);
const cases = data.cases, meta = data.review;
const key = meta.storageKey;
let saved = {};
try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch (_) {}
let current = 0, shot = 0, filter = 'all', overview = false, overlay = false, marking = false;
let zoomReturn = null;
let scrollTogether = true, zoom = 'fit', scrollSyncTarget = null;
const entry = () => saved[cases[current].id] || (saved[cases[current].id] = {status:'pending', note:'', pins:[]});
let layoutFrame = null;

function scheduleLayout() {
  if (layoutFrame !== null) return;
  layoutFrame = requestAnimationFrame(() => {
    layoutFrame = null;
    document.documentElement.style.setProperty('--header-height', $('appHeader').offsetHeight + 'px');
    updateNavigationButton();
    applyImageWidths();
  });
}

function syncStatus() {
  for (const option of document.querySelectorAll('[name="reviewStatus"]')) option.checked = option.value === entry().status;
  $('currentStatus').className = 'dot ' + entry().status;
  $('currentStatus').setAttribute('aria-label', {pending:'未审阅', done:'已核对', change:'需要修改'}[entry().status]);
  const count = entry().pins.length + (entry().note.trim() ? 1 : 0);
  $('noteCount').hidden = count === 0;
  $('noteCount').textContent = count;
}

function setNavigationOpen(open) {
  document.body.classList.toggle('nav-open', open);
  updateNavigationButton();
}

function updateNavigationButton() {
  const mobile = window.matchMedia('(max-width: 860px)').matches;
  const open = mobile ? document.body.classList.contains('nav-open') : !document.body.classList.contains('nav-collapsed');
  $('toggleNav').setAttribute('aria-expanded', String(open));
  const label = mobile ? (open ? '关闭页面清单' : '打开页面清单') : (open ? '折叠页面清单' : '展开页面清单');
  $('toggleNav').setAttribute('aria-label', label);
  $('toggleNav').title = label;
}

function setNotesOpen(open, focus = false) {
  document.body.classList.toggle('notes-open', open);
  $('reviewNotes').hidden = !open;
  $('notesToggle').setAttribute('aria-expanded', String(open));
  $('notesToggle').title = open ? '收起批注（N）' : '打开批注（N）';
  if (open && focus) $('comment').focus();
  scheduleLayout();
}

function setFocusMode(open) {
  document.body.classList.toggle('focus-mode', open);
  $('fullscreenBtn').setAttribute('aria-pressed', String(open));
  $('fullscreenBtn').textContent = open ? '退出全屏' : '全屏审图';
  setNavigationOpen(false);
  scheduleLayout();
}

async function toggleFullscreen() {
  const open = !document.body.classList.contains('focus-mode');
  setFocusMode(open);
  try {
    if (open && !document.fullscreenElement) await document.documentElement.requestFullscreen?.();
    else if (!open && document.fullscreenElement) await document.exitFullscreen();
  } catch (_) { /* The expanded reader also works where native fullscreen is unavailable. */ }
}

function applyImageWidths() {
  const c = cases[current];
  for (const [n, side] of [['1','before'], ['3','after']]) {
    const screenshot = c[side][shot];
    $('stack' + n).style.width = zoom === 'fit' || !screenshot ? '100%' : Math.round(screenshot.pixelSize[0] * Number(zoom) / 100) + 'px';
  }
}

function setZoom(value) {
  const positions = ['1','3'].map(n => {
    const pane = $('pane' + n);
    return {pane, x:(pane.scrollLeft + pane.clientWidth / 2) / (pane.scrollWidth || 1), y:(pane.scrollTop + pane.clientHeight / 2) / (pane.scrollHeight || 1)};
  });
  zoom = value; $('zoom').value = value;
  applyImageWidths(); scrollSyncTarget = null;
  for (const p of positions) {
    p.pane.scrollLeft = p.x * p.pane.scrollWidth - p.pane.clientWidth / 2;
    p.pane.scrollTop = p.y * p.pane.scrollHeight - p.pane.clientHeight / 2;
  }
}

function stepZoom(direction) {
  const screenshot = cases[current].before[shot] || cases[current].after[shot];
  const effective = zoom === 'fit' ? 100 * $('stack1').clientWidth / screenshot.pixelSize[0] : Number(zoom);
  const steps = [25,50,75,100,125,150,200,300];
  const value = direction > 0 ? steps.find(n => n > effective + .1) || 300 : steps.findLast(n => n < effective - .1) || 25;
  setZoom(String(value));
}

function synchronizeScroll(source, target) {
  if (!scrollTogether || $('screens').classList.contains('overlay')) return;
  if (scrollSyncTarget?.pane === source && Math.abs(source.scrollTop - scrollSyncTarget.top) < 1 && Math.abs(source.scrollLeft - scrollSyncTarget.left) < 1) {
    scrollSyncTarget = null; return;
  }
  const offset = (position, extent, viewport, targetExtent, targetViewport) => extent <= viewport ? 0 : position / (extent - viewport) * Math.max(0, targetExtent - targetViewport);
  const top = offset(source.scrollTop, source.scrollHeight, source.clientHeight, target.scrollHeight, target.clientHeight);
  const left = offset(source.scrollLeft, source.scrollWidth, source.clientWidth, target.scrollWidth, target.clientWidth);
  scrollSyncTarget = {pane:target, top, left};
  target.scrollTop = top; target.scrollLeft = left;
}

function resetScroll() {
  scrollSyncTarget = null;
  for (const n of ['1','3']) { $('pane' + n).scrollTop = 0; $('pane' + n).scrollLeft = 0; }
}

function changeShot(index) {
  shot = Math.max(0, Math.min(index, Math.max(cases[current].before.length, cases[current].after.length) - 1));
  renderImages();
  resetScroll();
}

function persist() {
  try {
    localStorage.setItem(key, JSON.stringify(saved));
    $('saved').textContent = '已自动保存；换机器或端口前，请备份批注。';
  } catch (_) { $('saved').textContent = '本地存储不可用，请导出意见或备份批注。'; }
  renderNav();
}

function eligible(c) {
  const q = $('search').value.trim().toLowerCase();
  return (!q || `${c.id} ${c.title} ${c.group}`.toLowerCase().includes(q)) &&
    (filter === 'all' || (saved[c.id]?.status || 'pending') === filter);
}

function renderNav() {
  $('nav').replaceChildren();
  let group = null, section;
  cases.forEach((c, i) => {
    if (!eligible(c)) return;
    if (c.group !== group) {
      group = c.group;
      section = document.createElement('div'); section.className = 'navgroup';
      const heading = document.createElement('div'); heading.className = 'group-title'; heading.textContent = group;
      section.append(heading); $('nav').append(section);
    }
    const button = document.createElement('button');
    button.className = 'navitem' + (i === current ? ' active' : '');
    button.setAttribute('aria-current', i === current ? 'page' : 'false');
    button.title = c.id + ' · ' + c.title;
    button.setAttribute('aria-label', c.id + ' ' + c.title);
    for (const [className, text] of [['navid',c.id], ['navtitle',c.title], ['dot ' + (saved[c.id]?.status || 'pending'),'']]) {
      const span = document.createElement('span'); span.className = className; span.textContent = text; button.append(span);
    }
    button.onclick = () => selectCase(i); section.append(button);
  });
  $('progress').textContent = `${cases.length} 项 · 已核对 ${cases.filter(c => saved[c.id]?.status === 'done').length} · 待修改 ${cases.filter(c => saved[c.id]?.status === 'change').length}`;
  $('globalProgress').textContent = $('progress').textContent;
}

function selectCase(i) {
  const next = Math.max(0, Math.min(cases.length - 1, i));
  if (next !== current && !overview) {
    completeReviewedEntry(entry());
    persist();
  }
  current = next; shot = 0;
  if (overview) showOverview();
  setNavigationOpen(false);
  render(); resetScroll();
}

function render() {
  const c = cases[current], e = entry();
  const max = Math.max(c.before.length, c.after.length);
  $('caseId').textContent = c.id; $('caseTitle').textContent = c.title;
  $('caseTitle').title = c.title;
  $('caseMeta').textContent = `${c.title} · ${c.group} · ${c.width} × ${c.height} 逻辑像素 · 左 ${c.before.length} / 右 ${c.after.length} 张分段`;
  $('special').hidden = !c.note; $('special').textContent = c.note;
  $('caseInfo').classList.toggle('has-note', !!c.note);
  $('caseInfo').open = false;
  syncStatus(); $('comment').value = e.note; $('noteHeading').textContent = c.id + ' · 修改意见';
  $('segment').replaceChildren();
  for (let i = 0; i < max; i++) $('segment').append(new Option(`${c.id}-${String(i + 1).padStart(2,'0')} · ${i + 1}/${max}`, String(i)));
  shot = Math.min(shot, max - 1);
  $('prev').disabled = current === 0; $('next').disabled = current === cases.length - 1;
  renderImages(); renderNav(); scheduleLayout();
}

function renderImages() {
  const c = cases[current], e = entry(), max = Math.max(c.before.length, c.after.length);
  $('segment').value = String(shot);
  for (const side of ['before','after']) {
    const n = side === 'before' ? '1' : '3', box = $('box' + n), im = $('image' + n), s = c[side][shot];
    box.querySelectorAll('.pin,.missing').forEach(element => element.remove());
    im.hidden = !s; $('imageAction' + n).hidden = !s; $('raw' + n).hidden = !s;
    if (s) {
      im.src = s.file; im.alt = `${c.id}-${shot + 1} ${side} ${c.title}`; $('raw' + n).href = s.file;
      im.title = marking ? '点击截图添加定位标点' : '点击查看原始尺寸';
    } else {
      im.removeAttribute('src');
      const empty = document.createElement('div'); empty.className = 'missing';
      empty.textContent = c[side].length ? '此侧已到页面末尾，后续无内容。' : '此侧未采集该页，保留空缺供复查。';
      box.append(empty);
    }
    box.classList.toggle('marking', marking);
    (e.pins || []).forEach((p, i) => {
      if (p.app !== side || p.shot !== shot) return;
      const pin = document.createElement('span'); pin.className = 'pin'; pin.textContent = i + 1;
      pin.style.left = p.x + '%'; pin.style.top = p.y + '%'; box.append(pin);
    });
  }
  const enabled = overlay && c.before[shot] && c.after[shot];
  $('screens').classList.toggle('overlay', !!enabled);
  const afterStack = enabled ? $('stack1') : $('stack3');
  if ($('box3').parentElement !== afterStack) afterStack.append($('box3'));
  $('box3').style.opacity = enabled ? $('opacity').value / 100 : 1;
  $('opacityWrap').hidden = !enabled;
  $('syncBtn').disabled = !!enabled;
  $('syncBtn').title = enabled ? '叠加模式使用同一滚动区' : '同步两侧的滚动位置';
  $('pairBtn').setAttribute('aria-pressed', String(!enabled));
  $('overlayBtn').setAttribute('aria-pressed', String(!!enabled));
  $('overlayBtn').disabled = !c.before[shot] || !c.after[shot];
  $('hint').textContent = `${c.id}-${String(shot + 1).padStart(2,'0')} · ${max > 1 ? '按实际滚动分段，重叠比例见采集说明。' : '当前视口。'} ${marking ? '点击截图放置标记，然后填写修改意见。' : '点击截图可查看原尺寸。'}${overlay && !enabled ? ' 此分段缺少一侧截图，使用左右对照。' : ''}`;
  $('pins').replaceChildren();
  (e.pins || []).forEach(p => {
    const item = document.createElement('li');
    item.textContent = `${c.id}-${String(p.shot + 1).padStart(2,'0')} · ${p.app === 'before' ? meta.beforeLabel : meta.afterLabel} · 距左 ${p.x.toFixed(1)}%、距上 ${p.y.toFixed(1)}%`;
    $('pins').append(item);
  });
  $('prevShot').disabled = shot === 0; $('nextShot').disabled = shot >= max - 1;
  applyImageWidths();
  scheduleLayout();
  history.replaceState(null, '', '#' + c.id + '-' + String(shot + 1).padStart(2,'0'));
}

function showOverview() {
  overview = !overview; $('detail').hidden = overview;
  $('overview').hidden = !overview;
  $('overviewBtn').textContent = overview ? '返回原图对照' : '全部缩略图';
  if (overview) renderGrid();
  scheduleLayout();
}

function renderGrid() {
  $('grid').replaceChildren();
  cases.forEach((c, i) => {
    if (!eligible(c)) return;
    const button = document.createElement('button'); button.className = 'card';
    const title = document.createElement('h3'); title.textContent = c.id + ' · ' + c.title;
    const sub = document.createElement('small'); sub.textContent = `${c.group} · ${Math.max(c.before.length,c.after.length)} 分段`;
    const pair = document.createElement('div'); pair.className = 'thumbpair';
    for (const side of ['before','after']) {
      const first = c[side][0], element = document.createElement(first ? 'img' : 'span');
      if (first) { element.src = first.file; element.alt = c.id + ' ' + side; element.loading = 'lazy'; }
      else { element.textContent = '未采集'; element.className = 'muted'; }
      pair.append(element);
    }
    button.append(title, sub, pair); button.onclick = () => selectCase(i); $('grid').append(button);
  });
}

function download(content, filename, type) {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportNotes() {
  const lines = [`# ${meta.title} 修改意见`, '', `项目：${meta.project}；版本：${meta.revision}；日期：${meta.date}；${cases.length} 项页面 / 状态。`, ''];
  for (const c of cases) {
    const e = saved[c.id]; if (!e || (!e.note && !e.pins.length && e.status === 'pending')) continue;
    lines.push(`## ${c.id} ${c.title}`, `状态：${{pending:'未审阅',done:'已核对',change:'需要修改'}[e.status]}`, '', e.note || '（未填写文字意见）', '');
    e.pins.forEach((p,i) => lines.push(`- 标记 ${i + 1}：${c.id}-${String(p.shot + 1).padStart(2,'0')} / ${p.app} / 距左 ${p.x.toFixed(1)}%、距上 ${p.y.toFixed(1)}%`));
    lines.push('');
  }
  download('\uFEFF' + lines.join('\n'), `${meta.project}-${meta.revision}-复查意见-${meta.date}.md`, 'text/markdown;charset=utf-8');
}

function validateNotes(notes) {
  if (!notes || typeof notes !== 'object' || Array.isArray(notes)) throw Error('批注格式无效');
  const result = {};
  for (const c of cases) {
    const e = notes[c.id]; if (!e) continue;
    if (!['pending','done','change'].includes(e.status) || typeof e.note !== 'string' || !Array.isArray(e.pins)) throw Error('批注格式无效');
    const pins = e.pins.filter(p => ['before','after'].includes(p.app) && Number.isInteger(p.shot) && p.shot >= 0 && p.shot < c[p.app].length && Number.isFinite(p.x) && Number.isFinite(p.y) && p.x >= 0 && p.x <= 100 && p.y >= 0 && p.y <= 100);
    if (pins.length !== e.pins.length) throw Error('标记与当前截图不对应');
    result[c.id] = {status:hasReviewFeedback(e) ? 'change' : e.status, note:e.note, pins};
  }
  return result;
}

try { saved = validateNotes(saved); } catch (_) { saved = {}; }
$('search').oninput = () => { renderNav(); if (overview) renderGrid(); };
document.querySelectorAll('[data-filter]').forEach(button => button.onclick = () => {
  filter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
  renderNav(); if (overview) renderGrid();
});
$('prev').onclick = () => selectCase(current - 1); $('next').onclick = () => selectCase(current + 1);
$('segment').onchange = () => changeShot(+$('segment').value);
$('prevShot').onclick = () => changeShot(shot - 1); $('nextShot').onclick = () => changeShot(shot + 1);
for (const option of document.querySelectorAll('[name="reviewStatus"]')) option.onchange = () => {
  if (option.checked) { entry().status = option.value; syncStatus(); persist(); }
};
$('toggleNav').onclick = () => {
  if (window.matchMedia('(max-width: 860px)').matches) setNavigationOpen(!document.body.classList.contains('nav-open'));
  else { document.body.classList.toggle('nav-collapsed'); updateNavigationButton(); scheduleLayout(); }
};
$('navBackdrop').onclick = () => setNavigationOpen(false);
$('notesToggle').onclick = () => setNotesOpen($('reviewNotes').hidden, true);
$('closeNotes').onclick = () => { setNotesOpen(false); $('notesToggle').focus(); };
$('fullscreenBtn').onclick = toggleFullscreen;
document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) setFocusMode(false); });
$('zoom').onchange = () => setZoom($('zoom').value);
$('zoomIn').onclick = () => stepZoom(1); $('zoomOut').onclick = () => stepZoom(-1);
$('syncBtn').onclick = () => {
  scrollTogether = !scrollTogether; scrollSyncTarget = null;
  $('syncBtn').setAttribute('aria-pressed', String(scrollTogether));
  if (scrollTogether) synchronizeScroll($('pane1'), $('pane3'));
};
for (const [source, target] of [['1','3'], ['3','1']]) $('pane' + source).addEventListener('scroll', () => synchronizeScroll($('pane' + source), $('pane' + target)), {passive:true});
$('comment').oninput = () => { updateReviewNote(entry(), $('comment').value); syncStatus(); persist(); };
$('clearPins').onclick = () => { clearReviewPins(entry()); syncStatus(); persist(); renderImages(); };
$('pinBtn').onclick = () => {
  marking = !marking; $('pinBtn').setAttribute('aria-pressed', String(marking));
  if (marking && window.matchMedia('(max-width: 860px)').matches) setNotesOpen(false);
  renderImages();
};
for (const [id, enabled] of [['pairBtn',false],['overlayBtn',true]]) $(id).onclick = () => {
  overlay = enabled; renderImages(); resetScroll();
};
$('opacity').oninput = renderImages; $('overviewBtn').onclick = showOverview; $('exportBtn').onclick = exportNotes;
$('backupBtn').onclick = () => download(JSON.stringify({project:meta.project, revision:meta.revision, notes:saved}, null, 2), `${meta.project}-${meta.revision}-批注备份.json`, 'application/json');
$('importBtn').onclick = () => $('notesFile').click();
$('notesFile').onchange = async event => {
  const file = event.target.files[0]; if (!file) return;
  try {
    const incoming = JSON.parse(await file.text());
    if (incoming.project !== meta.project || incoming.revision !== meta.revision) throw Error('此备份属于其他项目或版本');
    const notes = validateNotes(incoming.notes);
    if (Object.values(saved).some(e => e.note || e.pins.length || e.status !== 'pending') && !confirm('导入会替换当前批注。建议先备份；继续导入？')) return;
    saved = notes; persist(); render(); $('saved').textContent = '批注已恢复。';
  } catch (error) { $('saved').textContent = '导入失败：' + error.message; }
  finally { event.target.value = ''; setNotesOpen(true); }
};
for (const side of ['before','after']) {
  const n = side === 'before' ? '1' : '3';
  $('imageAction' + n).onclick = event => {
    const image = $('image' + n);
    if (marking) {
      const r = image.getBoundingClientRect();
      const x = event.detail === 0 ? 50 : 100 * (event.clientX-r.left) / r.width;
      const y = event.detail === 0 ? 50 : 100 * (event.clientY-r.top) / r.height;
      entry().pins.push({app:side, shot, x, y});
      entry().status = 'change'; syncStatus(); persist(); renderImages();
      setNotesOpen(true);
    } else {
      zoomReturn = event.currentTarget; $('large').src = image.src;
      $('lightbox').classList.add('open'); $('closeLight').focus();
    }
  };
}
function closeLight() { $('lightbox').classList.remove('open'); zoomReturn?.focus(); }
$('closeLight').onclick = closeLight;
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    if ($('lightbox').classList.contains('open')) closeLight();
    else if (document.body.classList.contains('nav-open')) setNavigationOpen(false);
    else if (!$('reviewNotes').hidden) { setNotesOpen(false); $('notesToggle').focus(); }
    else if (document.body.classList.contains('focus-mode')) { setFocusMode(false); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); }
    return;
  }
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) return;
  if ($('lightbox').classList.contains('open')) return;
  if (overview) return;
  if (event.key.toLowerCase() === 'n') { event.preventDefault(); setNotesOpen($('reviewNotes').hidden, true); }
  if (event.key.toLowerCase() === 'f') { event.preventDefault(); toggleFullscreen(); }
  if (event.key === 'ArrowRight' && shot < Math.max(cases[current].before.length,cases[current].after.length)-1) { event.preventDefault(); changeShot(shot + 1); }
  if (event.key === 'ArrowLeft' && shot > 0) { event.preventDefault(); changeShot(shot - 1); }
});
$('meta').textContent = `${cases.length} 项页面 / 交互状态 · ${data.pairs} 组截图分段 · ${meta.date} · ${meta.captureNote}`;
document.querySelector('h1').title = meta.title;
$('pdfLink').hidden = !meta.pdfFile; if (meta.pdfFile) $('pdfLink').href = meta.pdfFile;
function readHash() {
  const deep = decodeURIComponent(location.hash).match(/^#(.+)-(\d+)$/);
  if (deep) {
    const index = cases.findIndex(c => c.id === deep[1]);
    if (index >= 0) { current = index; shot = Math.max(0, Number(deep[2]) - 1); }
  }
  render();
}
window.addEventListener('hashchange', readHash);
window.addEventListener('resize', scheduleLayout);
window.visualViewport?.addEventListener('resize', scheduleLayout);
const layoutObserver = new ResizeObserver(scheduleLayout);
for (const id of ['appHeader','reviewToolbar','reviewNotes','reviewMain']) layoutObserver.observe($(id));
readHash();

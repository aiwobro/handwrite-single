(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const csrf = document.body.dataset.csrf;
  function status(text, error = false) { $('status').textContent = text; $('status').classList.toggle('error', error); }
  async function api(path, data) {
    const response = await fetch('/admin/templates/' + path, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify(data)
    });
    if (!response.ok) {
      let message = `请求失败 (${response.status})`;
      try { message = (await response.json()).error || message; } catch (_) { /* HTML error */ }
      if (response.status === 413) message = '图片数据过大，请缩小图片后重新标注（请求上限24MB）。';
      if (response.status === 401 || response.status === 403) message += '；若会话过期，请先下载草稿，再刷新登录。';
      throw new Error(message);
    }
    return response;
  }
  if ($('loginForm')) {
    $('loginForm').addEventListener('submit', async event => {
      event.preventDefault();
      try { await api('login', {password: $('password').value}); location.reload(); }
      catch (error) { status(error.message, true); }
    });
    return;
  }
  const labels = Object.fromEntries([...$('field').options].map(o => [o.value, o.textContent]));
  let sides = {}, zoom = 1, mode = 'draw', forceDraw = false, action = null, space = false, dirty = false, busy = false;
  const svg = $('canvas'), viewport = $('viewport'), ns = 'http://www.w3.org/2000/svg';
  const current = () => sides[$('side').value];
  const isGrid = side => side && side.body_mode === 'grid';
  const Grid = window.TemplateGrid;
  const boxes = s => ({...(s.body ? {body: s.body} : {}), ...s.meta});
  const selected = () => current() && boxes(current())[$('field').value];
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
  function changed() { dirty = true; }
  function putBox(key, box) { if (key === 'body') current().body = box; else current().meta[key] = box; }
  function setMode(value) {
    mode = value;
    forceDraw = false;
    $('modeHint').textContent = value === 'pan' ? '拖动画布平移。点击“框选 / 重画”恢复标注。' : '拖动空白处新建框；拖动已有框移动，拖动四角缩放。';
    svg.style.cursor = value === 'pan' ? 'grab' : 'crosshair';
  }
  function syncControls() {
    const s = current(), box = selected();
    for (const [id, key] of [['boxX', 'x'], ['boxY', 'y'], ['boxW', 'width'], ['boxH', 'height']]) {
      $(id).value = box ? box[key] : ''; $(id).disabled = !box;
    }
    $('fontSize').value = s ? s.font_size : 50;
    const grid = s ? isGrid(s) : true;
    $('bodyMode').value = grid ? 'grid' : 'legacy';
    $('lineSpacing').disabled = grid;
    $('lineSpacing').value = s ? s.line_spacing : 71;
    $('bodyAlignment').disabled = !grid;
    $('bodyAlignment').value = s ? s.body_alignment || 'bottom' : 'bottom';
    $('bottomGap').disabled = !grid || $('bodyAlignment').value === 'top';
    $('bottomGap').value = s ? s.bottom_gap ?? 2 : 2;
    $('rowsLabel').textContent = grid ? '纸张行数' : '按行数均分（旧算法）';
    $('layoutHint').classList.remove('invalid');
    if (grid) {
      $('rows').value = s ? s.row_count : 10;
      $('layoutHint').textContent = '从第一行上边线框到最后一行下边线。行距＝区域高度÷行数；显示值保留3位小数，实际绘制不累计取整误差。';
      if (s && s.body) {
        try {
          $('lineSpacing').value = Grid.geometry(s).spacing.toFixed(3);
          Grid.validate(s);
        } catch (error) { $('layoutHint').textContent = error.message; $('layoutHint').classList.add('invalid'); }
      }
    } else {
      if (s && s.body) $('rows').value = Math.max(1, Math.floor((s.body.height - s.font_size) / s.line_spacing) + 1);
      $('layoutHint').textContent = '兼容旧草稿：正文框顶部是第一行文字行框顶部，虚线不是纸上横线。切换到“按纸张格线排版”后，请确认矩形覆盖完整格子，并设置纸张实际行数。';
    }
    $('imageInfo').textContent = s ? `${s.width} × ${s.height} 像素 · 当前面` : '未上传图片';
    for (const option of $('field').options) option.disabled = $('side').value === 'back' && option.value !== 'body';
  }
  function element(tag, attributes) {
    const node = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    return node;
  }
  function paint() {
    const s = current(), overlay = $('overlays'); overlay.replaceChildren();
    $('empty').hidden = !!s; svg.style.display = s ? 'block' : 'none';
    if (!s) { syncControls(); return; }
    svg.setAttribute('viewBox', `0 0 ${s.width} ${s.height}`);
    svg.style.width = `${s.width * zoom}px`; svg.style.height = `${s.height * zoom}px`;
    if ($('paperImage').getAttribute('href') !== s.image) $('paperImage').setAttribute('href', s.image);
    $('paperImage').setAttribute('width', s.width); $('paperImage').setAttribute('height', s.height);
    $('zoomValue').textContent = `${Math.round(zoom * 100)}%`;
    const entries = Object.entries(boxes(s));
    // 正文先画，当前选中的小框最后画，便于拖动重叠框。
    entries.sort(([a], [b]) => a === 'body' ? -1 : b === 'body' ? 1 : (a === $('field').value ? 1 : 0) - (b === $('field').value ? 1 : 0));
    for (const [key, box] of entries) {
      const active = key === $('field').value;
      const rect = element('rect', {...box, class: `box ${key === 'body' ? 'body' : ''} ${active ? 'selected' : ''}`, 'data-field': key});
      overlay.append(rect);
      if (key === 'body') {
        if (isGrid(s)) {
          try {
            const geometry = Grid.geometry(s);
            for (const [values, className] of [[geometry.boundaries, 'grid-line'], [geometry.anchors, 'baseline']]) {
              for (const y of values) overlay.append(element('line', {x1: box.x, x2: box.x + box.width, y1: y, y2: y, class: className}));
            }
          } catch (_) { /* 非法草稿参数由侧栏提示；仍允许修改矩形。 */ }
        } else {
          for (let y = box.y, n = 0; y + s.font_size <= box.y + box.height && n < 1000; y += s.line_spacing, n++) {
            overlay.append(element('line', {x1: box.x, x2: box.x + box.width, y1: y, y2: y}));
          }
        }
      }
      const text = element('text', {x: box.x + 4 / zoom, y: Math.max(15 / zoom, box.y - 4 / zoom), 'font-size': 13 / zoom});
      text.textContent = labels[key]; overlay.append(text);
      if (active) {
        for (const corner of ['nw', 'ne', 'sw', 'se']) {
          const x = box.x + (corner.includes('e') ? box.width : 0), y = box.y + (corner.includes('s') ? box.height : 0);
          const handle = element('rect', {x: x - 5 / zoom, y: y - 5 / zoom, width: 10 / zoom, height: 10 / zoom,
            class: 'handle', 'data-field': key, 'data-corner': corner, style: `cursor:${corner}-resize`});
          overlay.append(handle);
        }
      }
    }
    syncControls();
  }
  function fit() {
    const s = current(); if (!s) return;
    zoom = clamp((viewport.clientWidth - 24) / s.width, .05, 3); paint();
  }
  function changeZoom(factor) {
    const old = zoom; zoom = clamp(zoom * factor, .05, 3);
    const x = (viewport.scrollLeft + viewport.clientWidth / 2) / old;
    const y = (viewport.scrollTop + viewport.clientHeight / 2) / old;
    paint(); viewport.scrollLeft = x * zoom - viewport.clientWidth / 2; viewport.scrollTop = y * zoom - viewport.clientHeight / 2;
  }
  function point(event) {
    const p = svg.createSVGPoint(); p.x = event.clientX; p.y = event.clientY;
    const v = p.matrixTransform(svg.getScreenCTM().inverse()), s = current();
    return {x: clamp(Math.round(v.x), 0, s.width), y: clamp(Math.round(v.y), 0, s.height)};
  }
  viewport.addEventListener('pointerdown', event => {
    if (!current() || event.button !== 0) return;
    viewport.focus();
    if (mode === 'pan' || space) {
      action = {kind: 'pan', x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop};
    } else {
      const p = point(event), hit = event.target.dataset.field;
      if (hit && !forceDraw && !(hit === 'body' && $('field').value !== 'body' && !selected())) {
        $('field').value = hit;
        action = {kind: event.target.dataset.corner ? 'resize' : 'move', corner: event.target.dataset.corner,
          start: p, original: {...selected()}, key: hit};
      } else {
        const key = $('field').value;
        if ($('side').value === 'back' && key !== 'body') return;
        action = {kind: 'draw', start: p, key};
      }
    }
    viewport.setPointerCapture(event.pointerId); event.preventDefault(); paint();
  });
  viewport.addEventListener('pointermove', event => {
    if (!action) return;
    if (action.kind === 'pan') {
      viewport.scrollLeft = action.left - event.clientX + action.x;
      viewport.scrollTop = action.top - event.clientY + action.y; return;
    }
    const s = current(), p = point(event), a = action;
    let box;
    if (a.kind === 'move') {
      box = {...a.original, x: clamp(a.original.x + p.x - a.start.x, 0, s.width - a.original.width),
        y: clamp(a.original.y + p.y - a.start.y, 0, s.height - a.original.height)};
    } else {
      const origin = a.kind === 'draw' ? a.start : {
        x: a.original.x + (a.corner.includes('w') ? a.original.width : 0),
        y: a.original.y + (a.corner.includes('n') ? a.original.height : 0)
      };
      box = {x: Math.min(origin.x, p.x), y: Math.min(origin.y, p.y), width: Math.abs(origin.x - p.x), height: Math.abs(origin.y - p.y)};
      if (box.width < 1 || box.height < 1) return;
    }
    putBox(a.key, box); changed(); paint();
  });
  function stopAction() { if (action) forceDraw = false; action = null; }
  viewport.addEventListener('pointerup', stopAction); viewport.addEventListener('pointercancel', stopAction);
  viewport.addEventListener('lostpointercapture', stopAction);
  viewport.addEventListener('wheel', event => {
    if (event.ctrlKey) { event.preventDefault(); changeZoom(event.deltaY < 0 ? 1.12 : 1 / 1.12); }
  }, {passive: false});
  viewport.addEventListener('keydown', event => {
    if (event.code === 'Space') { space = true; event.preventDefault(); return; }
    const box = selected(), s = current(); if (!box) return;
    const steps = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]};
    if (steps[event.key]) {
      event.preventDefault(); const [dx, dy] = steps[event.key], step = event.shiftKey ? 10 : 1;
      box.x = clamp(box.x + dx * step, 0, s.width - box.width); box.y = clamp(box.y + dy * step, 0, s.height - box.height);
      changed(); paint();
    }
  });
  document.addEventListener('keyup', event => { if (event.code === 'Space') space = false; });
  window.addEventListener('blur', () => { space = false; stopAction(); });
  function imageFromURL(url) {
    return new Promise((resolve, reject) => { const image = new Image(); image.onload = () => resolve(image); image.onerror = () => reject(new Error('无法读取图片。')); image.src = url; });
  }
  function readFile(file) {
    return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('无法读取文件。')); reader.readAsDataURL(file); });
  }
  $('imageFile').addEventListener('change', async event => {
    const file = event.target.files[0], side = $('side').value; if (!file) return;
    try {
      if (!['image/png', 'image/jpeg'].includes(file.type) || file.size > 16 * 1024 * 1024) throw new Error('请使用16MB以内的 PNG / JPEG。');
      if (sides[side] && !confirm('替换图片会清除当前面的标注，是否继续？')) return;
      const image = await imageFromURL(await readFile(file));
      if (image.naturalWidth * image.naturalHeight > 24000000) throw new Error('图片超过2400万像素，请先缩小。');
      // 统一 EXIF 方向，并导出无方向元数据的像素图，前后端坐标保持一致。
      const canvas = document.createElement('canvas'); canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
      const context = canvas.getContext('2d'); context.fillStyle = '#fff'; context.fillRect(0, 0, canvas.width, canvas.height); context.drawImage(image, 0, 0);
      const size = Math.max(8, Math.min(500, Math.round(canvas.width / 25)));
      sides[side] = {image: canvas.toDataURL('image/png'), width: canvas.width, height: canvas.height, meta: {}, body: null,
        font_size: size, line_spacing: Math.round(size * 1.4), body_mode: 'grid', row_count: 10, body_alignment: 'bottom', bottom_gap: 2};
      changed(); fit(); status('图片已加载。请框选正文区域及需要填写的字段。');
    } catch (error) { status(error.message, true); }
    finally { event.target.value = ''; }
  });
  $('side').addEventListener('change', () => { $('field').value = 'body'; setMode('draw'); paint(); fit(); });
  $('field').addEventListener('change', () => { setMode('draw'); forceDraw = !selected(); paint(); });
  $('draw').onclick = () => { setMode('draw'); forceDraw = true; $('modeHint').textContent = '下一次拖动将重画当前字段的框；完成后可直接拖动、缩放。'; }; $('pan').onclick = () => setMode('pan');
  $('deleteBox').onclick = () => { if (!current()) return; if ($('field').value === 'body') current().body = null; else delete current().meta[$('field').value]; changed(); paint(); };
  $('removeBack').onclick = () => { if (sides.back && confirm('清除背面图片和标注，改为重复正面背景？')) { delete sides.back; changed(); paint(); } };
  $('zoomIn').onclick = () => changeZoom(1.2); $('zoomOut').onclick = () => changeZoom(1 / 1.2); $('fit').onclick = fit;
  for (const [id, key] of [['boxX', 'x'], ['boxY', 'y'], ['boxW', 'width'], ['boxH', 'height']]) {
    $(id).addEventListener('change', () => {
      const box = selected(), s = current(); if (!box) return;
      const value = Number($(id).value); if (!Number.isFinite(value)) return;
      box[key] = Math.round(value);
      box.x = clamp(box.x, 0, s.width - 1); box.y = clamp(box.y, 0, s.height - 1);
      box.width = clamp(box.width, 1, s.width - box.x); box.height = clamp(box.height, 1, s.height - box.y);
      changed(); paint();
    });
  }
  for (const [id, key] of [['fontSize', 'font_size'], ['lineSpacing', 'line_spacing']]) {
    $(id).addEventListener('change', () => {
      const s = current(); if (!s) return;
      s[key] = clamp(Math.round(Number($(id).value)) || 8, 8, key === 'font_size' ? 500 : s.height);
      if (!isGrid(s)) s.line_spacing = Math.max(s.line_spacing, s.font_size);
      changed(); paint();
    });
  }
  $('bodyMode').addEventListener('change', () => {
    const s = current(); if (!s) return;
    s.body_mode = $('bodyMode').value;
    if (isGrid(s)) {
      s.row_count = s.row_count || (s.body ? clamp(Math.round(s.body.height / s.line_spacing), 1, 500) : 10);
      s.body_alignment = s.body_alignment || 'bottom'; s.bottom_gap = s.bottom_gap ?? 2;
    } else { s.line_spacing = Math.max(s.font_size, Math.round(s.line_spacing)); }
    changed(); paint();
  });
  for (const [id, key] of [['bodyAlignment', 'body_alignment'], ['bottomGap', 'bottom_gap']]) {
    $(id).addEventListener('change', () => {
      const s = current(); if (!s || !isGrid(s)) return;
      s[key] = id === 'bodyAlignment' ? $(id).value : Number($(id).value);
      changed(); paint();
    });
  }
  $('rows').addEventListener('change', () => {
    const s = current(); if (!s || !isGrid(s)) return;
    s.row_count = Number($('rows').value); changed(); paint();
  });
  $('applyRows').onclick = () => {
    const s = current(); if (!s || !s.body) { status('请先框选正文区域。', true); return; }
    if (isGrid(s)) {
      s.row_count = Number($('rows').value); changed(); paint();
      try { Grid.validate(s); status('行数已应用；请将蓝色边线与纸上格线对齐，再试写。'); }
      catch (error) { status(error.message, true); }
      return;
    }
    const rows = clamp(Math.round(Number($('rows').value)) || 1, 1, 500);
    const spacing = rows === 1 ? Math.max(s.font_size, s.body.height) : Math.floor((s.body.height - s.font_size) / (rows - 1));
    if (spacing < s.font_size || s.body.height < s.font_size) { status('区域不足以容纳这些行，请减少行数、减小字号或加大区域。', true); return; }
    s.line_spacing = spacing; changed(); paint();
  };
  function payload(validate = true) {
    const result = {id: $('templateId').value.trim(), display_name: $('templateName').value.trim(), sides};
    if (validate) {
      if (!/^[a-z][a-z0-9_-]{0,47}$/.test(result.id)) throw new Error('请填写合法模板 ID：小写字母开头，最多48位，仅含小写字母、数字、_、-。');
      if (!result.display_name) throw new Error('请填写模板显示名称。');
      if (!sides.front) throw new Error('请上传正面图片。');
      for (const [side, s] of Object.entries(sides)) {
        if (!s.body) throw new Error(`请框选${side === 'front' ? '正面' : '背面'}正文区域。`);
        if (s.body.height < s.font_size) throw new Error('正文区域高度不能小于字号。');
        if (isGrid(s)) Grid.validate(s);
      }
    }
    return result;
  }
  function download(blob, name) {
    const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = name;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
  $('templateId').oninput = changed; $('templateName').oninput = changed;
  $('draft').onclick = () => { download(new Blob([JSON.stringify(payload(false))], {type: 'application/json'}), 'editor.json'); dirty = false; status('标注草稿已下载。'); };
  $('importDraft').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      if (file.size > 24 * 1024 * 1024) throw new Error('草稿文件超过24MB。');
      const data = JSON.parse(await file.text()), imported = {};
      if (!data.sides || typeof data.sides !== 'object') throw new Error('无效草稿。');
      for (const side of ['front', 'back']) {
        const raw = data.sides[side]; if (!raw) continue;
        if (typeof raw.image !== 'string' || !/^data:image\/(png|jpeg);base64,/.test(raw.image)) throw new Error('草稿图片无效。');
        const img = await imageFromURL(raw.image), width = img.naturalWidth, height = img.naturalHeight;
        if (width * height > 24000000) throw new Error('草稿图片过大。');
        const validBox = box => {
          if (!box || !['x', 'y', 'width', 'height'].every(k => Number.isInteger(box[k])) || box.x < 0 || box.y < 0 || box.width < 1 || box.height < 1 || box.x + box.width > width || box.y + box.height > height) throw new Error('草稿存在越界或无效标注。');
          return {x: box.x, y: box.y, width: box.width, height: box.height};
        };
        const meta = {};
        if (side === 'front') for (const key of Object.keys(labels)) { if (key !== 'body' && raw.meta && raw.meta[key]) meta[key] = validBox(raw.meta[key]); }
        const font = raw.font_size, mode = raw.body_mode ?? 'legacy';
        if (!['legacy', 'grid'].includes(mode)) throw new Error('草稿正文模式无效。');
        const spacing = raw.line_spacing;
        if (!Number.isInteger(font) || font < 8 || font > 500 || !Number.isFinite(spacing) || spacing <= 0 || (mode === 'legacy' && (!Number.isInteger(spacing) || spacing < font || spacing > height))) throw new Error('草稿字号或行距无效。');
        const normalized = {image: raw.image, width, height, meta, body: raw.body ? validBox(raw.body) : null,
          font_size: font, line_spacing: spacing, body_mode: mode};
        if (mode === 'grid') {
          Object.assign(normalized, {row_count: raw.row_count, body_alignment: raw.body_alignment ?? 'bottom', bottom_gap: raw.bottom_gap ?? 2});
          // 草稿可暂时字号不合适，允许导入后修正；几何选项本身必须合法。
          Grid.geometry({...normalized, body: normalized.body || {y: 0, height: 1}});
        }
        imported[side] = normalized;
      }
      if (!Object.keys(imported).length) throw new Error('草稿没有图片。');
      if (dirty && !confirm('导入将替换当前未保存标注，是否继续？')) return;
      sides = imported; $('templateId').value = typeof data.id === 'string' ? data.id.slice(0, 48) : '';
      $('templateName').value = typeof data.display_name === 'string' ? data.display_name.slice(0, 80) : '';
      $('side').value = imported.front ? 'front' : 'back'; $('field').value = 'body'; changed(); fit(); status('草稿已导入。');
    } catch (error) { status('导入失败：' + error.message, true); }
    finally { event.target.value = ''; }
  });
  let previewURL;
  async function execute(kind) {
    if (busy) return;
    try {
      const data = payload();
      if (kind === 'save' && !confirm('将背景图及标注保存到项目，并向纸张注册表新增模板；不会覆盖已有模板。确认保存？')) return;
      busy = true; for (const id of ['preview', 'export', 'save']) $(id).disabled = true;
      status('正在处理，请稍候……');
      const snapshot = JSON.stringify(data);
      const response = await api(kind === 'preview' ? `preview?side=${$('side').value}` : kind, data);
      if (kind === 'preview') {
        if (previewURL) URL.revokeObjectURL(previewURL);
        previewURL = URL.createObjectURL(await response.blob()); $('previewImage').src = previewURL; $('previewDialog').showModal();
        status('试写完成，请检查实际文字位置。');
      } else if (kind === 'export') {
        download(await response.blob(), data.id + '.zip'); if (snapshot === JSON.stringify(payload(false))) dirty = false; status('模板包已导出。');
      } else {
        status((await response.json()).message); if (snapshot === JSON.stringify(payload(false))) dirty = false;
      }
    } catch (error) { status(error.message, true); }
    finally { busy = false; for (const id of ['preview', 'export', 'save']) $(id).disabled = false; }
  }
  for (const kind of ['preview', 'export', 'save']) $(kind).onclick = () => execute(kind);
  $('closePreview').onclick = () => $('previewDialog').close();
  $('logout').onclick = async () => {
    if (dirty && !confirm('有未保存标注，请先下载草稿。仍然退出？')) return;
    try { await api('logout', {}); dirty = false; location.reload(); } catch (error) { status(error.message, true); }
  };
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  paint();
})();

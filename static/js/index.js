(function () {
  'use strict';

  /* ===== Utilities ===== */
  const prefersReducedMotion =
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function $(id) {
    return document.getElementById(id);
  }

  function $$(selector, scope) {
    return Array.from((scope || document).querySelectorAll(selector));
  }

  /* ===== Scroll Reveal ===== */
  function bindRevealAnimations() {
    const nodes = $$('.reveal-on-scroll');
    if (!nodes.length) return;

    nodes.forEach((node, index) => {
      node.style.setProperty('--reveal-delay', `${Math.min(index, 10) * 80}ms`);
    });

    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
      nodes.forEach((node) => node.classList.add('is-visible'));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        });
      },
      { root: null, threshold: 0.12, rootMargin: '0px 0px -6% 0px' }
    );

    nodes.forEach((node) => observer.observe(node));
  }

  /* ===== Card Stagger ===== */
  function applyCardStagger(scope = document) {
    const cards = $$('.image-card', scope);
    cards.forEach((card, index) => {
      card.style.setProperty('--stagger-index', String(index));
    });
  }

  /* ===== Paper Preview ===== */
  const paperTypeSelect = $('select[name="paper_type"]');
  const paperPreviewGrid = $('paperPreviewGrid');
  const paperPreviewEmpty = $('paperPreviewEmpty');
  const heroPaperPrimary = $('heroPaperPrimary');
  const heroPaperSecondary = $('heroPaperSecondary');
  const heroPaperType = $('heroPaperType');

  const pageData = window.__INDEX_PAGE_DATA || {};
  const paperPreviewMap =
    pageData.paperPreviewMap && typeof pageData.paperPreviewMap === 'object'
      ? pageData.paperPreviewMap
      : {};
  const defaultPaperPreviews = Array.isArray(pageData.defaultPaperPreviews)
    ? pageData.defaultPaperPreviews
    : [];
  const selectedPaperType =
    typeof pageData.selectedPaperType === 'string'
      ? pageData.selectedPaperType
      : '';

  function getSelectedPaperType() {
    return paperTypeSelect && paperTypeSelect.value
      ? paperTypeSelect.value
      : selectedPaperType;
  }

  function getPaperPreviewItems(paperType) {
    const selected = paperPreviewMap[paperType];
    if (Array.isArray(selected) && selected.length) return selected;
    if (Array.isArray(defaultPaperPreviews) && defaultPaperPreviews.length)
      return defaultPaperPreviews;
    return [];
  }

  function setHeroPaperImage(imageNode, src, altText) {
    if (!imageNode) return;
    if (src) {
      imageNode.src = src;
      imageNode.alt = altText;
      imageNode.classList.remove('is-empty');
    } else {
      imageNode.removeAttribute('src');
      imageNode.alt = '暂无纸张预览';
      imageNode.classList.add('is-empty');
    }
  }

  function updateHeroPreview(items, paperType) {
    if (heroPaperType) {
      heroPaperType.textContent = paperType || 'default';
    }
    const primary = items[0] && items[0].url ? items[0].url : '';
    const secondary =
      items[1] && items[1].url ? items[1].url : primary;
    setHeroPaperImage(heroPaperPrimary, primary, '纸张正面预览');
    setHeroPaperImage(heroPaperSecondary, secondary, '纸张背面预览');
  }

  function buildPaperPreviewCard(item, index) {
    const card = document.createElement('div');
    card.className = 'image-card';

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'thumb-btn';
    button.setAttribute('data-src', item.url || '');
    button.setAttribute('aria-label', `查看纸张${item.label || index + 1}大图`);

    const image = document.createElement('img');
    image.className = 'thumb-img';
    image.src = item.url || '';
    image.alt = `纸张${item.label || index + 1}预览`;
    image.loading = 'lazy';
    button.appendChild(image);

    const note = document.createElement('p');
    note.className = 'thumb-note';
    note.textContent = `${item.label || `第${index + 1}页`}（点击放大）`;

    card.appendChild(button);
    card.appendChild(note);
    return card;
  }

  function renderPaperPreview() {
    const type = getSelectedPaperType();
    const items = getPaperPreviewItems(type);
    updateHeroPreview(items, type);

    if (!paperPreviewGrid || !paperPreviewEmpty) return;

    paperPreviewGrid.textContent = '';

    if (!items.length) {
      paperPreviewGrid.hidden = true;
      paperPreviewEmpty.hidden = false;
      return;
    }

    items.forEach((item, index) => {
      if (!item || !item.url) return;
      paperPreviewGrid.appendChild(buildPaperPreviewCard(item, index));
    });

    const hasCards = paperPreviewGrid.childElementCount > 0;
    paperPreviewGrid.hidden = !hasCards;
    paperPreviewEmpty.hidden = hasCards;
    applyCardStagger(paperPreviewGrid);
  }

  if (paperTypeSelect) {
    paperTypeSelect.addEventListener('change', renderPaperPreview);
  }
  renderPaperPreview();

  /* ===== Form Submission / Loading ===== */
  const generateForm = $('generateForm');
  const generateBtn = $('generateBtn');
  const generationPreview = $('generationPreview');
  const paperPreviewPanel = $('paperPreviewPanel');
  const generatedResultPanel = $('generatedResultPanel');
  const loadingFill = $('loadingFill');
  const loadingPercent = $('loadingPercent');

  if (generateForm && generationPreview && loadingFill && loadingPercent) {
    let progressValue = 0;
    let progressTimer = null;

    function tickProgress() {
      const cap = 94;
      if (progressValue >= cap) return;
      const remaining = cap - progressValue;
      const step = Math.max(1, Math.ceil(remaining * (0.07 + Math.random() * 0.09)));
      progressValue = Math.min(cap, progressValue + step);
      loadingFill.style.width = `${progressValue}%`;
      loadingPercent.textContent = `${progressValue}%`;
    }

    generateForm.addEventListener('submit', () => {
      progressValue = 4;
      loadingFill.style.width = `${progressValue}%`;
      loadingPercent.textContent = `${progressValue}%`;

      if (paperPreviewPanel) paperPreviewPanel.hidden = true;
      if (generatedResultPanel) generatedResultPanel.hidden = true;
      generationPreview.classList.add('show');
      generationPreview.setAttribute('aria-hidden', 'false');

      if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.textContent = '生成中…';
      }

      if (progressTimer) clearInterval(progressTimer);
      progressTimer = setInterval(tickProgress, 380);
    });
  }

  /* ===== Lightbox ===== */
  const lightbox = $('lightbox');
  const rightPanel = $('rightPanel');
  const lightboxImg = $('lightboxImg');
  const closeBtn = $('lightboxClose');
  const prevBtn = $('lightboxPrev');
  const nextBtn = $('lightboxNext');
  const downloadBtn = $('lightboxDownload');
  const lightboxStage = $('lightboxStage');
  const zoomOutBtn = $('zoomOutBtn');
  const zoomInBtn = $('zoomInBtn');
  const zoomResetBtn = $('zoomResetBtn');
  const zoomLevelText = $('zoomLevelText');
  const saveAllBtn = $('saveAllBtn');

  let imageItems = [];
  let currentIndex = 0;
  let zoomLevel = 1;
  const ZOOM_MIN = 0.5;
  const ZOOM_MAX = 3.5;
  const ZOOM_STEP = 0.25;

  function collectImageItems() {
    const scope = rightPanel || document;
    const buttons = $$('.thumb-btn', scope);
    imageItems = buttons
      .map((btn) => {
        const img = btn.querySelector('img');
        return {
          src: btn.getAttribute('data-src') || '',
          alt: img ? img.alt : '大图预览',
        };
      })
      .filter((item) => item.src);
  }

  function updateNavVisibility() {
    const visible = imageItems.length > 1;
    if (prevBtn) prevBtn.style.display = visible ? 'flex' : 'none';
    if (nextBtn) nextBtn.style.display = visible ? 'flex' : 'none';
  }

  function updateZoomView() {
    if (!lightboxImg) return;
    lightboxImg.style.transform = `scale(${zoomLevel})`;
    if (zoomLevelText)
      zoomLevelText.textContent = `${Math.round(zoomLevel * 100)}%`;
    if (zoomOutBtn) zoomOutBtn.disabled = zoomLevel <= ZOOM_MIN + 0.001;
    if (zoomInBtn) zoomInBtn.disabled = zoomLevel >= ZOOM_MAX - 0.001;
  }

  function setZoom(nextZoom) {
    const limited = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, nextZoom));
    zoomLevel = Math.round(limited * 100) / 100;
    updateZoomView();
  }

  function resetZoom() {
    zoomLevel = 1;
    if (lightboxStage) {
      lightboxStage.scrollTop = 0;
      lightboxStage.scrollLeft = 0;
    }
    updateZoomView();
  }

  function getFileName(src, fallbackName) {
    if (!src) return fallbackName;
    const raw = src.split('?')[0].split('#')[0];
    const name = raw.substring(raw.lastIndexOf('/') + 1);
    return name || fallbackName;
  }

  function renderLightbox(index) {
    if (!lightboxImg || !downloadBtn || !imageItems.length) return;

    currentIndex = (index + imageItems.length) % imageItems.length;
    const item = imageItems[currentIndex];
    const fallbackName = `page_${currentIndex + 1}.jpg`;

    lightboxImg.src = item.src;
    lightboxImg.alt = item.alt;
    downloadBtn.href = item.src;
    downloadBtn.download = getFileName(item.src, fallbackName);
    resetZoom();

    // Update aria label for screen readers
    lightbox.setAttribute('aria-label', `查看第 ${currentIndex + 1} 张图，共 ${imageItems.length} 张`);
  }

  function openLightbox(index) {
    if (!lightbox) return;

    collectImageItems();
    if (!imageItems.length) return;

    updateNavVisibility();
    renderLightbox(index);
    lightbox.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    if (!lightbox || !lightboxImg) return;
    lightbox.classList.remove('show');
    document.body.style.overflow = '';
    resetZoom();
    lightboxImg.src = '';
  }

  function downloadBySrc(src, fallbackName) {
    if (!src) return;
    const link = document.createElement('a');
    link.href = src;
    link.download = getFileName(src, fallbackName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  /* Lightbox click delegation */
  document.addEventListener('click', (event) => {
    const thumbBtn = event.target.closest('.thumb-btn');
    if (!thumbBtn) return;

    if (rightPanel && !thumbBtn.closest('#rightPanel')) return;

    const scope = rightPanel || document;
    const buttons = $$('.thumb-btn', scope);
    const index = buttons.indexOf(thumbBtn);
    if (index < 0) return;

    openLightbox(index);
  });

  /* Lightbox navigation */
  if (prevBtn) {
    prevBtn.addEventListener('click', () => renderLightbox(currentIndex - 1));
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => renderLightbox(currentIndex + 1));
  }

  /* Zoom controls */
  if (zoomOutBtn) {
    zoomOutBtn.addEventListener('click', () => setZoom(zoomLevel - ZOOM_STEP));
  }

  if (zoomInBtn) {
    zoomInBtn.addEventListener('click', () => setZoom(zoomLevel + ZOOM_STEP));
  }

  if (zoomResetBtn) {
    zoomResetBtn.addEventListener('click', resetZoom);
  }

  /* Save all */
  if (saveAllBtn) {
    saveAllBtn.addEventListener('click', () => {
      collectImageItems();
      imageItems.forEach((item, index) => {
        setTimeout(() => {
          downloadBySrc(item.src, `page_${index + 1}.jpg`);
        }, index * 200);
      });
    });
  }

  /* Close button */
  if (closeBtn) {
    closeBtn.addEventListener('click', closeLightbox);
  }

  /* Click outside to close */
  if (lightbox) {
    lightbox.addEventListener('click', (event) => {
      if (event.target === lightbox) closeLightbox();
    });
  }

  /* Keyboard navigation */
  document.addEventListener('keydown', (event) => {
    if (!lightbox || !lightbox.classList.contains('show')) return;

    switch (event.key) {
      case 'Escape':
        event.preventDefault();
        closeLightbox();
        break;
      case 'ArrowLeft':
        event.preventDefault();
        renderLightbox(currentIndex - 1);
        break;
      case 'ArrowRight':
        event.preventDefault();
        renderLightbox(currentIndex + 1);
        break;
      case '+':
      case '=':
        event.preventDefault();
        setZoom(zoomLevel + ZOOM_STEP);
        break;
      case '-':
      case '_':
        event.preventDefault();
        setZoom(zoomLevel - ZOOM_STEP);
        break;
      case '0':
        event.preventDefault();
        resetZoom();
        break;
    }
  });

  /* ===== Touch Swipe for Lightbox ===== */
  let touchStartX = 0;
  let touchStartY = 0;

  if (lightboxStage) {
    lightboxStage.addEventListener('touchstart', (e) => {
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
    }, { passive: true });

    lightboxStage.addEventListener('touchend', (e) => {
      const deltaX = e.changedTouches[0].clientX - touchStartX;
      const deltaY = e.changedTouches[0].clientY - touchStartY;

      // Only trigger swipe if horizontal movement is dominant
      if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
        if (deltaX < 0) {
          renderLightbox(currentIndex + 1);
        } else {
          renderLightbox(currentIndex - 1);
        }
      }
    }, { passive: true });
  }

  /* ===== Init ===== */
  collectImageItems();
  updateNavVisibility();
  updateZoomView();
  applyCardStagger();
  bindRevealAnimations();
})();

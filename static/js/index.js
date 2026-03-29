(function () {
  const root = document.documentElement;
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const coarsePointer = window.matchMedia("(pointer: coarse)").matches;

  function bindAmbientPointerGlow() {
    if (prefersReducedMotion || coarsePointer) {
      return;
    }

    let rafId = 0;
    let pointerX = 78;
    let pointerY = 12;

    function flush() {
      root.style.setProperty("--pointer-x", `${pointerX.toFixed(2)}%`);
      root.style.setProperty("--pointer-y", `${pointerY.toFixed(2)}%`);
      rafId = 0;
    }

    window.addEventListener(
      "pointermove",
      (event) => {
        if (event.pointerType === "touch") {
          return;
        }
        pointerX = (event.clientX / window.innerWidth) * 100;
        pointerY = (event.clientY / window.innerHeight) * 100;
        if (!rafId) {
          rafId = window.requestAnimationFrame(flush);
        }
      },
      { passive: true }
    );
  }

  function attachTilt(node) {
    if (!node || coarsePointer || prefersReducedMotion || node.dataset.tiltBound === "1") {
      return;
    }

    node.dataset.tiltBound = "1";
    const maxTilt = node.classList.contains("panel") ? 3.2 : 5.4;
    const easing = 0.18;
    let rafId = 0;
    let targetX = 0;
    let targetY = 0;
    let currentX = 0;
    let currentY = 0;

    function render() {
      currentX += (targetX - currentX) * easing;
      currentY += (targetY - currentY) * easing;
      node.style.setProperty("--tilt-x", `${currentX.toFixed(2)}deg`);
      node.style.setProperty("--tilt-y", `${currentY.toFixed(2)}deg`);

      const moving = Math.abs(targetX - currentX) > 0.02 || Math.abs(targetY - currentY) > 0.02;
      if (moving) {
        rafId = window.requestAnimationFrame(render);
      } else {
        rafId = 0;
      }
    }

    function schedule() {
      if (!rafId) {
        rafId = window.requestAnimationFrame(render);
      }
    }

    node.addEventListener("pointermove", (event) => {
      if (event.pointerType === "touch") {
        return;
      }

      const rect = node.getBoundingClientRect();
      if (!rect.width || !rect.height) {
        return;
      }

      const relativeX = (event.clientX - rect.left) / rect.width;
      const relativeY = (event.clientY - rect.top) / rect.height;
      targetX = (0.5 - relativeY) * maxTilt * 2;
      targetY = (relativeX - 0.5) * maxTilt * 2;
      schedule();
    });

    function resetTilt() {
      targetX = 0;
      targetY = 0;
      schedule();
    }

    node.addEventListener("pointerleave", resetTilt);
    node.addEventListener("pointercancel", resetTilt);
  }

  function bindTiltEffects(scope = document) {
    if (coarsePointer || prefersReducedMotion) {
      return;
    }

    const targets = scope.querySelectorAll(".panel, .image-card");
    targets.forEach((item) => attachTilt(item));
  }

  function applyCardStagger(scope = document) {
    const cards = scope.querySelectorAll(".image-card");
    cards.forEach((card, index) => {
      card.style.setProperty("--stagger-index", String(index));
    });
  }

  function bindRippleEffects() {
    if (prefersReducedMotion) {
      return;
    }

    document.addEventListener("click", (event) => {
      const target = event.target.closest("button:not(.thumb-btn), .secondary-btn");
      if (!target) {
        return;
      }
      if (target.tagName === "BUTTON" && target.disabled) {
        return;
      }

      const rect = target.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height) * 1.25;
      const fallbackX = rect.left + rect.width / 2;
      const fallbackY = rect.top + rect.height / 2;
      const originX = event.clientX > 0 ? event.clientX : fallbackX;
      const originY = event.clientY > 0 ? event.clientY : fallbackY;

      const ripple = document.createElement("span");
      ripple.className = "ui-ripple";
      ripple.style.width = `${size}px`;
      ripple.style.height = `${size}px`;
      ripple.style.left = `${originX - rect.left - size / 2}px`;
      ripple.style.top = `${originY - rect.top - size / 2}px`;

      target.appendChild(ripple);
      ripple.addEventListener("animationend", () => ripple.remove());
    });
  }

  bindAmbientPointerGlow();
  bindRippleEffects();

  const generateForm = document.getElementById("generateForm");
  const generateBtn = document.getElementById("generateBtn");
  const generationPreview = document.getElementById("generationPreview");
  const paperPreviewPanel = document.getElementById("paperPreviewPanel");
  const generatedResultPanel = document.getElementById("generatedResultPanel");
  const loadingFill = document.getElementById("loadingFill");
  const loadingPercent = document.getElementById("loadingPercent");
  const paperTypeSelect = document.querySelector('select[name="paper_type"]');
  const paperPreviewGrid = document.getElementById("paperPreviewGrid");
  const paperPreviewEmpty = document.getElementById("paperPreviewEmpty");
  const pageData = window.__INDEX_PAGE_DATA || {};
  const paperPreviewMap = pageData.paperPreviewMap && typeof pageData.paperPreviewMap === "object"
    ? pageData.paperPreviewMap
    : {};
  const defaultPaperPreviews = Array.isArray(pageData.defaultPaperPreviews)
    ? pageData.defaultPaperPreviews
    : [];

  function getPaperPreviewItems() {
    const selectedType = paperTypeSelect ? paperTypeSelect.value || "" : "";
    const selectedItems = paperPreviewMap[selectedType];
    if (Array.isArray(selectedItems) && selectedItems.length) {
      return selectedItems;
    }
    if (Array.isArray(defaultPaperPreviews) && defaultPaperPreviews.length) {
      return defaultPaperPreviews;
    }
    return [];
  }

  function buildPaperPreviewCard(item, index) {
    const card = document.createElement("div");
    card.className = "image-card";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "thumb-btn";
    button.setAttribute("data-src", item.url || "");
    button.setAttribute("aria-label", `查看纸张${item.label || index + 1}大图`);

    const image = document.createElement("img");
    image.className = "thumb-img";
    image.src = item.url || "";
    image.alt = `纸张${item.label || index + 1}预览`;
    image.loading = "lazy";
    button.appendChild(image);

    const note = document.createElement("p");
    note.className = "thumb-note";
    note.textContent = `${item.label || `第${index + 1}页`}（点击放大）`;

    card.appendChild(button);
    card.appendChild(note);
    return card;
  }

  function renderPaperPreview() {
    if (!paperPreviewGrid || !paperPreviewEmpty) {
      return;
    }

    const items = getPaperPreviewItems();
    paperPreviewGrid.textContent = "";

    if (!items.length) {
      paperPreviewGrid.hidden = true;
      paperPreviewEmpty.hidden = false;
      return;
    }

    items.forEach((item, index) => {
      if (!item || !item.url) {
        return;
      }
      paperPreviewGrid.appendChild(buildPaperPreviewCard(item, index));
    });

    const hasCards = paperPreviewGrid.childElementCount > 0;
    paperPreviewGrid.hidden = !hasCards;
    paperPreviewEmpty.hidden = hasCards;

    applyCardStagger(paperPreviewGrid);
    bindTiltEffects(paperPreviewGrid);
  }

  if (paperTypeSelect) {
    paperTypeSelect.addEventListener("change", renderPaperPreview);
  }

  renderPaperPreview();

  if (generateForm && generationPreview && loadingFill && loadingPercent) {
    let progressValue = 0;
    let progressTimer = null;

    function tickProgress() {
      const cap = 94;
      if (progressValue >= cap) {
        return;
      }
      const remaining = cap - progressValue;
      const step = Math.max(1, Math.ceil(remaining * (0.08 + Math.random() * 0.08)));
      progressValue = Math.min(cap, progressValue + step);
      loadingFill.style.width = `${progressValue}%`;
      loadingPercent.textContent = `${progressValue}%`;
    }

    generateForm.addEventListener("submit", () => {
      progressValue = 6;
      loadingFill.style.width = `${progressValue}%`;
      loadingPercent.textContent = `${progressValue}%`;

      if (paperPreviewPanel) {
        paperPreviewPanel.hidden = true;
      }
      if (generatedResultPanel) {
        generatedResultPanel.hidden = true;
      }
      generationPreview.classList.add("show");
      generationPreview.setAttribute("aria-hidden", "false");
      if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.textContent = "生成中...";
      }

      if (progressTimer) {
        window.clearInterval(progressTimer);
      }
      progressTimer = window.setInterval(tickProgress, 360);
    });
  }

  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightboxImg");
  const closeBtn = document.getElementById("lightboxClose");
  const prevBtn = document.getElementById("lightboxPrev");
  const nextBtn = document.getElementById("lightboxNext");
  const downloadBtn = document.getElementById("lightboxDownload");
  const lightboxStage = document.getElementById("lightboxStage");
  const zoomOutBtn = document.getElementById("zoomOutBtn");
  const zoomInBtn = document.getElementById("zoomInBtn");
  const zoomResetBtn = document.getElementById("zoomResetBtn");
  const zoomLevelText = document.getElementById("zoomLevelText");
  const saveAllBtn = document.getElementById("saveAllBtn");
  let imageItems = [];
  let currentIndex = 0;
  let zoomLevel = 1;
  const ZOOM_MIN = 0.6;
  const ZOOM_MAX = 3;
  const ZOOM_STEP = 0.2;

  function collectImageItems() {
    const buttons = Array.from(document.querySelectorAll(".thumb-btn"));
    imageItems = buttons
      .map((btn) => {
        const img = btn.querySelector("img");
        return {
          src: btn.getAttribute("data-src") || "",
          alt: img ? img.alt : "大图预览",
        };
      })
      .filter((item) => item.src);
  }

  function updateNavVisibility() {
    const visible = imageItems.length > 1;
    if (prevBtn) {
      prevBtn.style.display = visible ? "flex" : "none";
    }
    if (nextBtn) {
      nextBtn.style.display = visible ? "flex" : "none";
    }
  }

  function updateZoomView() {
    if (!lightboxImg) {
      return;
    }
    lightboxImg.style.transform = `scale(${zoomLevel})`;
    if (zoomLevelText) {
      zoomLevelText.textContent = `${Math.round(zoomLevel * 100)}%`;
    }
    if (zoomOutBtn) {
      zoomOutBtn.disabled = zoomLevel <= ZOOM_MIN + 0.001;
    }
    if (zoomInBtn) {
      zoomInBtn.disabled = zoomLevel >= ZOOM_MAX - 0.001;
    }
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
    if (!src) {
      return fallbackName;
    }
    const raw = src.split("?")[0].split("#")[0];
    const name = raw.substring(raw.lastIndexOf("/") + 1);
    return name || fallbackName;
  }

  function renderLightbox(index) {
    if (!lightboxImg || !downloadBtn || imageItems.length === 0) {
      return;
    }

    currentIndex = (index + imageItems.length) % imageItems.length;
    const item = imageItems[currentIndex];
    const fallbackName = `page_${currentIndex + 1}.jpg`;

    lightboxImg.src = item.src;
    lightboxImg.alt = item.alt;
    downloadBtn.href = item.src;
    downloadBtn.download = getFileName(item.src, fallbackName);
    resetZoom();
  }

  function openLightbox(index) {
    if (!lightbox) {
      return;
    }

    collectImageItems();
    if (imageItems.length === 0) {
      return;
    }
    updateNavVisibility();
    renderLightbox(index);
    lightbox.classList.add("show");
  }

  function closeLightbox() {
    if (!lightbox || !lightboxImg) {
      return;
    }

    lightbox.classList.remove("show");
    resetZoom();
    lightboxImg.src = "";
  }

  function downloadBySrc(src, fallbackName) {
    if (!src) {
      return;
    }

    const link = document.createElement("a");
    link.href = src;
    link.download = getFileName(src, fallbackName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  document.addEventListener("click", (event) => {
    const thumbBtn = event.target.closest(".thumb-btn");
    if (!thumbBtn) {
      return;
    }
    const buttons = Array.from(document.querySelectorAll(".thumb-btn"));
    const index = buttons.indexOf(thumbBtn);
    if (index < 0) {
      return;
    }
    openLightbox(index);
  });

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      renderLightbox(currentIndex - 1);
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      renderLightbox(currentIndex + 1);
    });
  }

  if (zoomOutBtn) {
    zoomOutBtn.addEventListener("click", () => {
      setZoom(zoomLevel - ZOOM_STEP);
    });
  }

  if (zoomInBtn) {
    zoomInBtn.addEventListener("click", () => {
      setZoom(zoomLevel + ZOOM_STEP);
    });
  }

  if (zoomResetBtn) {
    zoomResetBtn.addEventListener("click", () => {
      resetZoom();
    });
  }

  if (saveAllBtn) {
    saveAllBtn.addEventListener("click", () => {
      collectImageItems();
      imageItems.forEach((item, index) => {
        setTimeout(() => {
          downloadBySrc(item.src, `page_${index + 1}.jpg`);
        }, index * 180);
      });
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", closeLightbox);
  }

  if (lightbox) {
    lightbox.addEventListener("click", (event) => {
      if (event.target === lightbox) {
        closeLightbox();
      }
    });
  }

  document.addEventListener("keydown", (event) => {
    if (!lightbox || !lightbox.classList.contains("show")) {
      return;
    }
    if (event.key === "Escape") {
      closeLightbox();
      return;
    }
    if (event.key === "ArrowLeft") {
      renderLightbox(currentIndex - 1);
      return;
    }
    if (event.key === "ArrowRight") {
      renderLightbox(currentIndex + 1);
      return;
    }
    if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      setZoom(zoomLevel + ZOOM_STEP);
      return;
    }
    if (event.key === "-" || event.key === "_") {
      event.preventDefault();
      setZoom(zoomLevel - ZOOM_STEP);
      return;
    }
    if (event.key === "0") {
      event.preventDefault();
      resetZoom();
    }
  });

  collectImageItems();
  updateNavVisibility();
  updateZoomView();
  applyCardStagger();
  bindTiltEffects();
})();

(function () {
  const generateForm = document.getElementById("generateForm");
  const generateBtn = document.getElementById("generateBtn");
  const generationPreview = document.getElementById("generationPreview");
  const loadingFill = document.getElementById("loadingFill");
  const loadingPercent = document.getElementById("loadingPercent");

  const paperTypeSelect = document.getElementById("paperTypeSelect");
  const paperPreviewPanel = document.getElementById("paperPreviewPanel");
  const paperPreviewGrid = document.getElementById("paperPreviewGrid");
  const paperPreviewEmpty = document.getElementById("paperPreviewEmpty");
  const generatedResultPanel = document.getElementById("generatedResultPanel");

  const contentInput = document.getElementById("contentInput");
  const contentCount = document.getElementById("contentCount");

  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightboxImg");
  const lightboxClose = document.getElementById("lightboxClose");
  const lightboxPrev = document.getElementById("lightboxPrev");
  const lightboxNext = document.getElementById("lightboxNext");
  const lightboxDownload = document.getElementById("lightboxDownload");
  const lightboxStage = document.getElementById("lightboxStage");
  const zoomOutBtn = document.getElementById("zoomOutBtn");
  const zoomInBtn = document.getElementById("zoomInBtn");
  const zoomResetBtn = document.getElementById("zoomResetBtn");
  const zoomLevelText = document.getElementById("zoomLevelText");
  const saveAllBtn = document.getElementById("saveAllBtn");

  const pageData = window.__INDEX_PAGE_DATA || {};
  const paperPreviewMap = pageData.paperPreviewMap && typeof pageData.paperPreviewMap === "object"
    ? pageData.paperPreviewMap
    : {};
  const defaultPaperPreviews = Array.isArray(pageData.defaultPaperPreviews)
    ? pageData.defaultPaperPreviews
    : [];

  const ZOOM_MIN = 0.3;
  const ZOOM_MAX = 3;
  const ZOOM_STEP = 0.2;

  let progressTimer = null;
  let progressValue = 0;
  let lightboxItems = [];
  let currentIndex = 0;
  let zoomLevel = 1;
  let isSubmitting = false;

  function updateContentCount() {
    if (!contentInput || !contentCount) {
      return;
    }
    const value = contentInput.value || "";
    contentCount.textContent = `${value.length} 字`;
  }

  function getPaperPreviewItems() {
    const selectedType = paperTypeSelect ? (paperTypeSelect.value || "") : "";
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
    const article = document.createElement("article");
    article.className = "image-item";

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

    const meta = document.createElement("div");
    meta.className = "thumb-meta";

    const label = document.createElement("p");
    label.textContent = item.label || `第 ${index + 1} 页`;
    meta.appendChild(label);

    button.appendChild(image);
    article.appendChild(button);
    article.appendChild(meta);

    return article;
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

    if (hasCards) {
      const cards = paperPreviewGrid.querySelectorAll(".image-item");
      cards.forEach((card, index) => {
        card.style.animation = `revealUp 0.4s ease ${index * 0.04}s both`;
      });
    }
  }

  function startLoadingAnimation() {
    if (!generationPreview || !loadingFill || !loadingPercent) {
      return;
    }

    progressValue = 7;
    loadingFill.style.width = `${progressValue}%`;
    loadingPercent.textContent = `${progressValue}%`;

    generationPreview.classList.add("show");
    generationPreview.setAttribute("aria-hidden", "false");

    if (progressTimer) {
      window.clearInterval(progressTimer);
    }

    progressTimer = window.setInterval(() => {
      const cap = 94;
      if (progressValue >= cap) {
        return;
      }
      const remain = cap - progressValue;
      const step = Math.max(1, Math.ceil(remain * (0.08 + Math.random() * 0.08)));
      progressValue = Math.min(cap, progressValue + step);
      loadingFill.style.width = `${progressValue}%`;
      loadingPercent.textContent = `${progressValue}%`;
    }, 340);
  }

  function stopLoadingAnimation() {
    if (progressTimer) {
      window.clearInterval(progressTimer);
      progressTimer = null;
    }

    if (!generationPreview) {
      return;
    }

    generationPreview.classList.remove("show");
    generationPreview.setAttribute("aria-hidden", "true");
  }

  function getVisibleThumbButtons(scope) {
    const root = scope || document;
    return Array.from(root.querySelectorAll(".thumb-btn")).filter((btn) => {
      const src = btn.getAttribute("data-src");
      return src && btn.offsetParent !== null;
    });
  }

  function getFileName(src, fallbackName) {
    if (!src) {
      return fallbackName;
    }
    const raw = src.split("?")[0].split("#")[0];
    const name = raw.slice(raw.lastIndexOf("/") + 1);
    return name || fallbackName;
  }

  function updateNavVisibility() {
    const visible = lightboxItems.length > 1;
    if (lightboxPrev) {
      lightboxPrev.style.display = visible ? "flex" : "none";
    }
    if (lightboxNext) {
      lightboxNext.style.display = visible ? "flex" : "none";
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

  function renderLightbox(index) {
    if (!lightboxItems.length || !lightboxImg || !lightboxDownload) {
      return;
    }

    currentIndex = (index + lightboxItems.length) % lightboxItems.length;
    const item = lightboxItems[currentIndex];
    const fallbackName = `page_${currentIndex + 1}.jpg`;

    lightboxImg.src = item.src;
    lightboxImg.alt = item.alt || "大图预览";
    lightboxDownload.href = item.src;
    lightboxDownload.download = getFileName(item.src, fallbackName);

    // Default zoom level before image loads
    zoomLevel = 1;
    updateZoomView();

    // After image loads, adjust zoom to fit within viewport
    if (lightboxImg.complete) {
      fitImageToViewport();
    } else {
      lightboxImg.onload = fitImageToViewport;
    }
  }

  function fitImageToViewport() {
    if (!lightboxImg || !lightboxStage) {
      return;
    }
    const stageRect = lightboxStage.getBoundingClientRect();
    const imgWidth = lightboxImg.naturalWidth;
    const imgHeight = lightboxImg.naturalHeight;

    if (!imgWidth || !imgHeight) {
      return;
    }

    // Calculate scale to fit image within stage, with padding
    const scaleX = (stageRect.width - 40) / imgWidth;
    const scaleY = (stageRect.height - 40) / imgHeight;
    const fitScale = Math.min(scaleX, scaleY, 1); // Never scale up beyond 100%

    zoomLevel = Math.round(fitScale * 100) / 100;
    if (fitScale <= 0 || !isFinite(zoomLevel)) {
      zoomLevel = ZOOM_MIN;
    }
    zoomLevel = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoomLevel));
    updateZoomView();
  }

  function openLightbox(buttons, index) {
    if (!lightbox || !buttons.length) {
      return;
    }

    lightboxItems = buttons.map((btn) => {
      const img = btn.querySelector("img");
      return {
        src: btn.getAttribute("data-src") || "",
        alt: img ? img.alt : "大图预览",
      };
    }).filter((item) => item.src);

    if (!lightboxItems.length) {
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
    lightboxImg.src = "";
    resetZoom();
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

  if (paperTypeSelect) {
    paperTypeSelect.addEventListener("change", renderPaperPreview);
  }

  if (contentInput) {
    contentInput.addEventListener("input", updateContentCount);
  }

  if (generateForm) {
    generateForm.addEventListener("submit", async (event) => {
      if (isSubmitting) {
        return;
      }

      event.preventDefault();
      isSubmitting = true;

      if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.textContent = "生成中...";
      }

      if (paperPreviewPanel) {
        paperPreviewPanel.hidden = true;
      }
      if (generatedResultPanel) {
        generatedResultPanel.hidden = true;
      }

      startLoadingAnimation();
      const action = generateForm.getAttribute("action") || window.location.href;
      const method = (generateForm.getAttribute("method") || "POST").toUpperCase();
      const formData = new FormData(generateForm);

      try {
        const response = await fetch(action, {
          method,
          body: formData,
          credentials: "same-origin",
          redirect: "follow",
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        if (progressTimer) {
          window.clearInterval(progressTimer);
          progressTimer = null;
        }
        if (loadingFill && loadingPercent) {
          loadingFill.style.width = "100%";
          loadingPercent.textContent = "100%";
        }

        // Reload page to show new results, keeping loading animation visible briefly
        setTimeout(() => {
          window.location.reload();
        }, 400);
      } catch (error) {
        console.error("提交生成请求失败:", error);
        isSubmitting = false;
        stopLoadingAnimation();

        if (generateBtn) {
          generateBtn.disabled = false;
          generateBtn.textContent = "生成手写图片";
        }
        if (paperPreviewPanel) {
          paperPreviewPanel.hidden = false;
        }
        if (generatedResultPanel) {
          generatedResultPanel.hidden = false;
        }

        window.alert("生成请求失败，请检查网络或稍后重试。");
      }
    });
  }

  document.addEventListener("click", (event) => {
    const thumbBtn = event.target.closest(".thumb-btn");
    if (!thumbBtn) {
      return;
    }

    const sourcePanel = thumbBtn.closest(".images-grid");
    const buttons = getVisibleThumbButtons(sourcePanel || document);
    const index = buttons.indexOf(thumbBtn);
    if (index < 0) {
      return;
    }

    openLightbox(buttons, index);
  });

  if (lightboxPrev) {
    lightboxPrev.addEventListener("click", () => {
      renderLightbox(currentIndex - 1);
    });
  }

  if (lightboxNext) {
    lightboxNext.addEventListener("click", () => {
      renderLightbox(currentIndex + 1);
    });
  }

  if (lightboxClose) {
    lightboxClose.addEventListener("click", closeLightbox);
  }

  if (lightbox) {
    lightbox.addEventListener("click", (event) => {
      if (event.target === lightbox) {
        closeLightbox();
      }
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
    zoomResetBtn.addEventListener("click", resetZoom);
  }

  if (saveAllBtn) {
    saveAllBtn.addEventListener("click", () => {
      const resultButtons = generatedResultPanel
        ? getVisibleThumbButtons(generatedResultPanel)
        : getVisibleThumbButtons(document);

      // Download all immediately without artificial delay
      resultButtons.forEach((btn, index) => {
        const src = btn.getAttribute("data-src") || "";
        downloadBySrc(src, `page_${index + 1}.jpg`);
      });
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

  renderPaperPreview();
  updateContentCount();
  updateZoomView();
})();

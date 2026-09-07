(function () {
  "use strict";

  const generateForm = document.getElementById("generateForm");
  const generateBtn = document.getElementById("generateBtn");
  const generateBtnText = document.getElementById("generateBtnText");
  const formStatus = document.getElementById("formStatus");
  const formStatusText = document.getElementById("formStatusText");

  const generationPreview = document.getElementById("generationPreview");
  const loadingStage = document.getElementById("loadingStage");
  const loadingDetail = document.getElementById("loadingDetail");
  const loadingElapsed = document.getElementById("loadingElapsed");

  const paperTemplateInputs = Array.from(document.querySelectorAll("input[name='paper_type']"));
  const paperPreviewPanel = document.getElementById("paperPreviewPanel");
  const paperPreviewGrid = document.getElementById("paperPreviewGrid");
  const paperPreviewEmpty = document.getElementById("paperPreviewEmpty");
  const paperPreviewTitle = document.getElementById("paperPreviewTitle");
  const paperSideCount = document.getElementById("paperSideCount");
  const generatedResultPanel = document.getElementById("generatedResultPanel");
  const rightPanel = document.getElementById("rightPanel");

  const contentInput = document.getElementById("contentInput");
  const contentCount = document.getElementById("contentCount");
  const contentError = document.getElementById("contentError");
  const contentFileInput = document.getElementById("contentFileInput");
  const clearContentBtn = document.getElementById("clearContentBtn");
  const resetFormLink = document.getElementById("resetFormLink");
  const regenerateVariantBtn = document.getElementById("regenerateVariantBtn");

  const lightbox = document.getElementById("lightbox");
  const lightboxDialog = document.getElementById("lightboxDialog");
  const lightboxImg = document.getElementById("lightboxImg");
  const lightboxClose = document.getElementById("lightboxClose");
  const lightboxPrev = document.getElementById("lightboxPrev");
  const lightboxNext = document.getElementById("lightboxNext");
  const lightboxDownload = document.getElementById("lightboxDownload");
  const lightboxCounter = document.getElementById("lightboxCounter");
  const lightboxStage = document.getElementById("lightboxStage");
  const zoomOutBtn = document.getElementById("zoomOutBtn");
  const zoomInBtn = document.getElementById("zoomInBtn");
  const zoomResetBtn = document.getElementById("zoomResetBtn");
  const zoomLevelText = document.getElementById("zoomLevelText");
  const appShell = document.querySelector(".app-shell");

  const pageData = window.__INDEX_PAGE_DATA || {};
  const paperPreviewMap = pageData.paperPreviewMap && typeof pageData.paperPreviewMap === "object"
    ? pageData.paperPreviewMap
    : {};
  const defaultPaperPreviews = Array.isArray(pageData.defaultPaperPreviews)
    ? pageData.defaultPaperPreviews
    : [];
  const paperDisplayNames = pageData.paperDisplayNames && typeof pageData.paperDisplayNames === "object"
    ? pageData.paperDisplayNames
    : {};
  const maxContentChars = Number.isFinite(Number(pageData.maxContentChars))
    ? Number(pageData.maxContentChars)
    : 12000;

  const DRAFT_STORAGE_KEY = "handwrite-studio:draft:v2";
  const ZOOM_MIN = 0.5;
  const ZOOM_MAX = 4;
  const ZOOM_STEP = 0.2;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const generationStages = [
    {
      delay: 0,
      title: "正在准备排版",
      detail: "正在检查文字和纸张参数，请稍候。",
    },
    {
      delay: 1500,
      title: "正在计算分页",
      detail: "正在处理换行、标点规则和页面布局。",
    },
    {
      delay: 4300,
      title: "正在渲染手写笔迹",
      detail: "正文较长或图片较大时，这一步可能需要一些时间。",
    },
    {
      delay: 8500,
      title: "正在整理导出文件",
      detail: "正在准备图片与 PDF，请继续保持页面打开。",
    },
  ];

  let stageTimers = [];
  let elapsedTimer = null;
  let elapsedSeconds = 0;
  let isSubmitting = false;

  let lightboxItems = [];
  let currentIndex = 0;
  let zoomLevel = 1;
  let baseImageWidth = 0;
  let baseImageHeight = 0;
  let previousActiveElement = null;
  let dragState = null;

  function setFormStatus(message, type, shouldFocus) {
    if (!formStatus || !formStatusText) {
      return;
    }

    const hasMessage = Boolean(message);
    formStatus.hidden = !hasMessage;
    formStatusText.textContent = message || "";
    formStatus.classList.toggle("is-error", type !== "success");
    formStatus.classList.toggle("is-success", type === "success");

    if (hasMessage && shouldFocus) {
      formStatus.focus({ preventScroll: true });
      formStatus.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
    }
  }

  function setFieldError(input, errorElement, message) {
    if (input) {
      if (message) {
        input.setAttribute("aria-invalid", "true");
      } else {
        input.removeAttribute("aria-invalid");
      }
    }
    if (errorElement) {
      errorElement.textContent = message || "";
      errorElement.hidden = !message;
    }
  }

  function updateContentCount() {
    if (!contentInput || !contentCount) {
      return;
    }

    const length = (contentInput.value || "").length;
    contentCount.textContent = `${length.toLocaleString("zh-CN")} / ${maxContentChars.toLocaleString("zh-CN")}`;
    contentCount.classList.toggle("is-near-limit", length >= maxContentChars * 0.85 && length < maxContentChars);
    contentCount.classList.toggle("is-at-limit", length >= maxContentChars);

    if (length > 0 && length <= maxContentChars) {
      setFieldError(contentInput, contentError, "");
    }
  }

  function collectDraft() {
    if (!generateForm) {
      return {};
    }

    const draft = {};
    generateForm.querySelectorAll("input[name], select[name], textarea[name]").forEach((field) => {
      if (field.type === "file" || (field.type === "radio" && !field.checked)) {
        return;
      }
      draft[field.name] = field.value;
    });
    return draft;
  }

  function persistDraft() {
    try {
      window.sessionStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(collectDraft()));
    } catch (error) {
      console.warn("无法保存表单草稿:", error);
    }
  }

  function clearDraft() {
    try {
      window.sessionStorage.removeItem(DRAFT_STORAGE_KEY);
    } catch (error) {
      console.warn("无法清除表单草稿:", error);
    }
  }

  function restoreDraft() {
    if (!generateForm) {
      return;
    }

    if (pageData.clearDraft) {
      clearDraft();
      return;
    }

    let draft;
    try {
      draft = JSON.parse(window.sessionStorage.getItem(DRAFT_STORAGE_KEY) || "null");
    } catch (error) {
      clearDraft();
      return;
    }

    if (!draft || typeof draft !== "object") {
      return;
    }

    if (!draft.meeting_date && draft.year && draft.month && draft.day) {
      const year = String(draft.year).padStart(4, "0");
      const month = String(draft.month).padStart(2, "0");
      const day = String(draft.day).padStart(2, "0");
      draft.meeting_date = `${year}-${month}-${day}`;
    }

    Object.entries(draft).forEach(([name, value]) => {
      if (typeof value !== "string") {
        return;
      }
      const fields = Array.from(generateForm.querySelectorAll("input[name], select[name], textarea[name]"))
        .filter((field) => field.name === name);
      if (!fields.length || fields[0].type === "file") {
        return;
      }
      if (fields[0].type === "radio") {
        const matchingField = fields.find((field) => field.value === value);
        if (matchingField) {
          fields.forEach((field) => {
            field.checked = field === matchingField;
          });
        }
        return;
      }
      if (fields[0].tagName === "SELECT"
          && !Array.from(fields[0].options).some((option) => option.value === value)) {
        return;
      }
      fields[0].value = value;
    });
  }

  function getSelectedPaperInput() {
    const selectedInput = paperTemplateInputs.find((input) => input.checked);
    if (selectedInput) {
      return selectedInput;
    }
    if (paperTemplateInputs[0]) {
      paperTemplateInputs[0].checked = true;
      return paperTemplateInputs[0];
    }
    return null;
  }

  function getPaperPreviewItems() {
    const selectedInput = getSelectedPaperInput();
    const selectedType = selectedInput ? selectedInput.value : "";
    const selectedItems = paperPreviewMap[selectedType];
    if (Array.isArray(selectedItems) && selectedItems.length) {
      return selectedItems.filter((item) => item && item.url);
    }
    return defaultPaperPreviews.filter((item) => item && item.url);
  }

  function updateSelectedPaper() {
    const selectedInput = getSelectedPaperInput();
    paperTemplateInputs.forEach((input) => {
      const card = input.closest(".template-option");
      if (card) {
        card.classList.toggle("is-selected", input === selectedInput);
      }
    });

    if (paperPreviewTitle && selectedInput) {
      paperPreviewTitle.textContent = paperDisplayNames[selectedInput.value]
        || selectedInput.dataset.displayName
        || selectedInput.value;
    }
  }

  function buildPaperPreviewCard(item, index) {
    const article = document.createElement("article");
    article.className = "image-item preview-item";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "thumb-btn";
    button.dataset.src = item.url || "";
    button.dataset.label = item.label || `纸张 ${index + 1}`;
    button.setAttribute("aria-label", `查看纸张${item.label || index + 1}大图`);

    const image = document.createElement("img");
    image.className = "thumb-img";
    image.src = item.url || "";
    image.alt = `纸张${item.label || index + 1}预览`;
    image.loading = index === 0 ? "eager" : "lazy";
    image.decoding = "async";

    const zoomHint = document.createElement("span");
    zoomHint.className = "zoom-hint";
    zoomHint.setAttribute("aria-hidden", "true");
    zoomHint.textContent = "放大";

    const meta = document.createElement("div");
    meta.className = "thumb-meta";

    const label = document.createElement("p");
    label.textContent = item.label || `第 ${index + 1} 面`;

    button.append(image, zoomHint);
    meta.appendChild(label);
    article.append(button, meta);
    return article;
  }

  function renderPaperPreview() {
    updateSelectedPaper();

    if (!paperPreviewGrid || !paperPreviewEmpty) {
      return;
    }

    const items = getPaperPreviewItems();
    paperPreviewGrid.textContent = "";

    items.forEach((item, index) => {
      const card = buildPaperPreviewCard(item, index);
      if (!reduceMotion) {
        card.style.animation = `revealUp 0.38s ease ${index * 0.05}s both`;
      }
      paperPreviewGrid.appendChild(card);
    });

    const hasCards = paperPreviewGrid.childElementCount > 0;
    paperPreviewGrid.hidden = !hasCards;
    paperPreviewEmpty.hidden = hasCards;
    if (paperSideCount) {
      paperSideCount.textContent = hasCards ? `${paperPreviewGrid.childElementCount} 个页面` : "";
    }
  }

  function validateForm() {
    let firstInvalidField = null;
    const content = contentInput ? contentInput.value.trim() : "";

    setFieldError(contentInput, contentError, "");

    if (!content) {
      setFieldError(contentInput, contentError, "请输入会议正文后再生成。这个字段不能为空。");
      firstInvalidField = contentInput;
    } else if (content.length > maxContentChars) {
      setFieldError(contentInput, contentError, `正文最多允许 ${maxContentChars.toLocaleString("zh-CN")} 个字符。`);
      firstInvalidField = contentInput;
    }

    if (firstInvalidField) {
      setFormStatus("请检查标出的字段后再试。", "error", false);
      firstInvalidField.focus();
      firstInvalidField.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
      return false;
    }

    setFormStatus("", "error", false);
    return true;
  }

  function updateLoadingStage(stage) {
    if (loadingStage) {
      loadingStage.textContent = stage.title;
    }
    if (loadingDetail) {
      loadingDetail.textContent = stage.detail;
    }
  }

  function clearLoadingTimers() {
    stageTimers.forEach((timer) => window.clearTimeout(timer));
    stageTimers = [];
    if (elapsedTimer) {
      window.clearInterval(elapsedTimer);
      elapsedTimer = null;
    }
  }

  function startLoadingState() {
    if (!generationPreview) {
      return;
    }

    clearLoadingTimers();
    elapsedSeconds = 0;
    if (loadingElapsed) {
      loadingElapsed.textContent = "已用时 0 秒";
    }

    generationStages.forEach((stage) => {
      const timer = window.setTimeout(() => updateLoadingStage(stage), stage.delay);
      stageTimers.push(timer);
    });

    elapsedTimer = window.setInterval(() => {
      elapsedSeconds += 1;
      if (loadingElapsed) {
        loadingElapsed.textContent = `已用时 ${elapsedSeconds} 秒`;
      }
    }, 1000);

    generationPreview.classList.add("show");
    generationPreview.setAttribute("aria-hidden", "false");

    if (window.matchMedia("(max-width: 1120px)").matches && rightPanel) {
      rightPanel.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    }
  }

  function completeLoadingState() {
    clearLoadingTimers();
    updateLoadingStage({
      title: "生成完成",
      detail: "正在打开预览与下载页面。",
    });
  }

  function stopLoadingState() {
    clearLoadingTimers();
    if (!generationPreview) {
      return;
    }
    generationPreview.classList.remove("show");
    generationPreview.setAttribute("aria-hidden", "true");
  }

  function setSubmitting(submitting) {
    isSubmitting = submitting;
    if (!generateBtn) {
      return;
    }
    generateBtn.disabled = submitting;
    generateBtn.classList.toggle("is-loading", submitting);
    if (generateBtnText) {
      const idleLabel = generateForm ? generateForm.dataset.idleLabel : "开始生成";
      generateBtnText.textContent = submitting ? "正在生成，请稍候" : (idleLabel || "开始生成");
    }
  }

  function getVisibleThumbButtons(scope) {
    const root = scope || document;
    return Array.from(root.querySelectorAll(".thumb-btn")).filter((button) => {
      return Boolean(button.dataset.src) && button.offsetParent !== null;
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
    const hidden = lightboxItems.length <= 1;
    if (lightboxPrev) {
      lightboxPrev.hidden = hidden;
    }
    if (lightboxNext) {
      lightboxNext.hidden = hidden;
    }
  }

  function getStagePadding() {
    if (!lightboxStage) {
      return { horizontal: 0, vertical: 0 };
    }
    const style = window.getComputedStyle(lightboxStage);
    return {
      horizontal: parseFloat(style.paddingLeft) + parseFloat(style.paddingRight),
      vertical: parseFloat(style.paddingTop) + parseFloat(style.paddingBottom),
    };
  }

  function updateZoomView(preserveCenter) {
    if (!lightboxImg || !baseImageWidth || !baseImageHeight) {
      return;
    }

    let centerX = 0.5;
    let centerY = 0.5;
    if (preserveCenter && lightboxStage) {
      centerX = (lightboxStage.scrollLeft + lightboxStage.clientWidth / 2) / Math.max(lightboxStage.scrollWidth, 1);
      centerY = (lightboxStage.scrollTop + lightboxStage.clientHeight / 2) / Math.max(lightboxStage.scrollHeight, 1);
    }

    lightboxImg.style.width = `${Math.round(baseImageWidth * zoomLevel)}px`;
    lightboxImg.style.height = `${Math.round(baseImageHeight * zoomLevel)}px`;

    if (zoomLevelText) {
      zoomLevelText.textContent = `${Math.round(zoomLevel * 100)}%`;
    }
    if (zoomOutBtn) {
      zoomOutBtn.disabled = zoomLevel <= ZOOM_MIN + 0.001;
    }
    if (zoomInBtn) {
      zoomInBtn.disabled = zoomLevel >= ZOOM_MAX - 0.001;
    }

    if (preserveCenter && lightboxStage) {
      window.requestAnimationFrame(() => {
        lightboxStage.scrollLeft = centerX * lightboxStage.scrollWidth - lightboxStage.clientWidth / 2;
        lightboxStage.scrollTop = centerY * lightboxStage.scrollHeight - lightboxStage.clientHeight / 2;
      });
    }
  }

  function setZoom(nextZoom) {
    const limited = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, nextZoom));
    zoomLevel = Math.round(limited * 100) / 100;
    updateZoomView(true);
  }

  function fitImageToViewport() {
    if (!lightboxImg || !lightboxStage || !lightboxImg.naturalWidth || !lightboxImg.naturalHeight) {
      return;
    }

    const padding = getStagePadding();
    const availableWidth = Math.max(100, lightboxStage.clientWidth - padding.horizontal);
    const availableHeight = Math.max(100, lightboxStage.clientHeight - padding.vertical);
    const fitScale = Math.min(
      availableWidth / lightboxImg.naturalWidth,
      availableHeight / lightboxImg.naturalHeight,
      1,
    );

    baseImageWidth = Math.max(1, Math.floor(lightboxImg.naturalWidth * fitScale));
    baseImageHeight = Math.max(1, Math.floor(lightboxImg.naturalHeight * fitScale));
    zoomLevel = 1;
    updateZoomView(false);
    lightboxStage.scrollTop = 0;
    lightboxStage.scrollLeft = 0;
  }

  function resetZoom() {
    fitImageToViewport();
  }

  function renderLightbox(index) {
    if (!lightboxItems.length || !lightboxImg || !lightboxDownload) {
      return;
    }

    currentIndex = (index + lightboxItems.length) % lightboxItems.length;
    const item = lightboxItems[currentIndex];
    const fallbackName = `handwrite_page_${currentIndex + 1}.jpg`;

    baseImageWidth = 0;
    baseImageHeight = 0;
    zoomLevel = 1;
    lightboxImg.style.width = "";
    lightboxImg.style.height = "";
    lightboxImg.alt = item.alt || item.label || "大图预览";
    lightboxDownload.href = item.src;
    lightboxDownload.download = getFileName(item.src, fallbackName);
    if (lightboxCounter) {
      const label = item.label || `第 ${currentIndex + 1} 页`;
      lightboxCounter.textContent = `${label} · ${currentIndex + 1} / ${lightboxItems.length}`;
    }

    lightboxImg.onload = () => window.requestAnimationFrame(fitImageToViewport);
    lightboxImg.src = item.src;
    if (lightboxImg.complete && lightboxImg.naturalWidth) {
      window.requestAnimationFrame(fitImageToViewport);
    }
    updateNavVisibility();
  }

  function openLightbox(buttons, index) {
    if (!lightbox || !lightboxDialog || !buttons.length) {
      return;
    }

    lightboxItems = buttons.map((button) => {
      const image = button.querySelector("img");
      return {
        src: button.dataset.src || "",
        label: button.dataset.label || "",
        alt: image ? image.alt : "大图预览",
      };
    }).filter((item) => item.src);

    if (!lightboxItems.length) {
      return;
    }

    previousActiveElement = document.activeElement;
    lightbox.hidden = false;
    lightbox.setAttribute("aria-hidden", "false");
    lightbox.classList.add("show");
    document.body.classList.add("modal-open");
    if (appShell && "inert" in appShell) {
      appShell.inert = true;
    }

    renderLightbox(index);
    lightboxDialog.focus({ preventScroll: true });
  }

  function closeLightbox() {
    if (!lightbox || lightbox.hidden) {
      return;
    }

    lightbox.classList.remove("show");
    lightbox.setAttribute("aria-hidden", "true");
    lightbox.hidden = true;
    document.body.classList.remove("modal-open");
    if (appShell && "inert" in appShell) {
      appShell.inert = false;
    }
    if (lightboxImg) {
      lightboxImg.onload = null;
      lightboxImg.src = "";
    }
    dragState = null;

    if (previousActiveElement && typeof previousActiveElement.focus === "function") {
      previousActiveElement.focus({ preventScroll: true });
    }
  }

  function trapLightboxFocus(event) {
    if (!lightboxDialog || event.key !== "Tab") {
      return;
    }
    const focusable = Array.from(lightboxDialog.querySelectorAll(
      "a[href], button:not([disabled]):not([hidden]), [tabindex]:not([tabindex='-1'])",
    )).filter((element) => element.offsetParent !== null);
    if (!focusable.length) {
      event.preventDefault();
      lightboxDialog.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  if (generateForm) {
    restoreDraft();

    generateForm.addEventListener("input", () => {
      persistDraft();
    });
    generateForm.addEventListener("change", () => {
      persistDraft();
    });

    generateForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (isSubmitting || !validateForm()) {
        return;
      }

      persistDraft();
      setSubmitting(true);
      if (paperPreviewPanel) {
        paperPreviewPanel.hidden = true;
      }
      if (generatedResultPanel) {
        generatedResultPanel.hidden = true;
      }
      startLoadingState();

      const action = generateForm.getAttribute("action") || window.location.href;
      const method = (generateForm.getAttribute("method") || "POST").toUpperCase();

      try {
        const response = await fetch(action, {
          method,
          body: new FormData(generateForm),
          credentials: "same-origin",
          headers: {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
          },
        });

        const isJson = (response.headers.get("content-type") || "").includes("application/json");
        const payload = isJson ? await response.json() : null;
        if (!response.ok || (payload && payload.ok === false)) {
          throw new Error((payload && payload.message) || `生成请求失败（HTTP ${response.status}）`);
        }

        completeLoadingState();
        const redirectUrl = (payload && payload.redirect_url) || response.url || "/";
        window.setTimeout(() => window.location.assign(redirectUrl), reduceMotion ? 0 : 450);
      } catch (error) {
        console.error("提交生成请求失败:", error);
        setSubmitting(false);
        stopLoadingState();
        if (paperPreviewPanel) {
          paperPreviewPanel.hidden = false;
        }
        if (generatedResultPanel) {
          generatedResultPanel.hidden = false;
        }
        setFormStatus(error.message || "生成请求失败，请检查网络后重试。", "error", true);
      }
    });
  }

  paperTemplateInputs.forEach((input) => {
    input.addEventListener("change", renderPaperPreview);
  });

  if (contentInput) {
    contentInput.addEventListener("input", updateContentCount);
  }

  if (contentFileInput && contentInput) {
    contentFileInput.addEventListener("change", async () => {
      const file = contentFileInput.files && contentFileInput.files[0];
      if (!file) {
        return;
      }

      try {
        const text = await file.text();
        if (text.length > maxContentChars) {
          setFormStatus(
            `“${file.name}”共有 ${text.length.toLocaleString("zh-CN")} 个字符，超过 ${maxContentChars.toLocaleString("zh-CN")} 字上限，未导入。`,
            "error",
            true,
          );
          return;
        }
        contentInput.value = text;
        updateContentCount();
        persistDraft();
        setFormStatus(`已导入“${file.name}”。`, "success", false);
        contentInput.focus();
      } catch (error) {
        setFormStatus("无法读取该文件，请确认它是 UTF-8 编码的 TXT 文本。", "error", true);
      } finally {
        contentFileInput.value = "";
      }
    });
  }

  if (clearContentBtn && contentInput) {
    clearContentBtn.addEventListener("click", () => {
      if (contentInput.value && !window.confirm("确定清空当前正文吗？此操作无法撤销。")) {
        return;
      }
      contentInput.value = "";
      updateContentCount();
      persistDraft();
      contentInput.focus();
    });
  }

  if (regenerateVariantBtn && generateForm) {
    regenerateVariantBtn.addEventListener("click", () => {
      generateForm.requestSubmit();
    });
  }

  if (resetFormLink) {
    resetFormLink.addEventListener("click", (event) => {
      if (!window.confirm("确定重置全部内容并重新开始吗？")) {
        event.preventDefault();
        return;
      }
      clearDraft();
    });
  }

  document.addEventListener("click", (event) => {
    const thumbButton = event.target.closest(".thumb-btn");
    if (!thumbButton) {
      return;
    }
    const sourcePanel = thumbButton.closest(".images-grid");
    const buttons = getVisibleThumbButtons(sourcePanel || document);
    const index = buttons.indexOf(thumbButton);
    if (index >= 0) {
      openLightbox(buttons, index);
    }
  });

  if (lightboxPrev) {
    lightboxPrev.addEventListener("click", () => renderLightbox(currentIndex - 1));
  }
  if (lightboxNext) {
    lightboxNext.addEventListener("click", () => renderLightbox(currentIndex + 1));
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
    zoomOutBtn.addEventListener("click", () => setZoom(zoomLevel - ZOOM_STEP));
  }
  if (zoomInBtn) {
    zoomInBtn.addEventListener("click", () => setZoom(zoomLevel + ZOOM_STEP));
  }
  if (zoomResetBtn) {
    zoomResetBtn.addEventListener("click", resetZoom);
  }

  if (lightboxStage) {
    lightboxStage.addEventListener("wheel", (event) => {
      if (!event.ctrlKey && !event.metaKey) {
        return;
      }
      event.preventDefault();
      setZoom(zoomLevel + (event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP));
    }, { passive: false });

    lightboxStage.addEventListener("dblclick", () => {
      setZoom(zoomLevel > 1.05 ? 1 : 2);
    });

    lightboxStage.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "touch" || event.button !== 0) {
        return;
      }
      if (lightboxStage.scrollWidth <= lightboxStage.clientWidth
          && lightboxStage.scrollHeight <= lightboxStage.clientHeight) {
        return;
      }
      dragState = {
        pointerId: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        scrollLeft: lightboxStage.scrollLeft,
        scrollTop: lightboxStage.scrollTop,
      };
      lightboxStage.setPointerCapture(event.pointerId);
      lightboxStage.classList.add("is-dragging");
    });

    lightboxStage.addEventListener("pointermove", (event) => {
      if (!dragState || dragState.pointerId !== event.pointerId) {
        return;
      }
      lightboxStage.scrollLeft = dragState.scrollLeft - (event.clientX - dragState.x);
      lightboxStage.scrollTop = dragState.scrollTop - (event.clientY - dragState.y);
    });

    const endDrag = (event) => {
      if (!dragState || dragState.pointerId !== event.pointerId) {
        return;
      }
      dragState = null;
      lightboxStage.classList.remove("is-dragging");
    };
    lightboxStage.addEventListener("pointerup", endDrag);
    lightboxStage.addEventListener("pointercancel", endDrag);
  }

  document.addEventListener("keydown", (event) => {
    if (!lightbox || lightbox.hidden) {
      return;
    }

    trapLightboxFocus(event);
    if (event.defaultPrevented) {
      return;
    }

    if (event.key === "Escape") {
      closeLightbox();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      renderLightbox(currentIndex - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      renderLightbox(currentIndex + 1);
    } else if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      setZoom(zoomLevel + ZOOM_STEP);
    } else if (event.key === "-" || event.key === "_") {
      event.preventDefault();
      setZoom(zoomLevel - ZOOM_STEP);
    } else if (event.key === "0") {
      event.preventDefault();
      resetZoom();
    }
  });

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    if (!lightbox || lightbox.hidden) {
      return;
    }
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(fitImageToViewport, 120);
  });

  renderPaperPreview();
  updateContentCount();
  if (formStatus && !formStatus.hidden) {
    formStatus.setAttribute("aria-live", "assertive");
  }
})();

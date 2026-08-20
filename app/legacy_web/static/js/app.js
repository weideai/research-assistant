document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) window.lucide.createIcons();

  const workspaceSidebar = document.querySelector("#workspace-sidebar");
  const sidebarCollapse = document.querySelector("#sidebar-collapse");
  const sidebarReopen = document.querySelector("#sidebar-reopen");
  if (workspaceSidebar && sidebarCollapse && sidebarReopen) {
    const storageKey = "rlab-workspace-sidebar-collapsed";
    const setSidebarCollapsed = (collapsed, { persist = false, moveFocus = false } = {}) => {
      document.body.classList.toggle("sidebar-collapsed", collapsed);
      workspaceSidebar.toggleAttribute("inert", collapsed);
      workspaceSidebar.setAttribute("aria-hidden", collapsed ? "true" : "false");
      [sidebarCollapse, sidebarReopen].forEach((button) => {
        button.setAttribute("aria-expanded", collapsed ? "false" : "true");
      });
      if (persist) {
        try { window.localStorage.setItem(storageKey, collapsed ? "1" : "0"); } catch (_error) {}
      }
      if (moveFocus) {
        window.requestAnimationFrame(() => (collapsed ? sidebarReopen : sidebarCollapse).focus());
      }
    };

    let initiallyCollapsed = false;
    try { initiallyCollapsed = window.localStorage.getItem(storageKey) === "1"; } catch (_error) {}
    setSidebarCollapsed(initiallyCollapsed);
    sidebarCollapse.addEventListener("click", () => {
      setSidebarCollapsed(true, { persist: true, moveFocus: true });
    });
    sidebarReopen.addEventListener("click", () => {
      setSidebarCollapsed(false, { persist: true, moveFocus: true });
    });
  }

  // Execution drafts stay in this browser until the user explicitly submits the form.
  document.querySelectorAll("form[data-execution-form]").forEach((form, index) => {
    if (form.dataset.executionAutosave !== "1") return;
    const explicitKey = form.dataset.executionDraftKey;
    const action = form.getAttribute("action") || window.location.pathname;
    const draftKey = `research-assistant-execution-draft:${explicitKey || action}:${index}`;
    const fields = () => Array.from(form.querySelectorAll("input[name], textarea[name], select[name]"))
      .filter((field) => field.type !== "hidden" && field.type !== "file" && !field.disabled);
    const saveDraft = () => {
      const values = {};
      fields().forEach((field) => {
        if (field.type === "checkbox" || field.type === "radio") values[field.name] = field.checked;
        else values[field.name] = field.value;
      });
      try { window.localStorage.setItem(draftKey, JSON.stringify({savedAt: Date.now(), values})); } catch (_error) {}
    };
    const restoreDraft = () => {
      let draft = null;
      try { draft = JSON.parse(window.localStorage.getItem(draftKey) || "null"); } catch (_error) {}
      if (!draft || !draft.values || Date.now() - Number(draft.savedAt || 0) > 1000 * 60 * 60 * 24 * 14) return;
      fields().forEach((field) => {
        if (!(field.name in draft.values)) return;
        if (field.type === "checkbox" || field.type === "radio") field.checked = Boolean(draft.values[field.name]);
        else field.value = draft.values[field.name];
      });
    };
    restoreDraft();
    let saveTimer = null;
    const queueSave = () => {
      window.clearTimeout(saveTimer);
      saveTimer = window.setTimeout(saveDraft, 350);
    };
    form.addEventListener("input", queueSave);
    form.addEventListener("change", queueSave);
    form.addEventListener("submit", () => {
      try { window.localStorage.removeItem(draftKey); } catch (_error) {}
    });
    const interval = Math.max(15, Number.parseInt(form.dataset.executionAutosaveInterval || "30", 10) || 30);
    window.setInterval(saveDraft, interval * 1000);
  });

  const openHashDisclosure = () => {
    if (!window.location.hash) return;
    const target = document.querySelector(window.location.hash);
    if (target instanceof HTMLDetailsElement) target.open = true;
  };
  openHashDisclosure();
  window.addEventListener("hashchange", openHashDisclosure);

  const normalizeDirectoryText = (value) => String(value || "")
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN");

  document.querySelectorAll("[data-local-directory]").forEach((directory) => {
    const items = Array.from(directory.querySelectorAll("[data-directory-item]"));
    const inputs = items.map((item) => item.querySelector("[data-directory-input]")).filter(Boolean);
    const search = directory.querySelector("[data-directory-search]");
    const pageSize = directory.querySelector("[data-directory-page-size]");
    const total = directory.querySelector("[data-directory-total]");
    const selected = directory.querySelector("[data-directory-selected]");
    const selectPage = directory.querySelector("[data-directory-select-page]");
    const selectFiltered = directory.querySelector("[data-directory-select-filtered]");
    const clear = directory.querySelector("[data-directory-clear]");
    const previous = directory.querySelector("[data-directory-prev]");
    const next = directory.querySelector("[data-directory-next]");
    const pageLabel = directory.querySelector("[data-directory-page]");
    const empty = directory.querySelector("[data-directory-empty]");
    const mode = directory.dataset.directoryMode || "multiple";
    const unit = directory.dataset.directoryUnit || "项";
    let page = 1;
    let filteredItems = items;
    let pageItems = [];

    const itemInput = (item) => item.querySelector("[data-directory-input]");
    const updateSelectionState = () => {
      const selectedCount = inputs.filter((input) => input.checked).length;
      if (selected) selected.textContent = `已选择 ${selectedCount} ${unit}`;
      directory.classList.toggle("has-directory-selection", selectedCount > 0);
      if (mode !== "multiple") return;

      const pageInputs = pageItems.map(itemInput).filter((input) => input?.type === "checkbox");
      const pageSelectedCount = pageInputs.filter((input) => input.checked).length;
      if (selectPage) {
        selectPage.disabled = pageInputs.length === 0;
        selectPage.checked = pageInputs.length > 0 && pageSelectedCount === pageInputs.length;
        selectPage.indeterminate = pageSelectedCount > 0 && pageSelectedCount < pageInputs.length;
      }
      const filteredInputs = filteredItems.map(itemInput).filter((input) => input?.type === "checkbox");
      const allFilteredSelected = filteredInputs.length > 0 && filteredInputs.every((input) => input.checked);
      if (selectFiltered) {
        selectFiltered.disabled = filteredInputs.length === 0;
        selectFiltered.classList.toggle("is-active", allFilteredSelected);
        selectFiltered.setAttribute("aria-pressed", allFilteredSelected ? "true" : "false");
      }
      if (clear) clear.disabled = selectedCount === 0;
    };

    const renderDirectory = () => {
      const query = normalizeDirectoryText(search?.value.trim());
      const perPage = Number.parseInt(pageSize?.value || "8", 10) || 8;
      filteredItems = items.filter((item) => normalizeDirectoryText(
        item.dataset.directorySearchValue || item.textContent,
      ).includes(query));
      const pages = Math.max(1, Math.ceil(filteredItems.length / perPage));
      page = Math.min(Math.max(1, page), pages);
      const start = (page - 1) * perPage;
      pageItems = filteredItems.slice(start, start + perPage);
      const visibleItems = new Set(pageItems);
      items.forEach((item) => { item.hidden = !visibleItems.has(item); });
      if (empty) empty.hidden = filteredItems.length > 0;
      if (total) total.textContent = query
        ? `${filteredItems.length} / ${items.length} ${unit}`
        : `${items.length} ${unit}`;
      if (pageLabel) pageLabel.textContent = `第 ${page} / ${pages} 页`;
      if (previous) previous.disabled = page <= 1;
      if (next) next.disabled = page >= pages;
      updateSelectionState();
    };

    search?.addEventListener("input", () => { page = 1; renderDirectory(); });
    pageSize?.addEventListener("change", () => { page = 1; renderDirectory(); });
    previous?.addEventListener("click", () => { page -= 1; renderDirectory(); });
    next?.addEventListener("click", () => { page += 1; renderDirectory(); });
    selectPage?.addEventListener("change", () => {
      pageItems.map(itemInput).filter((input) => input?.type === "checkbox")
        .forEach((input) => { input.checked = selectPage.checked; });
      updateSelectionState();
    });
    selectFiltered?.addEventListener("click", () => {
      filteredItems.map(itemInput).filter((input) => input?.type === "checkbox")
        .forEach((input) => { input.checked = true; });
      updateSelectionState();
    });
    clear?.addEventListener("click", () => {
      inputs.filter((input) => input.type === "checkbox").forEach((input) => { input.checked = false; });
      updateSelectionState();
    });
    inputs.forEach((input) => input.addEventListener("change", updateSelectionState));
    renderDirectory();
  });

  document.querySelectorAll("select[data-filterable-select]").forEach((select) => {
    const options = Array.from(select.options).filter((option) => option.value);
    if (options.length <= 8) return;

    const shell = document.createElement("span");
    shell.className = "filterable-select-shell";
    const queryField = document.createElement("span");
    queryField.className = "filterable-select-query";
    const icon = document.createElement("i");
    icon.dataset.lucide = "search";
    const query = document.createElement("input");
    query.type = "search";
    query.placeholder = select.dataset.selectSearchPlaceholder || "查找选项";
    query.setAttribute("aria-label", query.placeholder);
    query.autocomplete = "off";
    const status = document.createElement("small");
    status.className = "filterable-select-status";
    status.setAttribute("aria-live", "polite");
    queryField.append(icon, query);
    select.before(shell);
    shell.append(queryField, status, select);

    const refreshOptions = () => {
      const value = normalizeDirectoryText(query.value.trim());
      let matchCount = 0;
      options.forEach((option) => {
        const matches = normalizeDirectoryText(option.textContent).includes(value);
        if (matches) matchCount += 1;
        const keepVisible = matches || option.selected;
        option.hidden = !keepVisible;
        option.disabled = !keepVisible;
      });
      status.textContent = value ? `${matchCount} 个匹配` : `${options.length} 个可选`;
      select.querySelectorAll('option[value=""]').forEach((option) => {
        option.hidden = false;
        option.disabled = false;
      });
    };

    query.addEventListener("input", refreshOptions);
    query.addEventListener("keydown", (event) => {
      if (["ArrowDown", "Enter"].includes(event.key)) {
        event.preventDefault();
        select.focus();
      }
    });
    select.addEventListener("change", () => {
      query.value = "";
      refreshOptions();
    });
    refreshOptions();
  });
  if (window.lucide) window.lucide.createIcons();

  const modelDiscoveryRoot = document.querySelector("[data-model-discovery-url]");
  if (modelDiscoveryRoot) {
    const discoveryUrl = modelDiscoveryRoot.dataset.modelDiscoveryUrl;
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const capabilitySpec = {
      vision: ["eye", "视觉输入"],
      reasoning: ["brain-circuit", "推理"],
      web_search: ["globe-2", "联网搜索"],
      tools: ["wrench", "工具调用"],
    };
    const capabilityStrip = (descriptor) => {
      const strip = document.createElement("span");
      strip.className = "model-capabilities";
      Object.entries(capabilitySpec).forEach(([key, [iconName, label]]) => {
        const capability = descriptor?.capabilities?.[key] || {};
        const state = capability.supported === true ? "supported" : (capability.supported === false ? "unsupported" : "unknown");
        const evidence = capability.status === "declared" ? "接口声明" : (capability.status === "inferred" ? "名称推测" : "尚未确认");
        const supportLabel = capability.supported === true ? "支持" : (capability.supported === false ? "不支持" : "未知");
        const icon = document.createElement("i");
        icon.dataset.lucide = iconName;
        icon.className = `model-capability is-${state} evidence-${capability.status || "unknown"}`;
        icon.title = `${label}：${supportLabel}（${evidence}）`;
        icon.setAttribute("aria-label", `${label}：${supportLabel}，${evidence}`);
        strip.append(icon);
      });
      return strip;
    };
    modelDiscoveryRoot.querySelectorAll("[data-api-preset-form]").forEach((form, formIndex) => {
      const fetchButton = form.querySelector("[data-fetch-models]");
      const catalog = form.querySelector("[data-model-catalog]");
      const options = form.querySelector("[data-model-options]");
      const status = form.querySelector("[data-model-status]");
      const filter = form.querySelector("[data-model-filter]");
      const modelInput = form.querySelector('[name="text_model"]');
      const apiUrlInput = form.querySelector('[name="preset_api_url"]');
      const capabilitySnapshotInput = form.querySelector('[name="model_capabilities_json"]');
      const normalizedApiUrl = () => (apiUrlInput?.value.trim() || "").replace(/\/+$/, "");
      const applySelectedModel = (model) => {
        modelInput.value = model.id;
        capabilitySnapshotInput.value = JSON.stringify({
          model_id: model.id,
          api_url: normalizedApiUrl(),
          capabilities: model.capabilities,
        });
        const summary = form.closest("details")?.querySelector(":scope > summary .api-selected-model");
        const summaryCode = summary?.querySelector("code");
        if (summaryCode) summaryCode.textContent = model.id;
        const currentStrip = summary?.querySelector(".model-capabilities");
        if (currentStrip) currentStrip.replaceWith(capabilityStrip(model));
        if (window.lucide) window.lucide.createIcons();
      };
      modelInput?.addEventListener("input", () => { capabilitySnapshotInput.value = ""; });
      apiUrlInput?.addEventListener("input", () => { capabilitySnapshotInput.value = ""; });
      let rows = [];
      filter?.addEventListener("input", () => {
        const query = filter.value.trim().toLowerCase();
        rows.forEach((row) => { row.hidden = Boolean(query) && !row.dataset.modelId.includes(query); });
      });
      fetchButton?.addEventListener("click", async () => {
        const apiUrl = apiUrlInput?.value.trim();
        const apiKey = form.querySelector('[name="preset_api_key"]')?.value.trim();
        const presetId = form.querySelector('[name="preset_id"]')?.value || null;
        if (!apiUrl) {
          form.querySelector('[name="preset_api_url"]')?.focus();
          return;
        }
        fetchButton.disabled = true;
        catalog.hidden = false;
        options.replaceChildren();
        if (status) status.textContent = "正在连接…";
        try {
          const response = await fetch(discoveryUrl, {
            method: "POST",
            headers: {"Content-Type": "application/json", "X-CSRFToken": csrf, "Accept": "application/json"},
            body: JSON.stringify({api_url: apiUrl, api_key: apiKey, preset_id: presetId}),
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || "模型拉取失败");
          rows = result.models.map((model, index) => {
            const row = document.createElement("label");
            row.className = "api-model-option";
            row.dataset.modelId = model.id.toLowerCase();
            const radio = document.createElement("input");
            radio.type = "radio";
            radio.name = `discovered-model-${formIndex}`;
            radio.value = model.id;
            radio.checked = model.id === modelInput.value;
            const copy = document.createElement("span");
            const title = document.createElement("b");
            title.textContent = model.id;
            const owner = document.createElement("small");
            owner.textContent = model.owned_by ? `提供方：${model.owned_by}` : "提供方未声明";
            copy.append(title, owner);
            row.append(radio, copy, capabilityStrip(model));
            radio.addEventListener("change", () => applySelectedModel(model));
            options.append(row);
            if (radio.checked) applySelectedModel(model);
            return row;
          });
          if (status) status.textContent = `共 ${result.models.length} 个`;
          if (filter) { filter.value = ""; filter.focus(); }
          if (window.lucide) window.lucide.createIcons();
        } catch (error) {
          if (status) status.textContent = "读取失败";
          const message = document.createElement("p");
          message.className = "empty-cell";
          message.textContent = error.message;
          options.replaceChildren(message);
        } finally {
          fetchButton.disabled = false;
        }
      });
    });
  }

  const updateCheckUrl = document.body.dataset.updateCheckUrl;
  const updateBanner = document.querySelector("#update-banner");
  if (updateCheckUrl && updateBanner) {
    fetch(updateCheckUrl, {headers: {"Accept": "application/json"}})
      .then((response) => response.ok ? response.json() : null)
      .then((result) => {
        if (!result?.enabled || !result.update_available || !result.latest_version || !result.release_url) return;
        const dismissKey = `research-assistant-update-dismissed:${result.latest_version}`;
        try {
          if (window.localStorage.getItem(dismissKey) === "1") return;
        } catch (_error) {
          // The reminder still works when browser storage is unavailable.
        }
        const version = document.querySelector("#update-version");
        const link = document.querySelector("#update-release-link");
        if (version) version.textContent = `v${result.latest_version}`;
        if (link) link.href = result.release_url;
        updateBanner.hidden = false;
        if (window.lucide) window.lucide.createIcons();
        document.querySelector("#update-dismiss")?.addEventListener("click", () => {
          updateBanner.hidden = true;
          try { window.localStorage.setItem(dismissKey, "1"); } catch (_error) {}
        }, {once: true});
      })
      .catch(() => {});
  }

  const openWorkspaceDialog = (dialogId) => {
    const dialog = document.getElementById(dialogId);
    if (!(dialog instanceof HTMLDialogElement)) return;
    if (!dialog.open) dialog.showModal();
    window.requestAnimationFrame(() => {
      dialog.querySelector("input:not([type='hidden']), select, textarea, button")?.focus();
    });
  };
  document.querySelectorAll("[data-dialog-open]").forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      openWorkspaceDialog(trigger.dataset.dialogOpen);
    });
  });
  document.querySelectorAll("dialog[data-workspace-dialog]").forEach((dialog) => {
    dialog.querySelectorAll("[data-dialog-close]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });
  const initialDialogId = window.location.hash.replace(/^#/, "");
  if (initialDialogId) openWorkspaceDialog(initialDialogId);

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
  document.querySelectorAll("button[data-confirm]").forEach((button) => {
    button.addEventListener("click", (event) => {
      if (!window.confirm(button.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll("[data-report-template-picker]").forEach((picker) => {
    picker.addEventListener("change", () => {
      document.querySelectorAll("[data-report-export]").forEach((link) => {
        const url = new URL(link.href, window.location.origin);
        url.searchParams.set("report_template", picker.value);
        link.href = url.pathname + url.search;
      });
    });
  });

  document.querySelectorAll("[data-attachment-bulk]").forEach((form) => {
    const checkboxes = [...document.querySelectorAll(`[data-attachment-select][form="${form.id}"]`)];
    const selectPage = form.querySelector("[data-attachment-select-page], [data-attachment-select-all]");
    const selectAllMatches = form.querySelector("[data-attachment-select-all-matches]");
    const selectionScope = form.querySelector("[data-attachment-selection-scope]");
    const selectedLabel = form.querySelector("[data-attachment-selected]");
    const actionButtons = [...form.querySelectorAll('button[name="action"]')];
    const totalCount = Number.parseInt(form.dataset.total || `${checkboxes.length}`, 10) || 0;
    let allMatchesSelected = selectionScope?.value === "all";
    const updateState = () => {
      const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
      const effectiveCount = allMatchesSelected ? totalCount : selectedCount;
      if (selectedLabel) {
        selectedLabel.textContent = allMatchesSelected
          ? `已选择全部 ${totalCount} 个匹配文件`
          : `已选择本页 ${selectedCount} 个`;
      }
      if (selectPage) {
        selectPage.checked = allMatchesSelected || (checkboxes.length > 0 && selectedCount === checkboxes.length);
        selectPage.indeterminate = !allMatchesSelected && selectedCount > 0 && selectedCount < checkboxes.length;
      }
      if (selectionScope) selectionScope.value = allMatchesSelected ? "all" : "page";
      selectAllMatches?.classList.toggle("is-active", allMatchesSelected);
      selectAllMatches?.setAttribute("aria-pressed", allMatchesSelected ? "true" : "false");
      actionButtons.forEach((button) => { button.disabled = effectiveCount === 0; });
      form.classList.toggle("has-selection", effectiveCount > 0);
    };
    selectPage?.addEventListener("change", () => {
      allMatchesSelected = false;
      checkboxes.forEach((checkbox) => { checkbox.checked = selectPage.checked; });
      updateState();
    });
    selectAllMatches?.addEventListener("click", () => {
      allMatchesSelected = !allMatchesSelected;
      checkboxes.forEach((checkbox) => { checkbox.checked = allMatchesSelected; });
      updateState();
    });
    checkboxes.forEach((checkbox) => checkbox.addEventListener("change", () => {
      allMatchesSelected = false;
      updateState();
    }));
    form.addEventListener("submit", (event) => {
      const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
      const effectiveCount = allMatchesSelected ? totalCount : selectedCount;
      if (!effectiveCount) {
        event.preventDefault();
        window.alert("请先勾选至少一个文件。");
        return;
      }
      if (event.submitter?.value === "delete" &&
          !window.confirm(`确定将选中的 ${effectiveCount} 个文件移入回收站吗？原始文件不会立即删除。`)) {
        event.preventDefault();
      }
    });
    updateState();
  });

  document.querySelectorAll("[data-bulk-form]").forEach((form) => {
    const checkboxes = [...document.querySelectorAll(`[data-bulk-select][form="${form.id}"]`)];
    const selectAll = form.querySelector("[data-bulk-select-all]");
    const selectAllMatches = form.querySelector("[data-bulk-select-all-matches]");
    const selectionScope = form.querySelector("[data-bulk-selection-scope]");
    const selectedLabel = form.querySelector("[data-bulk-selected]");
    const actionButtons = [...form.querySelectorAll('button[name="action"]')];
    const resourceLabel = form.dataset.bulkLabel || "项目";
    const counterLabel = form.dataset.bulkCounter || "";
    const totalCount = Number.parseInt(form.dataset.bulkTotal || `${checkboxes.length}`, 10) || 0;
    let allMatchesSelected = selectionScope?.value === "all";
    const updateState = () => {
      const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
      const effectiveCount = allMatchesSelected ? totalCount : selectedCount;
      if (selectedLabel) {
        selectedLabel.textContent = counterLabel
          ? (allMatchesSelected
            ? `已选择全部 ${totalCount} ${counterLabel}`
            : `已选择 ${selectedCount} ${counterLabel}`)
          : (allMatchesSelected
            ? `已选择全部 ${totalCount} 个${resourceLabel}`
            : `已选择 ${selectedCount} 个`);
      }
      if (selectAll) {
        selectAll.checked = allMatchesSelected || (checkboxes.length > 0 && selectedCount === checkboxes.length);
        selectAll.indeterminate = !allMatchesSelected && selectedCount > 0 && selectedCount < checkboxes.length;
      }
      if (selectionScope) selectionScope.value = allMatchesSelected ? "all" : "page";
      selectAllMatches?.classList.toggle("is-active", allMatchesSelected);
      selectAllMatches?.setAttribute("aria-pressed", allMatchesSelected ? "true" : "false");
      actionButtons.forEach((button) => { button.disabled = effectiveCount === 0; });
      form.classList.toggle("has-selection", effectiveCount > 0);
    };
    selectAll?.addEventListener("change", () => {
      allMatchesSelected = false;
      checkboxes.forEach((checkbox) => { checkbox.checked = selectAll.checked; });
      updateState();
    });
    selectAllMatches?.addEventListener("click", () => {
      allMatchesSelected = !allMatchesSelected;
      checkboxes.forEach((checkbox) => { checkbox.checked = allMatchesSelected; });
      updateState();
    });
    checkboxes.forEach((checkbox) => checkbox.addEventListener("change", () => {
      allMatchesSelected = false;
      updateState();
    }));
    form.addEventListener("submit", (event) => {
      const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
      const effectiveCount = allMatchesSelected ? totalCount : selectedCount;
      if (!effectiveCount) {
        event.preventDefault();
        window.alert(`请先勾选至少一个${resourceLabel}。`);
        return;
      }
      if (event.submitter?.value === "delete") {
        const message = form.dataset.bulkDeleteMessage
          ? form.dataset.bulkDeleteMessage.replace("{count}", String(effectiveCount))
          : `确定批量删除选中的 ${effectiveCount} 个${resourceLabel}吗？此操作无法撤销。`;
        if (!window.confirm(message)) event.preventDefault();
      }
    });
    updateState();
  });

  document.querySelectorAll("[data-schedule-controls]").forEach((group) => {
    const mode = group.querySelector("[data-schedule-mode]");
    const dateInput = group.querySelector("[data-schedule-date]");
    const intervalInput = group.querySelector("[data-schedule-interval]");
    const shiftInput = group.querySelector("[data-schedule-shift]");
    if (!mode) return;
    const updateScheduleFields = () => {
      const value = mode.value;
      if (dateInput) dateInput.disabled = !["set", "sequence"].includes(value);
      if (intervalInput) intervalInput.disabled = value !== "sequence";
      if (shiftInput) shiftInput.disabled = value !== "shift";
    };
    mode.addEventListener("change", updateScheduleFields);
    updateScheduleFields();
  });

  document.querySelectorAll("details[data-disclosure-key]").forEach((details) => {
    const storageKey = `research-assistant-disclosure:${details.dataset.disclosureKey}`;
    try {
      const savedState = window.localStorage.getItem(storageKey);
      if (savedState !== null) details.open = savedState === "open";
    } catch (_error) {
      // The panel still works when browser storage is unavailable.
    }
    details.addEventListener("toggle", () => {
      try {
        window.localStorage.setItem(storageKey, details.open ? "open" : "closed");
      } catch (_error) {
        // Ignore private-mode storage failures.
      }
    });
  });

  document.querySelectorAll("[data-template-apply-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const mode = form.querySelector("[name='apply_mode']")?.value;
      if (mode === "replace" && !window.confirm("替换会删除目标实验当前的全部步骤，再写入模板步骤。确认继续吗？")) {
        event.preventDefault();
      } else if (mode === "replace") {
        let confirmation = form.querySelector("[name='replace_confirmed']");
        if (!confirmation) {
          confirmation = document.createElement("input");
          confirmation.type = "hidden";
          confirmation.name = "replace_confirmed";
          form.append(confirmation);
        }
        confirmation.value = "1";
      }
    });
  });

  const wireTabKeyboard = (tabs, activate) => {
    tabs.forEach((tab, index) => {
      tab.addEventListener("keydown", (event) => {
        let nextIndex = null;
        if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
        if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
        if (event.key === "Home") nextIndex = 0;
        if (event.key === "End") nextIndex = tabs.length - 1;
        if (nextIndex === null) return;
        event.preventDefault();
        const nextTab = tabs[nextIndex];
        nextTab.focus();
        activate(nextTab);
      });
    });
  };

  // Keep the experiment page focused on one work area at a time. The panels
  // remain in the DOM so existing links, form actions and accessibility
  // fallbacks continue to work when JavaScript is unavailable.
  const experimentWorkspace = document.querySelector("[data-experiment-workspace]");
  if (experimentWorkspace) {
    experimentWorkspace.classList.add("tabs-ready");
    const tabs = [...document.querySelectorAll("[data-experiment-tab]")];
    const panels = [...experimentWorkspace.querySelectorAll("[data-experiment-panel]")];
    const tabForHash = {
      overview: "overview", protocol: "protocol", batches: "batches",
      "experiment-batches": "batches", "experiment-steps": "protocol", "step-templates": "protocol",
      "new-record": "batches", "record-history": "batches", "experiment-record-index": "batches",
    };
    const setExperimentTab = (value, updateHash = true) => {
      const tab = ["overview", "protocol", "batches"].includes(value) ? value : "overview";
      experimentWorkspace.dataset.activeTab = tab;
      panels.forEach((panel) => { panel.hidden = panel.dataset.experimentPanel !== tab; });
      const activePanels = panels.filter((panel) => panel.dataset.experimentPanel === tab);
      const activeDetails = activePanels.filter((panel) => panel.matches("details"));
      if (activeDetails.length && activeDetails.every((panel) => !panel.open)) activeDetails[0].open = true;
      tabs.forEach((link) => {
        const active = link.dataset.experimentTab === tab;
        link.classList.toggle("active", active);
        link.setAttribute("aria-selected", active ? "true" : "false");
        link.tabIndex = active ? 0 : -1;
        if (active) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
      if (updateHash && window.history?.replaceState) window.history.replaceState(null, "", `#${tab}`);
    };
    let initialTab = new URLSearchParams(window.location.search).get("view") || "";
    const hashName = window.location.hash.replace(/^#/, "");
    if (!initialTab && hashName) initialTab = tabForHash[hashName] || "";
    if (new URLSearchParams(window.location.search).has("record_template_id")) initialTab = "batches";
    setExperimentTab(initialTab || "overview", false);
    tabs.forEach((link) => link.addEventListener("click", (event) => {
      event.preventDefault();
      setExperimentTab(link.dataset.experimentTab);
    }));
    wireTabKeyboard(tabs, (link) => setExperimentTab(link.dataset.experimentTab));
    document.querySelectorAll("[data-experiment-tab-link]").forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        setExperimentTab(link.dataset.experimentTabLink);
        const target = document.querySelector(link.getAttribute("href"));
        target?.scrollIntoView({block: "start", behavior: "smooth"});
      });
    });
    window.addEventListener("hashchange", () => {
      const next = tabForHash[window.location.hash.replace(/^#/, "")];
      if (next) setExperimentTab(next, false);
    });
  }

  const batchWorkspace = document.querySelector("[data-batch-workspace]");
  if (batchWorkspace) {
    batchWorkspace.classList.add("tabs-ready");
    const tabs = [...document.querySelectorAll("[data-batch-tab]")];
    const panels = [...batchWorkspace.querySelectorAll("[data-batch-panel]")];
    const tabForHash = {
      "batch-steps": "steps", "new-record": "records", "batch-records": "records",
      "batch-parameters": "resources", "batch-samples": "resources",
    };
    const hashForTab = {steps: "batch-steps", records: "new-record", resources: "batch-parameters"};
    const setBatchTab = (value, updateHash = true) => {
      const tab = ["steps", "records", "resources"].includes(value) ? value : "steps";
      batchWorkspace.dataset.activeBatchTab = tab;
      panels.forEach((panel) => { panel.hidden = panel.dataset.batchPanel !== tab; });
      const activePanels = panels.filter((panel) => panel.dataset.batchPanel === tab);
      const activeDetails = activePanels.filter((panel) => panel.matches("details"));
      if (activeDetails.length && activeDetails.every((panel) => !panel.open)) activeDetails[0].open = true;
      tabs.forEach((link) => {
        const active = link.dataset.batchTab === tab;
        link.classList.toggle("active", active);
        link.setAttribute("aria-selected", active ? "true" : "false");
        link.tabIndex = active ? 0 : -1;
        if (active) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
      if (updateHash && window.history?.replaceState) window.history.replaceState(null, "", `#${hashForTab[tab]}`);
    };
    const hashName = window.location.hash.replace(/^#/, "");
    let initialTab = tabForHash[hashName] || new URLSearchParams(window.location.search).get("view") || "steps";
    if (new URLSearchParams(window.location.search).has("record_template_id")) initialTab = "records";
    setBatchTab(initialTab, false);
    tabs.forEach((link) => link.addEventListener("click", (event) => {
      event.preventDefault();
      setBatchTab(link.dataset.batchTab);
    }));
    wireTabKeyboard(tabs, (link) => setBatchTab(link.dataset.batchTab));
    document.querySelectorAll("[data-batch-tab-link]").forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        setBatchTab(link.dataset.batchTabLink);
        document.querySelector(link.getAttribute("href"))?.scrollIntoView({block: "start", behavior: "smooth"});
      });
    });
    window.addEventListener("hashchange", () => {
      const next = tabForHash[window.location.hash.replace(/^#/, "")];
      if (next) setBatchTab(next, false);
    });
  }

  const recordWorkspace = document.querySelector("[data-record-workspace]");
  if (recordWorkspace) {
    recordWorkspace.classList.add("tabs-ready");
    const tabs = [...document.querySelectorAll("[data-record-tab]")];
    const panels = [...recordWorkspace.querySelectorAll("[data-record-panel]")];
    const tabForHash = {
      "record-view": "view", "record-files": "files", "record-edit": "edit",
      "record-history": "history", "record-template-tools": "history",
    };
    const setRecordTab = (value, updateHash = true) => {
      const tab = ["view", "files", "edit", "history"].includes(value) ? value : "view";
      recordWorkspace.dataset.activeRecordTab = tab;
      panels.forEach((panel) => { panel.hidden = panel.dataset.recordPanel !== tab; });
      const activePanels = panels.filter((panel) => panel.dataset.recordPanel === tab);
      const activeDetails = activePanels.filter((panel) => panel.matches("details"));
      if (activeDetails.length && activeDetails.every((panel) => !panel.open)) activeDetails[0].open = true;
      tabs.forEach((link) => {
        const active = link.dataset.recordTab === tab;
        link.classList.toggle("active", active);
        link.setAttribute("aria-selected", active ? "true" : "false");
        link.tabIndex = active ? 0 : -1;
        if (active) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
      if (updateHash && window.history?.replaceState) window.history.replaceState(null, "", `#${tab === "view" ? "record-view" : `record-${tab}`}`);
    };
    const hashName = window.location.hash.replace(/^#/, "");
    setRecordTab(tabForHash[hashName] || new URLSearchParams(window.location.search).get("view") || "view", false);
    tabs.forEach((link) => link.addEventListener("click", (event) => {
      event.preventDefault();
      setRecordTab(link.dataset.recordTab);
    }));
    wireTabKeyboard(tabs, (link) => setRecordTab(link.dataset.recordTab));
    document.querySelectorAll("[data-record-tab-link]").forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        setRecordTab(link.dataset.recordTabLink);
        document.querySelector(link.getAttribute("href"))?.scrollIntoView({block: "start", behavior: "smooth"});
      });
    });
    window.addEventListener("hashchange", () => {
      const next = tabForHash[window.location.hash.replace(/^#/, "")];
      if (next) setRecordTab(next, false);
    });
  }
  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", () => {
      const target = document.querySelector(link.getAttribute("href"));
      if (target?.matches("details")) target.open = true;
    });
  });
  document.querySelectorAll(".flash-close").forEach((button) => {
    button.addEventListener("click", () => button.closest(".flash")?.remove());
  });
  document.querySelectorAll(".reveal-secret").forEach((button) => {
    button.addEventListener("click", () => {
      const input = button.closest(".secret-field")?.querySelector("input");
      if (!input) return;
      input.type = input.type === "password" ? "text" : "password";
      button.innerHTML = `<i data-lucide="${input.type === "password" ? "eye" : "eye-off"}"></i>`;
      if (window.lucide) window.lucide.createIcons();
    });
  });
  document.querySelectorAll(".copy-value").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copy || "");
        const original = button.innerHTML;
        button.textContent = "已复制";
        window.setTimeout(() => {
          button.innerHTML = original;
          if (window.lucide) window.lucide.createIcons();
        }, 1600);
      } catch (_error) {
        window.alert("复制失败，请手动选择链接。");
      }
    });
  });

  document.querySelectorAll("[data-parameter-builder]").forEach((builder) => {
    const rows = builder.querySelector("[data-parameter-rows]");
    builder.querySelector("[data-add-parameter]")?.addEventListener("click", () => {
      const source = rows?.querySelector(".parameter-input-row");
      if (!source || !rows) return;
      const clone = source.cloneNode(true);
      clone.querySelectorAll("input").forEach((input) => { input.value = ""; });
      rows.append(clone);
      if (window.lucide) window.lucide.createIcons();
      clone.querySelector("input")?.focus();
    });
    rows?.addEventListener("click", (event) => {
      const removeButton = event.target.closest("[data-remove-parameter]");
      if (!removeButton) return;
      const row = removeButton.closest(".parameter-input-row");
      const rowCount = rows.querySelectorAll(".parameter-input-row").length;
      if (rowCount > 1) row?.remove();
      else row?.querySelectorAll("input").forEach((input) => { input.value = ""; });
    });
  });

  document.querySelectorAll("[data-template-select]").forEach((select) => {
    const container = select.closest("form");
    const viewLink = container?.querySelector("[data-template-view]");
    const updateViewLink = () => {
      const option = select.options[select.selectedIndex];
      if (viewLink && option?.dataset.viewUrl) viewLink.href = option.dataset.viewUrl;
    };
    select.addEventListener("change", updateViewLink);
    updateViewLink();
  });

  const aiOpenButtons = Array.from(document.querySelectorAll("[data-open-ai-assistant]"));
  const aiOpenButton = aiOpenButtons[0] || null;
  const aiDock = document.querySelector("#ai-dock");
  const aiMessages = document.querySelector("#ai-messages");
  const aiComposer = document.querySelector("#ai-composer");
  const aiInput = document.querySelector("#ai-message-input");
  const aiFiles = document.querySelector("#ai-file-input");
  const aiFileList = document.querySelector("#ai-file-list");
  const aiExport = document.querySelector("#ai-export-chat");
  const aiModelLabel = document.querySelector("#ai-model-label");
  const aiHistoryList = document.querySelector("#ai-history-list");
  const aiHistoryCount = document.querySelector("#ai-history-count");
  const aiHistorySearch = document.querySelector("#ai-history-search");
  const aiHistoryLevel = document.querySelector("#ai-history-level");
  const aiHistoryPerPage = document.querySelector("#ai-history-per-page");
  const aiHistoryResults = document.querySelector("#ai-history-results");
  const aiHistoryPrev = document.querySelector("#ai-history-prev");
  const aiHistoryNext = document.querySelector("#ai-history-next");
  const aiHistoryPageLabel = document.querySelector("#ai-history-page");
  const aiKnowledgeList = document.querySelector("#ai-knowledge-list");
  const aiKnowledgeCount = document.querySelector("#ai-knowledge-count");
  const aiKnowledgeCreateForm = document.querySelector("#ai-knowledge-create-form");
  const aiKnowledgeSearch = document.querySelector("#ai-knowledge-search");
  const aiKnowledgePerPage = document.querySelector("#ai-knowledge-per-page");
  const aiKnowledgeSelectPage = document.querySelector("#ai-knowledge-select-page");
  const aiKnowledgeSelectMatches = document.querySelector("#ai-knowledge-select-matches");
  const aiKnowledgeTotal = document.querySelector("#ai-knowledge-total");
  const aiKnowledgeSelected = document.querySelector("#ai-knowledge-selected");
  const aiKnowledgeBulkEnabled = document.querySelector("#ai-knowledge-bulk-enabled");
  const aiKnowledgeDescriptionMode = document.querySelector("#ai-knowledge-description-mode");
  const aiKnowledgeDescriptionValue = document.querySelector("#ai-knowledge-description-value");
  const aiKnowledgeInstructionMode = document.querySelector("#ai-knowledge-instruction-mode");
  const aiKnowledgeInstructionValue = document.querySelector("#ai-knowledge-instruction-value");
  const aiKnowledgeBulkSave = document.querySelector("#ai-knowledge-bulk-save");
  const aiKnowledgeBulkDelete = document.querySelector("#ai-knowledge-bulk-delete");
  const aiKnowledgePrev = document.querySelector("#ai-knowledge-prev");
  const aiKnowledgeNext = document.querySelector("#ai-knowledge-next");
  const aiKnowledgePageLabel = document.querySelector("#ai-knowledge-page");
  const aiPromptForm = document.querySelector("#ai-prompt-form");
  const aiCustomPrompt = document.querySelector("#ai-custom-prompt");
  const aiPromptStatus = document.querySelector("#ai-prompt-status");
  const aiWebAccess = document.querySelector("#ai-web-access");
  const aiStop = document.querySelector("#ai-stop");
  const aiTaskStatus = document.querySelector("#ai-task-status");
  const aiCompletionToast = document.querySelector("#ai-completion-toast");
  const aiConversationSidebar = document.querySelector("#ai-conversation-sidebar");
  const aiConversationList = document.querySelector("#ai-conversation-list");
  const aiConversationSearch = document.querySelector("#ai-conversation-search");
  const aiConversationTotal = document.querySelector("#ai-conversation-total");
  const aiConversationSelectPage = document.querySelector("#ai-conversation-select-page");
  const aiConversationSelectMatches = document.querySelector("#ai-conversation-select-matches");
  const aiConversationPerPage = document.querySelector("#ai-conversation-per-page");
  const aiConversationSelected = document.querySelector("#ai-conversation-selected");
  const aiConversationTitleMode = document.querySelector("#ai-conversation-title-mode");
  const aiConversationTitleValue = document.querySelector("#ai-conversation-title-value");
  const aiConversationBulkSave = document.querySelector("#ai-conversation-bulk-save");
  const aiConversationBulkDelete = document.querySelector("#ai-conversation-bulk-delete");
  const aiConversationPrev = document.querySelector("#ai-conversation-prev");
  const aiConversationNext = document.querySelector("#ai-conversation-next");
  const aiConversationPageLabel = document.querySelector("#ai-conversation-page");
  const aiChatTitle = document.querySelector("#ai-chat-title");
  const aiContextDialog = document.querySelector("#ai-context-dialog");
  const aiContextProvider = document.querySelector("#ai-context-provider");
  const aiContextSummary = document.querySelector("#ai-context-summary");
  const aiContextSources = document.querySelector("#ai-context-sources");
  const aiContextWarning = document.querySelector("#ai-context-warning");
  const aiContextConfirm = document.querySelector("#ai-context-confirm");
  const aiContextPage = document.querySelector("#ai-context-page");
  const aiExperimentSourceOpen = document.querySelector("#ai-experiment-source-open");
  const aiKnowledgeSourceOpen = document.querySelector("#ai-knowledge-source-open");
  const aiContextPageClose = document.querySelector("#ai-context-page-close");
  const aiContextPageTitle = document.querySelector("#ai-context-page-title");
  const aiContextPageDescription = document.querySelector("#ai-context-page-description");
  const aiContextPageIcon = document.querySelector(".ai-context-page-icon");
  const aiInputCount = document.querySelector("#ai-input-count");
  const resizeAiInput = () => {
    if (!aiInput) return;
    aiInput.style.height = "auto";
    const maxHeight = Number.parseFloat(window.getComputedStyle(aiInput).maxHeight) || 190;
    const nextHeight = Math.min(aiInput.scrollHeight, maxHeight);
    aiInput.style.height = `${nextHeight}px`;
    aiInput.style.overflowY = aiInput.scrollHeight > maxHeight ? "auto" : "hidden";
  };
  const syncAiInputMeta = () => {
    if (aiInputCount) aiInputCount.textContent = (aiInput?.value.length || 0).toLocaleString();
    resizeAiInput();
  };
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const assistantPage = {
    type: document.body.dataset.assistantPageType || "",
    id: document.body.dataset.assistantPageId || "",
  };
  let aiConversationId = window.localStorage.getItem("research-assistant-conversation") || "";
  let aiLoaded = false;
  let aiExperimentOptions = [];
  let aiBatchOptions = [];
  let aiRecordOptions = [];
  let aiPageScope = {};
  let aiProjectOptions = [];
  let aiHistoryPage = 1;
  let aiKnowledgeOptions = [];
  let aiSelectedKnowledgeBaseIds = new Set();
  let aiKnowledgeContextOwner = null;
  let aiKnowledgePage = 1;
  let aiKnowledgePagination = {page: 1, pages: 0, per_page: 8, total: 0, has_prev: false, has_next: false};
  let aiKnowledgeSelectionScope = "page";
  let aiKnowledgeSearchTimer = null;
  const aiKnowledgeDocumentStates = new Map();
  let aiConversationOptions = [];
  let aiConversationPage = 1;
  let aiConversationPagination = {page: 1, pages: 0, per_page: 8, total: 0, has_prev: false, has_next: false};
  let aiConversationSelectionScope = "page";
  let aiConversationSearchTimer = null;
  let aiRequestRunning = false;
  let aiAbortController = null;
  let aiTaskStartedAt = 0;
  let aiTaskTimer = null;
  const baseDocumentTitle = document.title;
  const aiWindowStorageKey = "research-assistant-window-state-v3";
  const aiChannel = "BroadcastChannel" in window ? new BroadcastChannel("research-assistant-ai") : null;
  const hideAiNotice = () => {
    if (aiCompletionToast) aiCompletionToast.hidden = true;
    aiOpenButtons.forEach((button) => button.classList.remove("complete"));
    document.title = baseDocumentTitle;
  };

  const showAiNotice = (message, failed = false) => {
    if (!aiCompletionToast) return;
    aiCompletionToast.querySelector("b").textContent = failed ? "AI 运行失败" : "AI 已完成";
    aiCompletionToast.querySelector("small").textContent = message;
    aiCompletionToast.classList.toggle("failed", failed);
    aiCompletionToast.hidden = false;
    aiOpenButtons.forEach((button) => button.classList.toggle("complete", !failed));
    document.title = `${failed ? "!" : "✓"} ${failed ? "AI 运行失败" : "AI 已完成"} · ${baseDocumentTitle}`;
  };

  const makeElement = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };

  const setAiTaskStatus = (label = "") => {
    if (!aiTaskStatus) return;
    if (!label) {
      aiTaskStatus.hidden = true;
      window.clearInterval(aiTaskTimer);
      aiTaskTimer = null;
      return;
    }
    aiTaskStatus.hidden = false;
    aiTaskStatus.querySelector("span").textContent = label;
    const updateElapsed = () => {
      const seconds = Math.max(0, Math.floor((Date.now() - aiTaskStartedAt) / 1000));
      aiTaskStatus.querySelector("time").textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
    };
    updateElapsed();
    window.clearInterval(aiTaskTimer);
    aiTaskTimer = window.setInterval(updateElapsed, 1000);
  };

  const readAiWindowState = () => {
    try { return JSON.parse(window.localStorage.getItem(aiWindowStorageKey) || "{}"); }
    catch (_error) { return {}; }
  };

  const saveAiWindowState = () => {
    if (!aiDock) return;
    if (aiDock.classList.contains("ai-maximized")) {
      window.localStorage.setItem(aiWindowStorageKey, JSON.stringify({
        ...readAiWindowState(), maximized: true,
      }));
      return;
    }
    const rect = aiDock.getBoundingClientRect();
    window.localStorage.setItem(aiWindowStorageKey, JSON.stringify({
      left: Math.round(rect.left), top: Math.round(rect.top), width: Math.round(rect.width),
      height: Math.round(rect.height), maximized: false,
    }));
  };

  const fitAiWindowToViewport = () => {
    if (!aiDock || aiDock.classList.contains("ai-maximized")) return;
    const width = Math.min(aiDock.offsetWidth, Math.max(window.innerWidth - 16, 1));
    const height = Math.min(aiDock.offsetHeight, Math.max(window.innerHeight - 16, 1));
    if (aiDock.offsetWidth !== width) aiDock.style.width = `${width}px`;
    if (aiDock.offsetHeight !== height) aiDock.style.height = `${height}px`;
    const rect = aiDock.getBoundingClientRect();
    aiDock.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - rect.width - 8))}px`;
    aiDock.style.top = `${Math.max(8, Math.min(rect.top, window.innerHeight - rect.height - 8))}px`;
    aiDock.style.right = "auto";
    aiDock.style.bottom = "auto";
  };

  const applyAiWindowState = () => {
    if (!aiDock) return;
    const state = readAiWindowState();
    if (state.width) aiDock.style.width = `${Math.min(state.width, window.innerWidth - 24)}px`;
    if (state.height) aiDock.style.height = `${Math.min(state.height, window.innerHeight - 24)}px`;
    aiDock.classList.toggle("ai-maximized", Boolean(state.maximized));
    if (!state.maximized && Number.isFinite(state.left) && Number.isFinite(state.top)) {
      aiDock.style.left = `${state.left}px`;
      aiDock.style.top = `${state.top}px`;
      aiDock.style.right = "auto";
      aiDock.style.bottom = "auto";
    }
    window.requestAnimationFrame(fitAiWindowToViewport);
  };

  const copyText = async (text, button) => {
    try {
      await navigator.clipboard.writeText(text || "");
      const original = button.innerHTML;
      button.innerHTML = '<i data-lucide="check"></i>';
      button.title = "已复制";
      if (window.lucide) window.lucide.createIcons();
      window.setTimeout(() => {
        button.innerHTML = original;
        button.title = "复制回复";
        if (window.lucide) window.lucide.createIcons();
      }, 1200);
    } catch (_error) {
      button.title = "复制失败";
    }
  };

  const makeAiActionButton = (className, icon, label) => {
    const button = makeElement("button", className);
    button.type = "button";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.innerHTML = `<i data-lucide="${icon}"></i>`;
    return button;
  };

  const aiWelcome = () => {
    aiMessages.innerHTML = "";
    const welcome = makeElement("div", "ai-welcome");
    const mark = makeElement("span", "ai-welcome-mark");
    mark.innerHTML = '<i data-lucide="sparkles"></i>';
    welcome.append(mark, makeElement("b", "", "今天想推进哪项科研工作？"));
    welcome.append(makeElement("p", "", "整理实验、比较历史、生成计划或检索知识库。页面写入前都会展示差异。"));
    aiMessages.append(welcome);
    if (window.lucide) window.lucide.createIcons();
  };

  const renderAiMessage = (message) => {
    const article = makeElement("article", `ai-message ${message.role}`);
    article.dataset.messageId = message.id || "";
    const head = makeElement("div", "ai-message-head");
    const avatar = makeElement("span", "ai-message-avatar");
    avatar.innerHTML = `<i data-lucide="${message.role === "user" ? "user-round" : "sparkles"}"></i>`;
    const label = makeElement("small", "ai-message-role", message.role === "user" ? "你" : "AI 助手");
    head.append(avatar, label);
    const content = makeElement("div", "ai-message-content", message.content);
    article.append(head, content);

    if (message.role === "assistant") {
      const actions = makeElement("div", "ai-message-actions");
      const copy = makeAiActionButton("ai-copy-message", "copy", "复制回复");
      copy.addEventListener("click", () => copyText(message.content, copy));
      const quote = makeAiActionButton("ai-quote-message", "quote", "引用回复");
      quote.addEventListener("click", () => {
        if (!aiInput) return;
        const excerpt = (message.content || "").slice(0, 1200);
        aiInput.value = `针对这段回复继续：\n> ${excerpt.replaceAll("\n", "\n> ")}\n\n`;
        aiInput.focus();
      });
      actions.append(copy, quote);
      if (message.can_regenerate) {
        const regenerate = makeAiActionButton("ai-regenerate-message", "refresh-cw", "重新生成回复");
        regenerate.dataset.messageId = message.id;
        actions.append(regenerate);
      }
      if (message.can_delete) {
        const remove = makeAiActionButton("ai-delete-message", "trash-2", "删除回复");
        remove.dataset.messageId = message.id;
        actions.append(remove);
      }
      article.append(actions);
    } else if (message.can_edit || message.can_delete) {
      const actions = makeElement("div", "ai-message-actions");
      if (message.can_edit) {
        const edit = makeAiActionButton("ai-edit-message", "pencil", "编辑提问并重新生成");
        edit.dataset.messageId = message.id;
        actions.append(edit);
      }
      if (message.can_delete) {
        const remove = makeAiActionButton("ai-delete-message", "trash-2", "删除提问");
        remove.dataset.messageId = message.id;
        actions.append(remove);
      }
      article.append(actions);
    }

    if (message.role === "assistant" && (message.model_name || message.created_at)) {
      const meta = makeElement("div", "ai-message-meta");
      meta.append(makeElement("span", "", `${message.model_name || "模型未记录"} · ${message.created_at || ""}`));
      if (message.has_prompt_snapshot) {
        const promptLink = makeElement("a", "", "查看本次提示词");
        promptLink.href = `/assistant/messages/${message.id}/prompt.txt`;
        meta.append(promptLink);
      }
      article.append(meta);
    }

    if (message.requires_human_review) {
      const warning = makeElement("div", "ai-human-review");
      warning.append(makeElement("b", "", "需要人工核验"));
      warning.append(makeElement("span", "", "此回复涉及剂量、临床解释或统计结论，不能直接作为最终判断。"));
      article.append(warning);
    }

    if (message.attachments?.length) {
      const files = makeElement("div", "ai-message-files");
      message.attachments.forEach((file) => {
        const link = makeElement("a", "", `${file.name} · ${file.size}`);
        link.href = `/assistant/files/${file.id}/download`;
        files.append(link);
      });
      article.append(files);
    }

    if (message.references?.length) {
      const references = makeElement("div", "ai-references");
      references.append(makeElement("b", "", "引用来源"));
      message.references.forEach((reference, index) => {
        const row = makeElement("div", "ai-reference-row");
        const marker = reference.citation ? `[${reference.citation}]` : `[${index + 1}]`;
        const link = makeElement("a", "", `${marker} ${reference.title || reference.url}`);
        link.href = reference.url;
        if (/^https?:\/\//.test(reference.url)) {
          link.target = "_blank";
          link.rel = "noopener noreferrer";
        }
        row.append(link);
        if (reference.excerpt) row.append(makeElement("small", "", reference.excerpt));
        references.append(row);
      });
      article.append(references);
    }

    if (message.proposal) {
      const proposal = makeElement("section", "ai-proposal");
      const heading = makeElement("div", "ai-proposal-head");
      heading.append(makeElement("b", "", "页面修改提案"), makeElement("span", "", message.reverted ? "已撤销" : (message.applied ? "已保存" : "等待确认")));
      proposal.append(heading);
      if (message.proposal.action === "create_experiment") {
        const target = makeElement("label", "ai-proposal-target");
        const targetCopy = makeElement("span", "");
        targetCopy.append(makeElement("b", "", "所属科研项目"));
        targetCopy.append(makeElement("small", "", aiProjectOptions.length ? "保存前确认实验计划归属" : "当前没有项目，将保存到未分类项目"));
        const select = document.createElement("select");
        select.className = "ai-proposal-project";
        select.disabled = Boolean(message.applied);
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = aiProjectOptions.length ? "请选择科研项目" : "未分类项目";
        select.append(placeholder);
        aiProjectOptions.forEach((project) => {
          const option = document.createElement("option");
          option.value = String(project.id);
          option.textContent = `${project.code || "未编号"} · ${project.title}`;
          select.append(option);
        });
        const proposedProjectId = String(message.proposal.project_id || "");
        if (proposedProjectId && !aiProjectOptions.some((project) => String(project.id) === proposedProjectId)) {
          const unavailable = document.createElement("option");
          unavailable.value = proposedProjectId;
          unavailable.textContent = `科研项目 #${proposedProjectId}（当前不可用）`;
          select.append(unavailable);
        }
        select.value = proposedProjectId || (aiProjectOptions.length === 1 ? String(aiProjectOptions[0].id) : "");
        target.append(targetCopy, select);
        proposal.append(target);
      }
      message.proposal.diff?.forEach((change) => {
        const row = makeElement("div", "ai-diff-row");
        const select = makeElement("label", "ai-diff-select");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "ai-diff-checkbox";
        checkbox.value = change.id || "";
        checkbox.checked = true;
        checkbox.disabled = Boolean(message.applied);
        const changeBody = makeElement("div", "");
        changeBody.append(makeElement("b", "", change.field));
        const values = makeElement("div", "ai-diff-values");
        const before = makeElement("div", "before");
        before.append(makeElement("small", "", "修改前"), makeElement("pre", "", change.before || "（空）"));
        const after = makeElement("div", "after");
        after.append(makeElement("small", "", "修改后"), makeElement("pre", "", change.after || "（空）"));
        values.append(before, after);
        changeBody.append(values);
        select.append(checkbox, changeBody);
        row.append(select);
        proposal.append(row);
      });
      if (!message.applied) {
        const apply = makeElement("button", "btn primary full ai-apply-proposal", "确认并保存到页面");
        apply.type = "button";
        apply.dataset.messageId = message.id;
        proposal.append(apply);
      } else if (message.can_revert && !message.reverted) {
        const revert = makeElement("button", "btn full ai-revert-proposal", "撤销这次 AI 修改");
        revert.type = "button";
        revert.dataset.messageId = message.id;
        proposal.append(revert);
      }
      article.append(proposal);
    }
    aiMessages.append(article);
    if (window.lucide) window.lucide.createIcons();
    aiMessages.scrollTop = aiMessages.scrollHeight;
  };

  const setConversation = (conversation) => {
    if (!conversation) {
      aiConversationId = "";
      aiExport?.classList.add("disabled");
      if (aiChatTitle) aiChatTitle.textContent = "科研 AI 助手";
      aiWelcome();
      return;
    }
    aiConversationId = String(conversation.id);
    if (aiChatTitle) aiChatTitle.textContent = conversation.title || "新对话";
    window.localStorage.setItem("research-assistant-conversation", aiConversationId);
    if (aiExport) {
      aiExport.href = `/assistant/conversations/${conversation.id}/export.md`;
      aiExport.classList.remove("disabled");
    }
    aiMessages.innerHTML = "";
    if (!conversation.messages.length) aiWelcome();
    conversation.messages.forEach(renderAiMessage);
    renderConversationList();
  };

  const updateConversationSelectionState = () => {
    const boxes = Array.from(aiConversationList?.querySelectorAll(".ai-conversation-select input") || []);
    const checked = boxes.filter((input) => input.checked).length;
    const count = aiConversationSelectionScope === "all" ? aiConversationPagination.total : checked;
    if (aiConversationSelectPage) {
      aiConversationSelectPage.checked = Boolean(boxes.length) && checked === boxes.length;
      aiConversationSelectPage.indeterminate = checked > 0 && checked < boxes.length;
    }
    if (aiConversationSelectMatches) {
      aiConversationSelectMatches.classList.toggle("active", aiConversationSelectionScope === "all");
      aiConversationSelectMatches.setAttribute("aria-pressed", aiConversationSelectionScope === "all" ? "true" : "false");
      aiConversationSelectMatches.textContent = aiConversationSelectionScope === "all" ? "已选筛选全部" : "筛选全部";
    }
    if (aiConversationSelected) aiConversationSelected.textContent = `已选择 ${count} 个`;
    if (aiConversationBulkSave) aiConversationBulkSave.disabled = count === 0;
    if (aiConversationBulkDelete) aiConversationBulkDelete.disabled = count === 0;
  };

  const renderConversationList = () => {
    if (!aiConversationList) return;
    aiConversationList.innerHTML = "";
    aiConversationOptions.forEach((conversation) => {
      const row = makeElement("div", `ai-conversation-item${String(conversation.id) === String(aiConversationId) ? " active" : ""}`);
      row.dataset.conversationId = conversation.id;
      const select = makeElement("label", "ai-conversation-select");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = String(conversation.id);
      checkbox.checked = aiConversationSelectionScope === "all";
      checkbox.setAttribute("aria-label", `选择会话 ${conversation.title || "新对话"}`);
      select.append(checkbox);
      const open = makeElement("button", "ai-conversation-open");
      open.type = "button";
      open.dataset.conversationId = conversation.id;
      open.append(makeElement("b", "", conversation.title || "新对话"), makeElement("small", "", `${conversation.preview || "还没有消息"} · ${conversation.updated_at}`));
      const actions = makeElement("div", "ai-conversation-actions");
      const rename = makeAiActionButton("ai-rename-conversation", "pencil", "重命名会话");
      rename.dataset.conversationId = conversation.id;
      const remove = makeAiActionButton("ai-delete-conversation", "trash-2", "删除会话");
      remove.dataset.conversationId = conversation.id;
      actions.append(rename, remove);
      row.append(select, open, actions);
      aiConversationList.append(row);
    });
    if (!aiConversationOptions.length) aiConversationList.append(makeElement(
      "p", "", (aiConversationSearch?.value || "").trim() ? "没有匹配的会话" : "还没有历史聊天",
    ));
    updateConversationSelectionState();
    if (window.lucide) window.lucide.createIcons();
  };

  const selectedBatchIds = () => Array.from(
    aiHistoryList?.querySelectorAll('input[name="batch_ids"]:checked') || []
  ).map((input) => String(input.value));

  const selectedRecordIds = () => Array.from(
    aiHistoryList?.querySelectorAll('input[name="record_ids"]:checked') || []
  ).filter((input) => {
    const batchParent = input.closest("[data-history-batch-group]")?.querySelector("[data-batch-select-all]");
    return !batchParent?.checked;
  }).map((input) => String(input.value));

  const selectedExperimentIds = () => {
    const selected = Array.from(
      aiHistoryList?.querySelectorAll('input[name="experiment_ids"]:checked') || []
    ).map((input) => String(input.value));
    selectedBatchIds().forEach((batchId) => {
      const batch = aiBatchOptions.find((item) => String(item.id) === batchId);
      if (batch && !selected.includes(String(batch.experiment_id))) selected.push(String(batch.experiment_id));
    });
    selectedRecordIds().forEach((recordId) => {
      const record = aiRecordOptions.find((item) => String(item.id) === recordId);
      if (record && !selected.includes(String(record.experiment_id))) selected.push(String(record.experiment_id));
    });
    return selected;
  };

  const syncExperimentScopeControls = () => {
    aiHistoryList?.querySelectorAll("[data-history-batch-group]").forEach((group) => {
      const parent = group.querySelector("[data-batch-select-all]");
      const children = Array.from(group.querySelectorAll('input[name="record_ids"]'));
      if (!parent || !children.length) return;
      const checkedCount = children.filter((input) => input.checked).length;
      parent.checked = checkedCount === children.length;
      parent.indeterminate = checkedCount > 0 && checkedCount < children.length;
    });
    aiHistoryList?.querySelectorAll("[data-history-experiment-group]").forEach((group) => {
      const parent = group.querySelector("[data-experiment-select-all]");
      const children = Array.from(group.querySelectorAll('input[name="batch_ids"], input[name="record_ids"]'));
      if (!parent || !children.length) return;
      const checkedCount = children.filter((input) => input.checked).length;
      parent.checked = checkedCount === children.length;
      parent.indeterminate = checkedCount > 0 && checkedCount < children.length;
    });
  };

  const historyInputsMatchingFilter = () => Array.from(
    aiHistoryList?.querySelectorAll('input[name="experiment_ids"], input[name="batch_ids"], input[name="record_ids"]') || []
  ).filter((input) => {
    const experimentGroup = input.closest("[data-history-experiment-group]");
    const batchGroup = input.closest("[data-history-batch-group]");
    const recordRow = input.closest("[data-history-record]");
    return experimentGroup?.dataset.historyFilterMatch === "1"
      && (!batchGroup || batchGroup.dataset.historyFilterMatch === "1")
      && (!recordRow || recordRow.dataset.historyFilterMatch === "1");
  });

  const applyHistoryFilter = () => {
    if (!aiHistoryList) return;
    const needle = (aiHistorySearch?.value || "").trim().toLocaleLowerCase();
    const level = aiHistoryLevel?.value || "all";
    let visiblePlans = 0;
    let visibleBatches = 0;
    let visibleRecords = 0;
    aiHistoryList.querySelectorAll("[data-history-experiment-group]").forEach((group) => {
      const experimentMatches = !needle || (group.dataset.historySearch || "").includes(needle);
      let groupHasVisibleBatch = false;
      group.querySelectorAll("[data-history-batch-group]").forEach((batchGroup) => {
        const batchMatches = !needle || (batchGroup.dataset.historySearch || "").includes(needle);
        const recordRows = Array.from(batchGroup.querySelectorAll("[data-history-record]"));
        const recordMatches = recordRows.map((row) => (
          !needle || (row.dataset.historySearch || "").includes(needle)
        ));
        const hasMatchingRecord = recordMatches.some(Boolean);
        let batchVisible;
        if (level === "experiment") batchVisible = experimentMatches;
        else if (level === "batch") batchVisible = batchMatches;
        else if (level === "record") batchVisible = hasMatchingRecord;
        else batchVisible = experimentMatches || batchMatches || hasMatchingRecord;
        batchGroup.hidden = !batchVisible;
        if (batchVisible) {
          groupHasVisibleBatch = true;
          visibleBatches += 1;
        }
        recordRows.forEach((row, index) => {
          let recordVisible;
          if (level === "experiment") recordVisible = experimentMatches;
          else if (level === "batch") recordVisible = batchMatches;
          else if (level === "record") recordVisible = recordMatches[index];
          else recordVisible = experimentMatches || batchMatches || recordMatches[index];
          row.hidden = !batchVisible || !recordVisible;
          row.dataset.historyFilterMatch = row.hidden ? "0" : "1";
          if (!row.hidden) visibleRecords += 1;
        });
        batchGroup.dataset.historyFilterMatch = batchVisible ? "1" : "0";
        if ((needle || level !== "all") && batchGroup.tagName === "DETAILS") {
          batchGroup.open = batchVisible;
        }
      });
      const hasBatches = Boolean(group.querySelector("[data-history-batch-group]"));
      const groupVisible = level === "experiment"
        ? experimentMatches
        : (groupHasVisibleBatch || (!hasBatches && level === "all" && experimentMatches));
      group.hidden = !groupVisible;
      group.dataset.historyFilterMatch = groupVisible ? "1" : "0";
      if (groupVisible) visiblePlans += 1;
      if ((needle || level !== "all") && group.tagName === "DETAILS") group.open = groupVisible;
    });
    const matchedGroups = Array.from(
      aiHistoryList.querySelectorAll('[data-history-experiment-group][data-history-filter-match="1"]')
    );
    const requestedPerPage = Number.parseInt(aiHistoryPerPage?.value || "8", 10);
    const perPage = [8, 16, 32].includes(requestedPerPage) ? requestedPerPage : 8;
    const pageCount = Math.max(1, Math.ceil(matchedGroups.length / perPage));
    aiHistoryPage = Math.min(Math.max(1, aiHistoryPage), pageCount);
    const pageStart = (aiHistoryPage - 1) * perPage;
    matchedGroups.forEach((group, index) => {
      group.hidden = index < pageStart || index >= pageStart + perPage;
    });
    const noResults = aiHistoryList.querySelector("[data-history-no-results]");
    if (noResults) noResults.hidden = visiblePlans > 0;
    if (aiHistoryPageLabel) aiHistoryPageLabel.textContent = `第 ${aiHistoryPage} / ${pageCount} 页`;
    if (aiHistoryPrev) aiHistoryPrev.disabled = aiHistoryPage <= 1;
    if (aiHistoryNext) aiHistoryNext.disabled = aiHistoryPage >= pageCount;
    if (aiHistoryResults) {
      aiHistoryResults.textContent = `${visiblePlans} 个计划 · ${visibleBatches} 个批次 · ${visibleRecords} 条记录`;
    }
  };

  const updateHistoryCount = () => {
    syncExperimentScopeControls();
    const recordCount = selectedRecordIds().length;
    const executionCount = selectedBatchIds().length;
    const planCount = aiHistoryList?.querySelectorAll('input[name="experiment_ids"]:checked').length || 0;
    if (aiHistoryCount) {
      const parts = [];
      if (recordCount) parts.push(`${recordCount} 条记录`);
      if (executionCount) parts.push(`${executionCount} 个批次`);
      if (planCount) parts.push(`${planCount} 个计划`);
      aiHistoryCount.textContent = parts.length ? `已选择 ${parts.join("、")}` : "计划、批次与记录";
    }
    const pptLink = document.querySelector("#ai-create-ppt");
    if (pptLink) {
      const query = selectedExperimentIds().map((id) => `experiment_id=${encodeURIComponent(id)}`).join("&");
      pptLink.href = `/reports/presentation${query ? `?${query}` : ""}`;
    }
  };

  const renderExperimentScope = (
    experiments, batches, records, selectedIds = [], selectedExecutionIds = [],
    selectedRecordScopeIds = [], pageScope = {}, recordTotal = 0,
  ) => {
    if (!aiHistoryList) return;
    aiExperimentOptions = experiments || [];
    aiBatchOptions = batches || [];
    aiRecordOptions = records || [];
    aiPageScope = pageScope || {};
    const selectedPlans = new Set((selectedIds || []).map(String));
    const selectedExecutions = new Set((selectedExecutionIds || []).map(String));
    const selectedRecords = new Set((selectedRecordScopeIds || []).map(String));
    // Conversations created before execution-level scope stored only experiment IDs.
    selectedPlans.forEach((experimentId) => {
      aiBatchOptions
        .filter((batch) => String(batch.experiment_id) === experimentId)
        .forEach((batch) => selectedExecutions.add(String(batch.id)));
    });
    if (!selectedPlans.size && !selectedExecutions.size && !selectedRecords.size && aiPageScope.record_id) {
      selectedRecords.add(String(aiPageScope.record_id));
    } else if (!selectedPlans.size && !selectedExecutions.size && !selectedRecords.size && aiPageScope.batch_id) {
      selectedExecutions.add(String(aiPageScope.batch_id));
    } else if (!selectedPlans.size && !selectedExecutions.size && !selectedRecords.size && aiPageScope.experiment_id) {
      const currentBatches = aiBatchOptions.filter(
        (batch) => String(batch.experiment_id) === String(aiPageScope.experiment_id)
      );
      if (currentBatches.length) currentBatches.forEach((batch) => selectedExecutions.add(String(batch.id)));
      else selectedPlans.add(String(aiPageScope.experiment_id));
    } else if (!selectedPlans.size && !selectedExecutions.size && !selectedRecords.size && aiPageScope.project_id) {
      aiExperimentOptions
        .filter((experiment) => String(experiment.project_id || "") === String(aiPageScope.project_id))
        .forEach((experiment) => {
          const projectBatches = aiBatchOptions.filter((batch) => String(batch.experiment_id) === String(experiment.id));
          if (projectBatches.length) projectBatches.forEach((batch) => selectedExecutions.add(String(batch.id)));
          else selectedPlans.add(String(experiment.id));
        });
    }
    aiHistoryList.innerHTML = "";
    aiExperimentOptions.forEach((experiment, experimentIndex) => {
      const experimentBatches = aiBatchOptions.filter(
        (batch) => String(batch.experiment_id) === String(experiment.id)
      );
      const group = makeElement("details", "ai-history-experiment-group");
      group.dataset.historyExperimentGroup = String(experiment.id);
      group.dataset.historySearch = [
        experiment.title, experiment.code, experiment.status, experiment.updated_label,
      ].filter(Boolean).join(" ").toLocaleLowerCase();
      const experimentHasSelection = selectedPlans.has(String(experiment.id))
        || experimentBatches.some((batch) => selectedExecutions.has(String(batch.id)))
        || aiRecordOptions.some((record) => (
          String(record.experiment_id) === String(experiment.id) && selectedRecords.has(String(record.id))
        ));
      group.open = experimentIndex === 0 || experimentHasSelection;
      const summary = makeElement("summary", "ai-history-option ai-history-experiment");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = String(experiment.id);
      input.setAttribute("aria-label", `选择实验计划 ${experiment.title}`);
      if (experimentBatches.length) input.dataset.experimentSelectAll = String(experiment.id);
      else input.name = "experiment_ids";
      input.checked = selectedPlans.has(String(experiment.id));
      const copy = makeElement("span", "ai-history-node-copy");
      copy.append(makeElement("b", "", experiment.title));
      const experimentMeta = makeElement(
        "small", "", `${experiment.code} · ${experiment.status} · ${experimentBatches.length} 个批次 · 最后编辑 ${experiment.updated_label}`
      );
      experimentMeta.title = experiment.updated_title || experiment.updated_at || "";
      copy.append(experimentMeta);
      const chevron = document.createElement("i");
      chevron.dataset.lucide = "chevron-down";
      chevron.className = "ai-history-chevron";
      summary.append(input, copy, chevron);
      group.append(summary);
      if (experimentBatches.length) {
        const executionList = makeElement("div", "ai-history-execution-list");
        experimentBatches.forEach((batch, batchIndex) => {
          const batchRecords = aiRecordOptions.filter(
            (record) => String(record.batch_id) === String(batch.id)
          );
          const batchGroup = makeElement(batchRecords.length ? "details" : "section", "ai-history-batch-group");
          batchGroup.dataset.historyBatchGroup = String(batch.id);
          batchGroup.dataset.historySearch = [
            batch.code, batch.repeat_kind, batch.repeat_number, batch.group_name,
            batch.status, batch.start_date, batch.end_date, batch.updated_label,
          ].filter(Boolean).join(" ").toLocaleLowerCase();
          if (batchGroup.tagName === "DETAILS") {
            batchGroup.open = (experimentIndex === 0 && batchIndex === 0)
              || selectedExecutions.has(String(batch.id))
              || batchRecords.some((record) => selectedRecords.has(String(record.id)));
          }
          const executionLabel = makeElement(
            batchRecords.length ? "summary" : "label", "ai-history-option ai-history-execution"
          );
          const executionInput = document.createElement("input");
          executionInput.type = "checkbox";
          executionInput.name = "batch_ids";
          executionInput.value = String(batch.id);
          executionInput.dataset.experimentId = String(experiment.id);
          executionInput.setAttribute("aria-label", `选择实验批次 ${batch.code}`);
          if (batchRecords.length) executionInput.dataset.batchSelectAll = String(batch.id);
          executionInput.checked = selectedExecutions.has(String(batch.id));
          const executionCopy = makeElement("span", "ai-history-node-copy");
          executionCopy.append(makeElement("b", "", batch.code));
          const repeat = `${batch.repeat_kind} #${batch.repeat_number}`;
          const batchMeta = makeElement(
            "small", "", [repeat, batch.group_name, batch.status, `${batch.record_count || 0} 条记录`, `最后编辑 ${batch.updated_label}`].filter(Boolean).join(" · ")
          );
          batchMeta.title = batch.updated_title || batch.updated_at || "";
          executionCopy.append(batchMeta);
          executionLabel.append(executionInput, executionCopy);
          if (batchRecords.length) {
            const batchChevron = document.createElement("i");
            batchChevron.dataset.lucide = "chevron-down";
            batchChevron.className = "ai-history-chevron";
            executionLabel.append(batchChevron);
          }
          batchGroup.append(executionLabel);
          if (batchRecords.length) {
            const recordList = makeElement("div", "ai-history-record-list");
            batchRecords.forEach((record) => {
              const recordLabel = makeElement("label", "ai-history-option ai-history-record");
              recordLabel.dataset.historyRecord = String(record.id);
              recordLabel.dataset.historySearch = [
                `R-${record.id}`, record.record_date, record.operator, record.result,
                record.lifecycle_status, record.summary, record.updated_label,
              ].filter(Boolean).join(" ").toLocaleLowerCase();
              const recordInput = document.createElement("input");
              recordInput.type = "checkbox";
              recordInput.name = "record_ids";
              recordInput.value = String(record.id);
              recordInput.dataset.batchId = String(batch.id);
              recordInput.dataset.experimentId = String(experiment.id);
              recordInput.checked = selectedExecutions.has(String(batch.id)) || selectedRecords.has(String(record.id));
              recordInput.setAttribute("aria-label", `选择实验记录 R-${record.id}`);
              const recordCopy = makeElement("span", "ai-history-node-copy");
              recordCopy.append(makeElement("b", "", `R-${record.id} · ${record.record_date}`));
              const recordMeta = makeElement(
                "small", "", `${record.result} · ${record.operator} · ${record.summary} · 最后编辑 ${record.updated_label}`
              );
              recordMeta.title = record.updated_title || record.updated_at || "";
              recordCopy.append(recordMeta);
              recordLabel.append(recordInput, recordCopy);
              recordList.append(recordLabel);
            });
            batchGroup.append(recordList);
          }
          executionList.append(batchGroup);
        });
        group.append(executionList);
      } else {
        experimentMeta.textContent = `${experiment.code} · ${experiment.status} · 尚无实验批次 · 最后编辑 ${experiment.updated_label}`;
      }
      aiHistoryList.append(group);
    });
    if (!aiExperimentOptions.length) {
      aiHistoryList.append(makeElement("p", "", "还没有可选择的实验计划、批次或记录"));
    } else {
      const noResults = makeElement("p", "ai-history-no-results", "没有匹配的实验目录内容");
      noResults.dataset.historyNoResults = "1";
      noResults.hidden = true;
      aiHistoryList.append(noResults);
    }
    if (recordTotal > aiRecordOptions.length && aiHistoryResults) {
      aiHistoryResults.title = `记录较多，当前目录载入最近编辑的 ${aiRecordOptions.length}/${recordTotal} 条记录`;
    } else if (aiHistoryResults) {
      aiHistoryResults.removeAttribute("title");
    }
    if (window.lucide) window.lucide.createIcons();
    applyHistoryFilter();
    updateHistoryCount();
  };

  const appendExperimentScope = (data) => {
    data.set("experiment_scope_present", "1");
    data.set("batch_scope_present", "1");
    data.set("record_scope_present", "1");
    Array.from(aiHistoryList?.querySelectorAll('input[name="experiment_ids"]:checked') || [])
      .forEach((input) => data.append("experiment_ids", input.value));
    selectedBatchIds().forEach((itemId) => data.append("batch_ids", itemId));
    selectedRecordIds().forEach((itemId) => data.append("record_ids", itemId));
  };

  const selectedKnowledgeBaseIds = () => Array.from(aiSelectedKnowledgeBaseIds);

  const updateKnowledgeCount = () => {
    const count = selectedKnowledgeBaseIds().length;
    if (aiKnowledgeCount) aiKnowledgeCount.textContent = count ? `已选择 ${count} 个知识库` : "本地文档与使用说明";
  };

  const postAiForm = async (url, data) => {
    data.set("csrf_token", csrfToken);
    const response = await fetch(url, {method: "POST", body: data});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "操作失败");
    return result;
  };

  const knowledgeBaseItem = (baseId) => aiKnowledgeList?.querySelector(
    `[data-knowledge-base-id="${CSS.escape(String(baseId))}"]`,
  );

  const updateKnowledgeSelectionState = () => {
    const boxes = Array.from(aiKnowledgeList?.querySelectorAll(".ai-knowledge-manage-select input") || []);
    const checked = boxes.filter((input) => input.checked).length;
    const count = aiKnowledgeSelectionScope === "all" ? aiKnowledgePagination.total : checked;
    if (aiKnowledgeSelectPage) {
      aiKnowledgeSelectPage.checked = Boolean(boxes.length) && checked === boxes.length;
      aiKnowledgeSelectPage.indeterminate = checked > 0 && checked < boxes.length;
    }
    if (aiKnowledgeSelectMatches) {
      aiKnowledgeSelectMatches.classList.toggle("active", aiKnowledgeSelectionScope === "all");
      aiKnowledgeSelectMatches.setAttribute("aria-pressed", aiKnowledgeSelectionScope === "all" ? "true" : "false");
      aiKnowledgeSelectMatches.textContent = aiKnowledgeSelectionScope === "all" ? "已选筛选全部" : "选择筛选全部";
    }
    if (aiKnowledgeSelected) aiKnowledgeSelected.textContent = `已选择 ${count} 个`;
    if (aiKnowledgeBulkSave) aiKnowledgeBulkSave.disabled = count === 0;
    if (aiKnowledgeBulkDelete) aiKnowledgeBulkDelete.disabled = count === 0;
  };

  const documentStateForBase = (base) => {
    const key = String(base.id);
    const initialPagination = base.document_pagination || {
      page: 1, pages: 0, per_page: 8, total: base.documents?.length || 0,
      has_prev: false, has_next: false, page_sizes: [8, 16, 32],
    };
    let state = aiKnowledgeDocumentStates.get(key);
    const requiresRefresh = Boolean(state && (
      state.query || state.page !== 1 || state.perPage !== initialPagination.per_page
    ));
    if (!state) {
      state = {
        query: "", page: 1, perPage: initialPagination.per_page || 8,
        pagination: initialPagination, documents: base.documents || [],
        selectionScope: "page", searchTimer: null, loading: false, requestId: 0,
      };
      aiKnowledgeDocumentStates.set(key, state);
    } else if (!requiresRefresh) {
      state.pagination = initialPagination;
      state.documents = base.documents || [];
    }
    return {state, requiresRefresh};
  };

  const updateKnowledgeDocumentSelectionState = (baseId) => {
    const item = knowledgeBaseItem(baseId);
    const state = aiKnowledgeDocumentStates.get(String(baseId));
    if (!item || !state) return;
    const boxes = Array.from(item.querySelectorAll(".ai-knowledge-document-select input"));
    const checked = boxes.filter((input) => input.checked).length;
    const count = state.selectionScope === "all" ? state.pagination.total : checked;
    const selectPage = item.querySelector("[data-knowledge-document-select-page]");
    if (selectPage) {
      selectPage.checked = Boolean(boxes.length) && checked === boxes.length;
      selectPage.indeterminate = checked > 0 && checked < boxes.length;
    }
    const selectMatches = item.querySelector("[data-knowledge-document-select-matches]");
    if (selectMatches) {
      selectMatches.classList.toggle("active", state.selectionScope === "all");
      selectMatches.setAttribute("aria-pressed", state.selectionScope === "all" ? "true" : "false");
      selectMatches.textContent = state.selectionScope === "all" ? "已选筛选全部" : "选择筛选全部";
    }
    const selected = item.querySelector("[data-knowledge-document-selected]");
    if (selected) selected.textContent = `已选择 ${count} 个`;
    item.querySelectorAll("[data-knowledge-document-bulk-action]").forEach((button) => {
      button.disabled = count === 0;
    });
  };

  const renderKnowledgeDocumentRows = (baseId) => {
    const item = knowledgeBaseItem(baseId);
    const state = aiKnowledgeDocumentStates.get(String(baseId));
    if (!item || !state) return;
    const list = item.querySelector("[data-knowledge-document-list]");
    if (!list) return;
    list.innerHTML = "";
    state.documents.forEach((document) => {
      const row = makeElement("div", "ai-knowledge-document");
      const select = makeElement("label", "ai-knowledge-document-select");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = String(document.id);
      checkbox.checked = state.selectionScope === "all";
      checkbox.setAttribute("aria-label", `选择知识文档 ${document.title}`);
      select.append(checkbox);
      const copy = makeElement("div", "ai-knowledge-document-copy");
      const link = makeElement("a", "", document.title);
      link.href = `/assistant/knowledge-documents/${document.id}/download`;
      const source = document.name || "手工文字";
      const meta = makeElement("small", "", `${source} · ${document.size}${document.readable ? "" : " · 未提取文字"} · ${document.updated_at}`);
      meta.title = `最后编辑：${document.updated_at}`;
      copy.append(link, meta);
      const remove = makeAiActionButton("ai-delete-knowledge-document", "trash-2", "删除知识文档");
      remove.dataset.documentId = String(document.id);
      remove.dataset.baseId = String(baseId);
      remove.dataset.documentTitle = document.title;
      row.append(select, copy, remove);
      list.append(row);
    });
    if (!state.documents.length) {
      list.append(makeElement("p", "ai-knowledge-document-empty", state.query ? "没有匹配的知识文档" : "这个知识库还没有文档"));
    }
    const pagination = state.pagination;
    const summary = item.querySelector("[data-knowledge-document-summary]");
    if (summary) summary.textContent = `${pagination.total || 0} 个知识文档`;
    const total = item.querySelector("[data-knowledge-document-total]");
    if (total) total.textContent = `${pagination.total || 0} 个匹配文档`;
    const pageLabel = item.querySelector("[data-knowledge-document-page]");
    if (pageLabel) pageLabel.textContent = `第 ${pagination.page || 1} / ${Math.max(1, pagination.pages || 0)} 页`;
    const previous = item.querySelector("[data-knowledge-document-prev]");
    const next = item.querySelector("[data-knowledge-document-next]");
    if (previous) previous.disabled = !pagination.has_prev || state.loading;
    if (next) next.disabled = !pagination.has_next || state.loading;
    const perPage = item.querySelector("[data-knowledge-document-per-page]");
    if (perPage) perPage.value = String(pagination.per_page || state.perPage || 8);
    item.classList.toggle("is-loading", state.loading);
    updateKnowledgeDocumentSelectionState(baseId);
    if (window.lucide) window.lucide.createIcons();
  };

  const loadKnowledgeDocuments = async (baseId) => {
    const state = aiKnowledgeDocumentStates.get(String(baseId));
    if (!state) return;
    const requestId = (state.requestId || 0) + 1;
    state.requestId = requestId;
    state.loading = true;
    renderKnowledgeDocumentRows(baseId);
    const query = new URLSearchParams({
      page: String(state.page), per_page: String(state.perPage),
    });
    if (state.query) query.set("q", state.query);
    try {
      const response = await fetch(`/assistant/knowledge-bases/${baseId}/documents?${query.toString()}`, {
        headers: {"Accept": "application/json"},
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "无法读取知识文档");
      if (state.requestId !== requestId) return;
      state.documents = payload.documents || [];
      state.pagination = payload.pagination || state.pagination;
      state.page = state.pagination.page || 1;
      state.perPage = state.pagination.per_page || state.perPage;
      if (!state.documents.length && state.pagination.total > 0 && state.page > state.pagination.pages) {
        state.loading = false;
        state.page = Math.max(1, state.pagination.pages);
        await loadKnowledgeDocuments(baseId);
        return;
      }
    } catch (error) {
      if (state.requestId === requestId) window.alert(error.message);
    } finally {
      if (state.requestId === requestId) {
        state.loading = false;
        renderKnowledgeDocumentRows(baseId);
      }
    }
  };

  const createKnowledgeDocumentPanel = (base, state) => {
    const details = makeElement("details", "ai-knowledge-document-panel");
    const summary = makeElement("summary", "");
    const summaryLabel = makeElement("span", "");
    summaryLabel.innerHTML = '<i data-lucide="files"></i>';
    const summaryText = makeElement("b", "", `${state.pagination.total || 0} 个知识文档`);
    summaryText.dataset.knowledgeDocumentSummary = "1";
    summaryLabel.append(summaryText);
    summary.append(summaryLabel);
    const chevron = document.createElement("i");
    chevron.dataset.lucide = "chevron-down";
    summary.append(chevron);
    details.append(summary);

    const body = makeElement("div", "ai-knowledge-document-body");
    const toolbar = makeElement("div", "ai-knowledge-document-toolbar");
    const searchLabel = makeElement("label", "ai-knowledge-document-search");
    searchLabel.innerHTML = '<i data-lucide="search"></i>';
    const search = document.createElement("input");
    search.type = "search";
    search.maxLength = 120;
    search.placeholder = "搜索文档标题或内容";
    search.value = state.query;
    search.dataset.knowledgeDocumentSearch = String(base.id);
    search.setAttribute("aria-label", `搜索 ${base.name} 的知识文档`);
    searchLabel.append(search);
    const perPage = document.createElement("select");
    perPage.dataset.knowledgeDocumentPerPage = String(base.id);
    perPage.setAttribute("aria-label", "每页知识文档数量");
    (state.pagination.page_sizes || [8, 16, 32]).forEach((size) => {
      const option = document.createElement("option");
      option.value = String(size);
      option.textContent = `${size} / 页`;
      perPage.append(option);
    });
    toolbar.append(searchLabel, perPage);

    const selectionTools = makeElement("div", "ai-knowledge-document-page-tools");
    const selectPageLabel = makeElement("label", "", " 全选本页");
    const selectPage = document.createElement("input");
    selectPage.type = "checkbox";
    selectPage.dataset.knowledgeDocumentSelectPage = String(base.id);
    selectPageLabel.prepend(selectPage);
    const selectMatches = makeElement("button", "", "选择筛选全部");
    selectMatches.type = "button";
    selectMatches.dataset.knowledgeDocumentSelectMatches = String(base.id);
    const total = makeElement("small", "", `${state.pagination.total || 0} 个匹配文档`);
    total.dataset.knowledgeDocumentTotal = "1";
    selectionTools.append(selectPageLabel, selectMatches, total);

    const bulk = makeElement("details", "ai-knowledge-document-bulk");
    const bulkSummary = makeElement("summary", "");
    const bulkTitle = makeElement("span", "", "批量管理文档");
    const selected = makeElement("small", "", "已选择 0 个");
    selected.dataset.knowledgeDocumentSelected = "1";
    bulkSummary.append(bulkTitle, selected);
    const bulkFields = makeElement("div", "ai-knowledge-document-bulk-fields");
    const titleMode = document.createElement("select");
    titleMode.dataset.knowledgeDocumentTitleMode = "1";
    titleMode.setAttribute("aria-label", "文档标题批量操作");
    [["keep", "标题不变"], ["prefix", "添加前缀"], ["suffix", "添加后缀"]].forEach(([value, label]) => {
      const option = document.createElement("option"); option.value = value; option.textContent = label; titleMode.append(option);
    });
    const titleValue = document.createElement("input");
    titleValue.maxLength = 80;
    titleValue.placeholder = "标题前缀或后缀";
    titleValue.dataset.knowledgeDocumentTitleValue = "1";
    const save = makeElement("button", "btn", "保存修改");
    save.type = "button";
    save.dataset.knowledgeDocumentBulkAction = "update";
    save.dataset.baseId = String(base.id);
    save.disabled = true;
    const remove = makeElement("button", "btn danger", "批量删除");
    remove.type = "button";
    remove.dataset.knowledgeDocumentBulkAction = "delete";
    remove.dataset.baseId = String(base.id);
    remove.disabled = true;
    bulkFields.append(titleMode, titleValue, save, remove);
    bulk.append(bulkSummary, bulkFields);

    const list = makeElement("div", "ai-knowledge-documents");
    list.dataset.knowledgeDocumentList = "1";
    const pagination = makeElement("nav", "ai-knowledge-document-pagination");
    pagination.setAttribute("aria-label", `${base.name} 知识文档翻页`);
    const previous = makeAiActionButton("", "chevron-left", "上一页");
    previous.dataset.knowledgeDocumentPrev = String(base.id);
    const page = makeElement("span", "", "第 1 / 1 页");
    page.dataset.knowledgeDocumentPage = "1";
    const next = makeAiActionButton("", "chevron-right", "下一页");
    next.dataset.knowledgeDocumentNext = String(base.id);
    pagination.append(previous, page, next);
    body.append(toolbar, selectionTools, bulk, list, pagination);
    details.append(body);
    return details;
  };

  const makeKnowledgeCommand = (icon, label, className = "") => {
    const button = makeElement("button", className);
    button.type = "button";
    button.innerHTML = `<i data-lucide="${icon}"></i>`;
    button.append(document.createTextNode(label));
    return button;
  };

  const renderKnowledgeBases = (items) => {
    if (!aiKnowledgeList) return;
    aiKnowledgeOptions = items || [];
    aiKnowledgeList.innerHTML = "";
    const refreshDocuments = [];
    aiKnowledgeOptions.forEach((base) => {
      const item = makeElement("article", "ai-knowledge-item");
      item.dataset.knowledgeBaseId = String(base.id);
      const header = makeElement("div", "ai-knowledge-item-head");
      const manage = makeElement("label", "ai-knowledge-manage-select");
      const manageCheckbox = document.createElement("input");
      manageCheckbox.type = "checkbox";
      manageCheckbox.value = String(base.id);
      manageCheckbox.checked = aiKnowledgeSelectionScope === "all";
      manageCheckbox.setAttribute("aria-label", `批量选择知识库 ${base.name}`);
      manage.append(manageCheckbox);
      const copy = makeElement("div", "ai-knowledge-item-copy");
      const title = makeElement("div", "ai-knowledge-item-title");
      title.append(makeElement("b", "", base.name), makeElement("span", `status-pill ${base.is_enabled ? "is-enabled" : "is-disabled"}`, base.is_enabled ? "已启用" : "已停用"));
      const documentTotal = base.document_pagination?.total ?? base.documents.length;
      const meta = makeElement("small", "", `${documentTotal} 个知识文档 · 最后编辑 ${base.updated_at}`);
      meta.title = `最后编辑：${base.updated_at}`;
      copy.append(title, meta);
      if (base.description) {
        const description = makeElement("p", "", base.description);
        description.title = base.description;
        copy.append(description);
      }
      const contextSelect = makeElement("label", "ai-knowledge-select");
      const contextCheckbox = document.createElement("input");
      contextCheckbox.type = "checkbox";
      contextCheckbox.value = String(base.id);
      contextCheckbox.checked = aiSelectedKnowledgeBaseIds.has(String(base.id)) && base.is_enabled;
      contextCheckbox.disabled = !base.is_enabled;
      contextCheckbox.setAttribute("aria-label", `本次对话使用知识库 ${base.name}`);
      if (!base.is_enabled) aiSelectedKnowledgeBaseIds.delete(String(base.id));
      contextSelect.append(contextCheckbox, makeElement("span", "", "用于本次对话"));
      header.append(manage, copy, contextSelect);
      item.append(header);

      const actions = makeElement("div", "ai-knowledge-actions");
      const uploadLabel = makeElement("label", "ai-knowledge-file-label");
      uploadLabel.innerHTML = '<i data-lucide="upload"></i><span>上传文件</span>';
      const upload = document.createElement("input");
      upload.type = "file";
      upload.multiple = true;
      upload.addEventListener("change", async () => {
        if (!upload.files.length) return;
        const data = new FormData();
        Array.from(upload.files).forEach((file) => data.append("files", file));
        try { await postAiForm(`/assistant/knowledge-bases/${base.id}/documents`, data); await loadAiState(); }
        catch (error) { window.alert(error.message); }
      });
      uploadLabel.append(upload);
      const addText = makeKnowledgeCommand("file-plus-2", "添加文字");
      addText.addEventListener("click", async () => {
        const title = window.prompt("知识条目标题", "手工知识条目");
        if (title === null) return;
        const value = window.prompt("输入知识内容");
        if (!value?.trim()) return;
        const data = new FormData();
        data.set("title", title);
        data.set("text_content", value);
        try { await postAiForm(`/assistant/knowledge-bases/${base.id}/documents`, data); await loadAiState(); }
        catch (error) { window.alert(error.message); }
      });
      const edit = makeKnowledgeCommand("pencil", "编辑");
      edit.addEventListener("click", async () => {
        const name = window.prompt("知识库名称", base.name);
        if (!name?.trim()) return;
        const description = window.prompt("用途说明", base.description || "");
        if (description === null) return;
        const instructions = window.prompt("知识库使用说明", base.custom_instructions || "");
        if (instructions === null) return;
        const data = new FormData();
        data.set("name", name);
        data.set("description", description);
        data.set("custom_instructions", instructions);
        try { await postAiForm(`/assistant/knowledge-bases/${base.id}`, data); await loadAiState(); }
        catch (error) { window.alert(error.message); }
      });
      const toggle = makeKnowledgeCommand(base.is_enabled ? "pause" : "play", base.is_enabled ? "停用" : "启用");
      toggle.addEventListener("click", async () => {
        const data = new FormData(); data.set("action", "toggle");
        try {
          const result = await postAiForm(`/assistant/knowledge-bases/${base.id}`, data);
          if (!result.is_enabled) aiSelectedKnowledgeBaseIds.delete(String(base.id));
          await loadAiState();
        }
        catch (error) { window.alert(error.message); }
      });
      const removeBase = makeKnowledgeCommand("trash-2", "删除", "danger");
      removeBase.addEventListener("click", async () => {
        if (!window.confirm(`删除知识库“${base.name}”及其中的文件？`)) return;
        const data = new FormData(); data.set("action", "delete");
        try {
          await postAiForm(`/assistant/knowledge-bases/${base.id}`, data);
          aiSelectedKnowledgeBaseIds.delete(String(base.id));
          aiKnowledgeDocumentStates.delete(String(base.id));
          await loadAiState();
        }
        catch (error) { window.alert(error.message); }
      });
      actions.append(uploadLabel, addText, edit, toggle, removeBase);
      item.append(actions);
      const {state, requiresRefresh} = documentStateForBase(base);
      item.append(createKnowledgeDocumentPanel(base, state));
      aiKnowledgeList.append(item);
      renderKnowledgeDocumentRows(base.id);
      if (requiresRefresh) refreshDocuments.push(base.id);
    });
    if (!aiKnowledgeOptions.length) aiKnowledgeList.append(makeElement(
      "p", "", (aiKnowledgeSearch?.value || "").trim() ? "没有匹配的知识库" : "还没有知识库，可以在下方创建。",
    ));
    updateKnowledgeSelectionState();
    updateKnowledgeCount();
    if (window.lucide) window.lucide.createIcons();
    refreshDocuments.forEach((baseId) => loadKnowledgeDocuments(baseId));
  };

  const appendKnowledgeScope = (data) => {
    data.set("knowledge_scope_present", "1");
    selectedKnowledgeBaseIds().forEach((itemId) => data.append("knowledge_base_ids", itemId));
  };

  const loadAiState = async () => {
    const query = new URLSearchParams();
    if (aiConversationId) query.set("conversation_id", aiConversationId);
    const conversationQuery = (aiConversationSearch?.value || "").trim();
    if (conversationQuery) query.set("conversation_q", conversationQuery);
    query.set("conversation_page", String(aiConversationPage));
    query.set("conversation_per_page", String(aiConversationPerPage?.value || aiConversationPagination.per_page || 8));
    const knowledgeQuery = (aiKnowledgeSearch?.value || "").trim();
    if (knowledgeQuery) query.set("knowledge_q", knowledgeQuery);
    query.set("knowledge_page", String(aiKnowledgePage));
    query.set("knowledge_per_page", String(aiKnowledgePerPage?.value || aiKnowledgePagination.per_page || 8));
    if (assistantPage.type && assistantPage.id) {
      query.set("page_type", assistantPage.type);
      query.set("page_id", assistantPage.id);
    }
    const stateUrl = () => {
      const search = query.toString();
      return `/assistant/state${search ? `?${search}` : ""}`;
    };
    let response = await fetch(stateUrl(), {headers: {"Accept": "application/json"}});
    if (response.status === 404 && aiConversationId) {
      aiConversationId = "";
      window.localStorage.removeItem("research-assistant-conversation");
      query.delete("conversation_id");
      response = await fetch(stateUrl(), {headers: {"Accept": "application/json"}});
    }
    if (!response.ok) throw new Error("无法读取 AI 会话");
    const state = await response.json();
    const nextKnowledgePagination = state.knowledge_pagination || aiKnowledgePagination;
    if (!(state.knowledge_bases || []).length && nextKnowledgePagination.total > 0
        && nextKnowledgePagination.page > nextKnowledgePagination.pages) {
      aiKnowledgePage = Math.max(1, nextKnowledgePagination.pages);
      return loadAiState();
    }
    aiConversationOptions = state.conversations || [];
    aiConversationPagination = state.conversation_pagination || aiConversationPagination;
    aiConversationPage = aiConversationPagination.page || 1;
    if (aiConversationPerPage) aiConversationPerPage.value = String(aiConversationPagination.per_page || 8);
    if (aiConversationTotal) aiConversationTotal.textContent = `${aiConversationPagination.total || 0} 个匹配会话`;
    if (aiConversationPageLabel) aiConversationPageLabel.textContent = `第 ${aiConversationPagination.page || 1} / ${aiConversationPagination.pages || 1} 页`;
    if (aiConversationPrev) aiConversationPrev.disabled = !aiConversationPagination.has_prev;
    if (aiConversationNext) aiConversationNext.disabled = !aiConversationPagination.has_next;
    aiProjectOptions = state.projects || [];
    setConversation(state.conversation);
    renderConversationList();
    renderExperimentScope(
      state.experiments,
      state.batches,
      state.records,
      state.conversation?.selected_experiment_ids || [],
      state.conversation?.selected_batch_ids || [],
      state.conversation?.selected_record_ids || [],
      state.page_scope || {},
      state.record_total || 0,
    );
    aiKnowledgePagination = nextKnowledgePagination;
    aiKnowledgePage = aiKnowledgePagination.page || 1;
    if (aiKnowledgePerPage) aiKnowledgePerPage.value = String(aiKnowledgePagination.per_page || 8);
    if (aiKnowledgeTotal) aiKnowledgeTotal.textContent = `${aiKnowledgePagination.total || 0} 个匹配知识库`;
    if (aiKnowledgePageLabel) aiKnowledgePageLabel.textContent = `第 ${aiKnowledgePagination.page || 1} / ${Math.max(1, aiKnowledgePagination.pages || 0)} 页`;
    if (aiKnowledgePrev) aiKnowledgePrev.disabled = !aiKnowledgePagination.has_prev;
    if (aiKnowledgeNext) aiKnowledgeNext.disabled = !aiKnowledgePagination.has_next;
    if (aiKnowledgeSearch && document.activeElement !== aiKnowledgeSearch) aiKnowledgeSearch.value = state.knowledge_query || "";
    const knowledgeContextOwner = state.conversation ? String(state.conversation.id) : "draft";
    if (aiKnowledgeContextOwner !== knowledgeContextOwner) {
      aiSelectedKnowledgeBaseIds = new Set(
        (state.conversation?.selected_knowledge_base_ids || []).map(String),
      );
      aiKnowledgeContextOwner = knowledgeContextOwner;
    }
    renderKnowledgeBases(state.knowledge_bases);
    if (aiCustomPrompt) aiCustomPrompt.value = state.preference.custom_prompt || "";
    if (aiPromptStatus) aiPromptStatus.textContent = state.preference.using_default ? "使用默认提示词" : "已使用自定义提示词";
    if (aiModelLabel) {
      aiModelLabel.dataset.idleLabel = state.api.enabled ? state.api.model : "未配置 API";
      aiModelLabel.textContent = aiModelLabel.dataset.idleLabel;
    }
    if (aiWebAccess) {
      aiWebAccess.disabled = !state.api.web_capable;
      if (aiWebAccess.disabled) aiWebAccess.checked = false;
      const toggle = aiWebAccess.closest(".ai-web-toggle");
      toggle?.classList.toggle("disabled", aiWebAccess.disabled);
      if (toggle) toggle.title = state.api.web_capable
        ? "使用当前 API 的网页搜索能力并返回引用"
        : "当前 API 或模型未确认支持联网搜索";
    }
    aiLoaded = true;
  };

  const setAiContextPage = (view = "") => {
    if (!aiContextPage) return;
    const open = view === "experiment" || view === "knowledge";
    if (open && aiContextPage.parentElement !== document.body) document.body.append(aiContextPage);
    if (open) {
      aiContextPage.dataset.sourceView = view;
      const experimentView = view === "experiment";
      if (aiContextPageTitle) aiContextPageTitle.textContent = experimentView ? "选择实验资料" : "选择知识库";
      if (aiContextPageDescription) aiContextPageDescription.textContent = experimentView
        ? "按实验计划、实验批次和实验记录限定本次对话的读取范围。"
        : "选择本次对话可检索的知识库，并管理其中的本地文档。";
      if (aiContextPageIcon) aiContextPageIcon.innerHTML = `<i data-lucide="${experimentView ? "flask-conical" : "library-big"}"></i>`;
    }
    aiContextPage.hidden = !open;
    aiExperimentSourceOpen?.classList.toggle("active", view === "experiment");
    aiKnowledgeSourceOpen?.classList.toggle("active", view === "knowledge");
    aiExperimentSourceOpen?.setAttribute("aria-pressed", view === "experiment" ? "true" : "false");
    aiKnowledgeSourceOpen?.setAttribute("aria-pressed", view === "knowledge" ? "true" : "false");
    if (open) {
      if (!aiContextPage.dataset.positioned) {
        const rect = aiContextPage.getBoundingClientRect();
        aiContextPage.style.left = `${Math.max(12, Math.round((window.innerWidth - rect.width) / 2))}px`;
        aiContextPage.style.top = `${Math.max(12, Math.round((window.innerHeight - rect.height) / 2))}px`;
        aiContextPage.dataset.positioned = "1";
      }
      if (window.lucide) window.lucide.createIcons();
      aiContextPageClose?.focus();
    } else {
      aiInput?.focus();
    }
  };

  const openAiAssistant = async () => {
    hideAiNotice();
    aiDock?.classList.add("open");
    aiDock?.setAttribute("aria-hidden", "false");
    fitAiWindowToViewport();
    if (!aiLoaded) {
      try { await loadAiState(); } catch (error) { aiWelcome(); }
    }
    syncAiInputMeta();
    aiInput?.focus();
  };
  aiOpenButtons.forEach((button) => button.addEventListener("click", openAiAssistant));
  const prefillAiMessage = async (message = "") => {
    await openAiAssistant();
    if (!aiInput || !message.trim()) return;
    aiInput.value = message.trim();
    syncAiInputMeta();
    aiInput.focus();
    aiInput.setSelectionRange(aiInput.value.length, aiInput.value.length);
  };
  document.querySelectorAll("[data-ai-sidecar-prompt]").forEach((button) => {
    button.addEventListener("click", () => prefillAiMessage(button.dataset.aiSidecarPrompt || ""));
  });
  document.querySelector("#ai-sidecar-composer")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.querySelector("#ai-sidecar-input");
    prefillAiMessage(input?.value || "");
  });
  aiExperimentSourceOpen?.addEventListener("click", () => setAiContextPage("experiment"));
  aiKnowledgeSourceOpen?.addEventListener("click", () => setAiContextPage("knowledge"));
  aiContextPageClose?.addEventListener("click", () => setAiContextPage());
  if (new URLSearchParams(window.location.search).get("assistant") === "open") {
    window.setTimeout(openAiAssistant, 0);
  }
  document.querySelector("#ai-close")?.addEventListener("click", () => {
    setAiContextPage();
    aiDock?.classList.remove("open");
    aiDock?.setAttribute("aria-hidden", "true");
  });
  aiCompletionToast?.addEventListener("click", openAiAssistant);

  const fitAiContextPageToViewport = () => {
    if (!aiContextPage || aiContextPage.hidden) return;
    const rect = aiContextPage.getBoundingClientRect();
    const maxLeft = Math.max(8, window.innerWidth - Math.min(rect.width, window.innerWidth - 16) - 8);
    const maxTop = Math.max(8, window.innerHeight - Math.min(rect.height, window.innerHeight - 16) - 8);
    aiContextPage.style.left = `${Math.min(Math.max(8, rect.left), maxLeft)}px`;
    aiContextPage.style.top = `${Math.min(Math.max(8, rect.top), maxTop)}px`;
  };
  aiContextPage?.querySelector("[data-ai-context-drag-handle]")?.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest("button, input, select, textarea, a")) return;
    const rect = aiContextPage.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const startLeft = rect.left;
    const startTop = rect.top;
    aiContextPage.classList.add("is-dragging");
    const move = (moveEvent) => {
      const maxLeft = Math.max(8, window.innerWidth - aiContextPage.offsetWidth - 8);
      const maxTop = Math.max(8, window.innerHeight - aiContextPage.offsetHeight - 8);
      aiContextPage.style.left = `${Math.min(Math.max(8, startLeft + moveEvent.clientX - startX), maxLeft)}px`;
      aiContextPage.style.top = `${Math.min(Math.max(8, startTop + moveEvent.clientY - startY), maxTop)}px`;
    };
    const end = () => {
      aiContextPage.classList.remove("is-dragging");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
  });

  document.querySelector("#ai-maximize")?.addEventListener("click", () => {
    if (!aiDock) return;
    if (!aiDock.classList.contains("ai-maximized")) {
      saveAiWindowState();
      aiDock.classList.add("ai-maximized");
      saveAiWindowState();
      return;
    }
    const state = readAiWindowState();
    aiDock.classList.remove("ai-maximized");
    if (state.width) aiDock.style.width = `${state.width}px`;
    if (state.height) aiDock.style.height = `${state.height}px`;
    if (Number.isFinite(state.left) && Number.isFinite(state.top)) {
      aiDock.style.left = `${state.left}px`;
      aiDock.style.top = `${state.top}px`;
    }
    window.requestAnimationFrame(() => {
      fitAiWindowToViewport();
      saveAiWindowState();
    });
  });
  const aiDockHead = aiDock?.querySelector(".ai-dock-head");
  aiDockHead?.addEventListener("pointerdown", (event) => {
    if (aiDock.classList.contains("ai-maximized") || event.target.closest("button,a")) return;
    const rect = aiDock.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const startLeft = rect.left;
    const startTop = rect.top;
    aiDock.classList.add("ai-dragging");
    aiDock.style.left = `${startLeft}px`;
    aiDock.style.top = `${startTop}px`;
    aiDock.style.right = "auto";
    aiDock.style.bottom = "auto";
    aiDockHead.setPointerCapture(event.pointerId);
    const move = (moveEvent) => {
      const left = Math.max(8, Math.min(startLeft + moveEvent.clientX - startX, window.innerWidth - aiDock.offsetWidth - 8));
      const top = Math.max(8, Math.min(startTop + moveEvent.clientY - startY, window.innerHeight - aiDock.offsetHeight - 8));
      aiDock.style.left = `${left}px`;
      aiDock.style.top = `${top}px`;
    };
    const end = () => {
      aiDock.classList.remove("ai-dragging");
      aiDockHead.removeEventListener("pointermove", move);
      aiDockHead.removeEventListener("pointerup", end);
      aiDockHead.removeEventListener("pointercancel", end);
      saveAiWindowState();
    };
    aiDockHead.addEventListener("pointermove", move);
    aiDockHead.addEventListener("pointerup", end);
    aiDockHead.addEventListener("pointercancel", end);
  });

  const aiResizeHandle = document.querySelector("#ai-resize-handle");
  aiResizeHandle?.addEventListener("pointerdown", (event) => {
    if (aiDock?.classList.contains("ai-maximized")) return;
    event.preventDefault();
    event.stopPropagation();
    const rect = aiDock.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const startWidth = rect.width;
    const startHeight = rect.height;
    aiDock.classList.add("ai-resizing");
    const move = (moveEvent) => {
      const minWidth = Math.min(380, window.innerWidth - 16);
      const minHeight = Math.min(520, window.innerHeight - 16);
      const maxWidth = Math.max(minWidth, window.innerWidth - rect.left - 8);
      const maxHeight = Math.max(minHeight, window.innerHeight - rect.top - 8);
      aiDock.style.width = `${Math.max(minWidth, Math.min(startWidth + moveEvent.clientX - startX, maxWidth))}px`;
      aiDock.style.height = `${Math.max(minHeight, Math.min(startHeight + moveEvent.clientY - startY, maxHeight))}px`;
    };
    const end = () => {
      aiDock.classList.remove("ai-resizing");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
      fitAiWindowToViewport();
      saveAiWindowState();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
  });

  if (aiDock && "ResizeObserver" in window) {
    let resizeSaveTimer;
    new ResizeObserver(() => {
      window.clearTimeout(resizeSaveTimer);
      resizeSaveTimer = window.setTimeout(() => {
        fitAiWindowToViewport();
        saveAiWindowState();
      }, 250);
    }).observe(aiDock);
  }
  window.addEventListener("resize", fitAiWindowToViewport);
  window.addEventListener("resize", fitAiContextPageToViewport);
  applyAiWindowState();

  const createAiConversation = async () => {
    const data = new FormData();
    data.set("csrf_token", csrfToken);
    data.set("page_type", assistantPage.type);
    data.set("page_id", assistantPage.id);
    appendExperimentScope(data);
    appendKnowledgeScope(data);
    const response = await fetch("/assistant/conversations", {method: "POST", body: data});
    if (!response.ok) return;
    const conversation = await response.json();
    if (aiConversationSearch) aiConversationSearch.value = "";
    aiConversationPage = 1;
    aiConversationSelectionScope = "page";
    setConversation({...conversation, messages: []});
    aiChannel?.postMessage({type: "conversation", id: aiConversationId});
    await loadAiState();
    aiInput?.focus();
  };

  document.querySelector("#ai-new-chat")?.addEventListener("click", createAiConversation);
  document.querySelector("#ai-new-chat-side")?.addEventListener("click", createAiConversation);
  document.querySelector("#ai-sidebar-toggle")?.addEventListener("click", () => {
    if (!aiDock) return;
    if (aiDock.getBoundingClientRect().width >= 760) {
      aiDock.classList.toggle("conversations-collapsed");
      aiDock.classList.remove("show-conversations");
    } else {
      aiDock.classList.toggle("show-conversations");
      if (aiDock.classList.contains("show-conversations")) aiConversationSearch?.focus();
    }
  });
  aiConversationSearch?.addEventListener("input", () => {
    window.clearTimeout(aiConversationSearchTimer);
    aiConversationSearchTimer = window.setTimeout(async () => {
      aiConversationPage = 1;
      aiConversationSelectionScope = "page";
      await loadAiState();
    }, 260);
  });
  aiConversationPerPage?.addEventListener("change", async () => {
    aiConversationPage = 1;
    aiConversationSelectionScope = "page";
    await loadAiState();
  });
  aiConversationPrev?.addEventListener("click", async () => {
    if (!aiConversationPagination.has_prev) return;
    aiConversationPage = Math.max(1, aiConversationPage - 1);
    aiConversationSelectionScope = "page";
    await loadAiState();
  });
  aiConversationNext?.addEventListener("click", async () => {
    if (!aiConversationPagination.has_next) return;
    aiConversationPage += 1;
    aiConversationSelectionScope = "page";
    await loadAiState();
  });
  aiConversationSelectPage?.addEventListener("change", () => {
    aiConversationSelectionScope = "page";
    aiConversationList?.querySelectorAll(".ai-conversation-select input").forEach((input) => {
      input.checked = aiConversationSelectPage.checked;
    });
    updateConversationSelectionState();
  });
  aiConversationSelectMatches?.addEventListener("click", () => {
    aiConversationSelectionScope = aiConversationSelectionScope === "all" ? "page" : "all";
    aiConversationList?.querySelectorAll(".ai-conversation-select input").forEach((input) => {
      input.checked = aiConversationSelectionScope === "all";
    });
    updateConversationSelectionState();
  });
  aiConversationList?.addEventListener("change", (event) => {
    if (!event.target.matches(".ai-conversation-select input")) return;
    aiConversationSelectionScope = "page";
    updateConversationSelectionState();
  });
  const runConversationBulkAction = async (action) => {
    const selectedIds = Array.from(
      aiConversationList?.querySelectorAll(".ai-conversation-select input:checked") || [],
    ).map((input) => input.value);
    const count = aiConversationSelectionScope === "all" ? aiConversationPagination.total : selectedIds.length;
    if (!count) return;
    if (action === "delete" && !window.confirm(`确定删除选中的 ${count} 个历史会话及其聊天记录吗？`)) return;
    const data = new FormData();
    data.set("action", action);
    data.set("selection_scope", aiConversationSelectionScope);
    data.set("conversation_q", (aiConversationSearch?.value || "").trim());
    data.set("current_conversation_id", aiConversationId);
    data.set("title_mode", aiConversationTitleMode?.value || "keep");
    data.set("title_value", aiConversationTitleValue?.value || "");
    selectedIds.forEach((itemId) => data.append("conversation_ids", itemId));
    try {
      const result = await postAiForm("/assistant/conversations/bulk", data);
      if (result.current_deleted) {
        aiConversationId = result.next_conversation_id ? String(result.next_conversation_id) : "";
        if (aiConversationId) window.localStorage.setItem("research-assistant-conversation", aiConversationId);
        else window.localStorage.removeItem("research-assistant-conversation");
      }
      aiConversationSelectionScope = "page";
      await loadAiState();
    } catch (error) { window.alert(error.message); }
  };
  aiConversationBulkSave?.addEventListener("click", () => runConversationBulkAction("update"));
  aiConversationBulkDelete?.addEventListener("click", () => runConversationBulkAction("delete"));
  aiConversationList?.addEventListener("click", async (event) => {
    const open = event.target.closest(".ai-conversation-open");
    const rename = event.target.closest(".ai-rename-conversation");
    const remove = event.target.closest(".ai-delete-conversation");
    const conversationId = open?.dataset.conversationId || rename?.dataset.conversationId || remove?.dataset.conversationId;
    if (!conversationId) return;
    if (open) {
      aiConversationId = String(conversationId);
      window.localStorage.setItem("research-assistant-conversation", aiConversationId);
      await loadAiState();
      if (aiDock && aiDock.getBoundingClientRect().width < 760) aiDock.classList.remove("show-conversations");
      aiInput?.focus();
      return;
    }
    const conversation = aiConversationOptions.find((item) => String(item.id) === String(conversationId));
    if (rename) {
      const title = window.prompt("会话名称", conversation?.title || "新对话");
      if (!title?.trim()) return;
      const data = new FormData(); data.set("action", "rename"); data.set("title", title.trim());
      try { await postAiForm(`/assistant/conversations/${conversationId}`, data); await loadAiState(); }
      catch (error) { window.alert(error.message); }
      return;
    }
    if (!window.confirm(`删除会话“${conversation?.title || "新对话"}”及全部聊天记录？`)) return;
    const data = new FormData(); data.set("action", "delete");
    try {
      const result = await postAiForm(`/assistant/conversations/${conversationId}`, data);
      aiConversationId = result.next_conversation_id ? String(result.next_conversation_id) : "";
      if (aiConversationId) window.localStorage.setItem("research-assistant-conversation", aiConversationId);
      else window.localStorage.removeItem("research-assistant-conversation");
      await loadAiState();
    } catch (error) { window.alert(error.message); }
  });

  document.querySelectorAll("#ai-quick-prompts button").forEach((button) => {
    button.addEventListener("click", () => {
      if (aiInput) aiInput.value = button.textContent;
      syncAiInputMeta();
      aiInput?.focus();
    });
  });

  aiHistoryList?.addEventListener("change", (event) => {
    const experimentParent = event.target.closest("[data-experiment-select-all]");
    if (experimentParent) {
      const group = experimentParent.closest("[data-history-experiment-group]");
      group?.querySelectorAll('input[name="batch_ids"], input[name="record_ids"]').forEach((input) => {
        input.checked = experimentParent.checked;
      });
    }
    const batchParent = event.target.closest("[data-batch-select-all]");
    if (batchParent) {
      const group = batchParent.closest("[data-history-batch-group]");
      group?.querySelectorAll('input[name="record_ids"]').forEach((input) => {
        input.checked = batchParent.checked;
      });
    }
    updateHistoryCount();
  });
  aiHistoryList?.addEventListener("click", (event) => {
    if (event.target.matches('summary input[type="checkbox"]')) event.stopPropagation();
  });
  aiHistorySearch?.addEventListener("input", () => {
    aiHistoryPage = 1;
    applyHistoryFilter();
  });
  aiHistoryLevel?.addEventListener("change", () => {
    aiHistoryPage = 1;
    applyHistoryFilter();
  });
  aiHistoryPerPage?.addEventListener("change", () => {
    aiHistoryPage = 1;
    applyHistoryFilter();
  });
  aiHistoryPrev?.addEventListener("click", () => {
    aiHistoryPage = Math.max(1, aiHistoryPage - 1);
    applyHistoryFilter();
  });
  aiHistoryNext?.addEventListener("click", () => {
    aiHistoryPage += 1;
    applyHistoryFilter();
  });
  aiKnowledgeList?.addEventListener("change", updateKnowledgeCount);
  document.querySelector("#ai-select-current")?.addEventListener("click", () => {
    aiHistoryList?.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = false; });
    if (aiPageScope.record_id) {
      const current = aiHistoryList?.querySelector(`input[name="record_ids"][value="${CSS.escape(String(aiPageScope.record_id))}"]`);
      if (current) current.checked = true;
    } else if (aiPageScope.batch_id) {
      const current = aiHistoryList?.querySelector(`input[name="batch_ids"][value="${CSS.escape(String(aiPageScope.batch_id))}"]`);
      if (current) {
        current.checked = true;
        current.closest("[data-history-batch-group]")?.querySelectorAll('input[name="record_ids"]').forEach((input) => {
          input.checked = true;
        });
      }
    } else if (aiPageScope.experiment_id) {
      const group = aiHistoryList?.querySelector(`[data-history-experiment-group="${CSS.escape(String(aiPageScope.experiment_id))}"]`);
      const descendants = group?.querySelectorAll('input[name="batch_ids"], input[name="record_ids"]') || [];
      if (descendants.length) descendants.forEach((input) => { input.checked = true; });
      else {
        const plan = group?.querySelector('input[name="experiment_ids"]');
        if (plan) plan.checked = true;
      }
    } else if (aiPageScope.project_id) {
      aiExperimentOptions
        .filter((experiment) => String(experiment.project_id || "") === String(aiPageScope.project_id))
        .forEach((experiment) => {
          const group = aiHistoryList?.querySelector(`[data-history-experiment-group="${CSS.escape(String(experiment.id))}"]`);
          const descendants = group?.querySelectorAll('input[name="batch_ids"], input[name="record_ids"]') || [];
          if (descendants.length) descendants.forEach((input) => { input.checked = true; });
          else {
            const plan = group?.querySelector('input[name="experiment_ids"]');
            if (plan) plan.checked = true;
          }
        });
    }
    updateHistoryCount();
  });
  document.querySelector("#ai-select-all")?.addEventListener("click", () => {
    historyInputsMatchingFilter().forEach((input) => { input.checked = true; });
    updateHistoryCount();
  });
  document.querySelector("#ai-clear-selection")?.addEventListener("click", () => {
    aiHistoryList?.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = false; });
    updateHistoryCount();
  });

  aiKnowledgeSearch?.addEventListener("input", () => {
    window.clearTimeout(aiKnowledgeSearchTimer);
    aiKnowledgeSearchTimer = window.setTimeout(async () => {
      aiKnowledgePage = 1;
      aiKnowledgeSelectionScope = "page";
      await loadAiState();
    }, 260);
  });
  aiKnowledgePerPage?.addEventListener("change", async () => {
    aiKnowledgePage = 1;
    aiKnowledgeSelectionScope = "page";
    await loadAiState();
  });
  aiKnowledgePrev?.addEventListener("click", async () => {
    if (!aiKnowledgePagination.has_prev) return;
    aiKnowledgePage = Math.max(1, aiKnowledgePage - 1);
    aiKnowledgeSelectionScope = "page";
    await loadAiState();
  });
  aiKnowledgeNext?.addEventListener("click", async () => {
    if (!aiKnowledgePagination.has_next) return;
    aiKnowledgePage += 1;
    aiKnowledgeSelectionScope = "page";
    await loadAiState();
  });
  aiKnowledgeSelectPage?.addEventListener("change", () => {
    aiKnowledgeSelectionScope = "page";
    aiKnowledgeList?.querySelectorAll(".ai-knowledge-manage-select input").forEach((input) => {
      input.checked = aiKnowledgeSelectPage.checked;
    });
    updateKnowledgeSelectionState();
  });
  aiKnowledgeSelectMatches?.addEventListener("click", () => {
    aiKnowledgeSelectionScope = aiKnowledgeSelectionScope === "all" ? "page" : "all";
    aiKnowledgeList?.querySelectorAll(".ai-knowledge-manage-select input").forEach((input) => {
      input.checked = aiKnowledgeSelectionScope === "all";
    });
    updateKnowledgeSelectionState();
  });

  const runKnowledgeBulkAction = async (action) => {
    const selectedIds = Array.from(
      aiKnowledgeList?.querySelectorAll(".ai-knowledge-manage-select input:checked") || [],
    ).map((input) => input.value);
    const count = aiKnowledgeSelectionScope === "all" ? aiKnowledgePagination.total : selectedIds.length;
    if (!count) return;
    if (action === "delete" && !window.confirm(`确定删除选中的 ${count} 个知识库及其中全部文件吗？`)) return;
    const data = new FormData();
    data.set("action", action);
    data.set("selection_scope", aiKnowledgeSelectionScope);
    data.set("knowledge_q", (aiKnowledgeSearch?.value || "").trim());
    data.set("bulk_enabled", aiKnowledgeBulkEnabled?.value || "__keep__");
    data.set("description_mode", aiKnowledgeDescriptionMode?.value || "keep");
    data.set("description", aiKnowledgeDescriptionValue?.value || "");
    data.set("instruction_mode", aiKnowledgeInstructionMode?.value || "keep");
    data.set("custom_instructions", aiKnowledgeInstructionValue?.value || "");
    selectedIds.forEach((itemId) => data.append("knowledge_base_item_ids", itemId));
    try {
      const result = await postAiForm("/assistant/knowledge-bases/bulk", data);
      const affectedIds = (result.ids || selectedIds).map(String);
      if (action === "delete" || aiKnowledgeBulkEnabled?.value === "disabled") {
        affectedIds.forEach((itemId) => aiSelectedKnowledgeBaseIds.delete(itemId));
      }
      if (action === "delete") {
        affectedIds.forEach((itemId) => aiKnowledgeDocumentStates.delete(itemId));
      }
      aiKnowledgeSelectionScope = "page";
      await loadAiState();
    } catch (error) { window.alert(error.message); }
  };
  aiKnowledgeBulkSave?.addEventListener("click", () => runKnowledgeBulkAction("update"));
  aiKnowledgeBulkDelete?.addEventListener("click", () => runKnowledgeBulkAction("delete"));

  const runKnowledgeDocumentBulkAction = async (baseId, action) => {
    const item = knowledgeBaseItem(baseId);
    const state = aiKnowledgeDocumentStates.get(String(baseId));
    if (!item || !state) return;
    const selectedIds = Array.from(
      item.querySelectorAll(".ai-knowledge-document-select input:checked"),
    ).map((input) => input.value);
    const count = state.selectionScope === "all" ? state.pagination.total : selectedIds.length;
    if (!count) return;
    if (action === "delete" && !window.confirm(`确定删除选中的 ${count} 个知识文档吗？`)) return;
    const data = new FormData();
    data.set("action", action);
    data.set("selection_scope", state.selectionScope);
    data.set("q", state.query);
    data.set("title_mode", item.querySelector("[data-knowledge-document-title-mode]")?.value || "keep");
    data.set("title_value", item.querySelector("[data-knowledge-document-title-value]")?.value || "");
    selectedIds.forEach((documentId) => data.append("document_ids", documentId));
    try {
      await postAiForm(`/assistant/knowledge-bases/${baseId}/documents/bulk`, data);
      state.selectionScope = "page";
      await loadKnowledgeDocuments(baseId);
    } catch (error) { window.alert(error.message); }
  };

  aiKnowledgeList?.addEventListener("input", (event) => {
    const search = event.target.closest("[data-knowledge-document-search]");
    if (!search) return;
    const baseId = search.dataset.knowledgeDocumentSearch;
    const state = aiKnowledgeDocumentStates.get(String(baseId));
    if (!state) return;
    state.query = search.value.trim();
    window.clearTimeout(state.searchTimer);
    state.searchTimer = window.setTimeout(() => {
      state.page = 1;
      state.selectionScope = "page";
      loadKnowledgeDocuments(baseId);
    }, 260);
  });
  aiKnowledgeList?.addEventListener("change", (event) => {
    const context = event.target.closest(".ai-knowledge-select input");
    if (context) {
      if (context.checked) aiSelectedKnowledgeBaseIds.add(String(context.value));
      else aiSelectedKnowledgeBaseIds.delete(String(context.value));
      updateKnowledgeCount();
      return;
    }
    const manage = event.target.closest(".ai-knowledge-manage-select input");
    if (manage) {
      aiKnowledgeSelectionScope = "page";
      updateKnowledgeSelectionState();
      return;
    }
    const documentSelect = event.target.closest(".ai-knowledge-document-select input");
    if (documentSelect) {
      const baseId = documentSelect.closest("[data-knowledge-base-id]")?.dataset.knowledgeBaseId;
      const state = aiKnowledgeDocumentStates.get(String(baseId));
      if (state) state.selectionScope = "page";
      updateKnowledgeDocumentSelectionState(baseId);
      return;
    }
    const selectPage = event.target.closest("[data-knowledge-document-select-page]");
    if (selectPage) {
      const baseId = selectPage.dataset.knowledgeDocumentSelectPage;
      const state = aiKnowledgeDocumentStates.get(String(baseId));
      if (state) state.selectionScope = "page";
      knowledgeBaseItem(baseId)?.querySelectorAll(".ai-knowledge-document-select input").forEach((input) => {
        input.checked = selectPage.checked;
      });
      updateKnowledgeDocumentSelectionState(baseId);
      return;
    }
    const perPage = event.target.closest("[data-knowledge-document-per-page]");
    if (perPage) {
      const baseId = perPage.dataset.knowledgeDocumentPerPage;
      const state = aiKnowledgeDocumentStates.get(String(baseId));
      if (!state) return;
      state.perPage = Number.parseInt(perPage.value, 10) || 8;
      state.page = 1;
      state.selectionScope = "page";
      loadKnowledgeDocuments(baseId);
    }
  });
  aiKnowledgeList?.addEventListener("click", async (event) => {
    const selectMatches = event.target.closest("[data-knowledge-document-select-matches]");
    if (selectMatches) {
      const baseId = selectMatches.dataset.knowledgeDocumentSelectMatches;
      const state = aiKnowledgeDocumentStates.get(String(baseId));
      if (!state) return;
      state.selectionScope = state.selectionScope === "all" ? "page" : "all";
      knowledgeBaseItem(baseId)?.querySelectorAll(".ai-knowledge-document-select input").forEach((input) => {
        input.checked = state.selectionScope === "all";
      });
      updateKnowledgeDocumentSelectionState(baseId);
      return;
    }
    const previous = event.target.closest("[data-knowledge-document-prev]");
    const next = event.target.closest("[data-knowledge-document-next]");
    if (previous || next) {
      const baseId = previous?.dataset.knowledgeDocumentPrev || next?.dataset.knowledgeDocumentNext;
      const state = aiKnowledgeDocumentStates.get(String(baseId));
      if (!state) return;
      state.page = Math.max(1, state.page + (previous ? -1 : 1));
      state.selectionScope = "page";
      await loadKnowledgeDocuments(baseId);
      return;
    }
    const bulkAction = event.target.closest("[data-knowledge-document-bulk-action]");
    if (bulkAction) {
      await runKnowledgeDocumentBulkAction(bulkAction.dataset.baseId, bulkAction.dataset.knowledgeDocumentBulkAction);
      return;
    }
    const remove = event.target.closest(".ai-delete-knowledge-document");
    if (!remove) return;
    if (!window.confirm(`删除知识文档“${remove.dataset.documentTitle}”？`)) return;
    try {
      await postAiForm(`/assistant/knowledge-documents/${remove.dataset.documentId}/delete`, new FormData());
      const state = aiKnowledgeDocumentStates.get(String(remove.dataset.baseId));
      if (state) state.selectionScope = "page";
      await loadKnowledgeDocuments(remove.dataset.baseId);
    } catch (error) { window.alert(error.message); }
  });

  aiKnowledgeCreateForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await postAiForm("/assistant/knowledge-bases", new FormData(aiKnowledgeCreateForm));
      aiKnowledgeCreateForm.reset();
      if (aiKnowledgeSearch) aiKnowledgeSearch.value = "";
      aiKnowledgePage = 1;
      aiKnowledgeSelectionScope = "page";
      await loadAiState();
    } catch (error) { window.alert(error.message); }
  });
  aiPromptForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await postAiForm("/assistant/preferences", new FormData(aiPromptForm));
      if (aiPromptStatus) aiPromptStatus.textContent = result.using_default ? "使用默认提示词" : "已使用自定义提示词";
    } catch (error) { window.alert(error.message); }
  });
  document.querySelector("#ai-prompt-reset")?.addEventListener("click", async () => {
    const data = new FormData(); data.set("action", "reset");
    try {
      await postAiForm("/assistant/preferences", data);
      if (aiCustomPrompt) aiCustomPrompt.value = "";
      if (aiPromptStatus) aiPromptStatus.textContent = "使用默认提示词";
    } catch (error) { window.alert(error.message); }
  });
  document.querySelector("#ai-refresh-knowledge")?.addEventListener("click", () => loadAiState());

  aiFiles?.addEventListener("change", () => {
    aiFileList.innerHTML = "";
    Array.from(aiFiles.files || []).slice(0, 8).forEach((file) => aiFileList.append(makeElement("span", "", file.name)));
  });

  const confirmAiOutgoingContext = async (data) => {
    const previewData = new FormData();
    for (const [key, value] of data.entries()) {
      if (key !== "files") previewData.append(key, value);
    }
    Array.from(aiFiles?.files || []).slice(0, 8).forEach((file) => {
      previewData.append("file_names", file.name);
      previewData.append("file_sizes", String(file.size));
    });
    const response = await fetch("/assistant/context-preview", {
      method: "POST", body: previewData, headers: {"X-CSRFToken": csrfToken},
    });
    const preview = await response.json();
    if (!response.ok) throw new Error(preview.error || "无法检查外发上下文");
    if (!preview.requires_confirmation || !aiContextDialog) return true;

    aiContextProvider.textContent = `${preview.provider.host} · ${preview.provider.model || "未设置模型"}`;
    aiContextSummary.innerHTML = "";
    [
      [preview.message_chars, "提问字符"],
      [preview.research.experiment_count, "实验计划"],
      [preview.research.record_count, "过程记录"],
      [preview.knowledge.document_count, "知识文档"],
      [preview.files.length, "上传文件"],
      [preview.web_access ? "开启" : "关闭", "联网检索"],
    ].forEach(([value, label]) => {
      const row = makeElement("span", "");
      row.append(makeElement("b", "", String(value)), makeElement("small", "", label));
      aiContextSummary.append(row);
    });
    aiContextSources.innerHTML = "";
    const addSourceGroup = (label, rows) => {
      if (!rows?.length) return;
      const group = makeElement("section", "ai-context-source-group");
      group.append(makeElement("b", "", label));
      const list = document.createElement("ul");
      rows.forEach((row) => list.append(makeElement("li", "", row)));
      group.append(list); aiContextSources.append(group);
    };
    addSourceGroup("实验与记录", preview.research.sources);
    addSourceGroup("知识库", preview.knowledge.sources);
    addSourceGroup("本次文件", preview.files.map((file) => `${file.name} · ${file.size_bytes} B`));
    const warningText = aiContextWarning?.querySelector("span");
    if (warningText) warningText.textContent = preview.sensitive_terms?.length
      ? `检测到可能敏感的医学关键词：${preview.sensitive_terms.join("、")}。请确认内容已去标识化，并核对是否允许发送给该 API。`
      : "所选实验内容、知识库节选和文件可读文字会发送给外部 API。请先确认不含不应外发的患者身份信息。";
    if (window.lucide) window.lucide.createIcons();
    aiContextDialog.showModal();
    return new Promise((resolve) => {
      const finish = (accepted) => {
        if (aiContextDialog.open) aiContextDialog.close();
        resolve(accepted);
      };
      aiContextConfirm.onclick = () => finish(true);
      aiContextDialog.querySelectorAll("[data-ai-context-cancel]").forEach((button) => {
        button.onclick = () => finish(false);
      });
      aiContextDialog.oncancel = (event) => { event.preventDefault(); finish(false); };
    });
  };

  aiInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      aiComposer?.requestSubmit();
    }
  });
  aiInput?.addEventListener("input", () => {
    syncAiInputMeta();
  });

  aiComposer?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (aiRequestRunning || (!aiInput.value.trim() && !(aiFiles.files || []).length)) return;
    const sendButton = aiComposer.querySelector(".ai-send");
    const data = new FormData(aiComposer);
    data.set("conversation_id", aiConversationId);
    data.set("page_type", assistantPage.type);
    data.set("page_id", assistantPage.id);
    appendExperimentScope(data);
    appendKnowledgeScope(data);
    try {
      if (!await confirmAiOutgoingContext(data)) return;
    } catch (error) {
      window.alert(error.message || "无法检查外发上下文，请稍后重试。");
      return;
    }
    aiRequestRunning = true;
    aiAbortController = new AbortController();
    aiTaskStartedAt = Date.now();
    setAiTaskStatus("正在分析上下文和生成回复");
    if (aiStop) aiStop.hidden = false;
    sendButton.disabled = true;
    aiOpenButtons.forEach((button) => button.classList.add("working"));
    if (aiModelLabel) aiModelLabel.textContent = "正在后台运行…";
    const pending = makeElement("div", "ai-thinking", "AI 正在分析…");
    aiMessages.append(pending);
    aiMessages.scrollTop = aiMessages.scrollHeight;
    try {
      const response = await fetch("/assistant/chat", {method: "POST", body: data, signal: aiAbortController.signal});
      const result = await response.json();
      pending.remove();
      if (result.conversation_id) {
        aiConversationId = String(result.conversation_id);
        window.localStorage.setItem("research-assistant-conversation", aiConversationId);
        aiExport.href = `/assistant/conversations/${aiConversationId}/export.md`;
        aiExport.classList.remove("disabled");
        aiChannel?.postMessage({type: "conversation", id: aiConversationId});
      }
      await loadAiState();
      aiInput.value = "";
      aiFiles.value = "";
      aiFileList.innerHTML = "";
      syncAiInputMeta();
      if (!aiDock?.classList.contains("open")) showAiNotice("点击查看本次回复");
      aiChannel?.postMessage({type: "completed", id: aiConversationId});
    } catch (error) {
      pending.textContent = error.name === "AbortError" ? "已停止等待。本地 API 请求可能仍在完成收尾。" : "发送失败，请检查本地服务和 API 设置。";
      if (!aiDock?.classList.contains("open")) showAiNotice(error.name === "AbortError" ? "任务已停止" : "点击查看错误信息", true);
    } finally {
      aiRequestRunning = false;
      aiAbortController = null;
      if (aiStop) aiStop.hidden = true;
      setAiTaskStatus("");
      sendButton.disabled = false;
      aiOpenButtons.forEach((button) => button.classList.remove("working"));
      if (aiModelLabel) aiModelLabel.textContent = aiModelLabel.dataset.idleLabel || "准备就绪";
    }
  });

  aiStop?.addEventListener("click", () => aiAbortController?.abort());

  aiChannel?.addEventListener("message", async (event) => {
    if (event.data?.id) {
      aiConversationId = String(event.data.id);
      window.localStorage.setItem("research-assistant-conversation", aiConversationId);
    }
    if (event.data?.type === "completed" && !aiDock?.classList.contains("open")) showAiNotice("另一页面中的回复已完成");
    if (!aiRequestRunning && aiDock?.classList.contains("open")) {
      try { await loadAiState(); } catch (_error) { /* keep current view */ }
    }
  });

  aiMessages?.addEventListener("click", async (event) => {
    const applyButton = event.target.closest(".ai-apply-proposal");
    const revertButton = event.target.closest(".ai-revert-proposal");
    const editButton = event.target.closest(".ai-edit-message");
    const deleteButton = event.target.closest(".ai-delete-message");
    const regenerateButton = event.target.closest(".ai-regenerate-message");
    if (editButton) {
      const article = editButton.closest(".ai-message");
      const content = article?.querySelector(".ai-message-content");
      if (!article || !content || article.querySelector(".ai-message-editor")) return;
      const editor = makeElement("div", "ai-message-editor");
      const textarea = document.createElement("textarea");
      textarea.value = content.textContent || "";
      textarea.rows = Math.min(12, Math.max(3, textarea.value.split("\n").length + 1));
      const controls = makeElement("div", "ai-message-editor-actions");
      const cancel = makeElement("button", "", "取消"); cancel.type = "button";
      const save = makeElement("button", "primary", "保存并重新生成"); save.type = "button";
      controls.append(cancel, save); editor.append(textarea, controls);
      content.hidden = true; content.after(editor); textarea.focus(); textarea.setSelectionRange(textarea.value.length, textarea.value.length);
      cancel.addEventListener("click", () => { editor.remove(); content.hidden = false; });
      save.addEventListener("click", async () => {
        if (!textarea.value.trim()) return;
        save.disabled = true; save.textContent = "正在重新生成…";
        const data = new FormData(); data.set("action", "edit"); data.set("content", textarea.value.trim());
        if (document.querySelector("#ai-web-access")?.checked) data.set("web_access", "1");
        try {
          const response = await fetch(`/assistant/messages/${editButton.dataset.messageId}`, {method: "POST", body: data, headers: {"X-CSRFToken": csrfToken}});
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || "编辑失败");
          await loadAiState();
        } catch (error) { save.disabled = false; save.textContent = "保存并重新生成"; window.alert(error.message); }
      });
      return;
    }
    if (deleteButton) {
      if (!window.confirm("删除这条消息？此操作不能撤销。")) return;
      const data = new FormData(); data.set("action", "delete");
      try { await postAiForm(`/assistant/messages/${deleteButton.dataset.messageId}`, data); await loadAiState(); }
      catch (error) { window.alert(error.message); }
      return;
    }
    if (regenerateButton) {
      regenerateButton.disabled = true;
      regenerateButton.innerHTML = '<i data-lucide="loader-circle"></i>';
      regenerateButton.title = "正在重新生成";
      if (window.lucide) window.lucide.createIcons();
      const data = new FormData();
      if (document.querySelector("#ai-web-access")?.checked) data.set("web_access", "1");
      try { await postAiForm(`/assistant/messages/${regenerateButton.dataset.messageId}/regenerate`, data); await loadAiState(); }
      catch (error) {
        regenerateButton.disabled = false;
        regenerateButton.innerHTML = '<i data-lucide="refresh-cw"></i>';
        regenerateButton.title = "重新生成回复";
        if (window.lucide) window.lucide.createIcons();
        window.alert(error.message);
      }
      return;
    }
    if (applyButton) {
      applyButton.disabled = true;
      applyButton.textContent = "正在保存…";
      const data = new FormData();
      data.set("csrf_token", csrfToken);
      data.set("selection_present", "1");
      const proposalPanel = applyButton.closest(".ai-proposal");
      const projectSelect = proposalPanel?.querySelector(".ai-proposal-project");
      if (projectSelect && aiProjectOptions.length > 1 && !projectSelect.value) {
        applyButton.disabled = false;
        applyButton.textContent = "请先选择所属科研项目";
        projectSelect.focus();
        return;
      }
      if (projectSelect?.value) data.set("project_id", projectSelect.value);
      const selectedChanges = Array.from(proposalPanel?.querySelectorAll(".ai-diff-checkbox:checked") || []);
      selectedChanges.forEach((checkbox) => {
        data.append("selected_change_ids", checkbox.value);
      });
      if (selectedChanges.some((checkbox) => checkbox.value.includes(":delete:"))) {
        const confirmation = window.prompt("此提案包含删除操作。请输入“确认删除”继续：", "");
        if (confirmation !== "确认删除") {
          applyButton.disabled = false;
          applyButton.textContent = "确认并保存到页面";
          return;
        }
        data.set("destructive_confirmation", confirmation);
      }
      const response = await fetch(`/assistant/proposals/${applyButton.dataset.messageId}/apply`, {method: "POST", body: data});
      const result = await response.json();
      if (!response.ok) {
        applyButton.disabled = false;
        applyButton.textContent = result.error || "保存失败";
        return;
      }
      applyButton.textContent = result.warning || "已保存";
      if (result.redirect_url) window.location.href = result.redirect_url;
      return;
    }
    if (revertButton) {
      if (!window.confirm("撤销这次 AI 修改并恢复应用前内容？")) return;
      revertButton.disabled = true;
      revertButton.textContent = "正在撤销…";
      const data = new FormData(); data.set("csrf_token", csrfToken);
      const response = await fetch(`/assistant/proposals/${revertButton.dataset.messageId}/revert`, {method: "POST", body: data});
      const result = await response.json();
      if (!response.ok) {
        revertButton.disabled = false;
        revertButton.textContent = result.error || "撤销失败";
        return;
      }
      revertButton.textContent = "已撤销";
      if (result.redirect_url) window.location.href = result.redirect_url;
    }
  });

  document.addEventListener("keydown", (event) => {
    const modifier = event.ctrlKey || event.metaKey;
    if (modifier && event.key.toLowerCase() === "k" && (!aiDock || !aiDock.classList.contains("open"))) {
      event.preventDefault();
      const pageSearch = document.querySelector(".report-feed-search input, .report-search-form input, .file-center-search input, .weekly-index-filter input");
      if (pageSearch) pageSearch.focus();
      else document.querySelector(".topbar-search")?.click();
      return;
    }
    if (!aiDock || !aiDock.classList.contains("open")) return;
    if (modifier && event.key.toLowerCase() === "n") {
      event.preventDefault();
      createAiConversation();
    } else if (modifier && event.key.toLowerCase() === "k") {
      event.preventDefault();
      setAiContextPage();
      aiInput?.focus();
    } else if (modifier && event.shiftKey && event.key.toLowerCase() === "l") {
      event.preventDefault();
      if (aiDock.getBoundingClientRect().width >= 760) aiDock.classList.toggle("conversations-collapsed");
      else aiDock.classList.toggle("show-conversations");
    } else if (event.key === "Escape" && aiContextPage && !aiContextPage.hidden) {
      setAiContextPage();
    } else if (event.key === "Escape" && aiDock.classList.contains("show-conversations")) {
      aiDock.classList.remove("show-conversations");
    } else if (event.altKey && ["ArrowUp", "ArrowDown"].includes(event.key) && aiConversationOptions.length) {
      event.preventDefault();
      const current = Math.max(0, aiConversationOptions.findIndex((item) => String(item.id) === String(aiConversationId)));
      const delta = event.key === "ArrowUp" ? -1 : 1;
      const next = Math.max(0, Math.min(aiConversationOptions.length - 1, current + delta));
      aiConversationId = String(aiConversationOptions[next].id);
      window.localStorage.setItem("research-assistant-conversation", aiConversationId);
      loadAiState();
    }
  });

});

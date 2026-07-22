document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) window.lucide.createIcons();

  const sidebar = document.querySelector("#sidebar");
  document.querySelector("#menu-toggle")?.addEventListener("click", () => sidebar?.classList.toggle("open"));
  document.addEventListener("click", (event) => {
    if (window.innerWidth <= 820 && sidebar?.classList.contains("open") &&
        !sidebar.contains(event.target) && !event.target.closest("#menu-toggle")) sidebar.classList.remove("open");
  });

  const appearanceDialog = document.querySelector("#appearance-dialog");
  const appearanceForm = document.querySelector("#appearance-form");
  const backgroundInput = document.querySelector("#background-input");
  const backgroundPreview = document.querySelector("#background-preview");
  let appearanceSnapshot = null;
  let appearanceSubmitting = false;
  let previewObjectUrl = null;

  document.querySelector("#appearance-toggle")?.addEventListener("click", () => {
    appearanceSnapshot = {
      theme: document.documentElement.dataset.theme,
      mode: document.documentElement.dataset.mode,
      background: document.body.style.getPropertyValue("--workspace-background-image"),
      hasBackground: document.body.classList.contains("has-custom-background"),
    };
    appearanceSubmitting = false;
    appearanceDialog?.showModal();
  });
  document.querySelector("#appearance-close")?.addEventListener("click", () => appearanceDialog?.close());
  appearanceDialog?.addEventListener("close", () => {
    if (!appearanceSubmitting && appearanceSnapshot) {
      document.documentElement.dataset.theme = appearanceSnapshot.theme;
      document.documentElement.dataset.mode = appearanceSnapshot.mode;
      document.body.classList.toggle("has-custom-background", appearanceSnapshot.hasBackground);
      if (appearanceSnapshot.background) {
        document.body.style.setProperty("--workspace-background-image", appearanceSnapshot.background);
      } else {
        document.body.style.removeProperty("--workspace-background-image");
      }
      appearanceForm?.querySelector(`input[name="theme"][value="${appearanceSnapshot.theme}"]`)?.click();
      const modeToggle = document.querySelector("#dark-mode-toggle");
      if (modeToggle) modeToggle.checked = appearanceSnapshot.mode === "dark";
    }
    if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = null;
  });
  appearanceForm?.addEventListener("submit", () => { appearanceSubmitting = true; });
  appearanceForm?.querySelectorAll('input[name="theme"]').forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) document.documentElement.dataset.theme = input.value;
    });
  });
  document.querySelector("#dark-mode-toggle")?.addEventListener("change", (event) => {
    document.documentElement.dataset.mode = event.target.checked ? "dark" : "light";
  });
  backgroundInput?.addEventListener("change", () => {
    const file = backgroundInput.files?.[0];
    if (!file) return;
    if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = URL.createObjectURL(file);
    const imageValue = `url("${previewObjectUrl}")`;
    backgroundPreview?.classList.add("has-image");
    if (backgroundPreview) backgroundPreview.style.backgroundImage = imageValue;
    document.body.classList.add("has-custom-background");
    document.body.style.setProperty("--workspace-background-image", imageValue);
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll("[data-attachment-bulk]").forEach((form) => {
    const checkboxes = [...document.querySelectorAll(`[data-attachment-select][form="${form.id}"]`)];
    const selectAll = form.querySelector("[data-attachment-select-all]");
    const selectedLabel = form.querySelector("[data-attachment-selected]");
    const actionButtons = [...form.querySelectorAll('button[name="action"]')];
    const updateState = () => {
      const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
      if (selectedLabel) selectedLabel.textContent = `已选择 ${selectedCount} 个`;
      if (selectAll) {
        selectAll.checked = checkboxes.length > 0 && selectedCount === checkboxes.length;
        selectAll.indeterminate = selectedCount > 0 && selectedCount < checkboxes.length;
      }
      actionButtons.forEach((button) => { button.disabled = selectedCount === 0; });
    };
    selectAll?.addEventListener("change", () => {
      checkboxes.forEach((checkbox) => { checkbox.checked = selectAll.checked; });
      updateState();
    });
    checkboxes.forEach((checkbox) => checkbox.addEventListener("change", updateState));
    form.addEventListener("submit", (event) => {
      const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
      if (!selectedCount) {
        event.preventDefault();
        window.alert("请先勾选至少一个文件。");
        return;
      }
      if (event.submitter?.value === "delete" &&
          !window.confirm(`确定永久删除选中的 ${selectedCount} 个文件吗？此操作无法撤销。`)) {
        event.preventDefault();
      }
    });
    updateState();
  });

  document.querySelectorAll("[data-bulk-form]").forEach((form) => {
    const checkboxes = [...document.querySelectorAll(`[data-bulk-select][form="${form.id}"]`)];
    const selectAll = form.querySelector("[data-bulk-select-all]");
    const selectedLabel = form.querySelector("[data-bulk-selected]");
    const actionButtons = [...form.querySelectorAll('button[name="action"]')];
    const resourceLabel = form.dataset.bulkLabel || "项目";
    const updateState = () => {
      const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
      if (selectedLabel) selectedLabel.textContent = `已选择 ${selectedCount} 个`;
      if (selectAll) {
        selectAll.checked = checkboxes.length > 0 && selectedCount === checkboxes.length;
        selectAll.indeterminate = selectedCount > 0 && selectedCount < checkboxes.length;
      }
      actionButtons.forEach((button) => { button.disabled = selectedCount === 0; });
      form.classList.toggle("has-selection", selectedCount > 0);
    };
    selectAll?.addEventListener("change", () => {
      checkboxes.forEach((checkbox) => { checkbox.checked = selectAll.checked; });
      updateState();
    });
    checkboxes.forEach((checkbox) => checkbox.addEventListener("change", updateState));
    form.addEventListener("submit", (event) => {
      const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
      if (!selectedCount) {
        event.preventDefault();
        window.alert(`请先勾选至少一个${resourceLabel}。`);
        return;
      }
      if (event.submitter?.value === "delete" &&
          !window.confirm(`确定批量删除选中的 ${selectedCount} 个${resourceLabel}吗？此操作无法撤销。`)) {
        event.preventDefault();
      }
    });
    updateState();
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

  const aiFab = document.querySelector("#ai-fab");
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
  const aiKnowledgeList = document.querySelector("#ai-knowledge-list");
  const aiKnowledgeCount = document.querySelector("#ai-knowledge-count");
  const aiKnowledgeCreateForm = document.querySelector("#ai-knowledge-create-form");
  const aiPromptForm = document.querySelector("#ai-prompt-form");
  const aiCustomPrompt = document.querySelector("#ai-custom-prompt");
  const aiPromptStatus = document.querySelector("#ai-prompt-status");
  const aiStop = document.querySelector("#ai-stop");
  const aiTaskStatus = document.querySelector("#ai-task-status");
  const aiCompletionToast = document.querySelector("#ai-completion-toast");
  const aiConversationSidebar = document.querySelector("#ai-conversation-sidebar");
  const aiConversationList = document.querySelector("#ai-conversation-list");
  const aiConversationSearch = document.querySelector("#ai-conversation-search");
  const aiChatTitle = document.querySelector("#ai-chat-title");
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const assistantPage = {
    type: document.body.dataset.assistantPageType || "",
    id: document.body.dataset.assistantPageId || "",
  };
  let aiConversationId = window.localStorage.getItem("research-assistant-conversation") || "";
  let aiLoaded = false;
  let aiExperimentOptions = [];
  let aiKnowledgeOptions = [];
  let aiConversationOptions = [];
  let aiRequestRunning = false;
  let aiAbortController = null;
  let aiTaskStartedAt = 0;
  let aiTaskTimer = null;
  const baseDocumentTitle = document.title;
  const aiWindowStorageKey = "research-assistant-window-state-v2";
  const aiChannel = "BroadcastChannel" in window ? new BroadcastChannel("research-assistant-ai") : null;
  const isAiPopup = document.body.dataset.assistantPopup === "1";

  const hideAiNotice = () => {
    if (aiCompletionToast) aiCompletionToast.hidden = true;
    aiFab?.classList.remove("complete");
    document.title = baseDocumentTitle;
  };

  const showAiNotice = (message, failed = false) => {
    if (!aiCompletionToast) return;
    aiCompletionToast.querySelector("b").textContent = failed ? "AI 运行失败" : "AI 已完成";
    aiCompletionToast.querySelector("small").textContent = message;
    aiCompletionToast.classList.toggle("failed", failed);
    aiCompletionToast.hidden = false;
    aiFab?.classList.toggle("complete", !failed);
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
    if (!aiDock || isAiPopup || window.innerWidth <= 600) return;
    const rect = aiDock.getBoundingClientRect();
    window.localStorage.setItem(aiWindowStorageKey, JSON.stringify({
      left: Math.round(rect.left), top: Math.round(rect.top), width: Math.round(rect.width),
      height: Math.round(rect.height), dock: aiDock.classList.contains("dock-left") ? "left" : (aiDock.classList.contains("dock-right") ? "right" : "free"),
      maximized: aiDock.classList.contains("ai-maximized"),
    }));
  };

  const applyAiWindowState = () => {
    if (!aiDock || isAiPopup || window.innerWidth <= 600) return;
    const state = readAiWindowState();
    if (state.width) aiDock.style.width = `${Math.min(state.width, window.innerWidth - 24)}px`;
    if (state.height) aiDock.style.height = `${Math.min(state.height, window.innerHeight - 24)}px`;
    aiDock.classList.toggle("dock-left", state.dock === "left");
    aiDock.classList.toggle("dock-right", state.dock === "right");
    aiDock.classList.toggle("ai-maximized", Boolean(state.maximized));
    if (state.dock === "free" && Number.isFinite(state.left) && Number.isFinite(state.top)) {
      aiDock.style.left = `${Math.max(0, Math.min(state.left, window.innerWidth - 120))}px`;
      aiDock.style.top = `${Math.max(0, Math.min(state.top, window.innerHeight - 80))}px`;
      aiDock.style.right = "auto";
      aiDock.style.bottom = "auto";
    }
  };

  const dockAiWindow = (side) => {
    if (!aiDock) return;
    aiDock.classList.remove("ai-maximized", "dock-left", "dock-right");
    aiDock.classList.add(side === "left" ? "dock-left" : "dock-right");
    aiDock.style.left = "";
    aiDock.style.top = "";
    aiDock.style.right = "";
    aiDock.style.bottom = "";
    saveAiWindowState();
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
    const label = makeElement("small", "ai-message-role", message.role === "user" ? "你" : "AI 助手");
    const content = makeElement("div", "ai-message-content", message.content);
    article.append(label, content);

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

  const renderConversationList = (query = aiConversationSearch?.value || "") => {
    if (!aiConversationList) return;
    const needle = query.trim().toLocaleLowerCase();
    const rows = aiConversationOptions.filter((item) => !needle || `${item.title} ${item.preview}`.toLocaleLowerCase().includes(needle));
    aiConversationList.innerHTML = "";
    rows.forEach((conversation) => {
      const row = makeElement("div", `ai-conversation-item${String(conversation.id) === String(aiConversationId) ? " active" : ""}`);
      row.dataset.conversationId = conversation.id;
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
      row.append(open, actions);
      aiConversationList.append(row);
    });
    if (!rows.length) aiConversationList.append(makeElement("p", "", needle ? "没有匹配的会话" : "还没有历史聊天"));
    if (window.lucide) window.lucide.createIcons();
  };

  const selectedExperimentIds = () => Array.from(
    aiHistoryList?.querySelectorAll('input[type="checkbox"]:checked') || []
  ).map((input) => String(input.value));

  const updateHistoryCount = () => {
    const count = selectedExperimentIds().length;
    if (aiHistoryCount) aiHistoryCount.textContent = count ? `已选择 ${count} 个实验` : "未选择实验";
    const pptLink = document.querySelector("#ai-create-ppt");
    if (pptLink) {
      const query = selectedExperimentIds().map((id) => `experiment_id=${encodeURIComponent(id)}`).join("&");
      pptLink.href = `/reports/presentation${query ? `?${query}` : ""}`;
    }
  };

  const renderExperimentScope = (experiments, selectedIds = []) => {
    if (!aiHistoryList) return;
    aiExperimentOptions = experiments || [];
    const selected = new Set((selectedIds || []).map(String));
    if (!selected.size && assistantPage.type === "experiment" && assistantPage.id) selected.add(String(assistantPage.id));
    aiHistoryList.innerHTML = "";
    aiExperimentOptions.forEach((experiment) => {
      const label = makeElement("label", "ai-history-option");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.name = "experiment_ids";
      input.value = String(experiment.id);
      input.checked = selected.has(String(experiment.id));
      const copy = makeElement("span", "");
      copy.append(makeElement("b", "", experiment.title));
      copy.append(makeElement("small", "", `${experiment.code} · ${experiment.status} · ${experiment.updated_at}`));
      label.append(input, copy);
      aiHistoryList.append(label);
    });
    if (!aiExperimentOptions.length) aiHistoryList.append(makeElement("p", "", "还没有可选择的实验"));
    updateHistoryCount();
  };

  const appendExperimentScope = (data) => {
    data.set("experiment_scope_present", "1");
    selectedExperimentIds().forEach((itemId) => data.append("experiment_ids", itemId));
  };

  const selectedKnowledgeBaseIds = () => Array.from(
    aiKnowledgeList?.querySelectorAll('.ai-knowledge-select input[type="checkbox"]:checked') || []
  ).map((input) => String(input.value));

  const updateKnowledgeCount = () => {
    const count = selectedKnowledgeBaseIds().length;
    if (aiKnowledgeCount) aiKnowledgeCount.textContent = count ? `已选择 ${count} 个知识库` : "未选择知识库";
  };

  const postAiForm = async (url, data) => {
    data.set("csrf_token", csrfToken);
    const response = await fetch(url, {method: "POST", body: data});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "操作失败");
    return result;
  };

  const renderKnowledgeBases = (items, selectedIds = []) => {
    if (!aiKnowledgeList) return;
    aiKnowledgeOptions = items || [];
    const selected = new Set((selectedIds || []).map(String));
    aiKnowledgeList.innerHTML = "";
    aiKnowledgeOptions.forEach((base) => {
      const item = makeElement("article", "ai-knowledge-item");
      const select = makeElement("label", "ai-knowledge-select");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = String(base.id);
      checkbox.checked = selected.has(String(base.id));
      checkbox.disabled = !base.is_enabled;
      const label = makeElement("span", "");
      label.append(makeElement("b", "", base.name), makeElement("small", "", `${base.documents.length} 个条目 · ${base.is_enabled ? "已启用" : "已停用"}`));
      select.append(checkbox, label);
      item.append(select);

      const documents = makeElement("div", "ai-knowledge-documents");
      base.documents.forEach((document) => {
        const row = makeElement("div", "ai-knowledge-document");
        const link = makeElement("a", "", `${document.title} · ${document.size}${document.readable ? "" : " · 未提取文字"}`);
        link.href = `/assistant/knowledge-documents/${document.id}/download`;
        const remove = makeElement("button", "", "×");
        remove.type = "button";
        remove.title = "删除知识条目";
        remove.addEventListener("click", async () => {
          if (!window.confirm(`删除知识条目“${document.title}”？`)) return;
          try { await postAiForm(`/assistant/knowledge-documents/${document.id}/delete`, new FormData()); await loadAiState(); }
          catch (error) { window.alert(error.message); }
        });
        row.append(link, remove);
        documents.append(row);
      });
      item.append(documents);

      const actions = makeElement("div", "ai-knowledge-actions");
      const uploadLabel = makeElement("label", "ai-knowledge-file-label", "上传文件");
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
      const addText = makeElement("button", "", "添加文字");
      addText.type = "button";
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
      const edit = makeElement("button", "", "编辑");
      edit.type = "button";
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
      const toggle = makeElement("button", "", base.is_enabled ? "停用" : "启用");
      toggle.type = "button";
      toggle.addEventListener("click", async () => {
        const data = new FormData(); data.set("action", "toggle");
        try { await postAiForm(`/assistant/knowledge-bases/${base.id}`, data); await loadAiState(); }
        catch (error) { window.alert(error.message); }
      });
      const removeBase = makeElement("button", "", "删除");
      removeBase.type = "button";
      removeBase.addEventListener("click", async () => {
        if (!window.confirm(`删除知识库“${base.name}”及其中的文件？`)) return;
        const data = new FormData(); data.set("action", "delete");
        try { await postAiForm(`/assistant/knowledge-bases/${base.id}`, data); await loadAiState(); }
        catch (error) { window.alert(error.message); }
      });
      actions.append(uploadLabel, addText, edit, toggle, removeBase);
      item.append(actions);
      aiKnowledgeList.append(item);
    });
    if (!aiKnowledgeOptions.length) aiKnowledgeList.append(makeElement("p", "", "还没有知识库，可以在下方创建。"));
    updateKnowledgeCount();
  };

  const appendKnowledgeScope = (data) => {
    data.set("knowledge_scope_present", "1");
    selectedKnowledgeBaseIds().forEach((itemId) => data.append("knowledge_base_ids", itemId));
  };

  const loadAiState = async () => {
    const query = aiConversationId ? `?conversation_id=${encodeURIComponent(aiConversationId)}` : "";
    let response = await fetch(`/assistant/state${query}`, {headers: {"Accept": "application/json"}});
    if (response.status === 404 && aiConversationId) {
      aiConversationId = "";
      window.localStorage.removeItem("research-assistant-conversation");
      response = await fetch("/assistant/state", {headers: {"Accept": "application/json"}});
    }
    if (!response.ok) throw new Error("无法读取 AI 会话");
    const state = await response.json();
    aiConversationOptions = state.conversations || [];
    setConversation(state.conversation);
    renderExperimentScope(state.experiments, state.conversation?.selected_experiment_ids || []);
    renderKnowledgeBases(state.knowledge_bases, state.conversation?.selected_knowledge_base_ids || []);
    if (aiCustomPrompt) aiCustomPrompt.value = state.preference.custom_prompt || "";
    if (aiPromptStatus) aiPromptStatus.textContent = state.preference.using_default ? "使用默认提示词" : "已使用自定义提示词";
    if (aiModelLabel) {
      aiModelLabel.dataset.idleLabel = state.api.enabled ? state.api.model : "未配置 API";
      aiModelLabel.textContent = aiModelLabel.dataset.idleLabel;
    }
    aiLoaded = true;
  };

  aiFab?.addEventListener("click", async () => {
    hideAiNotice();
    aiDock?.classList.add("open");
    aiDock?.setAttribute("aria-hidden", "false");
    if (!aiLoaded) {
      try { await loadAiState(); } catch (error) { aiWelcome(); }
    }
    aiInput?.focus();
  });
  document.querySelector("#ai-close")?.addEventListener("click", () => {
    aiDock?.classList.remove("open");
    aiDock?.setAttribute("aria-hidden", "true");
  });
  aiCompletionToast?.addEventListener("click", () => aiFab?.click());

  document.querySelector("#ai-dock-left")?.addEventListener("click", () => dockAiWindow("left"));
  document.querySelector("#ai-dock-right")?.addEventListener("click", () => dockAiWindow("right"));
  document.querySelector("#ai-maximize")?.addEventListener("click", () => {
    if (!aiDock) return;
    aiDock.classList.toggle("ai-maximized");
    saveAiWindowState();
  });
  document.querySelector("#ai-popout")?.addEventListener("click", () => {
    window.open("/assistant/popup", "research-assistant-ai", "popup,width=1100,height=860,resizable=yes,scrollbars=no");
  });

  const aiDockHead = aiDock?.querySelector(".ai-dock-head");
  aiDockHead?.addEventListener("pointerdown", (event) => {
    if (isAiPopup || window.innerWidth <= 600 || aiDock.classList.contains("ai-maximized") || event.target.closest("button,a")) return;
    const rect = aiDock.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const startLeft = rect.left;
    const startTop = rect.top;
    aiDock.classList.remove("dock-left", "dock-right");
    aiDock.classList.add("ai-dragging");
    aiDock.style.left = `${startLeft}px`;
    aiDock.style.top = `${startTop}px`;
    aiDock.style.right = "auto";
    aiDock.style.bottom = "auto";
    aiDockHead.setPointerCapture(event.pointerId);
    const move = (moveEvent) => {
      const left = Math.max(0, Math.min(startLeft + moveEvent.clientX - startX, window.innerWidth - aiDock.offsetWidth));
      const top = Math.max(0, Math.min(startTop + moveEvent.clientY - startY, window.innerHeight - aiDock.offsetHeight));
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

  if (aiDock && "ResizeObserver" in window && !isAiPopup) {
    let resizeSaveTimer;
    new ResizeObserver(() => {
      window.clearTimeout(resizeSaveTimer);
      resizeSaveTimer = window.setTimeout(saveAiWindowState, 250);
    }).observe(aiDock);
  }
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
  aiConversationSearch?.addEventListener("input", () => renderConversationList());
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
      aiInput?.focus();
    });
  });

  aiHistoryList?.addEventListener("change", updateHistoryCount);
  aiKnowledgeList?.addEventListener("change", updateKnowledgeCount);
  document.querySelector("#ai-select-current")?.addEventListener("click", () => {
    aiHistoryList?.querySelectorAll('input[type="checkbox"]').forEach((input) => {
      input.checked = assistantPage.type === "experiment" && String(input.value) === String(assistantPage.id);
    });
    updateHistoryCount();
  });
  document.querySelector("#ai-select-all")?.addEventListener("click", () => {
    aiHistoryList?.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = true; });
    updateHistoryCount();
  });
  document.querySelector("#ai-clear-selection")?.addEventListener("click", () => {
    aiHistoryList?.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = false; });
    updateHistoryCount();
  });

  aiKnowledgeCreateForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await postAiForm("/assistant/knowledge-bases", new FormData(aiKnowledgeCreateForm));
      aiKnowledgeCreateForm.reset();
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

  aiInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      aiComposer?.requestSubmit();
    }
  });

  aiComposer?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (aiRequestRunning || (!aiInput.value.trim() && !(aiFiles.files || []).length)) return;
    const sendButton = aiComposer.querySelector(".ai-send");
    aiRequestRunning = true;
    aiAbortController = new AbortController();
    aiTaskStartedAt = Date.now();
    setAiTaskStatus("正在分析上下文和生成回复");
    if (aiStop) aiStop.hidden = false;
    sendButton.disabled = true;
    aiFab?.classList.add("working");
    if (aiModelLabel) aiModelLabel.textContent = "正在后台运行…";
    const pending = makeElement("div", "ai-thinking", "AI 正在分析…");
    aiMessages.append(pending);
    aiMessages.scrollTop = aiMessages.scrollHeight;
    const data = new FormData(aiComposer);
    data.set("conversation_id", aiConversationId);
    data.set("page_type", assistantPage.type);
    data.set("page_id", assistantPage.id);
    appendExperimentScope(data);
    appendKnowledgeScope(data);
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
      aiFab?.classList.remove("working");
      if (aiModelLabel) aiModelLabel.textContent = aiModelLabel.dataset.idleLabel || "准备就绪";
    }
  });

  aiStop?.addEventListener("click", () => aiAbortController?.abort());

  aiChannel?.addEventListener("message", async (event) => {
    if (event.data?.id) {
      aiConversationId = String(event.data.id);
      window.localStorage.setItem("research-assistant-conversation", aiConversationId);
    }
    if (event.data?.type === "completed" && !aiDock?.classList.contains("open")) showAiNotice("独立窗口中的回复已完成");
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
      applyButton.closest(".ai-proposal")?.querySelectorAll(".ai-diff-checkbox:checked").forEach((checkbox) => {
        data.append("selected_change_ids", checkbox.value);
      });
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
    if (!aiDock || (!aiDock.classList.contains("open") && !isAiPopup)) return;
    const modifier = event.ctrlKey || event.metaKey;
    if (modifier && event.key.toLowerCase() === "n") {
      event.preventDefault();
      createAiConversation();
    } else if (modifier && event.key.toLowerCase() === "k") {
      event.preventDefault();
      aiInput?.focus();
    } else if (modifier && event.shiftKey && event.key.toLowerCase() === "l") {
      event.preventDefault();
      if (aiDock.getBoundingClientRect().width >= 760) aiDock.classList.toggle("conversations-collapsed");
      else aiDock.classList.toggle("show-conversations");
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

  if (isAiPopup) {
    aiDock?.classList.add("open");
    aiDock?.setAttribute("aria-hidden", "false");
    loadAiState().catch(() => aiWelcome());
  }
});

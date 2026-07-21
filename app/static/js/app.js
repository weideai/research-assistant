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
  const aiCompletionToast = document.querySelector("#ai-completion-toast");
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const assistantPage = {
    type: document.body.dataset.assistantPageType || "",
    id: document.body.dataset.assistantPageId || "",
  };
  let aiConversationId = window.localStorage.getItem("research-assistant-conversation") || "";
  let aiLoaded = false;
  let aiExperimentOptions = [];
  let aiRequestRunning = false;
  const baseDocumentTitle = document.title;

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

  const aiWelcome = () => {
    aiMessages.innerHTML = "";
    const welcome = makeElement("div", "ai-welcome");
    welcome.append(makeElement("b", "", "可以开始讨论实验了"));
    welcome.append(makeElement("p", "", "比较历史实验、生成下一次计划或周报，也可以修改当前页面。所有写入都要经过差异确认。"));
    aiMessages.append(welcome);
  };

  const renderAiMessage = (message) => {
    const article = makeElement("article", `ai-message ${message.role}`);
    const label = makeElement("small", "ai-message-role", message.role === "user" ? "你" : "AI 助手");
    const content = makeElement("div", "ai-message-content", message.content);
    article.append(label, content);

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
      heading.append(makeElement("b", "", "页面修改提案"), makeElement("span", "", message.applied ? "已保存" : "等待确认"));
      proposal.append(heading);
      message.proposal.diff?.forEach((change) => {
        const row = makeElement("div", "ai-diff-row");
        row.append(makeElement("b", "", change.field));
        const values = makeElement("div", "ai-diff-values");
        const before = makeElement("div", "before");
        before.append(makeElement("small", "", "修改前"), makeElement("pre", "", change.before || "（空）"));
        const after = makeElement("div", "after");
        after.append(makeElement("small", "", "修改后"), makeElement("pre", "", change.after || "（空）"));
        values.append(before, after);
        row.append(values);
        proposal.append(row);
      });
      if (!message.applied) {
        const apply = makeElement("button", "btn primary full ai-apply-proposal", "确认并保存到页面");
        apply.type = "button";
        apply.dataset.messageId = message.id;
        proposal.append(apply);
      }
      article.append(proposal);
    }
    aiMessages.append(article);
    aiMessages.scrollTop = aiMessages.scrollHeight;
  };

  const setConversation = (conversation) => {
    if (!conversation) {
      aiConversationId = "";
      aiExport?.classList.add("disabled");
      aiWelcome();
      return;
    }
    aiConversationId = String(conversation.id);
    window.localStorage.setItem("research-assistant-conversation", aiConversationId);
    if (aiExport) {
      aiExport.href = `/assistant/conversations/${conversation.id}/export.md`;
      aiExport.classList.remove("disabled");
    }
    aiMessages.innerHTML = "";
    if (!conversation.messages.length) aiWelcome();
    conversation.messages.forEach(renderAiMessage);
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
    setConversation(state.conversation);
    renderExperimentScope(state.experiments, state.conversation?.selected_experiment_ids || []);
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

  document.querySelector("#ai-new-chat")?.addEventListener("click", async () => {
    const data = new FormData();
    data.set("csrf_token", csrfToken);
    data.set("page_type", assistantPage.type);
    data.set("page_id", assistantPage.id);
    appendExperimentScope(data);
    const response = await fetch("/assistant/conversations", {method: "POST", body: data});
    if (!response.ok) return;
    const conversation = await response.json();
    setConversation({...conversation, messages: []});
  });

  document.querySelectorAll("#ai-quick-prompts button").forEach((button) => {
    button.addEventListener("click", () => {
      if (aiInput) aiInput.value = button.textContent;
      aiInput?.focus();
    });
  });

  aiHistoryList?.addEventListener("change", updateHistoryCount);
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
    try {
      const response = await fetch("/assistant/chat", {method: "POST", body: data});
      const result = await response.json();
      pending.remove();
      if (result.conversation_id) {
        aiConversationId = String(result.conversation_id);
        window.localStorage.setItem("research-assistant-conversation", aiConversationId);
        aiExport.href = `/assistant/conversations/${aiConversationId}/export.md`;
        aiExport.classList.remove("disabled");
      }
      aiMessages.querySelector(".ai-welcome")?.remove();
      if (result.user_message) renderAiMessage(result.user_message);
      if (result.assistant_message) renderAiMessage(result.assistant_message);
      if (!result.assistant_message && result.error) renderAiMessage({role: "assistant", content: result.error});
      aiInput.value = "";
      aiFiles.value = "";
      aiFileList.innerHTML = "";
      if (!aiDock?.classList.contains("open")) showAiNotice("点击查看本次回复");
    } catch (_error) {
      pending.textContent = "发送失败，请检查本地服务和 API 设置。";
      if (!aiDock?.classList.contains("open")) showAiNotice("点击查看错误信息", true);
    } finally {
      aiRequestRunning = false;
      sendButton.disabled = false;
      aiFab?.classList.remove("working");
      if (aiModelLabel) aiModelLabel.textContent = aiModelLabel.dataset.idleLabel || "准备就绪";
    }
  });

  aiMessages?.addEventListener("click", async (event) => {
    const button = event.target.closest(".ai-apply-proposal");
    if (!button) return;
    button.disabled = true;
    button.textContent = "正在保存…";
    const data = new FormData();
    data.set("csrf_token", csrfToken);
    const response = await fetch(`/assistant/proposals/${button.dataset.messageId}/apply`, {method: "POST", body: data});
    const result = await response.json();
    if (!response.ok) {
      button.disabled = false;
      button.textContent = result.error || "保存失败";
      return;
    }
    button.textContent = "已保存";
    if (result.redirect_url) window.location.href = result.redirect_url;
  });
});

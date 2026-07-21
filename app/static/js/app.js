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

  const aiFab = document.querySelector("#ai-fab");
  const aiDock = document.querySelector("#ai-dock");
  const aiMessages = document.querySelector("#ai-messages");
  const aiComposer = document.querySelector("#ai-composer");
  const aiInput = document.querySelector("#ai-message-input");
  const aiFiles = document.querySelector("#ai-file-input");
  const aiFileList = document.querySelector("#ai-file-list");
  const aiExport = document.querySelector("#ai-export-chat");
  const aiModelLabel = document.querySelector("#ai-model-label");
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const assistantPage = {
    type: document.body.dataset.assistantPageType || "",
    id: document.body.dataset.assistantPageId || "",
  };
  let aiConversationId = window.localStorage.getItem("research-assistant-conversation") || "";
  let aiLoaded = false;

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
    welcome.append(makeElement("p", "", "询问实验规划、分析记录，或让我修改当前实验/记录。所有页面修改都要经过差异确认。"));
    aiMessages.append(welcome);
  };

  const renderAiMessage = (message) => {
    const article = makeElement("article", `ai-message ${message.role}`);
    const label = makeElement("small", "ai-message-role", message.role === "user" ? "你" : "AI 助手");
    const content = makeElement("div", "ai-message-content", message.content);
    article.append(label, content);

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
        const link = makeElement("a", "", `[${index + 1}] ${reference.title || reference.url}`);
        link.href = reference.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        references.append(link);
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
    if (aiModelLabel) aiModelLabel.textContent = state.api.enabled ? state.api.model : "未配置 API";
    aiLoaded = true;
  };

  aiFab?.addEventListener("click", async () => {
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

  document.querySelector("#ai-new-chat")?.addEventListener("click", async () => {
    const data = new FormData();
    data.set("csrf_token", csrfToken);
    data.set("page_type", assistantPage.type);
    data.set("page_id", assistantPage.id);
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

  aiFiles?.addEventListener("change", () => {
    aiFileList.innerHTML = "";
    Array.from(aiFiles.files || []).slice(0, 8).forEach((file) => aiFileList.append(makeElement("span", "", file.name)));
  });

  aiComposer?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!aiInput.value.trim() && !(aiFiles.files || []).length) return;
    const sendButton = aiComposer.querySelector(".ai-send");
    sendButton.disabled = true;
    const pending = makeElement("div", "ai-thinking", "AI 正在分析…");
    aiMessages.append(pending);
    aiMessages.scrollTop = aiMessages.scrollHeight;
    const data = new FormData(aiComposer);
    data.set("conversation_id", aiConversationId);
    data.set("page_type", assistantPage.type);
    data.set("page_id", assistantPage.id);
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
    } catch (_error) {
      pending.textContent = "发送失败，请检查本地服务和 API 设置。";
    } finally {
      sendButton.disabled = false;
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

(() => {
  "use strict";
  const R=window.RLab,{$,$$,state,invoke,navigate,icons,toast,escapeHtml,dateLabel,statusBadge,emptyRow,nativeDialog}=R;
  let settingsData=null,searchTimer,aiChange=null,aiHistoryPage=1,aiHistoryPages=1,aiHistoryTimer,aiHistoryItems=[];
  let trashItems=[],trashPage=1,trashPageSize=20;
  let currentConversationId=null,aiMessages=[],lastAiPrompt="",lastAiReply="";
  const aiHistorySelection=new Set();
  let aiRecordItems=[],aiRecordPage=1,aiRecordPageSize=10,aiRecordSearch="",aiRecordStart="",aiRecordEnd="",aiRecordProjectId=null;
  const aiRecordSelection=new Set();
  let aiRecordSelectionBeforeOpen=[];
  const aiRecordStatusLabels={draft:"草稿",in_progress:"进行中",awaiting_analysis:"待分析",completed:"已完成",archived:"已归档"};
  const entityLabels={project:"项目",record:"实验记录",literature:"文献",file:"文件",note:"笔记",task:"任务",calendar_event:"日历事件",weekly:"周报",lab_record:"实验记录",library_item:"文件",weekly_report:"周报"};

  async function search(){const input=$("#global-search-input"),query=input.value.trim();if(!query){$("#search-results").innerHTML=`<div class="empty-state"><i data-lucide="search"></i><p>输入关键词开始搜索</p></div>`;$("#search-diagnostic").textContent="输入关键词开始搜索";icons();return;}const data=await invoke("search.query",{query});$("#search-diagnostic").textContent=`${data.diagnostic} · ${data.items.length} 个结果`;const groups=Object.groupBy?Object.groupBy(data.items,x=>x.entity_type):data.items.reduce((acc,x)=>((acc[x.entity_type]??=[]).push(x),acc),{});$("#search-results").innerHTML=Object.entries(groups).map(([type,items])=>`<section><header><h2>${entityLabels[type]||type}</h2><span>${items.length}</span></header>${items.map((item,index)=>`<button class="search-result ${index===0?"highlighted":""}" data-search-view="${item.view_key}" data-search-type="${type}" data-search-id="${item.id}"><i data-lucide="${searchIcon(type)}"></i><span><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.excerpt||"无摘要")}</small></span><i data-lucide="arrow-up-right"></i></button>`).join("")}</section>`).join("")||`<div class="empty-state"><i data-lucide="search-x"></i><p>没有找到匹配内容</p></div>`;icons();}
  function searchIcon(type){return {project:"folder-kanban",record:"flask-conical",literature:"book-open",file:"file",note:"notebook-pen",task:"circle-check",weekly:"presentation"}[type]||"search";}
  async function openSearchResult(button){const type=button.dataset.searchType,id=Number(button.dataset.searchId),view=button.dataset.searchView;if(type==="record")return navigate("record-edit",{id});if(type==="project")return navigate("project-workbench",{id});if(type==="literature")return navigate("literature",{id});if(type==="note")return navigate("notes",{id});if(type==="task")return navigate("tasks",{id});if(type==="weekly")return navigate("weekly-library",{id});if(type==="file")return navigate("files",{id});return navigate(view||"home",{id});}

  const trashSelection=new Map();
  function trashKey(item){return `${item.entity_type}:${item.id}`;}
  function syncTrashSelection(){const bar=$("#trash-bulk-bar");bar.hidden=!trashSelection.size;$("[data-trash-selected-count]",bar).textContent=trashSelection.size;const boxes=$$("[data-trash-select]");$("#trash-select-page").checked=boxes.length>0&&boxes.every(box=>box.checked);}
  async function trash(){trashItems=await invoke("trash.list",{});const page=R.paginate(trashItems,trashPage,trashPageSize);trashPage=page.page;$("#trash-list").innerHTML=page.items.length?page.items.map(item=>`<tr class="${trashSelection.has(trashKey(item))?"selected":""}"><td class="check-column"><input type="checkbox" data-trash-select="${escapeHtml(trashKey(item))}" ${trashSelection.has(trashKey(item))?"checked":""} aria-label="选择 ${escapeHtml(item.title)}"></td><td><span class="record-cell"><i data-lucide="trash-2"></i>${escapeHtml(item.title)}</span></td><td>${entityLabels[item.entity_type]||item.entity_type}</td><td>${dateLabel(item.deleted_at,true)}</td><td>${escapeHtml(item.impact)}</td><td><div class="row-actions"><button class="button compact" data-restore-type="${item.entity_type}" data-restore-id="${item.id}"><i data-lucide="undo-2"></i>恢复</button><button class="icon-button subtle" data-trash-purge-type="${item.entity_type}" data-trash-purge-id="${item.id}" title="永久删除" aria-label="永久删除 ${escapeHtml(item.title)}"><i data-lucide="trash-2"></i></button></div></td></tr>`).join(""):emptyRow(6,"回收站为空。");R.renderPagination($("#trash-pagination"),page,value=>{trashPage=value;trash();},value=>{trashPageSize=value;trashPage=1;trash();});syncTrashSelection();icons();}
  async function restoreTrash(items){if(!items.length)return;for(const item of items)await invoke("trash.restore",{entity_type:item.entity_type,id:Number(item.id)});items.forEach(item=>trashSelection.delete(trashKey(item)));toast(`已恢复 ${items.length} 项`);await trash();}
  async function purgeTrash(items){if(!items.length||!await R.confirmAction("永久删除",`确认永久删除 ${items.length} 项吗？此操作不可恢复。`))return;for(const item of items)await invoke("trash.purge",{entity_type:item.entity_type,id:Number(item.id)});items.forEach(item=>trashSelection.delete(trashKey(item)));toast(`已永久删除 ${items.length} 项`);await trash();}

  async function settings(){settingsData=await invoke("settings.get",{});showSettings("workspace");}
  let apiPresetChoice;
  let apiPresetTemplate = "";
  const deepSeekApi = "https://api.deepseek.com";

  function renderApiSettings(data) {
    const presets = data.api_presets || [];
    const selectedId = apiPresetChoice === undefined ? data.api.id : apiPresetChoice;
    const selected = presets.find(preset => preset.id === selectedId);
    const fields = selected || {
      name: apiPresetTemplate === "deepseek" ? "DeepSeek" : "",
      url: apiPresetTemplate === "deepseek" ? deepSeekApi : "",
      model: "", enabled: true, has_key: false,
    };
    const current = selected && data.api.id === selected.id;
    const ready = data.api.enabled && data.api.has_key && data.api.model;
    return `<header><div><h2>API 与模型</h2><p>管理 OpenAI 兼容接口</p></div>
      <span class="api-current">${ready ? `助手使用 ${escapeHtml(data.api.name)}` : "助手尚未配置可用方案"}</span></header>
      <div class="api-profile-bar">
        <label>编辑方案<select data-api-profile>
          <option value="" ${selected ? "" : "selected"}>新方案</option>
          ${presets.map(preset => `<option value="${preset.id}" ${preset.id === selectedId ? "selected" : ""}>${escapeHtml(preset.name)}${preset.id === data.api.id ? " · 当前" : ""}</option>`).join("")}
        </select></label>
        <button class="button" type="button" data-api-action="new"><i data-lucide="plus"></i>新建方案</button>
      </div>
      <div class="api-provider-bar">
        <button class="button compact" type="button" data-api-action="deepseek">使用 DeepSeek 预设</button>
        <button class="text-button" type="button" data-open-url="https://www.deepseek.com/">官网</button>
        <button class="text-button" type="button" data-open-url="https://platform.deepseek.com/api_keys">管理 API Key</button>
        <button class="text-button" type="button" data-open-url="https://api-docs.deepseek.com/zh-cn/">接口文档<i data-lucide="external-link"></i></button>
      </div>
      <form id="api-preset-form" data-preset-id="${selected?.id || ""}">
        <label>方案名称<input name="name" maxlength="120" value="${escapeHtml(fields.name)}" placeholder="例如 DeepSeek 或我的转发接口" required></label>
        <label>API 地址<input type="url" name="url" maxlength="500" value="${escapeHtml(fields.url)}" placeholder="https://api.example.com/v1" spellcheck="false" required></label>
        <label>API Key<input name="api_key" type="password" maxlength="4096" autocomplete="new-password" placeholder="${fields.has_key ? "已加密保存，留空沿用" : "粘贴服务商提供的 Key"}"></label>
        <div class="api-model-row">
          <label>模型 ID<input name="model" maxlength="160" value="${escapeHtml(fields.model)}" placeholder="拉取后选择，或手动输入" spellcheck="false"></label>
          <button class="button" type="button" data-api-action="models"><i data-lucide="refresh-cw"></i>拉取模型</button>
        </div>
        <label data-api-results hidden>从接口返回的模型中选择<select data-api-models></select></label>
        <label class="toggle-row"><span><b>允许助手使用此方案</b><small>${fields.has_key ? "Key 已存储在本机" : "此方案尚未保存 Key"}</small></span><input name="enabled" type="checkbox" ${fields.enabled ? "checked" : ""}></label>
        <p class="api-feedback" role="status" aria-live="polite"></p>
        <div class="api-profile-actions">
          <button class="button primary" type="submit"><i data-lucide="save"></i>保存方案</button>
          ${selected && !current ? `<button class="button" type="button" data-api-action="activate">设为助手当前方案</button>` : ""}
        </div>
      </form>`;
  }

  function apiFeedback(form, message, isError = false) {
    const feedback = $(".api-feedback", form);
    feedback.textContent = message;
    feedback.classList.toggle("error", isError);
  }

  function apiPayload(form) {
    const payload = Object.fromEntries(new FormData(form));
    if (form.dataset.presetId) payload.id = Number(form.dataset.presetId);
    payload.enabled = form.elements.enabled.checked;
    return payload;
  }

  async function selectApiPreset(id, template = "") {
    const form = $("#api-preset-form");
    if (form?.dataset.dirty && !await R.confirmAction("切换 API 方案", "当前方案有未保存的修改，是否放弃这些修改？")) {
      $("[data-api-profile]").value = form.dataset.presetId;
      return;
    }
    apiPresetChoice = id;
    apiPresetTemplate = template;
    showSettings("api");
    const focus = template ? "api_key" : "name";
    $("#api-preset-form").elements[focus].focus();
  }

  async function fetchApiModels(form, button) {
    if (!form.elements.url.reportValidity()) return;
    const payload = apiPayload(form);
    button.disabled = true;
    apiFeedback(form, "正在拉取模型列表…");
    try {
      const result = await invoke("api.models.discover", {id:payload.id, url:payload.url, api_key:payload.api_key});
      if (!form.isConnected || form.elements.url.value !== payload.url || form.elements.api_key.value !== payload.api_key) return;
      const picker = $("[data-api-models]", form);
      picker.replaceChildren(new Option("选择一个模型", ""), ...result.models.map(id => new Option(id, id)));
      $("[data-api-results]", form).hidden = false;
      if (result.models.includes(form.elements.model.value)) picker.value = form.elements.model.value;
      apiFeedback(form, `已获取 ${result.models.length} 个模型。请选择或手动填写模型 ID。`);
      picker.focus();
    } catch (error) {
      if (form.isConnected && form.elements.url.value === payload.url && form.elements.api_key.value === payload.api_key) {
        apiFeedback(form, error.message, true);
      }
    } finally {
      button.disabled = false;
    }
  }

  async function persistApiPreset(form, activate = false) {
    if (activate && form.dataset.dirty) {
      apiFeedback(form, "请先保存方案修改，再设为当前方案。", true);
      return;
    }
    const payload = apiPayload(form);
    const controls = [...form.elements];
    const editable = controls.filter(control => !control.disabled);
    editable.forEach(control => control.disabled = true);
    try {
      const result = activate
        ? await invoke("api.presets.activate", {id:payload.id})
        : await invoke("api.presets.save", payload);
      settingsData.api_presets = [
        ...(settingsData.api_presets || []).filter(preset => preset.id !== result.id),
        result,
      ].sort((left, right) => left.name.localeCompare(right.name));
      if (activate || !settingsData.api.id || settingsData.api.id === result.id) settingsData.api = result;
      if (!form.isConnected) return;
      apiPresetChoice = result.id;
      apiPresetTemplate = "";
      showSettings("api");
      apiFeedback($("#api-preset-form"), activate ? "助手已切换到此方案。" : "方案已保存。");
    } catch (error) {
      apiFeedback(form, error.message, true);
    } finally {
      editable.forEach(control => control.disabled = false);
    }
  }

  function showSettings(section){$$('[data-settings-section]').forEach(x=>{const active=x.dataset.settingsSection===section;x.classList.toggle("active",active);x.setAttribute("aria-selected",String(active));x.tabIndex=active?0:-1;});const node=$("#settings-content"),d=settingsData;const templates={
    workspace:`<header><h2>工作区</h2><p>本机单工作区数据与时区</p></header><form data-settings-form="workspace"><label>工作区名称<input name="name" value="${escapeHtml(d.workspace.name)}" required></label><label>时区<input name="timezone" value="${escapeHtml(d.workspace.timezone)}" required></label><label>数据目录<input value="${escapeHtml(d.workspace.data_path)}" readonly></label><button class="button primary" type="submit"><i data-lucide="save"></i>保存</button></form>`,
    executors:`<header><h2>执行者</h2><p>统一管理可分配到项目和实验记录的人员</p></header><div class="settings-list">${d.executors.map(x=>`<div><i data-lucide="user-round"></i><span><b>${escapeHtml(x.name)}</b><small>${escapeHtml(x.role||"未设置角色")}</small></span>${statusBadge(x.is_active?"active":"disabled")}</div>`).join("")||`<p class="muted">尚无执行者</p>`}</div><form class="inline-settings-form" data-settings-form="executor"><input name="name" placeholder="执行者姓名" required><input name="role" placeholder="角色"><button class="button primary" type="submit"><i data-lucide="plus"></i>添加</button></form>`,
    save:`<header><h2>保存</h2><p>自动保存与恢复策略</p></header><form data-settings-form="save"><label class="toggle-row"><span><b>自动保存</b><small>编辑实验记录时定时保存</small></span><input name="autosave" type="checkbox" ${d.save.autosave?"checked":""}></label><label>保存间隔（秒）<input name="interval" type="number" min="5" max="600" value="${d.save.interval}"></label><button class="button primary" type="submit"><i data-lucide="save"></i>保存</button></form>`,
    zotero:`<header><h2>Zotero</h2><p>只读连接 Zotero Local API</p></header><div class="status-banner ${d.zotero.state}"><i data-lucide="library"></i><span><b>${d.zotero.state==="connected"?"已连接":"未连接"}</b><small>不会读写 zotero.sqlite</small></span></div><form data-settings-form="zotero"><label>Local API 地址<input name="base_url" value="${escapeHtml(d.zotero.base_url)}" required></label><button class="button primary" type="submit"><i data-lucide="save"></i>保存</button></form>`,
    api: section === "api" ? renderApiSettings(d) : "",
    appearance:`<header><h2>主题与背景</h2><p>四套皮肤共享相同的信息结构</p></header><label>界面皮肤<select id="settings-skin"><option value="soft-lab">柔雾实验室</option><option value="ide-light">Indigo Lab</option><option value="ide-dark">Research OS</option><option value="swiss">经典 Swiss</option></select></label><div class="skin-preview-row"><button data-set-skin="soft-lab">Soft Lab</button><button data-set-skin="ide-light">Indigo</button><button data-set-skin="ide-dark">Research OS</button><button data-set-skin="swiss">Swiss</button></div>`,
    backup:`<header><h2>备份</h2><p>保存数据库快照或完整工作区归档</p></header><div class="action-block"><i data-lucide="database-backup"></i><span><b>创建备份</b><small>保存到本地 backups 目录</small></span><label>范围<select id="backup-scope"><option value="workspace">完整工作区</option><option value="database">仅数据库</option></select></label><button class="button primary" id="create-backup"><i data-lucide="archive"></i>立即备份</button></div><p>完整工作区包含数据库及 library、uploads 中的托管文件。外部链接原文件不包含；换机恢复后需重新配置 API 凭据。</p><p id="backup-result" class="muted"></p>`,
    updates:`<header><h2>更新</h2><p>原位升级保留本地数据和附件</p></header><div class="status-banner connected"><i data-lucide="badge-check"></i><span><b>当前版本已就绪</b><small>更新前会创建备份并执行迁移预检</small></span></div><button class="button"><i data-lucide="refresh-cw"></i>检查更新</button>`,
    about:`<header><h2>关于</h2><p>独立桌面科研记录与资料管理工具</p></header><div class="about-product"><span class="brand-mark">R</span><div><h3>${escapeHtml(d.about.product)}</h3><p>作者：${escapeHtml(d.about.author)}</p><small>正式进程不监听 HTTP/TCP 端口</small></div></div>`,
  };node.innerHTML=templates[section]||templates.workspace;if(section==="appearance")$("#settings-skin").value=document.documentElement.dataset.skin;icons();}
  async function saveSettings(form){const payload=Object.fromEntries(new FormData(form));payload.section=form.dataset.settingsForm;for(const checkbox of $$('input[type="checkbox"]',form))payload[checkbox.name]=checkbox.checked;try{await invoke("settings.save",payload);settingsData=await invoke("settings.get",{});showSettings(payload.section==="executor"?"executors":payload.section);toast("设置已保存");}catch(error){toast(error.message);}}

  function currentAiTarget(){const projectId=Number($("#ai-project").value),target=state.projects.find(item=>item.id===projectId);return {type:"project",target};}
  function aiValue(value){if(value===null||value===undefined||value==="")return "清空";if(typeof value==="object")return JSON.stringify(value);return String(value);}
  function renderAiConversation(){const node=$("#ai-output");if(!aiMessages.length){node.innerHTML=`<div class="assistant-welcome"><i data-lucide="sparkles"></i><b>从一个项目开始</b><p>可选择相关实验记录，也可仅使用项目信息。</p></div>`;icons();return;}node.innerHTML=`<div class="assistant-chat-thread">${aiMessages.map((message,index)=>`<article class="assistant-message ${message.role}"><span>${message.role==="user"?"你":"AI"}</span><div><p>${escapeHtml(message.content||"")}</p>${message.references?.length?`<div class="assistant-references">${message.references.map(reference=>`<a href="${escapeHtml(reference.url)}" data-open-url="${escapeHtml(reference.url)}">${escapeHtml(reference.title||reference.url)}</a>`).join("")}</div>`:""}${message.proposal&&Object.keys(message.proposal).length?`<div class="diff-list">${Object.entries(message.proposal).map(([field,value])=>`<label><input type="checkbox" data-ai-field="${field}" checked><span><b>${escapeHtml(message.schema?.[field]?.label||field)}</b><small>${escapeHtml(aiValue(value))}</small></span></label>`).join("")}</div>${message.changeStatus==="proposed"||!message.changeStatus?`<button class="button compact primary" id="apply-ai-change"><i data-lucide="check"></i>应用已选字段</button>`:""}`:""}<footer class="assistant-message-actions"><button class="text-button" data-ai-message-copy="${index}" type="button"><i data-lucide="copy"></i>复制</button>${message.role==="assistant"&&index===aiMessages.length-1?`<button class="text-button" data-ai-message-regenerate="${index}" type="button"><i data-lucide="refresh-cw"></i>重新生成</button>`:""}</footer></div></article>`).join("")}</div>`;node.scrollTop=node.scrollHeight;icons();}
  async function aiGenerate(promptOverride=null){const {type,target}=currentAiTarget(),prompt=typeof promptOverride==="string"?promptOverride:$("#ai-prompt").value.trim();if(!target?.id)return toast("请先选择项目历史");if(!prompt)return toast("请输入消息");if(aiRecordProjectId!==target.id){aiRecordProjectId=target.id;aiRecordSelection.clear();syncAiRecordCount();}const button=$("#ai-generate");button.disabled=true;try{const recordIds=[...aiRecordSelection];const preview=await invoke("ai.preview",{target_type:type,target_id:target.id,source_ids:recordIds,records_explicit:true});const result=await invoke("ai.propose",{target_type:type,target_id:target.id,prompt,conversation_id:currentConversationId,record_ids:recordIds,web_access:$("#ai-web-access").checked,source_snapshot:preview.source_snapshot});currentConversationId=result.conversation_id;aiChange=result;lastAiPrompt=prompt;lastAiReply=result.reply;aiMessages.forEach(message=>message.proposal={});aiMessages.push({role:"user",content:prompt},{role:"assistant",content:result.reply,proposal:result.proposal||{},schema:result.field_schema||{},changeId:result.id,changeStatus:result.status,references:result.references||[]});$("#ai-prompt").value="";renderAiConversation();}catch(error){toast(error.message);}finally{button.disabled=false;}}
  async function reloadAfterAi(){if(state.view==="record-edit" && state.dirty){R.setAssistantContext();return;}const loader=R.modules?.get?.(state.view);if(loader?.load)await loader.load(state.params||{});else await R.loadInitial();R.setAssistantContext();}
  async function applyAi(){if(!aiChange)return;const accepted=$$('[data-ai-field]:checked').map(x=>x.dataset.aiField);if(!accepted.length)return toast("请至少选择一个字段");try{const applied=await invoke("ai.apply",{id:aiChange.id,accepted_fields:accepted});localStorage.setItem("rlab-last-ai-change",String(aiChange.id));const message=[...aiMessages].reverse().find(item=>item.changeId===aiChange.id);if(message){message.changeStatus=applied.status;message.proposal={};}await reloadAfterAi();renderAiConversation();toast("AI 内容已写入，可随时回退");}catch(error){toast(error.message);}}
  async function revertAi(){const changeId=aiChange?.id||Number(localStorage.getItem("rlab-last-ai-change"));if(!changeId)return toast("还没有可回退的 AI 写入");try{await invoke("ai.revert",{id:Number(changeId)});localStorage.removeItem("rlab-last-ai-change");const message=[...aiMessages].reverse().find(item=>item.changeId===Number(changeId));if(message)message.changeStatus="reverted";aiChange=null;await reloadAfterAi();renderAiConversation();toast("已回退上次 AI 写入");}catch(error){toast(error.message);}}
  function syncAiRecordCount(){const count=$("#ai-record-count");if(count)count.textContent=aiRecordSelection.size?String(aiRecordSelection.size):"仅项目";}
  function filteredAiRecords(){return aiRecordItems.filter(item=>(!aiRecordSearch||`${item.title} ${item.record_code||""}`.toLowerCase().includes(aiRecordSearch.toLowerCase()))&&(!aiRecordStart||!item.experiment_date||item.experiment_date>=aiRecordStart)&&(!aiRecordEnd||!item.experiment_date||item.experiment_date<=aiRecordEnd));}
  function renderAiRecordPicker(){const dialog=$("#ai-record-picker"),filtered=filteredAiRecords(),page=R.paginate(filtered,aiRecordPage,aiRecordPageSize);aiRecordPage=page.page;const pageSelected=page.items.length&&page.items.every(item=>aiRecordSelection.has(item.id));dialog.innerHTML=`<form method="dialog" class="resource-picker ai-record-picker-form"><header><div><h2>选择实验记录上下文</h2><p>只读取选中记录的文本字段，不读取任何文件</p></div><button class="icon-button" value="cancel"><i data-lucide="x"></i></button></header><div class="query-toolbar"><label class="grow"><span>记录名称</span><div><i data-lucide="search"></i><input data-ai-record-search value="${escapeHtml(aiRecordSearch)}" placeholder="标题或记录编号"></div></label><label><span>开始日期</span><input data-ai-record-start type="date" value="${aiRecordStart}"></label><label><span>结束日期</span><input data-ai-record-end type="date" value="${aiRecordEnd}"></label><button class="button" type="button" data-ai-record-query>查询</button></div><div class="picker-select-toolbar"><label><input type="checkbox" data-ai-record-select-page ${pageSelected?"checked":""}>全选当前页</label><button class="text-button" type="button" data-ai-record-select-filtered>选择全部查询结果（${filtered.length}）</button><button class="text-button" type="button" data-ai-record-clear>清除</button><span>已选择 ${aiRecordSelection.size} 条</span></div><div class="picker-list">${page.items.map(item=>`<label><input type="checkbox" data-ai-record-select="${item.id}" ${aiRecordSelection.has(item.id)?"checked":""}><span><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.record_code||"")} · ${dateLabel(item.experiment_date)} · ${escapeHtml(aiRecordStatusLabels[item.status]||item.status||"—")}</small></span></label>`).join("")||`<div class="empty-state"><p>没有匹配的实验记录</p></div>`}</div><footer class="list-pagination" id="ai-record-pagination"></footer><footer><span>已选择 ${aiRecordSelection.size} 条实验记录</span><button class="button" value="cancel">取消</button><button class="button primary" value="apply">使用所选记录</button></footer></form>`;R.renderPagination($("#ai-record-pagination"),page,value=>{aiRecordPage=value;renderAiRecordPicker();},value=>{aiRecordPageSize=value;aiRecordPage=1;renderAiRecordPicker();});icons();}
  async function openAiRecordPicker(){const projectId=Number($("#ai-project").value);if(!projectId)return toast("请先选择项目");const trigger=document.activeElement;aiRecordItems=await invoke("record.list",{project_id:projectId});if(aiRecordProjectId!==projectId){aiRecordSelection.clear();aiRecordProjectId=projectId;aiRecordPage=1;aiRecordSearch=aiRecordStart=aiRecordEnd="";}aiRecordSelectionBeforeOpen=[...aiRecordSelection];let dialog=$("#ai-record-picker");if(!dialog){dialog=document.createElement("dialog");dialog.id="ai-record-picker";document.body.append(dialog);dialog.addEventListener("close",()=>{if(dialog.returnValue!=="apply"){aiRecordSelection.clear();aiRecordSelectionBeforeOpen.forEach(id=>aiRecordSelection.add(id));}else if(currentConversationId && (aiRecordSelection.size!==aiRecordSelectionBeforeOpen.length || aiRecordSelectionBeforeOpen.some(id=>!aiRecordSelection.has(id)))){
      currentConversationId=null;
      aiMessages=[];
      aiChange=null;
      lastAiPrompt=lastAiReply="";
      renderAiConversation();
      toast("记录范围已更改，下条消息将开始新对话");
    }syncAiRecordCount();dialog._trigger?.focus?.();});}dialog._trigger=trigger;dialog.returnValue="cancel";renderAiRecordPicker();dialog.showModal();}
  async function newAiChat(){const projectId=Number($("#ai-project").value)||null;const conversation=await invoke("ai.conversation.create",{project_id:projectId,record_ids:[...aiRecordSelection],title:"新对话"});currentConversationId=conversation.id;aiMessages=[];aiChange=null;lastAiPrompt=lastAiReply="";renderAiConversation();await loadAiHistory(1);$("#ai-prompt").focus();}
  async function loadAiConversation(id){const data=await invoke("ai.conversation.get",{id});currentConversationId=data.id;if(data.project_id)$("#ai-project").value=String(data.project_id);aiRecordProjectId=data.project_id||null;aiRecordSelection.clear();(data.selected_record_ids||[]).forEach(value=>aiRecordSelection.add(Number(value)));syncAiRecordCount();R.setAssistantContext();aiMessages=(data.messages||[]).map(message=>({role:message.role,content:message.content,proposal:message.proposal||{},changeId:message.change_id,changeStatus:message.change_status}));const lastAssistant=[...aiMessages].reverse().find(message=>message.role==="assistant"),lastUser=[...aiMessages].reverse().find(message=>message.role==="user");lastAiReply=lastAssistant?.content||"";lastAiPrompt=lastUser?.content||"";if(lastAssistant?.changeId){aiChange={id:lastAssistant.changeId};aiMessages.forEach(message=>{if(message!==lastAssistant)message.proposal={};});}renderAiConversation();}
  function setAiHistoryCollapsed(collapsed){const panel=$("#assistant-history-panel"),windowNode=$("#assistant-window"),toggle=$("#ai-history-toggle");if(!panel||!windowNode||!toggle)return;panel.classList.toggle("collapsed",collapsed);windowNode.classList.toggle("history-collapsed",collapsed);toggle.setAttribute("aria-expanded",String(!collapsed));toggle.setAttribute("aria-label",collapsed?"展开对话":"折叠对话");toggle.title=collapsed?"展开对话":"折叠对话";const icon=$("i",toggle);if(icon)icon.setAttribute("data-lucide",collapsed?"chevron-right":"chevron-left");if(collapsed&&panel.classList.contains("managing")){panel.classList.remove("managing");$("#ai-history-manage")?.setAttribute("aria-pressed","false");aiHistorySelection.clear();syncAiHistoryBulk();}icons();}
  function syncAiHistoryBulk(){const bar=$("#ai-history-bulk");bar.hidden=!aiHistorySelection.size;if(!bar.hidden)$("[data-ai-history-selected]",bar).textContent=aiHistorySelection.size;}
  async function loadAiHistory(page=aiHistoryPage){try{const data=await invoke("ai.conversations",{page,per_page:10,query:$("#ai-history-query").value.trim(),project_id:$("#ai-project").value||null,date_start:$("#ai-history-start").value,date_end:$("#ai-history-end").value});aiHistoryItems=data.items||[];aiHistoryPage=data.pagination.page;aiHistoryPages=data.pagination.pages;$("#ai-history-list").innerHTML=aiHistoryItems.length?aiHistoryItems.map(item=>`<article class="assistant-history-item ${Number(item.id)===Number(currentConversationId)?"active":""}"><input type="checkbox" data-ai-history-select="${item.id}" ${aiHistorySelection.has(item.id)?"checked":""} aria-label="选择 ${escapeHtml(item.title)}"><button type="button" data-ai-conversation-id="${item.id}" title="打开聊天"><b>${escapeHtml(item.title)}</b><span>${item.message_count} 条消息<time>${dateLabel(item.updated_at,true)}</time></span></button></article>`).join(""):`<div class="empty-state compact"><p>没有匹配的聊天记录</p></div>`;$("#ai-history-page").textContent=`${aiHistoryPage} / ${aiHistoryPages}`;$("#ai-history-prev").disabled=aiHistoryPage<=1;$("#ai-history-next").disabled=aiHistoryPage>=aiHistoryPages;syncAiHistoryBulk();icons();}catch(error){toast(error.message);}}
  async function toggleAiHistory(){await loadAiHistory(1);}
  async function renameAiHistory(){if(!aiHistorySelection.size)return;const title=prompt("输入新的聊天标题");if(!title?.trim())return;await invoke("ai.conversations.bulk",{ids:[...aiHistorySelection],action:"rename",title:title.trim()});aiHistorySelection.clear();await loadAiHistory(1);toast("聊天标题已更新");}
  async function deleteAiHistory(){if(!aiHistorySelection.size||!await R.confirmAction("删除聊天记录",`删除选中的 ${aiHistorySelection.size} 条聊天记录？已应用的写入记录会被保留。`))return;const result=await invoke("ai.conversations.bulk",{ids:[...aiHistorySelection],action:"delete"});aiHistorySelection.clear();await loadAiHistory(1);toast(result.skipped?`已删除 ${result.updated} 条，${result.skipped} 条含已应用写入而保留`:`已删除 ${result.updated} 条聊天记录`);}
  async function copyAiMessage(index){const message=aiMessages[Number(index)];if(!message?.content)return toast("没有可复制的内容");try{await navigator.clipboard.writeText(message.content);}catch(_){const area=document.createElement("textarea");area.value=message.content;document.body.append(area);area.select();document.execCommand("copy");area.remove();}toast("已复制");}

  document.addEventListener("click",async event=>{
    const result=event.target.closest("[data-search-view]");if(result)await openSearchResult(result);
    const restore=event.target.closest("[data-restore-id]");if(restore){await invoke("trash.restore",{entity_type:restore.dataset.restoreType,id:Number(restore.dataset.restoreId)});toast("已恢复");await trash();}
    const purge=event.target.closest("[data-trash-purge-id]");if(purge)await purgeTrash([{entity_type:purge.dataset.trashPurgeType,id:Number(purge.dataset.trashPurgeId)}]);
    const copy=event.target.closest("[data-ai-message-copy]");if(copy)await copyAiMessage(copy.dataset.aiMessageCopy);
    const regenerate=event.target.closest("[data-ai-message-regenerate]");if(regenerate)lastAiPrompt?await aiGenerate(lastAiPrompt):toast("还没有可重新生成的消息");
    const section=event.target.closest("[data-settings-section]");if(section)showSettings(section.dataset.settingsSection);
    const apiAction = event.target.closest("[data-api-action]");
    if (apiAction) {
      const action = apiAction.dataset.apiAction;
      const form = $("#api-preset-form");
      if (action === "models") await fetchApiModels(form, apiAction);
      if (action === "activate") await persistApiPreset(form, true);
      if (action === "deepseek" || action === "new") await selectApiPreset(null, action);
      return;
    }
    const skin=event.target.closest("[data-set-skin]");if(skin){document.documentElement.dataset.skin=skin.dataset.setSkin;$("#skin-select").value=skin.dataset.setSkin;localStorage.setItem("rlab-desktop-skin",skin.dataset.setSkin);}
    const conversationItem=event.target.closest("[data-ai-conversation-id]");if(conversationItem)await loadAiConversation(Number(conversationItem.dataset.aiConversationId));
    const historySelect=event.target.closest("[data-ai-history-select]");if(historySelect){historySelect.checked?aiHistorySelection.add(Number(historySelect.dataset.aiHistorySelect)):aiHistorySelection.delete(Number(historySelect.dataset.aiHistorySelect));syncAiHistoryBulk();}
    if(event.target.closest("[data-ai-record-query]")){aiRecordSearch=$("[data-ai-record-search]").value.trim();aiRecordStart=$("[data-ai-record-start]").value;aiRecordEnd=$("[data-ai-record-end]").value;aiRecordPage=1;renderAiRecordPicker();}
    if(event.target.closest("[data-ai-record-select-filtered]")){filteredAiRecords().forEach(item=>aiRecordSelection.add(item.id));renderAiRecordPicker();}
    if(event.target.closest("[data-ai-record-clear]")){aiRecordSelection.clear();renderAiRecordPicker();}
    if(event.target.closest("#create-backup")){try{const data=await invoke("backup.create",{scope:$("#backup-scope").value});$("#backup-result").textContent=`已创建：${data.path}（${R.formatBytes(data.size_bytes)}）`;toast("备份已创建");}catch(error){toast(error.message);}}
    if(event.target.closest("#apply-ai-change"))await applyAi();
  });
  document.addEventListener("submit",event=>{const form=event.target.closest("[data-settings-form]");if(form){event.preventDefault();saveSettings(form);}});
  $("#settings-content").addEventListener("submit", event => {
    if (event.target.id !== "api-preset-form") return;
    event.preventDefault();
    persistApiPreset(event.target);
  });
  $("#settings-content").addEventListener("change", event => {
    if (event.target.matches("[data-api-profile]")) {
      selectApiPreset(Number(event.target.value) || null);
    } else if (event.target.matches("[data-api-models]") && event.target.value) {
      const form = event.target.form;
      form.elements.model.value = event.target.value;
      form.dataset.dirty = "true";
    }
  });
  $("#settings-content").addEventListener("input", event => {
    const form = event.target.form;
    if (form?.id !== "api-preset-form") return;
    form.dataset.dirty = "true";
    if (event.target.name === "url" || event.target.name === "api_key") {
      $("[data-api-results]", form).hidden = true;
      apiFeedback(form, "");
    }
  });
  document.addEventListener("change",event=>{if(event.target.matches("[data-trash-select]")){const item=trashItems.find(value=>trashKey(value)===event.target.dataset.trashSelect);if(item){event.target.checked?trashSelection.set(trashKey(item),item):trashSelection.delete(trashKey(item));event.target.closest("tr")?.classList.toggle("selected",event.target.checked);syncTrashSelection();}}if(event.target.matches("[data-ai-record-select]")){const id=Number(event.target.dataset.aiRecordSelect);event.target.checked?aiRecordSelection.add(id):aiRecordSelection.delete(id);renderAiRecordPicker();}if(event.target.matches("[data-ai-record-select-page]")){const page=R.paginate(filteredAiRecords(),aiRecordPage,aiRecordPageSize);page.items.forEach(item=>event.target.checked?aiRecordSelection.add(item.id):aiRecordSelection.delete(item.id));renderAiRecordPicker();}});
  $("#global-search-input").addEventListener("input",()=>{clearTimeout(searchTimer);searchTimer=setTimeout(search,120);});$("#global-search-input").addEventListener("keydown",event=>{const results=$$(".search-result");if(event.key==="ArrowDown"||event.key==="ArrowUp"){event.preventDefault();if(!results.length)return;const current=Math.max(0,results.findIndex(item=>item.classList.contains("highlighted"))),next=event.key==="ArrowDown"?Math.min(results.length-1,current+1):Math.max(0,current-1);results.forEach((item,index)=>item.classList.toggle("highlighted",index===next));results[next].scrollIntoView({block:"nearest"});return;}if(event.key==="Enter"){event.preventDefault();$(".search-result.highlighted")?.click();}});$("#rebuild-search").addEventListener("click",async()=>{const data=await invoke("search.rebuild",{});$("#search-diagnostic").textContent=`${data.diagnostic} · ${data.count} 个文档`;await search();toast("搜索索引已重建");});
  document.addEventListener("rlab:assistant-open",()=>loadAiHistory(1));
  $("#ai-generate").addEventListener("click",()=>aiGenerate());$("#ai-revert").addEventListener("click",revertAi);$("#ai-project").addEventListener("change",()=>{const projectId=Number($("#ai-project").value)||null;currentConversationId=null;aiMessages=[];aiChange=null;lastAiPrompt=lastAiReply="";aiRecordProjectId=projectId;aiRecordSelection.clear();syncAiRecordCount();R.setAssistantContext();renderAiConversation();loadAiHistory(1);});$("#ai-select-records").addEventListener("click",openAiRecordPicker);for(const button of [$("#assistant-new-chat"),$("#assistant-new-chat-side")])button.addEventListener("click",newAiChat);$("#ai-history-toggle").addEventListener("click",()=>setAiHistoryCollapsed(!$("#assistant-history-panel").classList.contains("collapsed")));setAiHistoryCollapsed(true);$("#ai-history-manage").addEventListener("click",event=>{const panel=$("#assistant-history-panel"),active=!panel.classList.contains("managing");panel.classList.toggle("managing",active);event.currentTarget.setAttribute("aria-pressed",String(active));if(!active){aiHistorySelection.clear();syncAiHistoryBulk();}});$("#ai-history-prev").addEventListener("click",()=>loadAiHistory(aiHistoryPage-1));$("#ai-history-next").addEventListener("click",()=>loadAiHistory(aiHistoryPage+1));$("#ai-history-select-page").addEventListener("click",()=>{aiHistoryItems.forEach(item=>aiHistorySelection.add(item.id));loadAiHistory(aiHistoryPage);});$("#ai-history-rename").addEventListener("click",renameAiHistory);$("#ai-history-delete").addEventListener("click",deleteAiHistory);$("#ai-history-query").addEventListener("input",()=>{clearTimeout(aiHistoryTimer);aiHistoryTimer=setTimeout(()=>loadAiHistory(1),160);});for(const input of [$("#ai-history-start"),$("#ai-history-end")])input.addEventListener("change",()=>loadAiHistory(1));$("#ai-prompt").addEventListener("keydown",event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();aiGenerate();}});$("#trash-select-page").addEventListener("change",event=>{const page=R.paginate(trashItems,trashPage,trashPageSize);page.items.forEach(item=>event.target.checked?trashSelection.set(trashKey(item),item):trashSelection.delete(trashKey(item)));trash();});$("#trash-clear-selection").addEventListener("click",()=>{trashSelection.clear();trash();});$("#trash-restore-selected").addEventListener("click",()=>restoreTrash([...trashSelection.values()]));$("#trash-purge-selected").addEventListener("click",()=>purgeTrash([...trashSelection.values()]));
  R.register("search",{load:search});R.register("recycle",{load:trash});R.register("settings",{load:settings});
})();

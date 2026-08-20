(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const bridgeRequired = window.location.hash === "#bridge=pywebview"
    || new URLSearchParams(window.location.search).get("bridge") === "pywebview";
  const supportedProtocol = {minimum: 1, maximum: 1};
  const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
  const state = {
    view: "home", params: {}, history: [{view:"home", params:{}}], historyIndex: 0,
    projects: [], records: [], dashboard: null, currentProject: null, currentRecord: null,
    currentNote: null, currentLiterature: null, currentWeekly: null, currentTask: null, currentCalendarEvent: null,
    lastAiChangeId: null, dirty: false, saveTimer: null,
    navigationLock: "", lastNavigationKey: "", lastNavigationAt: 0,
    navigationBusy: false, pendingNavigation: null,
  };
  const modules = new Map();
  let booted = false;
  let toastTimer;

  const meta = {
    home:["首页","工作台"], projects:["项目","研究管理"], "project-workbench":["项目工作台","项目"],
    records:["实验记录","记录库"], "record-edit":["编辑记录","实验记录"], "record-files":["文件与数据","实验记录"],
    "record-read":["阅读与导出","实验记录"], "record-history":["修订历史","实验记录"], "record-export":["导出中心","实验记录"],
    literature:["文献库","资料"], notes:["笔记","资料"], files:["文件库","资料"], tasks:["任务","安排"],
    calendar:["日历","安排"], weekly:["本周工作台","周报"], "weekly-library":["周报资料库","周报"],
    "weekly-ppt":["生成 PPT","周报"], recycle:["回收站","系统"], settings:["设置","系统"], search:["全局搜索","搜索层"],
  };
  const navParent = {
    "project-workbench":"projects", "record-edit":"records", "record-files":"records", "record-read":"records",
    "record-history":"records", "weekly-library":"weekly", "weekly-ppt":"weekly",
  };
  const statusLabels = {active:"进行中",paused:"已暂停",draft:"草稿",submitted:"已提交",reviewed:"已批注",in_progress:"进行中",awaiting_analysis:"待分析",completed:"已完成",archived:"已归档",todo:"待办",doing:"进行中",blocked:"受阻",done:"已完成",cancelled:"已取消",available:"可用",missing:"路径失效",modified:"文件已变更"};

  const demo = {
    projects:[
      {id:1,title:"胶质瘤细胞耐药机制",code:"GLIOMA-26",objective:"比较低氧条件下耐药相关通路变化，并验证关键候选基因。",status:"active",status_label:"进行中",record_count:2,row_version:1,updated_at:"2026-08-11T14:20:00"},
      {id:2,title:"耐药基因功能验证",code:"GENE-07",objective:"通过转染与药敏实验验证候选基因功能。",status:"active",status_label:"进行中",record_count:2,row_version:1,updated_at:"2026-08-10T17:35:00"},
      {id:3,title:"酶催化活性影响因素研究",code:"ENZ-03",objective:"系统评估温度与 pH 对目标酶活性的影响。",status:"active",status_label:"进行中",record_count:1,row_version:1,updated_at:"2026-08-09T14:18:00"},
    ],
    records:[
      {id:1,project_id:1,project_title:"胶质瘤细胞耐药机制",record_code:"LAB-20260811-001",title:"低氧培养条件预实验",status:"in_progress",experiment_date:"2026-08-11",executor_snapshot:"面壁者",location:"细胞房 A2",row_version:1,updated_at:"2026-08-11T14:20:00",objective:"建立稳定低氧培养条件并观察细胞状态。",background:"低氧微环境可能改变耐药相关信号通路。",hypothesis:"1% O₂ 培养 24 h 可诱导可重复的低氧反应。",design:"设置常氧对照与 1% O₂ 低氧组。",materials_conditions:"U87 细胞；DMEM；低氧培养箱。",expected_result:"低氧组 HIF-1α 信号升高，细胞活率保持在 85% 以上。",actual_process_summary:"已完成培养条件设置，等待 24 h 终点采样。",actual_result:"",analysis:"",conclusion:"",next_steps:"完成取样并检测 HIF-1α。",is_finalized:false,steps:[{title:"细胞铺板",instruction:"按 2×10⁵ cells/well 接种。"},{title:"低氧培养",instruction:"培养箱设置为 1% O₂。"}]},
      {id:2,project_id:2,project_title:"耐药基因功能验证",record_code:"LAB-20260810-001",title:"大肠杆菌转化效率优化",status:"completed",experiment_date:"2026-08-10",executor_snapshot:"",location:"",row_version:1,updated_at:"2026-08-10T17:35:00",objective:"优化转化条件。",actual_result:"42°C 热激 45 s 组转化效率最高。",conclusion:"采用 45 s 作为后续标准条件。",steps:[]},
      {id:3,project_id:2,project_title:"耐药基因功能验证",record_code:"LAB-20260810-002",title:"质粒提取与纯度检测",status:"completed",experiment_date:"2026-08-10",executor_snapshot:"",location:"",row_version:1,updated_at:"2026-08-10T16:20:00",steps:[]},
      {id:4,project_id:3,project_title:"酶催化活性影响因素研究",record_code:"LAB-20260809-001",title:"不同温度下酶活性测定",status:"awaiting_analysis",experiment_date:"2026-08-09",executor_snapshot:"",location:"",row_version:1,updated_at:"2026-08-09T14:18:00",steps:[]},
    ],
    literature:[{id:1,source:"zotero",title:"Hypoxia signaling in glioblastoma",authors:["Chen L.","Wang Y."],year:2025,journal:"Cancer Research",doi:"10.1000/example.1",read_status:"reading",abstract:"综述低氧微环境对胶质瘤进展和耐药的影响。",keywords:["hypoxia","glioblastoma"],reading_notes:"关注 HIF-1α 与药物外排通路。",updated_at:"2026-08-11T11:00:00"},{id:2,source:"manual",title:"Cell culture under controlled oxygen tension",authors:["Smith J."],year:2024,journal:"Methods",doi:"",read_status:"read",abstract:"可控氧浓度细胞培养方法。",keywords:["cell culture"],reading_notes:"",updated_at:"2026-08-10T10:00:00"}],
    notes:[{id:1,title:"低氧预实验观察要点",kind:"experiment_guide",project_id:1,body:"记录细胞形态、融合度和培养液颜色。\n24 h 后统一采样。",excerpt:"记录细胞形态、融合度和培养液颜色。",row_version:1,updated_at:"2026-08-11T09:20:00"}],
    files:[{id:1,display_name:"hypoxia-result-01.png",kind:"image",storage_mode:"managed",path:"2026/08/result.png",size_bytes:428000,link_status:"available",updated_at:"2026-08-11T13:10:00"}],
    tasks:[{id:1,title:"完成低氧组取样",status:"doing",priority:"high",deadline:"2026-08-11",project_id:1,row_version:1},{id:2,title:"整理转化效率数据",status:"todo",priority:"medium",deadline:"2026-08-12",project_id:2,row_version:1}],
    aiConversations:[],
    weekly:{id:1,title:"第 32 周研究进展",project_id:1,report_date:"2026-08-09",period_start:"2026-08-03",period_end:"2026-08-09",status:"reviewed",summary:"完成低氧培养条件预实验并整理初步结果。",body:"完成低氧培养条件预实验并整理初步结果。",issues_and_feedback:"补充阴性对照并统一图表单位。",next_week_plan:"完成 HIF-1α 检测。",row_version:2,annotation_count:2,updated_at:"2026-08-11T15:20:00",files:[{id:11,version_number:2,display_name:"week-32-v2.pptx",original_name:"week-32-v2.pptx",storage_mode:"managed",mime_type:"application/vnd.openxmlformats-officedocument.presentationml.presentation",size_bytes:1284000,sha256:"demo",link_status:"available",updated_at:"2026-08-11T15:20:00"},{id:10,version_number:1,display_name:"week-32-v1.pptx",original_name:"week-32-v1.pptx",storage_mode:"managed",mime_type:"application/vnd.openxmlformats-officedocument.presentationml.presentation",size_bytes:984000,sha256:"demo",link_status:"available",updated_at:"2026-08-09T18:10:00"}],updates:[{id:1,kind:"批注",status:"待处理",content:"第 12 页图表坐标轴需要补充单位。",created_at:"2026-08-11T11:15:00"},{id:2,kind:"指导",status:"已处理",content:"下一周增加与预期目标的横向对比。",created_at:"2026-08-11T15:30:00"}]},
  };

  function demoPage(items,payload={}){
    if(!payload.pagination)return items;
    const pageSize=Math.max(1,Number(payload.page_size)||20),total=items.length;
    const pages=Math.max(1,Math.ceil(total/pageSize)),page=Math.min(Math.max(1,Number(payload.page)||1),pages);
    return {items:items.slice((page-1)*pageSize,page*pageSize),pagination:{page,page_size:pageSize,pages,total}};
  }

  function demoResponse(request) {
    const p = request.payload || {};
    let data = {};
    switch (request.command) {
      case "system.ping": data={status:"ok"}; break;
      case "system.app_info": data={version:"desktop-preview",transport:"in-process-js-bridge",http_listener:false,protocol_version:1,protocol_compatibility:{minimum:1,maximum:1},capabilities:["ai.changesets","records.batch_export","zotero.jobs"],commands:[],deprecated_commands:{"record.export_batch":{replacement:"record.export.batch",remove_in_protocol:2}}}; break;
      case "dashboard.get": data={workspace:{name:"R/LAB 工作区"},projects:demo.projects,recent_records:demo.records,counts:{projects:3,records:4,open_tasks:demo.tasks.filter(x=>x.status!=="done").length,files:demo.files.length,in_progress:1,awaiting_analysis:1,completed:2}}; break;
      case "project.list": data=demo.projects.filter(x=>!p.search||`${x.title} ${x.code}`.includes(p.search)); break;
       case "project.create": data={id:Date.now(),title:p.title,code:p.code||"",objective:p.objective||"",status:"active",status_label:"进行中",record_count:0,row_version:1,updated_at:new Date().toISOString()},demo.projects.unshift(data); break;
       case "project.update": {const item=demo.projects.find(x=>x.id===Number(p.id));if(!item)throw new Error("项目不存在");Object.assign(item,{title:p.title,code:p.code||"",objective:p.objective||"",status:p.status||item.status,status_label:statusLabels[p.status||item.status],row_version:item.row_version+1,updated_at:new Date().toISOString()});data=item;break;}
      case "project.bulk": {const selected=demo.projects.filter(item=>(p.ids||[]).map(Number).includes(item.id));if(p.action==="trash")demo.projects=demo.projects.filter(item=>!selected.includes(item));else if(p.action==="status")selected.forEach(item=>{item.status=p.status;item.status_label={active:"进行中",paused:"已暂停",completed:"已完成",archived:"已归档"}[p.status]||p.status;item.row_version+=1;});data={updated:selected.length,skipped:0};break;}
      case "record.list": {const filtered=demo.records.filter(x=>(!p.project_id||x.project_id===Number(p.project_id))&&(!p.search||x.title.includes(p.search))&&(!p.status||x.status===p.status));if(p.pagination){const page=Math.max(1,Number(p.page)||1),pageSize=Math.max(1,Number(p.page_size)||20),pages=Math.max(1,Math.ceil(filtered.length/pageSize)),safePage=Math.min(page,pages);data={items:filtered.slice((safePage-1)*pageSize,safePage*pageSize),pagination:{page:safePage,page_size:pageSize,pages,total:filtered.length}};}else data=filtered;break;}
       case "record.get": data=demo.records.find(x=>x.id===Number(p.id)); break;
       case "record.export.batch": data={count:(p.ids||[]).length,size_bytes:0,items:(p.ids||[]).map(id=>({id:Number(id),path:`${p.directory||""}/R-LAB-record-${id}.${p.format||"docx"}`,size_bytes:0}))}; break;
      case "record.create": {const project=demo.projects.find(x=>x.id===Number(p.project_id));data={id:Date.now(),project_id:project.id,project_title:project.title,record_code:`LAB-${new Date().toISOString().slice(0,10).replaceAll("-","")}-001`,title:p.title,status:"draft",experiment_date:p.experiment_date||null,executor_snapshot:"",location:"",row_version:1,updated_at:new Date().toISOString(),objective:"",background:"",hypothesis:"",design:"",materials_conditions:"",expected_result:"",actual_process_summary:"",actual_result:"",analysis:"",conclusion:"",next_steps:"",steps:[]};demo.records.unshift(data);break;}
      case "record.update": {const item=demo.records.find(x=>x.id===Number(p.id));Object.assign(item,p,{row_version:item.row_version+1,updated_at:new Date().toISOString()});data=item;break;}
      case "literature.list": {const filtered=demo.literature.filter(x=>(!p.source||x.source===p.source)&&(!p.read_status||x.read_status===p.read_status)&&(!p.search||JSON.stringify(x).toLowerCase().includes(p.search.toLowerCase())));data=demoPage(filtered,p);break;}
      case "literature.get": data=demo.literature.find(x=>x.id===Number(p.id)); break;
      case "literature.save": data={id:Date.now(),source:"manual",read_status:"unread",authors:[],...p,updated_at:new Date().toISOString()},demo.literature.unshift(data); break;
      case "literature.facets": {const sources=demo.literature.reduce((acc,item)=>(acc[item.source]=(acc[item.source]||0)+1,acc),{});data={sources:{all:demo.literature.length,zotero:sources.zotero||0,manual:sources.manual||0,import:sources.import||0}};break;}
      case "zotero.status": data={state:"connected",last_success_at:"2026-08-11T10:00:00"}; break;
      case "zotero.collections.list": data=[]; break;
      case "zotero.sync": data={state:"connected",added:0,updated:2}; break;
      case "library.list": data=demoPage(demo.files.filter(x=>!p.search||x.display_name.includes(p.search)),p); break;
      case "library.verify": data=demo.files.find(x=>x.id===Number(p.id)); break;
      case "library.import": data={id:Date.now(),display_name:p.display_name,kind:p.kind,storage_mode:p.storage_mode,path:p.path,size_bytes:1200,link_status:"available",updated_at:new Date().toISOString()},demo.files.unshift(data); break;
      case "note.list": data=demoPage(demo.notes.filter(x=>(!p.kind||x.kind===p.kind)&&(!p.search||x.title.includes(p.search))),p); break;
      case "note.get": data=demo.notes.find(x=>x.id===Number(p.id)); break;
      case "note.save": {let item=p.id?demo.notes.find(x=>x.id===Number(p.id)):null;if(item)Object.assign(item,p,{row_version:item.row_version+1});else item={id:Date.now(),row_version:1,...p},demo.notes.unshift(item);data=item;break;}
      case "task.list": data=demoPage(demo.tasks.filter(x=>p.scope!=="completed"||x.status==="done"),p); break;
      case "task.save": {let item=p.id?demo.tasks.find(x=>x.id===Number(p.id)):null;if(item)Object.assign(item,p,{row_version:item.row_version+1});else item={id:Date.now(),row_version:1,status:"todo",...p},demo.tasks.unshift(item);data=item;break;}
      case "calendar.list": data=[...demo.records.filter(x=>x.experiment_date).map(x=>({id:`record:${x.id}`,source_type:"record",source_id:x.id,title:x.title,date:x.experiment_date,event_type:"experiment",project_id:x.project_id,lab_record_id:x.id,movable:false})),...demo.tasks.filter(x=>x.deadline).map(x=>({id:`task:${x.id}`,source_type:"task",source_id:x.id,title:x.title,date:x.deadline,event_type:"task",project_id:x.project_id,lab_record_id:x.lab_record_id,movable:true}))]; break;
      case "calendar.create": data={id:Date.now(),...p}; break;
      case "weekly.current": data=demo.weekly||{id:null,row_version:0,title:"本周研究周报",period_start:"2026-08-10",period_end:"2026-08-16",body:"",issues_and_feedback:"",next_week_plan:"",counts:{records:4,tasks:2,literature:2,notes:1,projects:3},entries:demo.records.slice(0,3).map(x=>({source_type:"record",source_id:x.id,source_title:x.title,source_excerpt:x.conclusion||x.objective||"",source_date:x.experiment_date,include_state:"included"}))}; break;
      case "weekly.save": data={id:p.id||1,row_version:(Number(p.row_version)||0)+1,updated_at:new Date().toISOString()},demo.weekly={...p,...data}; break;
      case "weekly.list": data=demoPage(demo.weekly?[demo.weekly]:[],p); break;
      case "weekly.get": data={...demo.weekly,current_file:demo.weekly?.files?.[0]||null}; break;
      case "weekly.update": Object.assign(demo.weekly,p,{row_version:(demo.weekly.row_version||0)+1});data={...demo.weekly,current_file:demo.weekly.files?.[0]||null};break;
      case "weekly.import_file": data={...demo.weekly,current_file:demo.weekly.files?.[0]||null};break;
      case "trash.list": data=[]; break;
      case "settings.get": data={workspace:{name:"R/LAB 工作区",timezone:"Asia/Shanghai",data_path:"%LOCALAPPDATA%\\ResearchAssistant\\data"},executors:[{id:1,name:"面壁者",role:"研究者",is_active:true}],save:{autosave:true,interval:30},zotero:{base_url:"http://127.0.0.1:23119",state:"connected"},api:{name:"桌面默认",url:"https://api.openai.com/v1",model:"gpt-5.6-terra",enabled:false,has_key:false},about:{product:"R/LAB Research Assistant",author:"面壁者"}}; break;
      case "settings.save": data={saved:true,section:p.section}; break;
      case "search.query": {const all=[...demo.projects.map(x=>({id:x.id,entity_type:"project",title:x.title,excerpt:x.objective,view_key:"projects"})),...demo.records.map(x=>({id:x.id,entity_type:"record",title:x.title,excerpt:x.objective||"",view_key:"record-edit"})),...demo.literature.map(x=>({id:x.id,entity_type:"literature",title:x.title,excerpt:x.abstract,view_key:"literature"}))];data={mode:"like",diagnostic:"连续子串匹配",items:all.filter(x=>JSON.stringify(x).toLowerCase().includes(String(p.query||"").toLowerCase()))};break;}
      case "search.rebuild": data={count:12,mode:"fts5-trigram",diagnostic:"FTS5 trigram"}; break;
      case "ai.preview": data={target:{title:"当前对象"},base_row_version:1,endpoint:"https://api.openai.com/v1",model:"gpt-5.6-terra",api_enabled:false,estimated_characters:240,source_snapshot:{},warning:"应用操作会直接写入所选字段，并生成可撤销的变更记录。"}; break;
      case "ai.conversation.create": {const item={id:Date.now(),title:p.title||"新聊天",project_id:p.project_id||null,selected_record_ids:p.record_ids||[],messages:[],updated_at:new Date().toISOString()};demo.aiConversations.unshift(item);data=item;break;}
      case "ai.conversations": {const items=demo.aiConversations.filter(x=>!p.query||x.title.includes(p.query)).map(x=>({...x,message_count:x.messages.length,preview:x.messages.at(-1)?.content||""}));data={items,pagination:{page:1,pages:1,per_page:10,total:items.length}};break;}
      case "ai.conversation.get": data=demo.aiConversations.find(x=>x.id===Number(p.id))||{id:p.id,title:"新聊天",project_id:null,messages:[]};break;
      case "ai.conversations.bulk": {const chosen=new Set((p.ids||[]).map(Number));if(p.action==="delete")demo.aiConversations=demo.aiConversations.filter(x=>!chosen.has(x.id));else demo.aiConversations.filter(x=>chosen.has(x.id)).forEach((x,index)=>x.title=(p.title||"聊天")+(chosen.size>1?` ${index+1}`:""));data={updated:chosen.size,skipped:0};break;}
      case "ai.propose": {let conversation=demo.aiConversations.find(x=>x.id===Number(p.conversation_id));if(!conversation){conversation={id:Date.now(),title:p.prompt.slice(0,80),project_id:Number(p.target_id),selected_record_ids:p.record_ids||[],messages:[],updated_at:new Date().toISOString()};demo.aiConversations.unshift(conversation);}conversation.selected_record_ids=p.record_ids||[];conversation.messages.push({id:Date.now(),role:"user",content:p.prompt,proposal:{}},{id:Date.now()+1,role:"assistant",content:"已结合项目历史与实验记录生成建议。",proposal:{objective:"建议的研究目的"},change_id:1,change_status:"proposed"});conversation.updated_at=new Date().toISOString();data={id:1,conversation_id:conversation.id,reply:"已结合项目历史与实验记录生成建议。",proposal:{objective:"建议的研究目的"},field_schema:{objective:{label:"研究目标",type:"text"}},status:"proposed",references:[],web_used:false};break;}
      case "ai.apply": data={id:p.id,status:"applied",applied_fields:p.accepted_fields}; break;
      case "dialog.open_file": data=[]; break;
      case "dialog.select_directory": data=[]; break;
      case "dialog.save_file": data=[]; break;
      default: data={accepted:true};
    }
    if(request.command==="weekly.current"&&data&&!data.counts){data={...data,counts:{records:demo.records.length,tasks:demo.tasks.filter(x=>x.status==="done").length,literature:demo.literature.length,notes:demo.notes.length,projects:demo.projects.length},entries:demo.records.slice(0,3).map(x=>({source_type:"record",source_id:x.id,source_title:x.title,source_excerpt:x.conclusion||x.objective||"",source_date:x.experiment_date,include_state:"included"}))};}
    return {ok:true,data,error:null,field_errors:{},request_id:request.request_id};
  }

  async function invoke(command, payload = {}, expectedRowVersion) {
    const request = {request_id:crypto.randomUUID(),command,payload};
    if (expectedRowVersion !== undefined && expectedRowVersion !== null) request.expected_row_version=expectedRowVersion;
    if (bridgeRequired && !window.pywebview?.api?.invoke) throw new Error("桌面服务仍在启动，请稍候重试");
    const response = window.pywebview?.api?.invoke ? await window.pywebview.api.invoke(request) : demoResponse(request);
    if (!response?.ok) {
      const error = new Error(response?.error?.message || "桌面命令执行失败");
      error.code=response?.error?.code; error.fieldErrors=response?.field_errors||{}; throw error;
    }
    return response.data;
  }

  function icons(){if(window.lucide)window.lucide.createIcons({attrs:{"aria-hidden":"true"}});}
  function toast(message){const node=$("#toast");node.textContent=message;node.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.hidden=true,2600);}
  function dateLabel(value,withTime=false){if(!value)return "—";const parsed=new Date(value);if(Number.isNaN(parsed.getTime()))return value;return new Intl.DateTimeFormat("zh-CN",withTime?{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit"}:{year:"numeric",month:"2-digit",day:"2-digit"}).format(parsed);}
  function formatBytes(value){const size=Number(value)||0;if(size>=1073741824)return `${(size/1073741824).toFixed(1)} GB`;if(size>=1048576)return `${(size/1048576).toFixed(1)} MB`;if(size>=1024)return `${(size/1024).toFixed(1)} KB`;return `${size} B`;}
  function statusBadge(value){return `<span class="status ${escapeHtml(value)}">${escapeHtml(statusLabels[value]||value||"—")}</span>`;}
  function emptyRow(columns,message){return `<tr class="empty-row"><td colspan="${columns}">${escapeHtml(message)}</td></tr>`;}
  function register(view, loader){modules.set(view,loader);}
  function setAssistantContext(){const select=$("#ai-project"),scope=$("#ai-project-scope");if(!select||!scope)return;if(!select.value&&state.currentProject?.id)select.value=String(state.currentProject.id);const projectId=Number(select.value),project=state.projects.find(item=>item.id===projectId),records=state.records.filter(item=>item.project_id===projectId);scope.textContent=project?`${project.title} · ${records.length} 条实验记录 · 不读取文件`:"选择后读取项目与实验记录，不读取文件";}
  function fillProjectOptions(){const options=state.projects.map(item=>`<option value="${item.id}">${escapeHtml(item.title)}</option>`).join("");for(const select of [$("#create-record-form select[name=project_id]"),$("#note-project"),$("#task-project"),$("#file-project"),$("#weekly-upload-project"),$("#ppt-project")]){if(!select)continue;const current=select.value;const first=select.id==="ppt-project"?"全部项目":select.closest("#create-record-form")?"请先创建项目":"不关联项目";select.innerHTML=`<option value="">${first}</option>${options}`;select.value=current;}for(const filter of [$("#record-project-filter"),$("#export-project-filter"),$("#task-project-filter"),$("#weekly-project-filter")]){if(!filter)continue;const current=filter.value;filter.innerHTML=`<option value="">全部项目</option>${options}`;filter.value=current;}const aiProject=$("#ai-project");if(aiProject){const current=aiProject.value;aiProject.innerHTML=`<option value="">选择项目历史</option>${options}`;aiProject.value=current;setAssistantContext();}}

  function paginate(items,page=1,pageSize=20){if(items.serverPagination){const value=items.serverPagination;return {items,total:value.total,pages:value.pages,page:value.page,pageSize:value.page_size};}const total=items.length,pages=Math.max(1,Math.ceil(total/pageSize)),safePage=Math.min(Math.max(1,page),pages),start=(safePage-1)*pageSize;return {items:items.slice(start,start+pageSize),total,pages,page:safePage,pageSize};}
  function paginationTokens(page,pages){
    if(pages<=7)return Array.from({length:pages},(_,index)=>index+1);
    let left=Math.max(2,page-1),right=Math.min(pages-1,page+1);
    if(page<=4){left=2;right=4;}
    if(page>=pages-3){left=pages-3;right=pages-1;}
    const values=[1];
    if(left>2)values.push("ellipsis-left");
    for(let value=left;value<=right;value++)values.push(value);
    if(right<pages-1)values.push("ellipsis-right");
    values.push(pages);
    return values;
  }
  function renderPagination(node,pageData,onPage,onSize){
    if(!node)return;
    const total=Math.max(0,Number(pageData.total)||0),pages=Math.max(1,Number(pageData.pages)||1),page=Math.min(pages,Math.max(1,Number(pageData.page)||1)),pageSize=Math.max(1,Number(pageData.pageSize)||20);
    const first=total?(page-1)*pageSize+1:0,last=Math.min(page*pageSize,total);
    const pageButtons=paginationTokens(page,pages).map(value=>typeof value==="number"
      ?`<button type="button" class="pagination-page ${value===page?'active':''}" data-page="${value}" ${value===page?'aria-current="page"':''} aria-label="第 ${value} 页">${value}</button>`
      :`<span class="pagination-ellipsis" aria-hidden="true">…</span>`).join("");
    const sizeOptions=[10,20,50].includes(pageSize)?[10,20,50]:[...new Set([10,20,50,pageSize])].sort((a,b)=>a-b);
    const controls=pages>1?`<nav class="pagination-pages" aria-label="页码"><button type="button" class="pagination-edge" data-page="1" ${page<=1?'disabled':''} title="首页" aria-label="首页"><i data-lucide="chevrons-left"></i></button><button type="button" data-page="${Math.max(1,page-1)}" ${page<=1?'disabled':''} title="上一页" aria-label="上一页"><i data-lucide="chevron-left"></i></button>${pageButtons}<button type="button" data-page="${Math.min(pages,page+1)}" ${page>=pages?'disabled':''} title="下一页" aria-label="下一页"><i data-lucide="chevron-right"></i></button><button type="button" class="pagination-edge" data-page="${pages}" ${page>=pages?'disabled':''} title="末页" aria-label="末页"><i data-lucide="chevrons-right"></i></button></nav><span class="pagination-status">第 ${page} / ${pages} 页</span><label class="pagination-jump"><span>跳至</span><input type="number" min="1" max="${pages}" value="${page}" inputmode="numeric" aria-label="跳转页码"><span>页</span></label>`:"";
    node.setAttribute("aria-label","列表分页");
    node.innerHTML=`<strong class="pagination-summary">第 ${first}-${last} 条，共 ${total} 条</strong><label class="pagination-size"><span>每页</span><select aria-label="每页条数">${sizeOptions.map(value=>`<option value="${value}" ${pageSize===value?'selected':''}>${value} 条</option>`).join("")}</select></label><span class="pagination-spacer"></span>${controls}`;
    const goToPage=value=>{const target=Math.min(pages,Math.max(1,Number(value)||page));if(target!==page)onPage(target);};
    node.onclick=event=>{const button=event.target.closest('[data-page]');if(button&&!button.disabled)goToPage(button.dataset.page);};
    node.querySelector('select').onchange=event=>onSize(Number(event.target.value));
    const jump=node.querySelector('.pagination-jump input');
    if(jump){jump.onchange=event=>{goToPage(event.target.value);event.target.value=String(Math.min(pages,Math.max(1,Number(event.target.value)||page)));};jump.onkeydown=event=>{if(event.key==="Enter"){event.preventDefault();event.target.blur();}};}
    icons();
  }

  function captureNavigationState(){const scroll={},controls={};$$('[id]').forEach(node=>{if(node.scrollTop||node.scrollLeft)scroll[node.id]=[node.scrollLeft,node.scrollTop];});const panel=$('.view.active');$$('input[id],select[id],textarea[id]',panel).forEach(node=>{controls[node.id]={value:node.value,checked:"checked" in node?node.checked:undefined};});return {scroll,controls};}
  function restoreNavigationControls(snapshot){Object.entries(snapshot?.controls||{}).forEach(([id,value])=>{const node=document.getElementById(id);if(!node)return;node.value=value.value;if(value.checked!==undefined)node.checked=value.checked;});}
  function restoreNavigationState(snapshot){if(!snapshot)return;requestAnimationFrame(()=>{Object.entries(snapshot.scroll||{}).forEach(([id,[left,top]])=>{const node=document.getElementById(id);if(node)node.scrollTo(left,top);});});}

  // Run one navigation transaction.  The public navigate() wrapper below
  // serialises these transactions so a burst of sidebar clicks cannot leave
  // several loaders mutating the same panel and history at once.
  async function navigateOnce(view,params={},options={}){
    const navigationKey=`${view}|${JSON.stringify(params||{})}|${options.push===false?"replace":"push"}`;
    const now=performance.now();
    if(state.navigationLock===navigationKey||(state.lastNavigationKey===navigationKey&&now-state.lastNavigationAt<320))return true;
    state.navigationLock=navigationKey;state.lastNavigationKey=navigationKey;state.lastNavigationAt=now;
    try{
    const previous={view:state.view,params:{...state.params},panel:$(".view.active"),historyIndex:state.historyIndex};
    const switchingRecord=state.view==="record-edit"&&(view!=="record-edit"||Number(params?.id)!==Number(state.currentRecord?.id));
    if(state.dirty&&switchingRecord){if(!confirm("当前实验记录尚未保存，仍要离开吗？"))return;clearTimeout(state.saveTimer);state.dirty=false;}
    const panelView=view;
    const panel=$(`[data-view-panel="${panelView}"]`);if(!panel){toast("页面不存在");return;}
    $$(".view").forEach(item=>item.classList.remove("active"));panel.classList.add("active");
    const parent=navParent[view]||view;$$(`.nav-item`).forEach(item=>item.classList.toggle("active",item.dataset.view===parent));
    const leaving=state.history[state.historyIndex];if(options.push!==false&&leaving&&leaving.view===state.view)leaving.ui=captureNavigationState();
    state.view=view;state.params={...params};setAssistantContext();
    if(options.push!==false){state.history=state.history.slice(0,state.historyIndex+1);state.history.push({view,params:{...params}});state.historyIndex=state.history.length-1;}
    updateHistory();$("#workspace").scrollTop=0;
    restoreNavigationControls(state.history[state.historyIndex]?.ui);const loader=modules.get(view);if(loader?.load){try{await loader.load(params);}catch(error){toast(error.message);$$('.view').forEach(item=>item.classList.remove('active'));previous.panel?.classList.add('active');state.view=previous.view;state.params=previous.params;if(options.push!==false){state.history=state.history.slice(0,-1);state.historyIndex=previous.historyIndex;}updateHistory();return false;}}
    restoreNavigationState(state.history[state.historyIndex]?.ui);icons();
    if(view==="search")setTimeout(()=>$("#global-search-input")?.focus(),20);
    return true;
    }finally{if(state.navigationLock===navigationKey)state.navigationLock="";}
  }

  async function navigate(view,params={},options={}){
    const request={view,params:{...(params||{})},options:{...(options||{})}};
    // Keep only the latest click while a loader is waiting on the bridge.
    // Returning immediately is intentional: returning the active promise
    // here would deadlock loaders that redirect (for example, to projects
    // when a requested id no longer exists).
    if(state.navigationBusy){state.pendingNavigation=request;return false;}
    state.navigationBusy=true;
    document.documentElement.dataset.navigationBusy="true";
    try{
      let result=true,next=request;
      while(next){
        state.pendingNavigation=null;
        result=await navigateOnce(next.view,next.params,next.options);
        next=state.pendingNavigation;
      }
      return result;
    }finally{
      state.pendingNavigation=null;
      state.navigationBusy=false;
      delete document.documentElement.dataset.navigationBusy;
    }
  }
  function updateHistory(){$("#nav-back").disabled=state.historyIndex<=0;$("#nav-forward").disabled=state.historyIndex>=state.history.length-1;}
  async function moveHistory(delta){const previousIndex=state.historyIndex,next=previousIndex+delta;if(next<0||next>=state.history.length)return;const current=state.history[previousIndex];if(current)current.ui=captureNavigationState();state.historyIndex=next;const item=state.history[next];if(!await navigate(item.view,item.params,{push:false}))state.historyIndex=previousIndex;updateHistory();}
  async function refresh(){const loader=modules.get(state.view);if(loader?.load)await loader.load(state.params);else await loadInitial();toast("视图已刷新");}

  function validateProtocol(info){
    const version=Number(info?.protocol_version);
    if(!Number.isInteger(version)||version<supportedProtocol.minimum||version>supportedProtocol.maximum){
      throw new Error(`桌面界面与应用服务协议不兼容（服务版本：${info?.protocol_version??"未知"}，支持：${supportedProtocol.minimum}-${supportedProtocol.maximum}）。请重新安装同一版本的 R/LAB。`);
    }
    return info;
  }

  async function loadInitial(){
    const [dashboard,projects,records,info]=await Promise.all([invoke("dashboard.get"),invoke("project.list"),invoke("record.list"),invoke("system.app_info")]);
    state.dashboard=dashboard;state.projects=projects;state.records=records;fillProjectOptions();
    state.appInfo=validateProtocol(info);
    const workspaceName=dashboard?.workspace?.name||"科研工作区";
    if($("#sidebar-workspace-name"))$("#sidebar-workspace-name").textContent=workspaceName;
    if($("#sidebar-version"))$("#sidebar-version").textContent=info?.version?`v${info.version}`:"本地桌面版";
  }
  function openDialog(id){const dialog=document.getElementById(id);if(!dialog||dialog.open)return;const trigger=document.activeElement;dialog.addEventListener("close",()=>trigger?.focus?.(),{once:true});dialog.showModal();}
  async function nativeDialog(command,payload){try{return await invoke(command,payload)||[];}catch(error){toast(error.message);return [];}}
  function confirmAction(title,message){return new Promise(resolve=>{const dialog=$("#confirm-dialog");$("#confirm-title").textContent=title;$("#confirm-message").textContent=message;dialog.addEventListener("close",()=>resolve(dialog.returnValue==="confirm"),{once:true});dialog.showModal();});}

  // A double-click dispatches a second click after the first navigation may
  // already have replaced the DOM under the pointer.  Without this capture
  // guard the second click can land on a newly-rendered tab/action and launch
  // a second navigation, which looks like a frozen workspace.  Preserve the
  // assistant header's own dblclick maximize gesture (it is not an action
  // control) while making actionable controls single-activation only.
  document.addEventListener("click",event=>{if(event.detail>1&&event.target.closest?.("button,[role=button],tr,a")){event.preventDefault();event.stopImmediatePropagation();}},true);

  const assistantStorageKey="rlab-assistant-window-v3";
  let assistantNormalRect=null;
  function readAssistantLayout(){try{return JSON.parse(localStorage.getItem(assistantStorageKey)||"{}")||{};}catch(_){return {};}}
  function captureAssistantRect(){const win=$("#assistant-window");if(!win||win.classList.contains("maximized")||win.classList.contains("minimized"))return;assistantNormalRect={left:win.offsetLeft,top:win.offsetTop,width:win.offsetWidth,height:win.offsetHeight};}
  function updateAssistantWindowControls(){const win=$("#assistant-window"),button=$("#assistant-maximize"),icon=$("i",button);if(!win||!button||!icon)return;const maximized=win.classList.contains("maximized");button.title=maximized?"还原":"最大化";icon.setAttribute("data-lucide",maximized?"minimize-2":"maximize-2");}
  function saveAssistantLayout(){const win=$("#assistant-window");if(!win||win.hidden)return;captureAssistantRect();const rect=assistantNormalRect||{};localStorage.setItem(assistantStorageKey,JSON.stringify({...rect,minimized:win.classList.contains("minimized"),maximized:win.classList.contains("maximized")}));}
  function constrainAssistant(){const win=$("#assistant-window");if(!win||win.hidden||win.classList.contains("maximized"))return;const left=Math.min(Math.max(8,win.offsetLeft),Math.max(8,window.innerWidth-win.offsetWidth-8)),top=Math.min(Math.max(8,win.offsetTop),Math.max(8,window.innerHeight-win.offsetHeight-8));win.style.left=`${left}px`;win.style.top=`${top}px`;captureAssistantRect();}
  function applyAssistantNormalRect(){const win=$("#assistant-window"),rect=assistantNormalRect||{};win.style.left=`${Number(rect.left)||Math.max(8,window.innerWidth-414)}px`;win.style.top=`${Number(rect.top)||Math.max(62,window.innerHeight-720)}px`;win.style.width=`${Math.max(320,Number(rect.width)||390)}px`;win.style.height=`${Math.max(420,Number(rect.height)||640)}px`;}
  function restoreAssistant(){const win=$("#assistant-window");win.classList.remove("maximized","minimized");applyAssistantNormalRect();constrainAssistant();updateAssistantWindowControls();icons();}
  function openAssistant(){const win=$("#assistant-window"),saved=readAssistantLayout();assistantNormalRect={left:Number(saved.left)||Math.max(8,window.innerWidth-414),top:Number(saved.top)||Math.max(62,window.innerHeight-720),width:Math.max(320,Number(saved.width)||390),height:Math.max(420,Number(saved.height)||640)};win.hidden=false;applyAssistantNormalRect();win.classList.toggle("minimized",Boolean(saved.minimized));win.classList.toggle("maximized",Boolean(saved.maximized));for(const trigger of [$("#assistant-fab"),$("#assistant-top-button")])trigger?.setAttribute("aria-expanded","true");setAssistantContext();document.dispatchEvent(new CustomEvent("rlab:assistant-open"));constrainAssistant();updateAssistantWindowControls();icons();}
  function closeAssistant(){const win=$("#assistant-window");saveAssistantLayout();win.hidden=true;for(const trigger of [$("#assistant-fab"),$("#assistant-top-button")])trigger?.setAttribute("aria-expanded","false");}
  function toggleAssistant(){if($("#assistant-window").hidden)openAssistant();else closeAssistant();}
  function setupAssistantWindow(){const win=$("#assistant-window"),handle=$("#assistant-drag-handle");let mode=null,start=null,pointerOwner=null;const begin=(event,nextMode)=>{if(event.button!==0)return;if(win.classList.contains("maximized")||win.classList.contains("minimized"))restoreAssistant();mode=nextMode;pointerOwner=event.currentTarget;start={x:event.clientX,y:event.clientY,left:win.offsetLeft,top:win.offsetTop,width:win.offsetWidth,height:win.offsetHeight};pointerOwner.setPointerCapture?.(event.pointerId);event.preventDefault();event.stopPropagation();};handle.addEventListener("pointerdown",event=>{if(event.target.closest("button,select,input,label"))return;begin(event,"move");});$$('[data-assistant-resize]').forEach(resize=>resize.addEventListener("pointerdown",event=>begin(event,resize.dataset.assistantResize)));window.addEventListener("pointermove",event=>{if(!mode||!start)return;const dx=event.clientX-start.x,dy=event.clientY-start.y,minWidth=320,minHeight=420,maxWidth=Math.max(minWidth,window.innerWidth-16),maxHeight=Math.max(minHeight,window.innerHeight-16);if(mode==="move"){win.style.left=`${start.left+dx}px`;win.style.top=`${start.top+dy}px`;}else{let left=start.left,top=start.top,width=start.width,height=start.height;if(mode.includes("e"))width=Math.min(maxWidth,Math.max(minWidth,start.width+dx));if(mode.includes("s"))height=Math.min(maxHeight,Math.max(minHeight,start.height+dy));if(mode.includes("w")){width=Math.min(maxWidth,Math.max(minWidth,start.width-dx));left=start.left+start.width-width;}if(mode.includes("n")){height=Math.min(maxHeight,Math.max(minHeight,start.height-dy));top=start.top+start.height-height;}win.style.left=`${left}px`;win.style.top=`${top}px`;win.style.width=`${width}px`;win.style.height=`${height}px`;}constrainAssistant();});const finish=event=>{if(!mode)return;try{pointerOwner?.releasePointerCapture?.(event.pointerId);}catch(_){}mode=null;start=null;pointerOwner=null;saveAssistantLayout();};window.addEventListener("pointerup",finish);window.addEventListener("pointercancel",finish);handle.addEventListener("dblclick",event=>{if(event.target.closest("button"))return;$("#assistant-maximize").click();});$("#assistant-fab").addEventListener("click",toggleAssistant);$("#assistant-top-button").addEventListener("click",toggleAssistant);$("#assistant-close").addEventListener("click",closeAssistant);$("#assistant-minimize").addEventListener("click",()=>{if(win.classList.contains("minimized"))restoreAssistant();else{captureAssistantRect();win.classList.add("minimized");win.classList.remove("maximized");updateAssistantWindowControls();saveAssistantLayout();}});$("#assistant-maximize").addEventListener("click",()=>{if(win.classList.contains("maximized"))restoreAssistant();else{captureAssistantRect();win.classList.add("maximized");win.classList.remove("minimized");updateAssistantWindowControls();saveAssistantLayout();icons();}});window.addEventListener("resize",()=>{if(win.classList.contains("maximized"))return;constrainAssistant();});}

  function bindCore(){
    $$(".form-error").forEach(node=>{node.setAttribute("role","alert");node.setAttribute("aria-live","assertive");});
    ["zotero-state","note-save-state","save-state"].forEach(id=>{const node=$("#"+id);if(node){node.setAttribute("role","status");node.setAttribute("aria-live","polite");}});
    document.addEventListener("click",event=>{
      const cancel=event.target.closest('dialog button[value="cancel"]');if(cancel){event.preventDefault();cancel.closest("dialog")?.close("cancel");return;}
      const view=event.target.closest("[data-view]");if(view){event.preventDefault();navigate(view.dataset.view);return;}
      const open=event.target.closest("[data-open]");if(open){event.preventDefault();openDialog(open.dataset.open);return;}
      const recordView=event.target.closest("[data-record-view]");if(recordView){event.preventDefault();navigate(recordView.dataset.recordView,{id:state.currentRecord?.id});return;}
    });
    $("#nav-back").addEventListener("click",()=>moveHistory(-1));$("#nav-forward").addEventListener("click",()=>moveHistory(1));$("#refresh-view").addEventListener("click",refresh);
    $("#skin-select").addEventListener("change",event=>{document.documentElement.dataset.skin=event.target.value;localStorage.setItem("rlab-desktop-skin",event.target.value);});
    setupAssistantWindow();
    const assistantWindow=$("#assistant-window");new ResizeObserver(()=>assistantWindow.classList.toggle("assistant-wide",assistantWindow.offsetWidth>=720)).observe(assistantWindow);
    document.addEventListener("keydown",event=>{
      const tab=event.target.closest?.('[role="tab"]');if(tab&&(event.key==="ArrowLeft"||event.key==="ArrowRight"||event.key==="Home"||event.key==="End")){const tabs=$$('[role="tab"]',tab.closest('[role="tablist"]')),current=tabs.indexOf(tab);if(tabs.length&&current>=0){event.preventDefault();const next=event.key==="Home"?0:event.key==="End"?tabs.length-1:(current+(event.key==="ArrowRight"?1:-1)+tabs.length)%tabs.length;tabs[next].focus();tabs[next].click();}return;}
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"){event.preventDefault();navigate("search");}
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="s"){event.preventDefault();modules.get(state.view)?.save?.();}
      if(event.key==="Escape"&&state.view==="search")moveHistory(-1);
    });
    window.addEventListener("beforeunload",event=>{if(state.dirty){event.preventDefault();event.returnValue="";}});
  }

  async function boot(){
    if(booted)return;booted=true;bindCore();
    const skin=localStorage.getItem("rlab-desktop-skin")||"soft-lab";document.documentElement.dataset.skin=skin;$("#skin-select").value=skin;
    $("#today-label").textContent=new Intl.DateTimeFormat("zh-CN",{year:"numeric",month:"long",day:"numeric"}).format(new Date());
    try{await invoke("system.ping");await loadInitial();await modules.get("home")?.load({});updateHistory();icons();}
    catch(error){toast(error.message);}
  }

  window.RLab={$, $$, state, modules, invoke, register, navigate, loadInitial, fillProjectOptions, icons, toast, escapeHtml, dateLabel, formatBytes, statusBadge, emptyRow, openDialog, nativeDialog, confirmAction, paginate, renderPagination, setAssistantContext};
  window.addEventListener("pywebviewready",boot,{once:true});
  window.addEventListener("DOMContentLoaded",()=>{if(!bridgeRequired)setTimeout(boot,window.pywebview?.api?0:350);});
})();

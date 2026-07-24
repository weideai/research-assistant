import fs from "node:fs/promises";

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) throw new Error("Usage: build_weekly_presentation.mjs input.json output.pptx");
const { Presentation, PresentationFile } = await import(process.env.ARTIFACT_TOOL_MODULE);
const report = JSON.parse(await fs.readFile(inputPath, "utf8"));
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

const palettes = {
  evidence: { ink: "#111827", muted: "#64748B", line: "#D8DEE7", soft: "#F4F7FA", blue: "#2563EB", cyan: "#0891B2", green: "#059669", amber: "#D97706", red: "#DC2626", white: "#FFFFFF" },
  review: { ink: "#1F2933", muted: "#66737D", line: "#DDD7CF", soft: "#F8F5F0", blue: "#0F766E", cyan: "#0891B2", green: "#15803D", amber: "#C56A16", red: "#C2413B", white: "#FFFFFF" },
  paper: { ink: "#111111", muted: "#666666", line: "#D2D2D2", soft: "#F5F5F5", blue: "#1D4ED8", cyan: "#555555", green: "#08775B", amber: "#8A5B08", red: "#B4232A", white: "#FFFFFF" },
};
const C = palettes[report.skill?.theme] || palettes.evidence;
const FONT = "Microsoft YaHei";
const safe = (value, fallback = "-") => String(value ?? "").trim() || fallback;
const clamp = (value, max) => safe(value).length > max ? `${safe(value).slice(0, max - 1)}…` : safe(value);

function box(slide, left, top, width, height, fill = C.white, line = C.line) {
  return slide.shapes.add({ geometry: "rect", position: { left, top, width, height }, fill, line: { style: "solid", fill: line, width: 1 } });
}

function text(slide, value, left, top, width, height, size = 20, color = C.ink, bold = false, align = "left") {
  const shape = slide.shapes.add({ geometry: "textbox", position: { left, top, width, height }, fill: "none", line: { style: "solid", fill: "none", width: 0 } });
  shape.text = safe(value, "");
  shape.text.style = { fontSize: size, typeface: FONT, color, bold, alignment: align, verticalAlignment: "middle", autoFit: "shrinkText", insets: { top: 0, right: 0, bottom: 0, left: 0 } };
  return shape;
}

function slideBase(title, index, eyebrow = "RESEARCH WEEKLY") {
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  box(slide, 0, 0, 12, 720, C.blue, C.blue);
  text(slide, eyebrow, 42, 28, 280, 20, 12, C.blue, true);
  text(slide, title, 42, 55, 1110, 58, 34, C.ink, true);
  box(slide, 42, 126, 1196, 1, C.line, C.line);
  text(slide, String(index).padStart(2, "0"), 1180, 665, 58, 20, 12, C.muted, true, "right");
  text(slide, `${report.period.start} - ${report.period.end}`, 42, 665, 300, 20, 11, C.muted);
  return slide;
}

function metric(slide, label, value, left, top, accent) {
  box(slide, left, top, 270, 118, C.soft, C.line);
  box(slide, left, top, 6, 118, accent, accent);
  text(slide, value, left + 22, top + 18, 225, 48, 34, C.ink, true);
  text(slide, label, left + 22, top + 73, 225, 24, 12, C.muted, true);
}

// Cover
{
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  box(slide, 0, 0, 18, 720, C.blue, C.blue);
  text(slide, `R/LAB · ${safe(report.skill?.name, "RESEARCH REPORT").toUpperCase()}`, 64, 62, 720, 26, 14, C.blue, true);
  text(slide, report.title, 64, 148, 820, 164, 52, C.ink, true);
  text(slide, `${report.period.start} - ${report.period.end}`, 66, 335, 420, 34, 22, C.muted);
  box(slide, 64, 438, 1110, 1, C.line, C.line);
  text(slide, `${report.metrics.experiment_count} 个实验`, 64, 470, 240, 36, 22, C.ink, true);
  text(slide, `${report.metrics.record_count} 条记录`, 345, 470, 240, 36, 22, C.ink, true);
  text(slide, `${report.metrics.image_count} 张结果图`, 625, 470, 240, 36, 22, C.ink, true);
  text(slide, `汇报人：${report.author}`, 64, 625, 500, 24, 13, C.muted);
  text(slide, `生成时间：${report.generated_at}`, 760, 625, 414, 24, 13, C.muted, false, "right");
}

// Overview
{
  const slide = slideBase("本周概览", 2);
  metric(slide, "纳入实验", report.metrics.experiment_count, 42, 164, C.blue);
  metric(slide, "实验记录", report.metrics.record_count, 342, 164, C.cyan);
  metric(slide, "成功 / 完成", report.metrics.success_count, 642, 164, C.green);
  metric(slide, "失败 / 待核验", report.metrics.attention_count, 942, 164, C.amber);
  text(slide, "实验状态分布", 42, 330, 360, 32, 19, C.ink, true);
  const rows = Object.entries(report.status_counts || {});
  const total = Math.max(1, rows.reduce((sum, row) => sum + Number(row[1]), 0));
  rows.slice(0, 5).forEach(([label, value], index) => {
    const top = 390 + index * 47;
    text(slide, label, 42, top, 150, 24, 13, C.muted, true);
    box(slide, 195, top + 3, 760, 17, C.soft, C.soft);
    box(slide, 195, top + 3, Math.max(8, 760 * Number(value) / total), 17, index === 0 ? C.blue : C.cyan, index === 0 ? C.blue : C.cyan);
    text(slide, value, 980, top, 80, 24, 13, C.ink, true);
  });
}

// Experiment progress, up to 5 per slide
for (let offset = 0; offset < report.experiments.length; offset += 5) {
  const page = report.experiments.slice(offset, offset + 5);
  const slide = slideBase("实验进展", 3 + Math.floor(offset / 5), "SELECTED EXPERIMENTS");
  page.forEach((experiment, index) => {
    const top = 153 + index * 98;
    box(slide, 42, top, 1196, 82, index % 2 ? C.white : C.soft, C.line);
    text(slide, clamp(experiment.code, 18), 60, top + 13, 150, 22, 11, C.blue, true);
    text(slide, clamp(experiment.title, 36), 220, top + 9, 420, 30, 19, C.ink, true);
    text(slide, clamp(experiment.objective, 90), 220, top + 43, 580, 24, 11, C.muted);
    text(slide, experiment.status, 825, top + 12, 120, 24, 12, experiment.status === "完成" ? C.green : C.blue, true);
    text(slide, `${experiment.record_count} 条记录`, 960, top + 12, 110, 24, 12, C.ink, true);
    text(slide, `${experiment.completed_steps}/${experiment.step_count} 步骤`, 1080, top + 12, 130, 24, 12, C.ink, true, "right");
    text(slide, clamp(experiment.latest_result, 42), 825, top + 45, 385, 20, 11, C.muted, false, "right");
  });
}

// Evidence
{
  const slide = slideBase("参数与结果证据", 3 + Math.ceil(report.experiments.length / 5), "TRACEABLE EVIDENCE");
  const evidence = report.evidence.slice(0, 6);
  evidence.forEach((record, index) => {
    const col = index % 2;
    const row = Math.floor(index / 2);
    const left = 42 + col * 608;
    const top = 153 + row * 164;
    box(slide, left, top, 588, 144, C.soft, C.line);
    text(slide, `${record.date} · ${clamp(record.experiment, 24)}`, left + 16, top + 12, 410, 23, 12, C.blue, true);
    text(slide, record.result, left + 454, top + 12, 115, 23, 12, record.result === "成功" ? C.green : C.amber, true, "right");
    text(slide, clamp(record.parameters, 70), left + 16, top + 44, 552, 25, 11, C.ink, true);
    text(slide, clamp(record.summary, 115), left + 16, top + 75, 552, 54, 11, C.muted);
  });
  if (!evidence.length) text(slide, "所选日期范围内没有实验记录。", 42, 180, 800, 40, 22, C.muted);
}

// Result images, 4 per slide
for (let offset = 0; offset < report.images.length; offset += 4) {
  const images = report.images.slice(offset, offset + 4);
  const slide = slideBase("实验结果图片", 4 + Math.ceil(report.experiments.length / 5) + Math.floor(offset / 4), "RESULT IMAGES");
  for (let index = 0; index < images.length; index += 1) {
    const item = images[index];
    const col = index % 2;
    const row = Math.floor(index / 2);
    const left = 42 + col * 608;
    const top = 153 + row * 244;
    box(slide, left, top, 588, 220, C.soft, C.line);
    try {
      const bytes = await fs.readFile(item.path);
      slide.images.add({ blob: bytes, contentType: item.mime_type, alt: item.alt, fit: "contain", position: { left: left + 10, top: top + 10, width: 350, height: 174 } });
      text(slide, clamp(item.experiment, 28), left + 378, top + 22, 190, 28, 13, C.ink, true);
      text(slide, clamp(item.name, 31), left + 378, top + 57, 190, 45, 11, C.blue, true);
      text(slide, clamp(item.description, 80), left + 378, top + 110, 190, 70, 10, C.muted);
    } catch (_error) {
      text(slide, `图片无法读取：${item.name}`, left + 18, top + 80, 550, 40, 14, C.red, true);
    }
  }
}

// Next plan and review
{
  const index = 4 + Math.ceil(report.experiments.length / 5) + Math.ceil(report.images.length / 4);
  const slide = slideBase("下周计划与人工核验", index, "NEXT ACTIONS");
  text(slide, "待推进步骤", 42, 154, 560, 30, 19, C.ink, true);
  const actions = report.next_actions.slice(0, 7);
  actions.forEach((action, row) => {
    const top = 202 + row * 50;
    box(slide, 42, top + 4, 22, 22, C.blue, C.blue);
    text(slide, String(row + 1), 42, top + 4, 22, 22, 10, C.white, true, "center");
    text(slide, clamp(action, 75), 78, top, 515, 31, 12, C.ink);
  });
  if (!actions.length) text(slide, "暂无未完成步骤，请在实验页面补充下一步计划。", 42, 208, 540, 40, 14, C.muted);
  box(slide, 650, 154, 588, 394, "#FFF7ED", "#FDBA74");
  text(slide, "人工核验清单", 674, 178, 520, 34, 20, C.amber, true);
  const checks = ["剂量、浓度和给药条件", "临床含义与患者相关解释", "统计显著性、效应量和样本量", "图片标注、原始数据与附件完整性", "AI 生成文字与引用是否匹配原始记录"];
  checks.forEach((check, row) => {
    const top = 235 + row * 55;
    box(slide, 676, top + 2, 20, 20, C.white, C.amber);
    text(slide, check, 710, top, 480, 26, 12, C.ink, row === 4);
  });
  text(slide, "本演示文稿由实验数据库自动排版，不能替代研究者判断。", 650, 574, 588, 30, 12, C.red, true);
}

const pptx = await PresentationFile.exportPptx(deck);
await pptx.save(outputPath);

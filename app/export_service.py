import csv
import io
import json
import re
import tempfile
import zipfile
from datetime import date, datetime


def _date_value(value):
    return value.isoformat() if value else None


def _text(value, fallback=""):
    if value is None:
        return fallback
    return str(value)


def _active(items):
    return [item for item in items if not getattr(item, "is_deleted", False)]


def _record_sort_key(record):
    return record.record_date or date.min, record.id or 0


def _batch_sort_key(batch):
    return batch.start_date or date.min, batch.id or 0


def _step_sort_key(step):
    return step.position or 0, step.id or 0


def _plan_step_payload(step):
    return {
        "id": step.id,
        "position": step.position,
        "title": step.title,
        "description": step.description,
        "operator": step.operator,
        "planned_date": _date_value(step.planned_date),
    }


def _batch_step_payload(step):
    return {
        "id": step.id,
        "source_step_id": step.source_step_id,
        "position": step.position,
        "title": step.title,
        "description": step.description,
        "operator": step.operator,
        "planned_date": _date_value(step.planned_date),
        "completed_date": _date_value(step.completed_date),
        "is_done": step.is_done,
    }


def _parameter_payload(parameter):
    return {
        "position": parameter.position,
        "name": parameter.name,
        "value": parameter.value,
        "unit": parameter.unit,
        "notes": parameter.notes,
    }


def _sample_usage_payload(usage):
    return {
        "sample_code": usage.sample.sample_code,
        "sample_type": usage.sample.sample_type,
        "source": usage.sample.source,
        "location": usage.sample.location,
        "quantity": usage.sample.quantity,
        "status": usage.sample.status,
        "role": usage.role,
        "amount_used": usage.amount_used,
        "notes": usage.notes,
    }


def _attachment_payload(attachment):
    return {
        "id": attachment.id,
        "category": attachment.category,
        "original_name": attachment.original_name,
        "relative_path": attachment.relative_path,
        "version_number": attachment.version_number,
        "size_bytes": attachment.size_bytes,
        "mime_type": attachment.mime_type,
        "sha256": attachment.sha256,
        "tags": attachment.tags,
        "description": attachment.description,
        "storage_mode": attachment.storage_mode,
        "link_status": attachment.link_status,
    }


def _record_payload(record, batch):
    return {
        "id": record.id,
        "batch_id": batch.id if batch else None,
        "batch_code": (batch.batch_code or f"EXEC-{batch.id}") if batch else "HISTORY-UNASSIGNED",
        "record_date": _date_value(record.record_date),
        "operator": record.operator,
        "conditions": record.conditions,
        "content": record.content,
        "result": record.result,
        "remark": record.remark,
        "lifecycle_status": record.lifecycle_status,
        "finalized_at": _date_value(record.finalized_at),
        "parameters": [_parameter_payload(parameter) for parameter in record.parameters],
        "attachments": [
            _attachment_payload(attachment)
            for attachment in sorted(
                _active(record.attachments),
                key=lambda attachment: (attachment.relative_path.lower(), attachment.version_number),
            )
        ],
    }


def execution_groups(payload):
    """Return real executions plus one explicit compatibility group for orphaned records."""
    groups = list(payload["batches"])
    if payload["unassigned_records"]:
        groups.append({
            "id": None,
            "batch_code": "HISTORY-UNASSIGNED",
            "repeat_kind": "历史数据",
            "repeat_number": None,
            "group_name": "待归档",
            "operator": "",
            "status": "待修复",
            "start_date": None,
            "end_date": None,
            "summary": "这些旧记录缺少有效的实验执行归属；导出保留数据，但建议先运行数据库升级完成归档。",
            "conclusion": "",
            "requires_repeat": False,
            "steps": [],
            "actual_parameters": [],
            "sample_usages": [],
            "records": payload["unassigned_records"],
            "is_unassigned": True,
        })
    return groups


def experiment_payload(item, exported_at=None):
    """Return one stable data shape shared by every structured export format."""
    exported_at = exported_at or datetime.now()
    batches = sorted(_active(item.batches), key=_batch_sort_key)
    batch_by_id = {batch.id: batch for batch in batches}
    records = sorted(_active(item.records), key=_record_sort_key)
    record_payloads = {
        record.id: _record_payload(record, batch_by_id.get(record.batch_id))
        for record in records
    }
    assigned_record_ids = set()
    batch_payloads = []
    for batch in batches:
        batch_records = [
            record_payloads[record.id]
            for record in records
            if record.batch_id == batch.id
        ]
        assigned_record_ids.update(record["id"] for record in batch_records)
        batch_payloads.append({
            "id": batch.id,
            "batch_code": batch.batch_code or f"EXEC-{batch.id}",
            "repeat_kind": batch.repeat_kind,
            "repeat_number": batch.repeat_number,
            "group_name": batch.group_name,
            "operator": batch.operator,
            "status": batch.status,
            "start_date": _date_value(batch.start_date),
            "end_date": _date_value(batch.end_date),
            "summary": batch.summary,
            "conclusion": batch.conclusion,
            "requires_repeat": batch.requires_repeat,
            "steps": [
                _batch_step_payload(step)
                for step in sorted(batch.steps, key=_step_sort_key)
            ],
            "actual_parameters": [_parameter_payload(parameter) for parameter in batch.actual_parameters],
            "sample_usages": [_sample_usage_payload(usage) for usage in batch.sample_usages],
            "records": batch_records,
            "is_unassigned": False,
        })
    unassigned_records = [
        record_payloads[record.id]
        for record in records
        if record.id not in assigned_record_ids
    ]
    return {
        "schema_version": 3,
        "exported_at": exported_at.isoformat(timespec="seconds"),
        "experiment": {
            "id": item.id,
            "project_id": item.project_id,
            "title": item.title,
            "code": item.code,
            "status": item.status,
            "owner": item.owner,
            "start_date": _date_value(item.start_date),
            "end_date": _date_value(item.end_date),
            "objective": item.objective,
        },
        "samples": [_sample_usage_payload(usage) for usage in item.sample_usages],
        "plan_parameters": [_parameter_payload(parameter) for parameter in item.plan_parameters],
        "steps": [
            _plan_step_payload(step)
            for step in sorted(item.steps, key=_step_sort_key)
        ],
        "batches": batch_payloads,
        "unassigned_records": unassigned_records,
        "records": [record_payloads[record.id] for record in records],
    }


def build_json_export(item):
    return json.dumps(experiment_payload(item), ensure_ascii=False, indent=2).encode("utf-8")


def _markdown_value(value, fallback="未填写"):
    return str(value).strip() if value not in (None, "") else fallback


def _markdown_cell(value, fallback="—"):
    text = _markdown_value(value, fallback).replace("|", "\\|")
    return "<br>".join(part.strip() for part in text.splitlines())


def _markdown_table(headers, rows, empty="暂无数据。"):
    if not rows:
        return [empty]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_markdown_cell(value) for value in row) + " |" for row in rows)
    return lines


def _size_label(size_bytes):
    size = int(size_bytes or 0)
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


def _markdown_from_payload(payload):
    experiment = payload["experiment"]
    lines = [
        f"# {experiment['title']}",
        "",
        "> 实验导出报告 · R/LAB Research Assistant",
        "> 数据按当前实验快照生成，原始附件请优先使用 ZIP 完整归档保存。",
        "",
        "## 目录",
        "",
        "1. [实验概览](#实验概览)",
        "2. [实验目的](#实验目的)",
        "3. [关联样本与计划参数](#关联样本与计划参数)",
        "4. [计划步骤定义](#计划步骤定义)",
        "5. [实验执行与过程记录](#实验执行与过程记录)",
        "",
        "---",
        "",
        "## 实验概览",
        "",
    ]
    lines.extend(_markdown_table(("字段", "内容"), [
        ("实验编号", _markdown_value(experiment["code"], "未设置")),
        ("状态", experiment["status"]),
        ("负责人", _markdown_value(experiment["owner"])),
        ("计划开始", _markdown_value(experiment["start_date"], "未安排")),
        ("计划结束", _markdown_value(experiment["end_date"], "未安排")),
        ("导出时间", payload["exported_at"].replace("T", " ")),
    ]))
    lines.extend([
        "", "## 实验目的", "",
        "> " + _markdown_value(experiment["objective"]).replace("\n", "\n> "), "",
        "## 关联样本与计划参数", "", "### 关联样本", "",
    ])
    lines.extend(_markdown_table(("样本编号", "类型", "用途", "使用量", "位置", "状态", "备注"), [
        (sample["sample_code"], sample["sample_type"], sample["role"], sample["amount_used"],
         sample["location"], sample["status"], sample["notes"])
        for sample in payload["samples"]
    ], "暂无关联样本。"))
    lines.extend(["", "### 计划参数", ""])
    lines.extend(_markdown_table(("序号", "参数", "数值", "单位", "说明"), [
        (parameter["position"], parameter["name"], parameter["value"], parameter["unit"], parameter["notes"])
        for parameter in payload["plan_parameters"]
    ], "暂无结构化计划参数。"))
    lines.extend(["", "## 计划步骤定义", ""])
    lines.extend(_markdown_table(("序号", "步骤", "计划执行人", "计划日期", "说明"), [
        (step["position"], step["title"], step["operator"],
         step["planned_date"] or "未安排", step["description"])
        for step in payload["steps"]
    ], "暂无计划步骤。"))
    lines.extend(["", "## 实验执行与过程记录", ""])

    groups = execution_groups(payload)
    if not groups:
        lines.append("暂无实验执行。")
    for execution_index, execution in enumerate(groups, start=1):
        lines.extend([
            f"### 执行 {execution_index:02d} · {execution['batch_code']}",
            "",
        ])
        if execution.get("is_unassigned"):
            lines.extend(["> 注意：以下为历史未归档记录。数据已保留，请运行数据库升级完成执行归属修复。", ""])
        lines.extend(_markdown_table(("字段", "内容"), [
            ("执行编号", execution["batch_code"]),
            ("重复类型", execution["repeat_kind"]),
            ("重复序号", execution["repeat_number"]),
            ("实验分组", execution["group_name"]),
            ("执行人员", execution["operator"]),
            ("状态", execution["status"]),
            ("实际开始", execution["start_date"]),
            ("实际结束", execution["end_date"]),
            ("建议重复", "是" if execution["requires_repeat"] else "否"),
        ]))
        lines.extend(["", "#### 执行摘要", "", _markdown_value(execution["summary"]), ""])
        if execution["conclusion"]:
            lines.extend(["#### 执行结论", "", execution["conclusion"], ""])
        lines.extend(["#### 执行步骤", ""])
        lines.extend(_markdown_table(
            ("序号", "状态", "步骤", "执行人", "计划日期", "完成日期", "说明"),
            [
                (
                    step["position"], "已完成" if step["is_done"] else "待完成",
                    step["title"], step["operator"], step["planned_date"] or "未安排",
                    step["completed_date"] or "未完成", step["description"],
                )
                for step in execution["steps"]
            ],
            "暂无执行步骤。",
        ))
        lines.append("")
        if execution["actual_parameters"]:
            lines.extend(["#### 实际参数", ""])
            lines.extend(_markdown_table(("参数", "数值", "单位", "说明"), [
                (parameter["name"], parameter["value"], parameter["unit"], parameter["notes"])
                for parameter in execution["actual_parameters"]
            ]))
            lines.append("")

        if not execution["records"]:
            lines.extend(["暂无过程记录。", ""])
        for record_index, record in enumerate(execution["records"], start=1):
            lines.extend([
                f"#### 过程记录 {execution_index:02d}.{record_index:02d} · {record['record_date']} · {record['result']}",
                "",
                f"**实验人员：** {_markdown_value(record['operator'])}",
                "",
                "##### 结构化参数",
                "",
            ])
            lines.extend(_markdown_table(("参数", "数值", "单位", "说明"), [
                (parameter["name"], parameter["value"], parameter["unit"], parameter["notes"])
                for parameter in record["parameters"]
            ], "暂无结构化过程记录参数。"))
            if record["parameters"]:
                parameter_summary = "；".join(
                    f"{parameter['name']}：{parameter['value']}"
                    f"{' ' + parameter['unit'] if parameter['unit'] else ''}"
                    for parameter in record["parameters"]
                )
                lines.extend(["", f"**参数摘要：** {parameter_summary}"])
            lines.extend([
                "", "##### 实验条件", "",
                "> " + _markdown_value(record["conditions"]).replace("\n", "\n> "),
                "", "##### 实验过程", "", record["content"] or "未填写。",
                "", "##### 结论与备注", "", "> " + _markdown_value(record["remark"]), "",
            ])
            if record["attachments"]:
                lines.extend(["##### 结果与数据文件", ""])
                lines.extend(_markdown_table(
                    ("分类", "文件夹 / 文件", "版本", "大小", "SHA-256", "标签", "说明"),
                    [
                        (attachment["category"], f"`{attachment['relative_path']}`",
                         f"v{attachment['version_number']}", _size_label(attachment["size_bytes"]),
                         attachment["sha256"] or "旧文件未计算", attachment["tags"], attachment["description"])
                        for attachment in record["attachments"]
                    ],
                ))
                lines.append("")
        lines.extend(["---", ""])

    lines.extend([
        "*导出完成。请结合实验室 SOP 对剂量、统计结论和临床相关内容进行人工核验。*"
    ])
    return "\ufeff" + "\n".join(lines).rstrip() + "\n"


def build_markdown_export(item):
    return _markdown_from_payload(experiment_payload(item))


def _set_docx_font(document):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt, RGBColor

    style_specs = {
        "Normal": (10.5, "26343B", False),
        "Title": (26, "14242B", True),
        "Heading 1": (17, "14242B", True),
        "Heading 2": (13.5, "2166F3", True),
        "Heading 3": (11.5, "26343B", True),
    }
    for style_name, (font_size, color, bold) in style_specs.items():
        style = document.styles[style_name]
        style.font.name = "Microsoft YaHei"
        style.font.size = Pt(font_size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = bold
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.paragraph_format.space_after = Pt(7)
        style.paragraph_format.line_spacing = 1.25
    document.styles["Heading 1"].paragraph_format.space_before = Pt(18)
    document.styles["Heading 1"].paragraph_format.keep_with_next = True
    document.styles["Heading 2"].paragraph_format.space_before = Pt(13)
    document.styles["Heading 2"].paragraph_format.keep_with_next = True

    section = document.sections[0]
    section.top_margin = Mm(18)
    section.bottom_margin = Mm(17)
    section.left_margin = Mm(19)
    section.right_margin = Mm(19)
    header = section.header.paragraphs[0]
    header.text = "R/LAB  ·  RESEARCH ASSISTANT"
    header.style = document.styles["Normal"]
    header.runs[0].font.size = Pt(8)
    header.runs[0].font.bold = True
    header.runs[0].font.color.rgb = RGBColor.from_string("2166F3")
    footer = section.footer.paragraphs[0]
    footer.alignment = 2
    footer.add_run("实验报告  ·  ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    for run in footer.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor.from_string("74838A")


def _shade_docx_cell(cell, fill):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    properties = cell._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        properties.append(shading)
    shading.set(qn("w:fill"), fill)


def _format_docx_table(table):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    table.autofit = True
    header_properties = table.rows[0]._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    header_properties.append(repeat)
    for cell in table.rows[0].cells:
        _shade_docx_cell(cell, "2166F3")
        for run in cell.paragraphs[0].runs:
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(9)
    for row_index, row in enumerate(table.rows[1:], start=1):
        if row_index % 2 == 0:
            for cell in row.cells:
                _shade_docx_cell(cell, "F3F6F7")
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                for run in paragraph.runs:
                    run.font.size = Pt(9)


def _add_docx_callout(document, label, text, fill="EDF3FF"):
    from docx.shared import Pt, RGBColor

    table = document.add_table(rows=1, cols=1)
    table.autofit = True
    cell = table.cell(0, 0)
    _shade_docx_cell(cell, fill)
    heading = cell.paragraphs[0]
    label_run = heading.add_run(label)
    label_run.bold = True
    label_run.font.color.rgb = RGBColor.from_string("2166F3")
    body = cell.add_paragraph(_text(text, "未填写。") or "未填写。")
    body.paragraph_format.space_after = Pt(5)
    document.add_paragraph().paragraph_format.space_after = Pt(0)


def _add_docx_table(document, headers, rows):
    if not rows:
        document.add_paragraph("暂无数据。")
        return
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for index, header in enumerate(headers):
        table.rows[0].cells[index].text = header
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = _text(value, "-") or "-"
    _format_docx_table(table)
    return table


def build_docx_export(item):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    payload = experiment_payload(item)
    experiment = payload["experiment"]
    document = Document()
    _set_docx_font(document)
    document.core_properties.title = experiment["title"]
    document.core_properties.subject = "实验计划、实验执行与过程记录导出报告"
    document.core_properties.author = "R/LAB Research Assistant"
    title = document.add_heading(experiment["title"], 0)
    title.paragraph_format.space_after = Pt(4)
    subtitle = document.add_paragraph("EXPERIMENT REPORT  /  实验计划、执行与过程记录")
    subtitle.runs[0].font.size = Pt(9)
    subtitle.runs[0].font.bold = True
    subtitle.runs[0].font.color.rgb = RGBColor.from_string("2166F3")
    subtitle.paragraph_format.space_after = Pt(15)

    document.add_heading("01  实验概览", level=1)
    _add_docx_table(document, ("字段", "内容"), (
        ("实验编号", experiment["code"] or "未设置"),
        ("状态", experiment["status"]),
        ("负责人", experiment["owner"]),
        ("计划开始", experiment["start_date"]),
        ("计划结束", experiment["end_date"]),
        ("导出时间", payload["exported_at"].replace("T", " ")),
    ))
    document.add_heading("02  实验目的", level=1)
    _add_docx_callout(document, "OBJECTIVE  /  研究目的", experiment["objective"])

    document.add_heading("03  样本与计划参数", level=1)
    document.add_heading("3.1  关联样本", level=2)
    _add_docx_table(document, ("样本编号", "类型", "用途", "使用量", "位置", "状态", "备注"), [
        (sample["sample_code"], sample["sample_type"], sample["role"], sample["amount_used"],
         sample["location"], sample["status"], sample["notes"])
        for sample in payload["samples"]
    ])

    document.add_heading("3.2  计划参数", level=2)
    _add_docx_table(document, ("序号", "参数", "数值", "单位", "说明"), [
        (parameter["position"], parameter["name"], parameter["value"], parameter["unit"], parameter["notes"])
        for parameter in payload["plan_parameters"]
    ])

    document.add_heading("04  计划步骤定义", level=1)
    _add_docx_table(document, ("序号", "步骤", "计划执行人", "计划日期", "说明"), [
        (step["position"], step["title"], step["operator"],
         step["planned_date"], step["description"])
        for step in payload["steps"]
    ])

    document.add_page_break()
    document.add_heading("05  实验执行与过程记录", level=1)
    groups = execution_groups(payload)
    if not groups:
        document.add_paragraph("暂无实验执行。")
    for execution_index, execution in enumerate(groups, start=1):
        if execution_index > 1:
            document.add_page_break()
        document.add_heading(
            f"执行 {execution_index:02d}  /  {execution['batch_code']}", level=2
        )
        if execution.get("is_unassigned"):
            _add_docx_callout(
                document,
                "DATA INTEGRITY  /  历史未归档",
                "以下记录缺少有效的实验执行归属。数据已保留，请运行数据库升级完成修复。",
                "FFF4D6",
            )
        _add_docx_table(document, ("字段", "内容"), (
            ("执行编号", execution["batch_code"]),
            ("重复类型", execution["repeat_kind"]),
            ("重复序号", execution["repeat_number"]),
            ("实验分组", execution["group_name"]),
            ("执行人员", execution["operator"]),
            ("状态", execution["status"]),
            ("实际开始", execution["start_date"]),
            ("实际结束", execution["end_date"]),
            ("建议重复", "是" if execution["requires_repeat"] else "否"),
        ))
        _add_docx_callout(document, "SUMMARY  /  执行摘要", execution["summary"], "F3F6F7")
        if execution["conclusion"]:
            _add_docx_callout(document, "CONCLUSION  /  执行结论", execution["conclusion"], "FFF4D6")
        document.add_heading(f"5.{execution_index}.1  执行步骤", level=3)
        _add_docx_table(document, ("序号", "状态", "步骤", "执行人", "计划日期", "完成日期", "说明"), [
            (
                step["position"], "已完成" if step["is_done"] else "待完成",
                step["title"], step["operator"], step["planned_date"],
                step["completed_date"], step["description"],
            )
            for step in execution["steps"]
        ])
        if execution["actual_parameters"]:
            document.add_heading(f"5.{execution_index}.2  实际参数", level=3)
            _add_docx_table(document, ("参数", "数值", "单位", "说明"), [
                (parameter["name"], parameter["value"], parameter["unit"], parameter["notes"])
                for parameter in execution["actual_parameters"]
            ])
        if not execution["records"]:
            document.add_paragraph("暂无过程记录。")
        for record_index, record in enumerate(execution["records"], start=1):
            document.add_heading(
                f"过程记录 {execution_index:02d}.{record_index:02d}  /  {record['record_date']}",
                level=3,
            )
            summary = document.add_paragraph()
            summary.alignment = WD_ALIGN_PARAGRAPH.LEFT
            summary.add_run(
                f"结果：{record['result']}  ·  实验人员：{record['operator'] or '未填写'}"
            ).bold = True
            document.add_paragraph("结构化参数").runs[0].bold = True
            _add_docx_table(document, ("参数", "数值", "单位", "说明"), [
                (parameter["name"], parameter["value"], parameter["unit"], parameter["notes"])
                for parameter in record["parameters"]
            ])
            document.add_paragraph("实验条件").runs[0].bold = True
            _add_docx_callout(document, "CONDITIONS  /  实验条件", record["conditions"], "F3F6F7")
            document.add_paragraph("实验过程").runs[0].bold = True
            document.add_paragraph(record["content"] or "未填写。")
            document.add_paragraph("结论与备注").runs[0].bold = True
            _add_docx_callout(document, "CONCLUSION  /  结论与后续", record["remark"], "FFF4D6")
            document.add_paragraph("结果与数据文件").runs[0].bold = True
            _add_docx_table(document, ("分类", "文件", "版本", "大小（字节）", "SHA-256", "标签", "说明"), [
                (attachment["category"], attachment["relative_path"], attachment["version_number"],
                 attachment["size_bytes"], attachment["sha256"], attachment["tags"], attachment["description"])
                for attachment in record["attachments"]
            ])

    document.add_paragraph()
    review = document.add_paragraph("人工核验提示：剂量、统计结论和临床相关解释须结合实验室 SOP 与原始数据复核。")
    review.runs[0].italic = True
    review.runs[0].font.size = Pt(8.5)
    review.runs[0].font.color.rgb = RGBColor.from_string("74838A")

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _add_xlsx_sheet(workbook, title, headers, rows):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    sheet = workbook.create_sheet(title)
    sheet.append(list(headers))
    for row in rows:
        sheet.append([_text(value) for value in row])
    header_fill = PatternFill("solid", fgColor="2166F3")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(vertical="center")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column_index, header in enumerate(headers, start=1):
        values = [header, *[row[column_index - 1] for row in rows if len(row) >= column_index]]
        width = min(max(max((len(_text(value)) for value in values), default=8) + 2, 10), 48)
        sheet.column_dimensions[get_column_letter(column_index)].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    return sheet


def build_xlsx_export(item):
    from openpyxl import Workbook

    payload = experiment_payload(item)
    experiment = payload["experiment"]
    groups = execution_groups(payload)
    workbook = Workbook()
    workbook.remove(workbook.active)
    _add_xlsx_sheet(workbook, "实验信息", ("字段", "内容"), [
        ("实验名称", experiment["title"]), ("实验编号", experiment["code"]),
        ("状态", experiment["status"]), ("负责人", experiment["owner"]),
        ("计划开始", experiment["start_date"]), ("计划结束", experiment["end_date"]),
        ("实验目的", experiment["objective"]), ("导出时间", payload["exported_at"]),
    ])
    _add_xlsx_sheet(workbook, "关联样本", ("样本编号", "类型", "来源", "位置", "库存量", "状态", "用途", "使用量", "备注"), [
        (sample["sample_code"], sample["sample_type"], sample["source"], sample["location"],
         sample["quantity"], sample["status"], sample["role"], sample["amount_used"], sample["notes"])
        for sample in payload["samples"]
    ])
    _add_xlsx_sheet(workbook, "计划参数", ("序号", "参数", "数值", "单位", "说明"), [
        (parameter["position"], parameter["name"], parameter["value"], parameter["unit"], parameter["notes"])
        for parameter in payload["plan_parameters"]
    ])
    _add_xlsx_sheet(workbook, "实验步骤", ("序号", "步骤", "计划执行人", "计划日期", "说明"), [
        (step["position"], step["title"], step["operator"], step["planned_date"], step["description"])
        for step in payload["steps"]
    ])
    _add_xlsx_sheet(workbook, "实验执行", (
        "执行 ID", "执行编号", "重复类型", "重复序号", "实验分组", "执行人员", "状态",
        "实际开始", "实际结束", "执行摘要", "执行结论", "建议重复", "记录数",
    ), [
        (execution["id"], execution["batch_code"], execution["repeat_kind"], execution["repeat_number"],
         execution["group_name"], execution["operator"], execution["status"], execution["start_date"],
         execution["end_date"], execution["summary"], execution["conclusion"],
         execution["requires_repeat"], len(execution["records"]))
        for execution in groups
    ])
    _add_xlsx_sheet(workbook, "执行步骤", (
        "执行 ID", "执行编号", "步骤 ID", "来源计划步骤 ID", "序号", "状态", "步骤",
        "执行人", "计划日期", "完成日期", "说明",
    ), [
        (
            execution["id"], execution["batch_code"], step["id"], step["source_step_id"],
            step["position"], "已完成" if step["is_done"] else "待完成", step["title"],
            step["operator"], step["planned_date"], step["completed_date"], step["description"],
        )
        for execution in groups for step in execution["steps"]
    ])
    _add_xlsx_sheet(workbook, "过程记录", (
        "执行 ID", "执行编号", "过程记录 ID", "日期", "实验人员", "结果", "实验条件", "实验过程", "结论与备注",
    ), [
        (record["batch_id"], record["batch_code"], record["id"], record["record_date"],
         record["operator"], record["result"], record["conditions"], record["content"], record["remark"])
        for record in payload["records"]
    ])
    _add_xlsx_sheet(workbook, "过程记录参数", (
        "执行编号", "过程记录 ID", "日期", "序号", "参数", "数值", "单位", "说明",
    ), [
        (record["batch_code"], record["id"], record["record_date"], parameter["position"], parameter["name"],
         parameter["value"], parameter["unit"], parameter["notes"])
        for record in payload["records"] for parameter in record["parameters"]
    ])
    _add_xlsx_sheet(workbook, "附件清单", (
        "执行编号", "过程记录 ID", "日期", "分类", "文件", "版本", "大小（字节）", "类型", "SHA-256", "标签", "说明",
    ), [
        (record["batch_code"], record["id"], record["record_date"], attachment["category"], attachment["relative_path"],
         attachment["version_number"], attachment["size_bytes"], attachment["mime_type"],
         attachment["sha256"], attachment["tags"], attachment["description"])
        for record in payload["records"] for attachment in record["attachments"]
    ])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _archive_component(value, fallback):
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", _text(value).strip()).strip(". ")
    return cleaned[:120] or fallback


def _archive_relative_parts(value):
    parts = []
    for index, raw_part in enumerate(_text(value).replace("\\", "/").split("/"), start=1):
        if raw_part in {"", "."}:
            continue
        if raw_part == "..":
            raw_part = "parent"
        parts.append(_archive_component(raw_part, f"item-{index}"))
    return parts or ["file"]


def build_archive_export(item, attachment_path_resolver):
    """Build a ZIP from the same filtered payload used by every other export."""
    payload = experiment_payload(item)
    record_by_id = {record.id: record for record in _active(item.records)}
    attachment_by_id = {
        attachment.id: attachment
        for record in record_by_id.values()
        for attachment in _active(record.attachments)
    }
    archive = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    manifest_output = io.StringIO()
    manifest_writer = csv.writer(manifest_output)
    manifest_writer.writerow([
        "execution_id", "execution_code", "record_date", "record_id", "category", "relative_path",
        "version", "size_bytes", "mime_type", "sha256", "tags", "description", "archive_path",
    ])
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
    ) as bundle:
        bundle.writestr("report.md", _markdown_from_payload(payload).encode("utf-8"))
        bundle.writestr(
            "experiment.json",
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        for execution in execution_groups(payload):
            execution_code = execution["batch_code"]
            execution_folder = _archive_component(execution_code, "execution")
            for record in execution["records"]:
                for attachment_data in record["attachments"]:
                    attachment = attachment_by_id.get(attachment_data["id"])
                    path_parts = _archive_relative_parts(attachment_data["relative_path"])
                    if attachment_data["version_number"] > 1:
                        path_parts[-1] = f"v{attachment_data['version_number']}-{path_parts[-1]}"
                    archive_path = "/".join([
                        "files",
                        execution_folder,
                        record["record_date"] or "unknown-date",
                        f"record-{record['id']}",
                        _archive_component(attachment_data["category"], "uncategorized"),
                        *path_parts,
                    ])
                    source_path = attachment_path_resolver(attachment) if attachment else None
                    exists = bool(source_path and source_path.is_file())
                    if exists:
                        bundle.write(source_path, archive_path)
                    elif attachment_data["storage_mode"] == "external":
                        archive_path = "外部链接（未打包）"
                    else:
                        archive_path = "文件缺失"
                    manifest_writer.writerow([
                        record["batch_id"], execution_code, record["record_date"], record["id"],
                        attachment_data["category"], attachment_data["relative_path"],
                        attachment_data["version_number"], attachment_data["size_bytes"],
                        attachment_data["mime_type"], attachment_data["sha256"], attachment_data["tags"],
                        attachment_data["description"], archive_path,
                    ])
        bundle.writestr("file-manifest.csv", ("\ufeff" + manifest_output.getvalue()).encode("utf-8"))
    archive.seek(0)
    return archive

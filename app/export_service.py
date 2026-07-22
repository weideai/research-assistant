import io
import json
from datetime import datetime


def _date_value(value):
    return value.isoformat() if value else None


def _text(value, fallback=""):
    if value is None:
        return fallback
    return str(value)


def experiment_payload(item, exported_at=None):
    """Return one stable data shape shared by every structured export format."""
    exported_at = exported_at or datetime.now()
    records = sorted(item.records, key=lambda record: (record.record_date, record.id))
    return {
        "schema_version": 1,
        "exported_at": exported_at.isoformat(timespec="seconds"),
        "experiment": {
            "id": item.id,
            "title": item.title,
            "code": item.code,
            "batch_code": item.batch_code,
            "repeat_kind": item.repeat_kind,
            "repeat_number": item.repeat_number,
            "group_name": item.group_name,
            "status": item.status,
            "owner": item.owner,
            "start_date": _date_value(item.start_date),
            "end_date": _date_value(item.end_date),
            "objective": item.objective,
        },
        "samples": [
            {
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
            for usage in item.sample_usages
        ],
        "plan_parameters": [
            {
                "position": parameter.position,
                "name": parameter.name,
                "value": parameter.value,
                "unit": parameter.unit,
                "notes": parameter.notes,
            }
            for parameter in item.plan_parameters
        ],
        "steps": [
            {
                "id": step.id,
                "position": step.position,
                "title": step.title,
                "description": step.description,
                "operator": step.operator,
                "planned_date": _date_value(step.planned_date),
                "completed_date": _date_value(step.completed_date),
                "is_done": step.is_done,
            }
            for step in item.steps
        ],
        "records": [
            {
                "id": record.id,
                "record_date": _date_value(record.record_date),
                "operator": record.operator,
                "conditions": record.conditions,
                "content": record.content,
                "result": record.result,
                "remark": record.remark,
                "parameters": [
                    {
                        "position": parameter.position,
                        "name": parameter.name,
                        "value": parameter.value,
                        "unit": parameter.unit,
                        "notes": parameter.notes,
                    }
                    for parameter in record.parameters
                ],
                "attachments": [
                    {
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
                    }
                    for attachment in sorted(
                        record.attachments,
                        key=lambda attachment: (attachment.relative_path.lower(), attachment.version_number),
                    )
                ],
            }
            for record in records
        ],
    }


def build_json_export(item):
    return json.dumps(experiment_payload(item), ensure_ascii=False, indent=2).encode("utf-8")


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
    document.core_properties.subject = "实验计划与实验记录导出报告"
    document.core_properties.author = "R/LAB Research Assistant"
    title = document.add_heading(experiment["title"], 0)
    title.paragraph_format.space_after = Pt(4)
    subtitle = document.add_paragraph("EXPERIMENT REPORT  /  实验计划与记录")
    subtitle.runs[0].font.size = Pt(9)
    subtitle.runs[0].font.bold = True
    subtitle.runs[0].font.color.rgb = RGBColor.from_string("2166F3")
    subtitle.paragraph_format.space_after = Pt(15)

    document.add_heading("01  实验概览", level=1)
    _add_docx_table(document, ("字段", "内容"), (
        ("实验编号", experiment["code"] or "未设置"),
        ("实验批次", experiment["batch_code"] or "未设置"),
        ("重复类型", f"{experiment['repeat_kind']} #{experiment['repeat_number']}"),
        ("实验分组", experiment["group_name"]),
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

    document.add_heading("04  实验步骤", level=1)
    _add_docx_table(document, ("序号", "完成", "步骤", "执行人", "计划日期", "完成日期", "说明"), [
        (step["position"], "是" if step["is_done"] else "否", step["title"], step["operator"],
         step["planned_date"], step["completed_date"], step["description"])
        for step in payload["steps"]
    ])

    document.add_page_break()
    document.add_heading("05  实验记录", level=1)
    if not payload["records"]:
        document.add_paragraph("暂无实验记录。")
    for index, record in enumerate(payload["records"], start=1):
        if index > 1:
            document.add_page_break()
        document.add_heading(f"记录 {index:02d}  /  {record['record_date']}", level=2)
        summary = document.add_paragraph()
        summary.alignment = WD_ALIGN_PARAGRAPH.LEFT
        summary.add_run(f"结果：{record['result']}  ·  实验人员：{record['operator'] or '未填写'}").bold = True
        document.add_heading("5.%d.1  结构化参数" % index, level=3)
        _add_docx_table(document, ("参数", "数值", "单位", "说明"), [
            (parameter["name"], parameter["value"], parameter["unit"], parameter["notes"])
            for parameter in record["parameters"]
        ])
        document.add_heading("5.%d.2  实验条件" % index, level=3)
        _add_docx_callout(document, "CONDITIONS  /  实验条件", record["conditions"], "F3F6F7")
        document.add_heading("5.%d.3  实验过程" % index, level=3)
        document.add_paragraph(record["content"] or "未填写。")
        document.add_heading("5.%d.4  结论与备注" % index, level=3)
        _add_docx_callout(document, "CONCLUSION  /  结论与后续", record["remark"], "FFF4D6")
        document.add_heading("5.%d.5  结果与数据文件" % index, level=3)
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
    workbook = Workbook()
    workbook.remove(workbook.active)
    _add_xlsx_sheet(workbook, "实验信息", ("字段", "内容"), [
        ("实验名称", experiment["title"]), ("实验编号", experiment["code"]),
        ("实验批次", experiment["batch_code"]), ("重复类型", experiment["repeat_kind"]),
        ("重复序号", experiment["repeat_number"]), ("实验分组", experiment["group_name"]),
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
    _add_xlsx_sheet(workbook, "实验步骤", ("序号", "完成", "步骤", "执行人", "计划日期", "完成日期", "说明"), [
        (step["position"], step["is_done"], step["title"], step["operator"], step["planned_date"],
         step["completed_date"], step["description"])
        for step in payload["steps"]
    ])
    _add_xlsx_sheet(workbook, "实验记录", ("记录 ID", "日期", "实验人员", "结果", "实验条件", "实验过程", "结论与备注"), [
        (record["id"], record["record_date"], record["operator"], record["result"], record["conditions"],
         record["content"], record["remark"])
        for record in payload["records"]
    ])
    _add_xlsx_sheet(workbook, "记录参数", ("记录 ID", "日期", "序号", "参数", "数值", "单位", "说明"), [
        (record["id"], record["record_date"], parameter["position"], parameter["name"],
         parameter["value"], parameter["unit"], parameter["notes"])
        for record in payload["records"] for parameter in record["parameters"]
    ])
    _add_xlsx_sheet(workbook, "附件清单", ("记录 ID", "日期", "分类", "文件", "版本", "大小（字节）", "类型", "SHA-256", "标签", "说明"), [
        (record["id"], record["record_date"], attachment["category"], attachment["relative_path"],
         attachment["version_number"], attachment["size_bytes"], attachment["mime_type"],
         attachment["sha256"], attachment["tags"], attachment["description"])
        for record in payload["records"] for attachment in record["attachments"]
    ])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()

"""Exportação do laudo para PDF (via Qt, sem dependências extras)."""
from __future__ import annotations

import html
from dataclasses import dataclass

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument


@dataclass
class ReportHeader:
    institution: str = ""
    physician: str = ""
    crm: str = ""
    patient_name: str = ""
    patient_id: str = ""
    exam_date: str = ""
    accession: str = ""


def _fmt_date(d: str) -> str:
    return f"{d[6:8]}/{d[4:6]}/{d[0:4]}" if len(d) == 8 and d.isdigit() else d


def build_html(header: ReportHeader, body: str) -> str:
    e = html.escape
    lines = body.splitlines()
    title = e(lines[0]) if lines else ""
    rest = []
    for ln in lines[1:]:
        s = e(ln)
        if ln.strip().endswith(":") and ln.strip().upper() == ln.strip():
            rest.append(f"<p style='margin-top:10px'><b>{s}</b></p>")
        elif ln.strip():
            rest.append(f"<p style='margin:2px 0'>{s}</p>")
    return f"""
<html><body style="font-family:Helvetica,Arial; font-size:10.5pt">
<p style="font-size:9pt; color:#555">{e(header.institution)}</p>
<table width="100%" style="font-size:9.5pt; border-bottom:1px solid #999">
<tr><td><b>Paciente:</b> {e(header.patient_name)}</td><td><b>ID:</b> {e(header.patient_id)}</td></tr>
<tr><td><b>Data do exame:</b> {e(_fmt_date(header.exam_date))}</td><td><b>Atendimento:</b> {e(header.accession)}</td></tr>
</table>
<h3 style="text-align:center; margin-top:16px">{title}</h3>
{''.join(rest)}
<p style="margin-top:40px; text-align:center">______________________________<br>
{e(header.physician)}<br>{('CRM ' + e(header.crm)) if header.crm else ''}</p>
</body></html>"""


def export_pdf(path: str, header: ReportHeader, body: str) -> None:
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(20, 18, 20, 18), QPageLayout.Unit.Millimeter)
    writer.setResolution(300)
    doc = QTextDocument()
    doc.setHtml(build_html(header, body))
    doc.print_(writer)

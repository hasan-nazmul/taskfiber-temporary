import io
import csv
from datetime import datetime
from django.http import HttpResponse, StreamingHttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


class Echo:
    """Pseudo-buffer for streaming CSV writes."""
    def write(self, value):
        return value


def csv_response(filename, headers, rows):
    """Build a streaming CSV response from headers and row data."""
    def stream():
        writer = csv.writer(Echo())
        yield '\ufeff'  # UTF-8 BOM for Excel compatibility
        yield writer.writerow(headers)
        for row in rows:
            yield writer.writerow(row)

    response = StreamingHttpResponse(stream(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def pdf_response(filename, title, headers, rows, landscape_mode=False):
    """Build a PDF HttpResponse with a styled table."""
    buffer = io.BytesIO()
    page_size = landscape(A4) if landscape_mode else A4

    doc = SimpleDocTemplate(
        buffer, pagesize=page_size,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Heading1'],
        fontSize=14, spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'ReportSubtitle', parent=styles['Normal'],
        fontSize=8, textColor=colors.grey, spaceAfter=12,
    )

    elements = []
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(
        f'Generated on {datetime.now().strftime("%b %d, %Y at %I:%M %p")}',
        subtitle_style,
    ))

    # Wrap long text in Paragraph for cell wrapping
    cell_style = ParagraphStyle(
        'Cell', parent=styles['Normal'], fontSize=8, leading=10,
    )
    header_style = ParagraphStyle(
        'HeaderCell', parent=styles['Normal'],
        fontSize=8, leading=10, textColor=colors.whitesmoke,
    )

    table_data = [[Paragraph(str(h), header_style) for h in headers]]
    for row in rows:
        table_data.append([Paragraph(str(cell), cell_style) for cell in row])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        f'Total records: {len(rows)}',
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey),
    ))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

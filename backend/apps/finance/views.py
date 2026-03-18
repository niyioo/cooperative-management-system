import io
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django.http import FileResponse

# ReportLab Imports for Professional PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from .models import LedgerEntry
from .serializers import LedgerEntrySerializer
from apps.accounts.permissions import IsManagerOrAdmin 

class LedgerEntryViewSet(viewsets.ModelViewSet):
    """Global Income and Expense Ledger with PDF Export."""
    
    queryset = LedgerEntry.objects.select_related('member__user', 'recorded_by').order_by('-date', '-created_at')
    serializer_class = LedgerEntrySerializer
    permission_classes = [IsManagerOrAdmin]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

    @action(detail=False, methods=['get'])
    def export_pdf(self, request):
        """Generates a professional PDF statement of the current ledger view."""
        # 1. Get filtered data (respects search/type filters from frontend)
        queryset = self.filter_queryset(self.get_queryset())
        
        # 2. Setup PDF Buffer and Document
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4, 
            rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
        )
        elements = []
        styles = getSampleStyleSheet()

        # 3. Branding & Header Style
        header_style = ParagraphStyle(
            'Heading', 
            parent=styles['Heading1'], 
            textColor=colors.HexColor("#1e293b"), 
            fontSize=18, 
            spaceAfter=12
        )
        
        elements.append(Paragraph("BravEdge Solutions - Finance Ledger", header_style))
        elements.append(Paragraph(f"Generated on: {timezone.now().strftime('%b %d, %Y | %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 0.3 * inch))

        # 4. Prepare Table Data
        # Table Header
        data = [['Date', 'Reference', 'Category', 'Member', 'Type', 'Amount']]
        
        # Table Rows
        total_income = 0
        total_expense = 0

        for tx in queryset:
            amount_val = float(tx.amount)
            if tx.type == 'INCOME':
                total_income += amount_val
            else:
                total_expense += amount_val

            member_name = f"{tx.member.user.first_name} {tx.member.user.last_name}" if tx.member else "Global"
            
            data.append([
                tx.date.strftime('%Y-%m-%d'),
                tx.reference_id,
                tx.category[:15], # Truncate category if long
                member_name[:15],
                tx.type,
                f"N{amount_val:,.2f}"
            ])

        # 5. Create and Style the Table
        # Column widths adjusted for A4 (approx 7.5 inches total)
        table = Table(data, colWidths=[1.0*inch, 1.2*inch, 1.4*inch, 1.4*inch, 0.8*inch, 1.3*inch])
        
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")), # Dark Blue Header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'), # Right align amounts
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]) # Zebra stripes
        ])
        table.setStyle(style)
        elements.append(table)

        # 6. Summary Section
        elements.append(Spacer(1, 0.5 * inch))
        summary_data = [
            [f"Total Income: N{total_income:,.2f}"],
            [f"Total Expenses: N{total_expense:,.2f}"],
            [f"Net Balance: N{(total_income - total_expense):,.2f}"]
        ]
        
        for row in summary_data:
            elements.append(Paragraph(row[0], styles['Normal']))

        # 7. Build and Return
        doc.build(elements)
        buffer.seek(0)
        
        filename = f"BravEdge_Statement_{timezone.now().strftime('%Y%m%d')}.pdf"
        return FileResponse(buffer, as_attachment=True, filename=filename)
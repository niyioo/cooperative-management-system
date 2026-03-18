import io
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.http import FileResponse
from decimal import Decimal

# ReportLab Imports for Professional PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from apps.members.models import Member
from apps.savings.models import SavingsAccount
from apps.loans.models import Loan
from apps.shares.models import ShareAccount
from apps.finance.models import LedgerEntry 

def get_admin_stats():
    """Helper to calculate the core financials for the dashboard and PDF."""
    total_income = LedgerEntry.objects.filter(type='INCOME').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expenses = LedgerEntry.objects.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    return {
        "members": {
            "total": Member.objects.count(),
            "active": Member.objects.filter(status='ACTIVE').count()
        },
        "financials": {
            "total_savings": SavingsAccount.objects.aggregate(total=Sum('balance'))['total'] or Decimal('0.00'),
            "total_shares": ShareAccount.objects.aggregate(total=Sum('current_value'))['total'] or Decimal('0.00'),
            "total_loans_disbursed": Loan.objects.filter(status__in=['ACTIVE', 'COMPLETED']).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0.00'),
            "outstanding_loans": Loan.objects.filter(status='ACTIVE').aggregate(total=Sum('balance_remaining'))['total'] or Decimal('0.00'),
            "coop_income": total_income,
            "coop_expenses": total_expenses,
            "net_profit": total_income - total_expenses
        }
    }

class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # 1. Handle Member Dashboard
        if user.role == 'MEMBER':
            member = getattr(user, 'member_profile', None)
            if not member:
                return Response({"detail": "Member profile not found"}, status=404)
            
            savings = SavingsAccount.objects.filter(member=member).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
            shares = ShareAccount.objects.filter(member=member).aggregate(total=Sum('current_value'))['total'] or Decimal('0.00')
            active_loans = Loan.objects.filter(member=member, status='ACTIVE').aggregate(total=Sum('balance_remaining'))['total'] or Decimal('0.00')
            recent_entries = LedgerEntry.objects.filter(member=member).order_by('-date')[:5]
            
            formatted_transactions = [{
                "id": e.id, "type": e.type, "amount": float(e.amount),
                "date": e.date, "description": e.description or f"{e.type.title()} Entry"
            } for e in recent_entries]

            return Response({
                "role": "MEMBER", "total_savings": savings, "total_shares_value": shares,
                "outstanding_loan_balance": active_loans, "recent_transactions": formatted_transactions
            })

        # 2. Handle Admin Dashboard
        stats = get_admin_stats()
        
        # Monthly Chart Logic
        six_months_ago = timezone.now().replace(day=1) - timezone.timedelta(days=150)
        monthly_stats = LedgerEntry.objects.filter(date__gte=six_months_ago).annotate(month=TruncMonth('date')).values('month', 'type').annotate(total=Sum('amount')).order_by('month')

        chart_map = {}
        for entry in monthly_stats:
            m_name = entry['month'].strftime('%b')
            if m_name not in chart_map: chart_map[m_name] = {"month": m_name, "income": 0, "expenses": 0}
            chart_map[m_name]['income' if entry['type'] == 'INCOME' else 'expenses'] = float(entry['total'])

        return Response({
            **stats,
            "role": "ADMIN",
            "chart_data": list(chart_map.values())
        })

class DashboardExportPDFView(APIView):
    """Generates the professional branded PDF report for the Dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stats = get_admin_stats()
        f = stats['financials']
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        elements = []
        styles = getSampleStyleSheet()

        # Branded Header
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor("#0f172a"), spaceAfter=12)
        elements.append(Paragraph("BravEdge Executive Summary", title_style))
        elements.append(Paragraph(f"Report Generated: {timezone.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 0.4 * inch))

        # Financial Data Table
        table_data = [
            ['Financial Metric', 'Current Value'],
            ['Active Members', stats['members']['active']],
            ['Total Savings Pool', f"N{f['total_savings']:,.2f}"],
            ['Total Share Capital', f"N{f['total_shares']:,.2f}"],
            ['Total Loan Portfolio', f"N{f['total_loans_disbursed']:,.2f}"],
            ['Cooperative Income', f"N{f['coop_income']:,.2f}"],
            ['Cooperative Expenses', f"N{f['coop_expenses']:,.2f}"],
            ['Net Operational Profit', f"N{f['net_profit']:,.2f}"],
        ]

        t = Table(table_data, colWidths=[3.5*inch, 2.5*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(t)

        doc.build(elements)
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename=f"BravEdge_Full_Report_{timezone.now().date()}.pdf")
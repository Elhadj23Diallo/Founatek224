# product_transparency/api/sales.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from product_transparency.models import Sale, SaleItem, Product, Company
from decimal import Decimal

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from product_transparency.models import Sale

@method_decorator(csrf_exempt, name="dispatch")
class CreateSaleAPIView(APIView):
    permission_classes = [AllowAny]  # 🔥 IMPORTANT

    def post(self, request):
        data = request.data

        company_id = data.get("company_id")
        items = data.get("items", [])

        if not company_id or not items:
            return Response(
                {"error": "Données invalides"},
                status=400
            )

        company = Company.objects.get(id=company_id)

        sale = Sale.objects.create(
            company=company,
            total_amount=Decimal("0.00")
        )

        total = Decimal("0.00")

        for item in items:
            product = Product.objects.get(uuid=item["product_id"])
            qty = int(item["quantity"])
            price = product.pricing.price

            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=qty,
                unit_price=price
            )

            total += price * qty

        sale.total_amount = total
        sale.save()

        return Response({
            "success": True,
            "sale_id": str(sale.id),
            "total": total
        })





class SaleTicketPDFView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, sale_id):
        sale = get_object_or_404(Sale, id=sale_id)

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="ticket_{sale.id}.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("<b>FOUNATEK IOT</b>", styles["Title"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Vente ID : {sale.id}", styles["Normal"]))
        story.append(Paragraph(f"Date : {sale.created_at}", styles["Normal"]))
        story.append(Spacer(1, 12))

        for item in sale.items.all():
            story.append(
                Paragraph(
                    f"{item.quantity} x {item.product.name} — {item.line_total()} GNF",
                    styles["Normal"]
                )
            )

        story.append(Spacer(1, 12))
        story.append(
            Paragraph(f"<b>TOTAL : {sale.total_amount} GNF</b>", styles["Heading2"])
        )

        doc.build(story)
        return response


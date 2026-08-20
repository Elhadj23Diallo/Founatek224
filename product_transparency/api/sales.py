# product_transparency/api/sales.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
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
    # Le site web appelle cette API avec la session du navigateur (cookie) + CSRF,
    # l'app mobile avec le Token DRF — les deux doivent être acceptés.
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        items = data.get("items", [])

        if not items:
            return Response({"error": "Panier vide"}, status=400)

        # La caisse n'appartient qu'au propriétaire de l'entreprise connecté —
        # jamais au company_id envoyé par le client (évite qu'un compte quelconque
        # crée une vente pour l'entreprise d'un autre).
        company = Company.objects.filter(user=request.user).first()
        if not company:
            return Response({"error": "Aucune entreprise associée à votre compte"}, status=403)

        sale = Sale.objects.create(
            company=company,
            total_amount=Decimal("0.00")
        )

        total = Decimal("0.00")

        for item in items:
            try:
                # Le produit doit appartenir à la même entreprise que le vendeur.
                product = Product.objects.get(uuid=item["product_id"], company=company)
                qty = int(item["quantity"])
                price = product.pricing.price
            except (Product.DoesNotExist, KeyError, TypeError, ValueError):
                sale.delete()
                return Response({"error": "Produit invalide dans le panier"}, status=400)

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
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, sale_id):
        sale = get_object_or_404(Sale, id=sale_id)
        company = Company.objects.filter(user=request.user).first()
        if not company or sale.company_id != company.id:
            return Response({"error": "Accès refusé"}, status=403)

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


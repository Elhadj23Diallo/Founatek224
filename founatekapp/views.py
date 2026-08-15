from decimal import Decimal
from django.views.decorators.cache import never_cache
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from .models import Category, Product, Cart, CartItem, Order, OrderItem, LoyaltyAccount, ExchangeRate, Review, get_display_price
from .signals import send_order_email, send_admin_order_notification


def _get_currency_context(request):
    currency_code = (request.session.get('currency_code') or 'GNF').upper()
    exchange_rate = None
    if currency_code != 'GNF':
        exchange_rate = ExchangeRate.objects.filter(currency_code=currency_code).first()
    return {'currency_code': currency_code, 'exchange_rate': exchange_rate}


def _apply_currency_to_request(request):
    return _get_currency_context(request)


def home(request):
    categories = Category.objects.all()
    featured = Product.objects.filter(is_active=True)[:8]
    context = {'categories': categories, 'featured': featured}
    context.update(_apply_currency_to_request(request))
    return render(request, 'store/home.html', context)


def product_list(request):
    products = Product.objects.filter(is_active=True)
    categories = Category.objects.all()
    category_slug = request.GET.get('category')
    query = request.GET.get('q', '')

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    else:
        category = None

    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))

    context = {
        'products': products,
        'categories': categories,
        'current_category': category,
        'query': query,
    }
    context.update(_apply_currency_to_request(request))
    return render(request, 'store/product_list.html', context)


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category, is_active=True)
    context = {
        'category': category,
        'products': products,
    }
    context.update(_apply_currency_to_request(request))
    return render(request, 'store/category_detail.html', context)


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    related = Product.objects.filter(category=product.category, is_active=True).exclude(pk=product.pk)[:4]
    reviews = product.reviews.select_related('user').all()
    user_review = reviews.filter(user=request.user).first() if request.user.is_authenticated else None
    context = {'product': product, 'related': related, 'reviews': reviews, 'user_review': user_review}
    context.update(_apply_currency_to_request(request))
    return render(request, 'store/product_detail.html', context)


def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@login_required
@never_cache
def cart_detail(request):
    cart = _get_or_create_cart(request.user)
    context = {'cart': cart}
    context.update(_apply_currency_to_request(request))
    return render(request, 'store/cart.html', context)


@login_required
@never_cache
def cart_add(request, product_id):
    if request.method != 'POST':
        return redirect('founatekapp:cart')
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    cart = _get_or_create_cart(request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += 1
        item.save()
    messages.success(request, f'"{product.name}" ajouté au panier.')
    return redirect('founatekapp:cart')


@login_required
@never_cache
def cart_remove(request, item_id):
    if request.method != 'POST':
        return redirect('founatekapp:cart')
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    item.delete()
    messages.info(request, 'Article retiré du panier.')
    return redirect('founatekapp:cart')


@login_required
def cart_update(request, item_id):
    if request.method != 'POST':
        return redirect('founatekapp:cart')
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    qty = int(request.POST.get('quantity', 1))
    if qty > 0:
        item.quantity = qty
        item.save()
    else:
        item.delete()
    return redirect('founatekapp:cart')


@login_required
def checkout(request):
    cart = _get_or_create_cart(request.user)
    if not cart.cart_items.exists():
        messages.warning(request, 'Votre panier est vide.')
        return redirect('founatekapp:cart')

    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        address = request.POST.get('address', '').strip()
        phone = request.POST.get('phone', '').strip()
        contact_email = request.POST.get('contact_email', '').strip()
        note = request.POST.get('note', '').strip()
        payment_method = request.POST.get('payment_method', 'cash')
        payment_reference = request.POST.get('payment_reference', '').strip()
        use_points = int(request.POST.get('use_points', 0))

        if not address:
            messages.error(request, "L'adresse de livraison est obligatoire.")
            return render(request, 'store/checkout.html', {'cart': cart, 'loyalty': loyalty})
        if not phone:
            messages.error(request, "Le numéro de téléphone est obligatoire.")
            return render(request, 'store/checkout.html', {'cart': cart, 'loyalty': loyalty})

        # Calcul remise fidélité
        use_points = min(use_points, loyalty.points)
        discount = (use_points // 10) * 400

        order = Order.objects.create(
            user=request.user,
            shipping_address=address,
            phone=phone,
            contact_email=contact_email or request.user.email,
            note=note,
            discount=discount,
            payment_method=payment_method,
            payment_reference=payment_reference,
        )
        for cart_item in cart.cart_items.all():
            # Appliquer remise proportionnellement sur le premier article
            unit_price = cart_item.product.price
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                unit_price=unit_price,
            )
            p = cart_item.product
            p.stock = max(0, p.stock - cart_item.quantity)
            p.save()

        # Points de fidélité — appelé après création des items pour que order.total soit correct
        earned = loyalty.add_points(order)

        # Appliquer la remise points si demandé
        if discount > 0 and use_points > 0:
            loyalty.use_points(use_points, order)
            messages.info(request, f'{use_points} points utilisés â†’ -{discount:,} GNF de remise.'.replace(',', ' '))

        send_order_email(order, earned, loyalty)
        send_admin_order_notification(order)
        cart.cart_items.all().delete()
        messages.success(request, f'Commande #{order.pk} passée avec succès !')
        return redirect('founatekapp:order_confirmation', pk=order.pk)

    context = {'cart': cart, 'loyalty': loyalty}
    context.update(_apply_currency_to_request(request))
    return render(request, 'store/checkout.html', context)


@login_required
def order_confirmation(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
    earned_tx = order.loyaltytransaction_set.filter(kind='earn').first()
    earned_points = earned_tx.points if earned_tx else 0
    context = {
        'order': order,
        'loyalty': loyalty,
        'earned_points': earned_points,
    }
    context.update(_apply_currency_to_request(request))
    return render(request, 'store/order_confirmation.html', context)


@login_required
def loyalty_dashboard(request):
    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
    transactions = loyalty.transactions.all()[:20]
    context = {'loyalty': loyalty, 'transactions': transactions}
    context.update(_apply_currency_to_request(request))
    return render(request, 'store/loyalty.html', context)


@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user)
    context = {'orders': orders}
    context.update(_apply_currency_to_request(request))
    return render(request, 'store/order_list.html', context)


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    context = {'order': order}
    context.update(_apply_currency_to_request(request))
    return render(request, 'store/order_detail.html', context)


def build_order_receipt_pdf(order, currency_code='GNF'):
    """Genere le PDF du recu de commande et retourne un buffer BytesIO pret a l'emploi."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    import io

    exchange_rate = None
    if currency_code != 'GNF':
        from .models import ExchangeRate
        exchange_rate = ExchangeRate.objects.filter(currency_code=currency_code).first()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=2*cm, rightMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    W = A4[0] - 4*cm  # largeur utile

    # â”€â”€ Styles personnalisés â”€â”€
    s_title    = ParagraphStyle('title',    fontSize=22, fontName='Helvetica-Bold',  textColor=colors.HexColor('#1a1a2e'), alignment=TA_CENTER, spaceAfter=4)
    s_subtitle = ParagraphStyle('subtitle', fontSize=11, fontName='Helvetica',       textColor=colors.HexColor('#555555'), alignment=TA_CENTER, spaceAfter=2)
    s_section  = ParagraphStyle('section',  fontSize=11, fontName='Helvetica-Bold',  textColor=colors.HexColor('#1a1a2e'), spaceBefore=12, spaceAfter=4)
    s_normal   = ParagraphStyle('normal',   fontSize=10, fontName='Helvetica',       textColor=colors.HexColor('#333333'), spaceAfter=2)
    s_small    = ParagraphStyle('small',    fontSize=8,  fontName='Helvetica',       textColor=colors.HexColor('#777777'), alignment=TA_CENTER)
    s_right    = ParagraphStyle('right',    fontSize=10, fontName='Helvetica',       alignment=TA_RIGHT)
    s_total    = ParagraphStyle('total',    fontSize=13, fontName='Helvetica-Bold',  textColor=colors.HexColor('#0f9b58'), alignment=TA_RIGHT)

    accent  = colors.HexColor('#e94560')
    dark    = colors.HexColor('#1a1a2e')
    light   = colors.HexColor('#f5f5f5')
    green   = colors.HexColor('#0f9b58')

    STATUS_FR = {
        'pending':   'En attente',
        'confirmed': 'Confirmée',
        'shipped':   'Expédiée',
        'delivered': 'Livrée',
        'cancelled': 'Annulée',
    }

    from reportlab.platypus import Image as RLImage
    import os as _os
    story = []

    # â”€â”€ En-tête avec logo â”€â”€
    logo_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'static', 'img', 'logo_fou.jpeg')
    logo_cell = RLImage(logo_path, width=2.2*cm, height=2.2*cm) if _os.path.exists(logo_path) else Paragraph('FOUNATEK', styles['Normal'])

    header_data = [[
        logo_cell,
        Paragraph('<b><font size=16 color="#e94560">FOUNATEK</font> <font size=16 color="#1a1a2e">SHOP</font></b><br/>'
                  '<font size=8 color="#888">IoT · IA · Éducation · Réseau Social</font>', styles['Normal']),
        Paragraph(f'<b>REÇU DE COMMANDE</b><br/><font size=9 color="#777">N° {order.pk:06d}</font>',
                  ParagraphStyle('h', fontSize=13, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
    ]]
    header_table = Table(header_data, colWidths=[2.4*cm, W*0.45, W - 2.4*cm - W*0.45])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (1,0), (1,0), 8),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width=W, thickness=2, color=accent, spaceAfter=10))

    # â”€â”€ Infos commande + client â”€â”€
    now = timezone.localtime(order.created_at)
    info_data = [
        [
            Paragraph('<b>CLIENT</b>', s_section),
            Paragraph('<b>COMMANDE</b>', s_section),
        ],
        [
            Paragraph(f'{order.user.get_full_name() or order.user.username}<br/>{order.user.email}', s_normal),
            Paragraph(
                f'Date : {now.strftime("%d/%m/%Y Ã  %H:%M")}<br/>'
                f'Statut : <b>{STATUS_FR.get(order.status, order.status)}</b>',
                s_normal
            ),
        ],
    ]
    if order.shipping_address:
        info_data.append([
            Paragraph(f'<b>ADRESSE DE LIVRAISON</b><br/>{order.shipping_address}', s_normal),
            Paragraph('', s_normal),
        ])

    info_table = Table(info_data, colWidths=[W*0.5, W*0.5])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), light),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#dddddd')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4*cm))

    # â”€â”€ Tableau des articles â”€â”€
    story.append(Paragraph('DÉTAIL DES ARTICLES', s_section))

    col_widths = [W*0.45, W*0.15, W*0.20, W*0.20]
    table_data = [['Produit', 'Qté', 'Prix unitaire', 'Sous-total']]

    for item in order.items.all():
        table_data.append([
            Paragraph(item.product.name, s_normal),
            str(item.quantity),
            f'{int(item.unit_price):,} GNF'.replace(',', ' '),
            f'{int(item.subtotal):,} GNF'.replace(',', ' '),
        ])

    items_table = Table(table_data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        # En-tête
        ('BACKGROUND',    (0,0), (-1,0), dark),
        ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,0), 10),
        ('ALIGN',         (1,0), (-1,-1), 'CENTER'),
        ('ALIGN',         (3,1), (3,-1), 'RIGHT'),
        ('ALIGN',         (2,1), (2,-1), 'CENTER'),
        # Lignes
        ('FONTSIZE',      (0,1), (-1,-1), 10),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor('#f9f9f9')]),
        ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#cccccc')),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (0,-1), 8),
    ]))
    story.append(items_table)

    # â”€â”€ Totaux â”€â”€
    story.append(Spacer(1, 0.3*cm))
    s_red = ParagraphStyle('red', fontSize=10, fontName='Helvetica', textColor=colors.HexColor('#dc3545'), alignment=TA_RIGHT)
    total_rows = [
        ['', Paragraph(f'Nombre d\'articles : {order.total_items}', s_right)],
        ['', Paragraph(f'Sous-total : {int(order.subtotal):,} GNF'.replace(',', ' '), s_right)],
    ]
    if order.discount:
        total_rows.append(['', Paragraph(f'Réduction points fidélité : -{int(order.discount):,} GNF'.replace(',', ' '), s_red)])
    total_rows.append(['', Paragraph(f'<b>TOTAL PAYÉ : {int(order.total):,} GNF</b>'.replace(',', ' '), s_total)])
    if exchange_rate:
        converted = order.total * exchange_rate.rate_from_gnf
        s_converted = ParagraphStyle('converted', fontSize=9, fontName='Helvetica-Oblique', textColor=colors.HexColor('#777777'), alignment=TA_RIGHT)
        total_rows.append(['', Paragraph(f'&asymp; {converted:.2f} {currency_code}', s_converted)])

    total_table = Table(total_rows, colWidths=[W*0.6, W*0.4])
    style_cmds = [
        ('LINEABOVE', (1,0), (1,0), 1, colors.HexColor('#cccccc')),
        ('LINEABOVE', (1, len(total_rows)-1), (1, len(total_rows)-1), 2, green),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]
    total_table.setStyle(TableStyle(style_cmds))
    story.append(total_table)

    # â”€â”€ Note â”€â”€
    if order.note:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(f'<b>Note :</b> {order.note}', s_normal))

    # â”€â”€ Pied de page â”€â”€
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width=W, thickness=2, color=accent, spaceAfter=10))

    contact_lines = '<b>Contact client</b><br/>'
    if order.phone:
        contact_lines += f'<font size=9>&#9990;  {order.phone}</font><br/>'
    if order.contact_email:
        contact_lines += f'<font size=9>&#9993;  {order.contact_email}</font>'

    footer_data = [[
        Paragraph(
            '<b><font color="#e94560">FOUNATEK</font> SHOP</b><br/>'
            '<font size=8 color="#555">Composants électroniques, capteurs &amp; actionneurs</font><br/>'
        '<font size=8 color="#555">FOUNATEK SHOP — Lille, France</font>',
            ParagraphStyle('fl', fontSize=9, fontName='Helvetica', textColor=colors.HexColor('#333'))
        ),
        Paragraph(
            contact_lines,
            ParagraphStyle('fr', fontSize=9, fontName='Helvetica', alignment=TA_RIGHT, textColor=colors.HexColor('#333'))
        ),
    ]]
    footer_table = Table(footer_data, colWidths=[W*0.55, W*0.45])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(footer_table)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f'Document généré le {timezone.localtime(timezone.now()).strftime("%d/%m/%Y Ã  %H:%M")}',
        s_small
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


@login_required
def order_receipt_pdf(request, pk):
    if request.user.is_staff:
        order = get_object_or_404(Order, pk=pk)
    else:
        order = get_object_or_404(Order, pk=pk, user=request.user)

    currency_code = request.session.get('currency_code', 'GNF')
    buffer = build_order_receipt_pdf(order, currency_code)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recu-commande-{order.pk:06d}.pdf"'
    return response


def set_currency(request):
    currency_code = (request.POST.get('currency_code') or 'GNF').upper()
    if currency_code != 'GNF':
        exchange_rate = ExchangeRate.objects.filter(currency_code=currency_code).first()
        if not exchange_rate:
            currency_code = 'GNF'
    request.session['currency_code'] = currency_code
    messages.info(request, f'Devise affichée : {currency_code}')
    return redirect(request.META.get('HTTP_REFERER') or 'founatekapp:home')


@login_required
def submit_review(request, product_id):
    if request.method != 'POST':
        return redirect('founatekapp:product_list')
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    rating = int(request.POST.get('rating', 5))
    comment = request.POST.get('comment', '').strip()
    Review.objects.update_or_create(
        product=product,
        user=request.user,
        defaults={'rating': rating, 'comment': comment},
    )
    messages.success(request, 'Votre avis a été enregistré.')
    return redirect(product.get_absolute_url())


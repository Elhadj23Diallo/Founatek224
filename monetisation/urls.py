from django.urls import path
from . import views
from . import stripe_payments, refunds, academy_checkout, parcours_checkout, saas_billing

app_name = 'monetisation'
urlpatterns = [
    path('academy/create-checkout/', academy_checkout.create_academy_checkout, name='academy_create_checkout'),
    path('academy/status/', academy_checkout.academy_checkout_status, name='academy_checkout_status'),
    path('parcours/<int:parcours_id>/checkout/', parcours_checkout.parcours_checkout_page, name='parcours_checkout_page'),
    path('parcours/<int:parcours_id>/create-checkout/', parcours_checkout.create_parcours_checkout, name='parcours_create_checkout'),
    path('parcours/<int:parcours_id>/status/', parcours_checkout.parcours_checkout_status, name='parcours_checkout_status'),
    path('parcours/<int:parcours_id>/paypal/create-order/', parcours_checkout.create_parcours_paypal_order_view, name='parcours_create_paypal_order'),
    path('parcours/<int:parcours_id>/paypal/capture-order/', parcours_checkout.capture_parcours_paypal_order_view, name='parcours_capture_paypal_order'),
    path('', views.dashboard, name='monetisation_dashboard'),
    path('acheter-credit/', views.init_mobile_money, name='monetisation_acheter_credit'),
    path('transactions/', views.transactions, name='monetisation_transactions'),
    path('abonnement/', views.subscription_view, name='monetisation_abonnement'),
    path('abonnement/carte/', saas_billing.create_saas_checkout, name='saas_create_checkout'),
    path('abonnement/carte/gerer/', saas_billing.billing_portal, name='saas_billing_portal'),
    path('wallet/', views.wallet_dashboard, name='wallet_dashboard'),
    path('wallet/init/', views.init_mobile_money, name='init_mobile_money'),
    # wallet/callback/ (mobile_money_callback) retiré : faille de sécurité, voir
    # le commentaire dans views.py — aucun opérateur ne l'appelle réellement.
    path("buy-credit/", views.init_mobile_money, name="buy_credit"),
    path("paypal/create-order/", views.create_paypal_order, name="create_paypal_order"),
    path("paypal/capture-order/", views.capture_paypal_order, name="capture_paypal_order"),
    path('referrals/', views.referral_dashboard, name='referral_dashboard'),
    path('wallet/paypal/checkout/', views.wallet_paypal_checkout, name='wallet_paypal_checkout'),
    path("payment/success/", views.payment_success, name="payment_success"),
    path('convert-commission/', views.convert_commission_to_wallet, name='convert_commission_to_wallet'),

    path('stripe/create-checkout/', stripe_payments.stripe_create_checkout, name='stripe_create_checkout'),
    path('stripe/success/', stripe_payments.stripe_success, name='stripe_success'),
    # Hors de /api/ : APIKeyMiddleware n'exige pas de Token ici — l'authenticité
    # de l'appel est garantie par la signature Stripe-Signature, pas un header.
    path('stripe/webhook/', stripe_payments.stripe_webhook, name='stripe_webhook'),
    path('paypal/webhook/', refunds.paypal_webhook, name='paypal_webhook'),
]

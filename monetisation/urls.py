from django.urls import path
from . import views

app_name = 'monetisation'
urlpatterns = [
    path('', views.dashboard, name='monetisation_dashboard'),
    path('acheter-credit/', views.buy_credit, name='monetisation_acheter_credit'),
    path('transactions/', views.transactions, name='monetisation_transactions'),
    path('abonnement/', views.subscription_view, name='monetisation_abonnement'),
    path('wallet/', views.wallet_dashboard, name='wallet_dashboard'),
    path('wallet/init/', views.init_mobile_money, name='init_mobile_money'),
    path('wallet/callback/', views.mobile_money_callback, name='mobile_money_callback'),
    path("buy-credit/", views.buy_credit, name="buy_credit"),
    path("paypal/create-order/", views.create_paypal_order, name="create_paypal_order"),
    path("paypal/capture-order/", views.capture_paypal_order, name="capture_paypal_order"),
    path('referrals/', views.referral_dashboard, name='referral_dashboard'),
    path('wallet/paypal/checkout/', views.wallet_paypal_checkout, name='wallet_paypal_checkout'),
    path("payment/success/", views.payment_success, name="payment_success"),
    path('convert-commission/', views.convert_commission_to_wallet, name='convert_commission_to_wallet'),

]

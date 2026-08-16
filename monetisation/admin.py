from django.contrib import admin
from .models import Wallet, Transaction, Subscription, PaymentRequest, UsageLog, Referral, ReferralTransaction, MobileMoneyAccount

# Wallet
@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance')
    search_fields = ('user__username',)

# Transaction
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'amount', 'timestamp', 'description')
    list_filter = ('type',)
    search_fields = ('user__username', 'description')

# Subscription
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date')
    list_filter = ('plan',)
    search_fields = ('user__username',)

# PaymentRequest
@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'phone_number', 'amount', 'status', 'transaction_id', 'created_at', 'reviewed_by')
    list_filter = ('provider', 'status')
    search_fields = ('user__username', 'transaction_id', 'phone_number')

# MobileMoneyAccount
@admin.register(MobileMoneyAccount)
class MobileMoneyAccountAdmin(admin.ModelAdmin):
    list_display = ('provider', 'phone_number', 'owner_name', 'is_active')
    list_filter = ('provider', 'is_active')

# UsageLog
@admin.register(UsageLog)
class UsageLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'api_calls', 'device_count')
    list_filter = ('date',)
    search_fields = ('user__username',)

# Referral
@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referred', 'code', 'created_at')
    search_fields = ('referrer__username', 'referred__username', 'code')

# ReferralTransaction
@admin.register(ReferralTransaction)
class ReferralTransactionAdmin(admin.ModelAdmin):
    list_display = ('referral', 'amount', 'description', 'created_at')
    search_fields = ('referral__referrer__username', 'referral__referred__username', 'description')

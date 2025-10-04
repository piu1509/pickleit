from django.contrib import admin
from apps.user.models import *
from django.utils.html import format_html, mark_safe
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _


class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'phone', 'role', 'is_active', 'is_verified', 'is_staff', 'created_at')
    list_filter = ('is_active', 'is_verified', 'is_staff', 'role', 'is_admin', 'is_player', 'is_coach', 'is_organizer')
    search_fields = ('username', 'email', 'phone')
    ordering = ('-created_at',)
    filter_horizontal = ()
    
    fieldsets = (
        (_("Personal Info"), {"fields": ("uuid", "secret_key", "username", "email", "phone", "first_name", "last_name", "bio", "image")}),
        (_("Address"), {"fields": ("street", "city", "state", "postal_code", "country", "permanent_location", "current_location","latitude", "longitude")}),
        (_("Authentication"), {"fields": ("password", "password_raw", "generated_otp")}),
        (_("Roles & Status"), {"fields": ("role", "is_admin", "is_team_manager", "is_coach", "is_player", "is_organizer",
                                          "is_organizer_expires_at", "is_ambassador", "is_ambassador_expires_at",
                                          "is_merchant", "is_sponsor", "is_sponsor_expires_at", "is_verified")}),
        (_("Permissions"), {"fields": ("is_staff", "is_active", "is_rank", "rank")}),
        (_("Social Links"), {"fields": ("fb_link", "twitter_link", "youtube_link", "tictok_link", "instagram_link")}),
        (_("Other Details"), {"fields": ("availability", "stripe_customer_id", "is_screen", "is_updated")}),
        (_("Important Dates"), {"fields": ("created_at", "updated_at")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "phone", "password1", "password2"),
        }),
    )

    readonly_fields = ("created_at", "updated_at")

admin.site.register(User, UserAdmin)
admin.site.register(Role)
admin.site.register(IsSponsorDetails)
admin.site.register(AppUpdate)
admin.site.register(BasicQuestionsUser)
admin.site.register(UserAnswer)
admin.site.register(MatchingDetails)
admin.site.register(FCMTokenStore)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'instance_id', 'timestamp')
    ordering = ('-timestamp',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs
    
    list_per_page = 20

admin.site.register(LogEntry, LogEntryAdmin)

admin.site.register(AppVersionUpdate)

admin.site.register(StoreCallId)
# admin.site.register(SubscriptionPlan)
# admin.site.register(AllPaymentsTable)
# admin.site.register(Features)

###wallet admin
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'created_at', 'updated_at')
    readonly_fields = ('user', 'created_at', 'updated_at', 'transactions_details', 'withdrawal_requests_details')
    search_fields = ('user__first_name', 'user__last_name', 'user__username')

    def transactions_details(self, obj):
        transactions = WalletTransaction.objects.filter(Q(sender=obj.user) | Q(reciver=obj.user))
        if transactions.exists():
            html = "<ul>"
            for tx in transactions:
                tx_date = tx.created_at.date() if tx.created_at else "N/A"
                tx_time = tx.created_at.time() if tx.created_at else "N/A"
                sender_name = tx.sender.username if tx.sender else "N/A"
                receiver_name = tx.reciver.username if tx.reciver else "N/A"
                html += f"<li>{tx.transaction_id} - {tx.transaction_type} - ${tx.amount} - {sender_name} ➝ {receiver_name} - {tx_date} {tx_time}</li>"
            html += "</ul>"
            return mark_safe(html)
        return "No transactions"

    transactions_details.short_description = "Transactions"

    def withdrawal_requests_details(self, obj):
        withdrawals = WithdrawalRequest.objects.filter(user=obj.user)
        if withdrawals.exists():
            html = "<ul>"
            for wd in withdrawals:
                wd_date = wd.created_at.date() if wd.created_at else "N/A"
                wd_time = wd.created_at.time() if wd.created_at else "N/A"
                html += f"<li>${wd.amount} - {wd.status} - {wd_date} {wd_time}</li>"
            html += "</ul>"
            return mark_safe(html)
        return "No withdrawal requests"

    withdrawal_requests_details.short_description = "Withdrawal Requests"

admin.site.register(Wallet, WalletAdmin)

class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id", "sender", "reciver", "transaction_type", "transaction_for", "amount", "created_at"
    )
    search_fields = ("transaction_id", "sender__username", "reciver__username")
    # list_filter = ("transaction_type", "transaction_for", "created_at")
    ordering = ("-created_at",)

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        if search_term:
            users_queryset = queryset.model.objects.filter(
                Q(transaction_id__icontains=search_term) |
                Q(sender__username__icontains=search_term) |
                Q(reciver__username__icontains=search_term)
            )
            queryset = queryset | users_queryset
        
        return queryset, use_distinct

admin.site.register(WalletTransaction, WalletTransactionAdmin)
admin.site.register(WithdrawalRequest)
admin.site.register(TransactionFor)
admin.site.register(AdminWallet)
admin.site.register(AdminWalletTransaction)
# admin.site.register(WithdrawalRequest)



@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "platform", "price", "duration_days")
    search_fields = ("name", "product_id")
    list_filter = ("platform",)
    ordering = ("price",)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "transaction_id", "platform", "status", "created_at")
    search_fields = ("user__username", "transaction_id")
    list_filter = ("platform", "status")
    ordering = ("-created_at",)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "start_date", "end_date", "is_active")
    search_fields = ("user__username", "plan__name")
    list_filter = ("is_active",)
    ordering = ("-end_date",)

admin.site.register(PromoCode)


@admin.register(AllPaymentsTable)
class AllPaymentsTableAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'payment_for', 'payment_date', 'payment_mode', 'status')
    search_fields = ('user__username', 'status', 'payment_for')
    list_filter = ('status', 'payment_mode', 'payment_date')
from django.contrib import admin
from apps.user.models import *

class RoleAdmin(admin.ModelAdmin):
    list_display = ('role', 'created_at', 'updated_at')
    search_fields = ('role',)


class UserAdmin(admin.ModelAdmin):
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'role', 'is_active', 
        'is_staff', 'is_merchant', 'is_verified'
    )
    list_filter = ('is_staff', 'is_active', 'is_merchant', 'role', 'gender')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    autocomplete_fields = ('role',)
    readonly_fields = ('created_at', 'updated_at')


class ProductSellerRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'status')
    list_filter = ('status',)
    autocomplete_fields = ('user',)


class IsSponsorDetailsAdmin(admin.ModelAdmin):
    list_display = ('sponsor', 'sponsor_added_by', 'league_uuid', 'description')
    autocomplete_fields = ('sponsor', 'sponsor_added_by')


class AppUpdateAdmin(admin.ModelAdmin):
    list_display = ('update',)
    filter_horizontal = ('updated_users',)


class BasicQuestionsUserAdmin(admin.ModelAdmin):
    list_display = ('question', 'question_for', 'is_last')
    list_filter = ('question_for', 'is_last')
    search_fields = ('question',)
    autocomplete_fields = ('parent',)


class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'answer')
    autocomplete_fields = ('user', 'question')


class PDFFileAdmin(admin.ModelAdmin):
    list_display = ('user', 'filename', 'tournament')
    autocomplete_fields = ('user',)


class MatchingPlayersAdmin(admin.ModelAdmin):
    list_display = ('player', 'available_from', 'available_to', 'preference', 'location')
    list_filter = ('preference',)
    search_fields = ('player__username', 'location')
    autocomplete_fields = ('player',)


class FCMTokenStoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'fcm_token')
    autocomplete_fields = ('user',)


class AppVersionUpdateAdmin(admin.ModelAdmin):
    list_display = ('version', 'release_date', 'created_at', 'created_by')
    search_fields = ('version', 'description')
    filter_horizontal = ('updated_users',)


admin.site.register(User, UserAdmin)
admin.site.register(Role, RoleAdmin)
admin.site.register(ProductSellerRequest, ProductSellerRequestAdmin)
admin.site.register(IsSponsorDetails, IsSponsorDetailsAdmin)
admin.site.register(AppUpdate, AppUpdateAdmin)
admin.site.register(BasicQuestionsUser, BasicQuestionsUserAdmin)
admin.site.register(UserAnswer, UserAnswerAdmin)
admin.site.register(PDFFile, PDFFileAdmin)
admin.site.register(MatchingPlayers, MatchingPlayersAdmin)
admin.site.register(FCMTokenStore, FCMTokenStoreAdmin)
admin.site.register(AppVersionUpdate, AppVersionUpdateAdmin)

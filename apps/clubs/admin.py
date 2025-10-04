from django.contrib import admin
from .models import *

class ClubImageInline(admin.TabularInline):
    model = ClubImage
    extra = 0


class ClubPackageInline(admin.TabularInline):
    model = ClubPackage
    extra = 0


class ClubRatingInline(admin.TabularInline):
    model = ClubRating
    extra = 0




@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'location', 'contact', 'email', 'overall_rating')
    search_fields = ('name', 'location', 'contact', 'email')
    list_filter = ('open_time', 'close_time')
    inlines = [ClubImageInline, ClubPackageInline, ClubRatingInline]
    readonly_fields = ('overall_rating',)  # Prevent manual editing
    ordering = ('name',)

admin.site.register(ClubPackage)
admin.site.register(ClubRating)
@admin.register(BookClub)
class BookClubAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'package', 'date', 'price', 'status', 'qr_data', 'apply_date')
    list_filter = ('status', 'package__club__name', 'date', 'apply_date')
    search_fields = ('user__username', 'package__club__name', 'qr_data')
    readonly_fields = ('qr_data', 'apply_date')  # Make QR data readonly
    ordering = ('-apply_date',)

    fieldsets = (
        (None, {
            'fields': (
                'user',
                'package',
                'date',
                'price',
                'status',
                'qr_data',  # Show QR data here
                'apply_date',
            )
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'package', 'package__club')
admin.site.register(JoinClub)
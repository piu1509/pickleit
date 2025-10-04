from django.contrib import admin
from apps.store.models import *


# Register your models here.

class MerchandiseProductSpecificationInline(admin.TabularInline):
    model = MerchandiseProductSpecification
    extra = 0

class MerchandiseProductImagesInline(admin.TabularInline):
    model = MerchandiseProductImages
    extra = 0

class RatingImagesInline(admin.TabularInline):
    model = RatingImages
    extra = 0

class ProductRatingInline(admin.TabularInline):
    model = ProductRating
    extra = 0

class ProductInline(admin.TabularInline):
    model = MerchandiseStoreProduct
    extra = 0

class ProductSpecificationHighlightsInline(admin.TabularInline):
    model = ProductSpecificationHighlights
    extra = 0
    fields = ['highlight_key', 'highlight_des']      

class MerchandiseProductSpecificationAdmin(admin.ModelAdmin):
    autocomplete_fields = ['product']
    list_display = ('product', 'size', 'old_price', 'current_price', 'discount', 'total_product', 'available_product')
    list_filter = ('size', 'discount')
    search_fields = ('product__name', 'size')
    inlines = [ProductSpecificationHighlightsInline] 

class MerchandiseStoreProductAdmin(admin.ModelAdmin):
    autocomplete_fields =  ['category']
    inlines = [MerchandiseProductSpecificationInline, MerchandiseProductImagesInline, ProductRatingInline]
    list_display = ['name', 'category', 'rating', 'rating_count', 'created_at', 'created_by']
    search_fields = ['name', 'category__name', 'description', 'created_by__username']
    list_filter = ['category', 'created_at', 'created_by']

class MerchandiseStoreCategoryAdmin(admin.ModelAdmin):
    inlines = [ProductInline]
    list_display = ['name', 'created_at', 'created_by']
    search_fields = ['name', 'created_by__username']
    list_filter = ['created_at', 'created_by']

class ProductRatingAdmin(admin.ModelAdmin):
    autocomplete_fields = ['product']
    inlines = [RatingImagesInline]
    list_display = ['user', 'product', 'rating', 'created_at']
    search_fields = ['user__username', 'product__name']
    list_filter = ['rating', 'created_at', 'user']

admin.site.register(MerchandiseProductSpecification, MerchandiseProductSpecificationAdmin)
admin.site.register(MerchandiseStoreCategory, MerchandiseStoreCategoryAdmin)
admin.site.register(MerchandiseStoreProduct, MerchandiseStoreProductAdmin)
admin.site.register(ProductRating, ProductRatingAdmin)
admin.site.register(CustomerMerchandiseStoreProductBuy)
admin.site.register(CouponCode)
admin.site.register(ProductDeliveryAddress)
admin.site.register(MerchandiseStore)
# admin.site.register(PaymentTable)
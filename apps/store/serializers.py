from apps.store.models import *
from rest_framework import serializers


class MerchandiseStoreCategorySerializer(serializers.ModelSerializer):
    created_by__first_name = serializers.SerializerMethodField()
    created_by__last_name = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    class Meta:
        model = MerchandiseStoreCategory
        fields = ['id','uuid','secret_key','name','image','created_by__first_name','created_by__last_name']

    def get_created_by__first_name(self, obj):
        return obj.created_by.first_name
    
    def get_created_by__last_name(self, obj):
        return obj.created_by.last_name
    
    def get_image(self, obj):
        if obj.image:
            return obj.image.name  
        return None

class MerchandiseProductImagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchandiseProductImages
        fields = ['id','image']

class ProductSpecificationHighlightsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpecificationHighlights
        fields = ['id','highlight_key','highlight_des']

class MerchandiseProductSpecificationSerializer(serializers.ModelSerializer):
    specificHighlight = ProductSpecificationHighlightsSerializer(many=True, read_only=True)

    class Meta:
        model = MerchandiseProductSpecification
        fields = ['id','size','old_price','current_price','discount','total_product','available_product','specificHighlight']

class RatingImagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = RatingImages
        fields = ['id', 'image']

class ProductRatingSerializer(serializers.ModelSerializer):
    ratingImages = RatingImagesSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField()

    class Meta:
        model = ProductRating
        fields = ['id', 'user','rating','comment','created_at','ratingImages']

class MerchandiseStoreProductSerializer(serializers.ModelSerializer):
    productImages = MerchandiseProductImagesSerializer(many=True, read_only=True)
    specificProduct = MerchandiseProductSpecificationSerializer(many=True, read_only=True)
    ratedProduct = ProductRatingSerializer(many=True, read_only=True)
    leagues_for = serializers.SerializerMethodField()
    category__name = serializers.SerializerMethodField()
    created_by__first_name = serializers.SerializerMethodField()
    created_by__last_name = serializers.SerializerMethodField()
    
    class Meta:
        model = MerchandiseStoreProduct
        fields = ['id','uuid','secret_key','name','description','specifications','rating','rating_count','advertisement_image','is_love','category__name','created_by__first_name','created_by__last_name','productImages','specificProduct','ratedProduct','leagues_for']

    def get_leagues_for(self, obj):
        return obj.get_leagues_names()
    
    def get_category__name(self, obj):
        return obj.category.name
    
    def get_created_by__first_name(self, obj):
        return obj.created_by.first_name

    def get_created_by__last_name(self, obj):
        return obj.created_by.last_name

class ProductListSerializer(serializers.ModelSerializer):
    category__name = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    created_by__first_name = serializers.SerializerMethodField()
    created_by__last_name = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
        model = MerchandiseStoreProduct
        fields = ['id','uuid','secret_key','category__name','name','price','description','specifications','rating','rating_count','advertisement_image','image','is_love','created_by__first_name','created_by__last_name']
    
    def to_representation(self, instance):
        # Update rating before serialization
        instance.update_rating()
        return super().to_representation(instance)

    def get_category__name(self, obj):
        return obj.category.name
    
    def get_image(self, obj):
        images = MerchandiseProductImages.objects.filter(product=obj).first().image
        image = images.name if images else None
        return image
    
    def get_created_by__first_name(self, obj):
        return obj.created_by.first_name
    
    def get_created_by__last_name(self, obj):
        return obj.created_by.last_name
    
    def get_price(self, obj):
        prices = MerchandiseProductSpecification.objects.filter(product=obj).values_list('current_price', flat=True)
        print(prices)
        price = min(prices)
        print(price)
        return price
    
class CustomerMerchandiseStoreProductBuySerializer(serializers.ModelSerializer):
    product_image = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerMerchandiseStoreProductBuy
        fields = ('id', 'uuid', 'secret_key', 'cart_idd', 'product','product_image', 'product_name', 'price_per_product', 'quantity', 'total_price',
            'status','size','is_paid','is_delivered','delivery_address_main','delivery_address','delivered_at','created_at','created_by'
        ) 
    product_name = serializers.CharField(source='product.name', read_only=True)

    def get_product_image(self, obj):
        image = MerchandiseProductImages.objects.filter(product=obj.product).first().image.url
        return image
    

    
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
        fields = ['id','size','color','old_price','current_price','discount','total_product','available_product','specificHighlight']

class RatingImagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = RatingImages
        fields = ['id', 'image']

class ProductRatingSerializer(serializers.ModelSerializer):
    ratingImages = RatingImagesSerializer(many=True, read_only=True)
    user = serializers.SerializerMethodField()

    class Meta:
        model = ProductRating
        fields = ['id', 'user','rating','comment','created_at','ratingImages']

    def get_user(self, obj):
        try:
            name = obj.user.first_name + ' ' + obj.user.last_name
        except:
            name = "Not Defined"
        return name
    
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
        fields = ['id','uuid','secret_key','name','store_name','description','specifications','rating','rating_count','advertisement_image','is_love','has_single_spec','category__name','created_by__first_name','created_by__last_name','productImages','specificProduct','ratedProduct','leagues_for']

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
    old_price = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()

    class Meta:
        model = MerchandiseStoreProduct
        fields = ['id', 'uuid', 'secret_key', 'category__name', 'name', 'store_name', 'price', 'old_price', 'discount', 'description', 'specifications', 'rating', 'rating_count', 'advertisement_image', 'image', 'is_love', 'has_single_spec', 'created_by__first_name', 'created_by__last_name']

    def to_representation(self, instance):
        # Update rating before serialization
        instance.update_rating()
        return super().to_representation(instance)

    def get_category__name(self, obj):
        return obj.category.name

    def get_image(self, obj):
        images_ins = MerchandiseProductImages.objects.filter(product=obj).first()
        if images_ins:
            image = images_ins.image.name
            return image
        else:
            return None

    def get_created_by__first_name(self, obj):
        return obj.created_by.first_name

    def get_created_by__last_name(self, obj):
        return obj.created_by.last_name

    def get_price(self, obj):
        try:
            specs = MerchandiseProductSpecification.objects.filter(product=obj).values('current_price', 'discount')
            if not specs:
                return 0
            # Treat null discounts as 0 for comparison
            lowest_discount_spec = min(specs, key=lambda x: x['discount'] if x['discount'] is not None else 0)
            return lowest_discount_spec['current_price'] or 0
        except:
            return 0

    def get_old_price(self, obj):
        try:
            specs = MerchandiseProductSpecification.objects.filter(product=obj).values('old_price', 'discount')
            if not specs:
                return 0
            # Treat null discounts as 0 for comparison
            lowest_discount_spec = min(specs, key=lambda x: x['discount'] if x['discount'] is not None else 0)
            return lowest_discount_spec['old_price'] or 0
        except:
            return 0

    def get_discount(self, obj):
        try:
            specs = MerchandiseProductSpecification.objects.filter(product=obj).values('discount')
            if not specs:
                return 0
            # Treat null discounts as 0 for comparison
            lowest_discount_spec = min(specs, key=lambda x: x['discount'] if x['discount'] is not None else 0)
            discount = lowest_discount_spec['discount'] if lowest_discount_spec['discount'] is not None else 0
            return round(discount, 2)
        except:
            return 0

class ProductDeliveryAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductDeliveryAddress
        fields = (
            'id', 'uuid', 'street', 'city', 'state', 'postal_code', 'country',
            'latitude', 'longitude', 'complete_address', 'default_address'
        )


class CustomerMerchandiseStoreProductBuySerializer(serializers.ModelSerializer):
    product_image = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    delivery_address = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerMerchandiseStoreProductBuy
        fields = ('id', 'uuid', 'secret_key', 'cart_idd', 'product','product_image', 'product_name', 'price_per_product', 'quantity', 'total_price',
            'status','size','color','is_paid','is_delivered','delivery_address','latitude','longitude','delivered_at','created_at','created_by'
        ) 
    product_name = serializers.CharField(source='product.name', read_only=True)

    def get_product_image(self, obj):
        image = MerchandiseProductImages.objects.filter(product=obj.product).first().image.url
        return image
    
    def get_created_by(self, obj):
        first_name = obj.created_by.first_name or ''
        last_name = obj.created_by.last_name or ''
        
        if first_name and last_name:
            return f'{first_name} {last_name}'
        return first_name
    
    def get_delivery_address(self, obj):
        if obj.delivery_address_main:
            return obj.delivery_address_main.complete_address
        return None

    def get_latitude(self, obj):
        if obj.delivery_address_main:
            return obj.delivery_address_main.latitude
        return None

    def get_longitude(self, obj):
        if obj.delivery_address_main:
            return obj.delivery_address_main.longitude
        return None

class MerchandiseStoreProductDetailSerializer(serializers.ModelSerializer):
    specifications = MerchandiseProductSpecificationSerializer(
        source="specificProduct", many=True, read_only=True
    )
    images = MerchandiseProductImagesSerializer(
        source="productImages", many=True, read_only=True
    )
    leagues = serializers.SlugRelatedField(
        source="leagues_for", many=True, read_only=True, slug_field="name"
    )
    loved_by = serializers.PrimaryKeyRelatedField(
        source="is_love", many=True, read_only=True
    )
    leagues_names = serializers.SerializerMethodField()

    class Meta:
        model = MerchandiseStoreProduct
        fields = (
            "id",
            "category",
            "name",
            "store_name",
            "description",
            "specifications",
            "images",
            "leagues",
            "leagues_names",
            "loved_by",
            "rating",
            "rating_count",
            "advertisement_image",
            "has_single_spec",
            "created_at",
            "created_by",
        )

    def get_leagues_names(self, obj):
        return obj.get_leagues_names()
    
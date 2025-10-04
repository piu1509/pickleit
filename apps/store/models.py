from django.db import models
from apps.user.models import *
from apps.team.models import *
import uuid
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Count, F, Min
from apps.pickleitcollection.models import *
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower

# Create your models here.

class MerchandiseStore(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores')
    description = models.TextField(null=True, blank=True)
    company_website = models.CharField(max_length=255, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self) :
        return f"{self.name}"

class MerchandiseStoreCategory(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, null=True, blank=True, unique=True)
    name = models.CharField(max_length=250, null=True, blank=True)
    image = models.ImageField(upload_to='store_category/', null=True, blank=True)       
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='categoryCreatedBy')
    
    def __str__(self) :
        return f"{self.name}"
    
class MerchandiseStoreProductQuerySet(models.QuerySet):
    def sort_by_price(self):
        return self.annotate(
            lowest_price=Min('specificProduct__current_price')
        ).order_by('lowest_price', 'id')  # Ascending order by the lowest price

    def sort_by_price_desc(self):
        return self.annotate(
            lowest_price=Min('specificProduct__current_price')
        ).order_by('-lowest_price', 'id')    # Sort primarily by price descending, then by id

    def sort_by_popularity(self):
        return self.annotate(
            popularity=Count('is_love')
        ).order_by('-popularity', 'id')  # Sort primarily by popularity, then by id

    def sort_by_newest(self):
        return self.order_by('-created_at', 'id')

class MerchandiseStoreProductManager(models.Manager):
    def get_queryset(self):
        return MerchandiseStoreProductQuerySet(self.model, using=self._db)

    def sort_by_price(self):
        return self.get_queryset().sort_by_price()
    
    def sort_by_price_desc(self):
        return self.get_queryset().sort_by_price_desc()

    def sort_by_popularity(self):
        return self.get_queryset().sort_by_popularity()

    def sort_by_newest(self):
        return self.get_queryset().sort_by_newest()



class MerchandiseStoreProduct(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, null=True, blank=True, unique=True)
    category = models.ForeignKey(MerchandiseStoreCategory,on_delete=models.SET_NULL, null=True, blank=True, related_name='productCategory')
    name = models.CharField(max_length=250, null=True, blank=True)
    store_name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    specifications = models.TextField(null=True, blank=True)    
    leagues_for = models.ManyToManyField(Leagues, blank=True)
    is_love = models.ManyToManyField(User, blank=True)
    rating = models.FloatField(null=True, blank=True,default=0)
    rating_count = models.PositiveIntegerField(default=0)
    advertisement_image = models.ImageField(upload_to='product/advertisement/images', null=True, blank=True)
    has_single_spec = models.BooleanField(
        default=False,
        help_text="Check if this product requires only one specification"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='productCreatedBy')
    
    objects = MerchandiseStoreProductManager()

    def __str__(self) :
        return f"{self.name}, Category : {self.category.name}"

    def get_leagues_names(self):
        leagues_for_id = self.leagues_for.all()
        leagues_name = [i.name for i in leagues_for_id]
        return leagues_name

    def update_rating(self):
        total_rating = sum(rating.rating for rating in self.ratedProduct.all())
        self.rating_count = self.ratedProduct.count()
        self.rating = round(total_rating / self.rating_count, 1) if self.rating_count > 0 else 0
        self.save()


class MerchandiseProductSpecification(models.Model):
    product = models.ForeignKey(MerchandiseStoreProduct, on_delete=models.CASCADE, related_name='specificProduct')
    size = models.CharField(max_length=5, null=True, blank=True)
    color = models.CharField(max_length=5, null=True, blank=True)
    old_price = models.PositiveIntegerField(null=True, blank=True)
    current_price = models.PositiveIntegerField(null=True, blank=True)
    discount = models.FloatField(null=True, blank=True)
    total_product = models.PositiveIntegerField(null=True, blank=True)
    available_product = models.PositiveIntegerField(null=True, blank=True)

    
    def save(self, *args, **kwargs):    
        if self.total_product is not None and self.available_product is None:
            self.available_product = self.total_product

        if self.old_price and self.current_price:
            self.discount = round(((self.old_price - self.current_price) / self.old_price) * 100, 2)
        elif not self.old_price:
            self.discount = 0
        else:
            self.discount = None

        super().save(*args, **kwargs)

    def __str__(self):
        return self.product.name


class ProductSpecificationHighlights(models.Model):
    specification = models.ForeignKey(MerchandiseProductSpecification, on_delete=models.CASCADE, related_name='specificHighlight')
    highlight_key = models.CharField(max_length=255, null=True, blank=True)
    highlight_des = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'Highlights for {self.specification.product.name}'


class MerchandiseProductImages(models.Model):
    product = models.ForeignKey(MerchandiseStoreProduct, on_delete=models.CASCADE, related_name='productImages')
    image = models.FileField(upload_to='store_product/images/')

    def __str__(self):
        return f"Images of {self.product.name}"


class ProductRating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='productRatedBy')
    product = models.ForeignKey(MerchandiseStoreProduct, on_delete=models.CASCADE, related_name='ratedProduct')
    rating = models.PositiveIntegerField(help_text="Rate between 1 and 5.") 
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')  

    def __str__(self):
        return f'{self.user.first_name} rated {self.product} as {self.rating}'
    
@receiver(post_save, sender=ProductRating)
def update_product_rating_on_save(sender, instance, **kwargs):
    instance.product.update_rating()

@receiver(post_delete, sender=ProductRating)
def update_product_rating_on_delete(sender, instance, **kwargs):
    instance.product.update_rating()


class RatingImages(models.Model):
    product_rating = models.ForeignKey(ProductRating, on_delete=models.CASCADE, related_name='ratingImages')
    image = models.FileField(upload_to='store_product/product_rating_images', null=True, blank=True)

    def __str__(self):
        return f'Images for rating of {self.product_rating.product.name} by {self.product_rating.user.first_name}'


BUYING_STATUS = (
    ("CART", "CART"),
    ("BuyNow", "BUY NOW"),
    ("ORDER PLACED", "ORDER PLACED"),
    ("SHIPPED", "SHIPPED"),
    ("CANCEL", "CANCEL"),
    ("DELIVERED", "DELIVERED"),
)

class ProductDeliveryAddress(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, null=True, blank=True, unique=True)
    street = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)
    default_address = models.BooleanField(default=False)
    complete_address = models.TextField(null=True, blank=True,help_text="street, city, state, country, PIN-postal_code")
    latitude = models.CharField(max_length=15, null=True, blank=True)
    longitude = models.CharField(max_length=15, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.created_by.username} {self.complete_address}"
    
    def save(self, *args, **kwargs):
        # Check if any of the address components are not None
        if self.street and self.city and self.state and self.postal_code and self.country:
            # Concatenate the address components to form the complete_address
            self.complete_address = f"{self.street}, {self.city}, {self.state}, {self.country}, PIN-{self.postal_code}"
            full_address = self.complete_address.replace(" ", "+")
            api_key = settings.MAP_API_KEY  # Store your API key in Django settings

            url = f"https://maps.googleapis.com/maps/api/geocode/json?address={full_address}&key={api_key}"
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    result = response.json()
                    if result["status"] == "OK" and result["results"]:
                        location = result["results"][0]["geometry"]["location"]
                        self.latitude = str(location["lat"])
                        self.longitude = str(location["lng"])
            except Exception as e:
                # Optional: Log the exception or handle error
                print(f"Geocoding error: {e}")

        super().save(*args, **kwargs)


class CustomerMerchandiseStoreProductBuy(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, null=True, blank=True, unique=True)
    cart_idd = models.CharField(max_length=250, null=True, blank=True)
    product = models.ForeignKey(MerchandiseStoreProduct,on_delete=models.SET_NULL, null=True, blank=True, related_name='product')
    price_per_product = models.PositiveBigIntegerField()
    quantity = models.PositiveIntegerField()
    total_price = models.PositiveBigIntegerField()
    status = models.CharField(choices=BUYING_STATUS, max_length=250, null=True, blank=True)
    size = models.CharField(max_length=250, null=True, blank=True)
    color = models.CharField(max_length=5, null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    is_delivered = models.BooleanField(default=False)
    delivery_address_main = models.ForeignKey(ProductDeliveryAddress,on_delete=models.SET_NULL, null=True, blank=True)
    delivery_address = models.TextField(null=True, blank=True,help_text="street, city, state, country, PIN-postal_code")
    delivered_at = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.CASCADE, related_name='productBuyby')
    
    def __str__(self):
        created_by_username = self.created_by.username if self.created_by else 'Unknown User'
        product_name = self.product.name if self.product else 'Unknown Product'
        return f"{created_by_username} - {product_name}"

    def save(self, *args, **kwargs):
        # Track if the instance is being created or updated
        is_new_instance = self.pk is None

        # Fetch the current instance from the database if it's not a new instance
        if not is_new_instance:
            previous_instance = CustomerMerchandiseStoreProductBuy.objects.get(pk=self.pk)
        else:
            previous_instance = None

        # Fetch the related product specification
        update_product = MerchandiseProductSpecification.objects.filter(product=self.product, size=self.size).first()

        # Adjust the available product quantity based on the status change
        if previous_instance:
            # If the status has changed from "BuyNow" or "ORDER PLACED" to something else
            if previous_instance.status in ["BuyNow", "ORDER PLACED"] and self.status not in ["BuyNow", "ORDER PLACED"]:
                update_product.available_product += previous_instance.quantity
            
            # If the status has changed to "BuyNow" or "ORDER PLACED"
            if self.status in ["BuyNow", "ORDER PLACED"] and previous_instance.status not in ["BuyNow", "ORDER PLACED"]:
                update_product.available_product -= self.quantity

            # If the status is still the same but the quantity has changed
            if self.status in ["BuyNow", "ORDER PLACED"] and previous_instance.quantity != self.quantity:
                update_product.available_product += previous_instance.quantity - self.quantity

        # If it's a new instance and the status is "BuyNow" or "ORDER PLACED"
        if is_new_instance and self.status in ["BuyNow", "ORDER PLACED"]:
            update_product.available_product -= self.quantity

        # If the status is "CANCEL" and it's not a new instance
        if self.status == "CANCEL" and not is_new_instance and previous_instance and previous_instance.status != "CANCEL":
            update_product = MerchandiseProductSpecification.objects.filter(product=self.product, size=self.size).first()
            
            update_product.available_product += self.quantity

        # Save the updated product specification
        update_product.save()

        # Call the original save method to save the instance
        super(CustomerMerchandiseStoreProductBuy, self).save(*args, **kwargs)

class CouponCode(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    percentage = models.IntegerField(help_text="This Input Count As A Discount Percentage", default=0)
    coupon_code = models.CharField(max_length=20, unique=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    product = models.ManyToManyField(MerchandiseStoreProduct, blank=True)

    def __str__(self):
        return f"{self.coupon_code} || {self.percentage} ({self.start_date.date()} to {self.end_date.date()})"

class ProductSearchLog(models.Model):
    product = models.ForeignKey(MerchandiseStoreProduct, on_delete=models.CASCADE, related_name='searchLogs')
    search_count = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f'{self.product.name} - Searches: {self.search_count}'
    

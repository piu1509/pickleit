from typing import Iterable
from django.db import models
from apps.user.models import *
from apps.team.models import *
import uuid
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Count, F
from datetime import datetime

# Use tables 

SCREEN_TYPE = (
    # ("Team Create", "Team Create"),
    # ("Leauge Register", "Leauge Register"),
    ("Player List", "Player List"),
    ("User Team List", "User Team List"),
    ("Leauge List", "Leauge List"),
    ("Home", "Home"),
    ("stats", "Stats"),
    ("sponsor_view", "Sponsor View"),
    ("sponsor_add", "Sponsor Add"),
)

DURATION_TYPE = (
    ('Days', 'Days'),
    ('Weeks', 'Weeks'),
    ('Months', 'Months'),
    ('Year', 'Year')
)

ADD_TYPE = (
    ("Image", "Image"),
    ("Script", "Script"),
)


class AdvertisementDurationRate(models.Model):
    duration = models.PositiveIntegerField()
    duration_type = models.CharField(max_length=10, choices=DURATION_TYPE, default="Days")
    rate = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.duration} {self.duration_type} : ${self.rate}"

class Advertisement(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    name = models.CharField(max_length=250, null=True, blank=True)
    duration = models.ForeignKey(AdvertisementDurationRate, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to='advertisement_image/', null=True, blank=True)
    script_text = models.TextField(null=True, blank=True)
    url = models.TextField(null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company_website = models.TextField(null=True, blank=True)
    approved_by_admin = models.BooleanField(default=True)
    admin_approve_status = models.CharField(max_length=25, choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='advertisementCreatedBy')
    description = models.TextField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    view_count = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        if self.start_date and self.duration:
            if isinstance(self.start_date, str):
                self.start_date = datetime.strptime(self.start_date, "%Y-%m-%d")

            if self.duration.duration_type == "Days":
                self.end_date = self.start_date + timedelta(days=self.duration.duration)
            elif self.duration.duration_type == "Weeks":
                self.end_date = self.start_date + timedelta(weeks=self.duration.duration)
            elif self.duration.duration_type == "Months":
                self.end_date = self.start_date + timedelta(days=self.duration.duration * 30) 
            elif self.duration.duration_type == "Year":
                self.end_date = self.start_date + timedelta(days=self.duration.duration * 365) 

        super().save(*args, **kwargs)

    def __getattribute__(self, name):
        # whenever 'view_count' is accessed, bump it
        if name == "view_count":
            obj = super().__getattribute__(name)
            Advertisement.objects.filter(pk=self.pk).update(view_count=models.F("view_count") + 1)
            return Advertisement.objects.get(pk=self.pk).view_count
        return super().__getattribute__(name)
    
    def __str__(self) :
        return f"{self.name} [{self.start_date} to {self.end_date}]"   
    

#### not used tables
FACILITY_TYPE = (
    ("Pickleball Facility", "Pickleball Facility"),
    ("Sports Facility", "Sports Facility"),
    ("Country Club", "Country Club"),
    ("Neighborhood Courts", "Neighborhood Courts"),
    ("Public Area", "Public Area"),
    ("Other", "Other"),
)

COURT_TYPE = (
    ("Outdoor Court Only","Outdoor Court Only"),
    ("Indoor Court Only", "Indoor Court Only"),
    ("Both Outdoor and Indoor","Both Outdoor and Indoor"),
)

MEMBERSHIP_TYPE = (
    ("Open to Public","Open to Public"),
    ("Members only", "Members only"),
    ("Pay to Play", "Pay to Play"),
)

CHARGE_FOR = (
    ("product_buy", "product_buy"),
    ("for_advertisement", "for_advertisement"),
)

CHARGE_TYPE = (
    ("Organizer", "To Become an Organizer"),
    ("Sponsors", "To Become a Sponsors"),
    ("Ambassador", "To Become a Ambassador"),
)

class ChargeAmount(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    charge_for = models.CharField(choices=CHARGE_TYPE, max_length=250, null=True, blank=True, unique=True)
    charge_amount = models.PositiveIntegerField(help_text="subscription amount ($)", null=True, blank=True)
    effective_time = models.DurationField(help_text="subscription duration of month number,i.e. [days hours:minutes:seconds], for 1 month [30 00:00:00]", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='chargeAmountCreatedBy')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='chargeAmountUpdatedBy')

    def __str__(self) :
        return f"{self.charge_for} - Amount : {self.charge_amount}$ - Time for {self.effective_time} months"
        
class Notifications(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    screen = models.CharField(max_length=250,choices=SCREEN_TYPE, null=True, blank=True)
    url = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self) :
        return f"{self.user.username} - Message : {self.message}$ - Status : {self.is_read}"


class AmbassadorsPost(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, null=True, blank=True, unique=True)
    file = models.URLField(null=True, blank=True)
    thumbnail = models.URLField(null=True, blank=True)
    post_text = models.TextField(null=True, blank=True)
    approved_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='postby')
    likes = models.ManyToManyField(User)
    number_comment = models.IntegerField(default=0)
    number_like = models.IntegerField(default=0)
    tags = models.JSONField(default=dict)

    def __str__(self):
        return f'{self.post_text} - {self.created_by}'

class Tags(models.Model):
    name = models.CharField(max_length=255, unique=True)
    number_of_use = models.IntegerField(default=0)
    
class PostComment(models.Model):
    post = models.ForeignKey(AmbassadorsPost, on_delete=models.CASCADE, related_name="reel_comment")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="commenting_user")
    comment_text = models.TextField()
    parent_comment = models.ForeignKey("PostComment", on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            AmbassadorsPost.objects.filter(pk=self.post.pk).update(number_comment=F('number_comment') + 1)

    def delete(self, *args, **kwargs):
        AmbassadorsPost.objects.filter(pk=self.post.pk).update(number_comment=F('number_comment') - 1)
        super().delete(*args, **kwargs)

class AmbassadorsDetails(models.Model):
    ambassador = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='ambassador')
    follower = models.ManyToManyField(User,related_name='ambassador_follower')
    following = models.ManyToManyField(User,related_name='ambassador_following')

    def __str__(self):
        return f'{self.ambassador}'

class AdvertiserFacility(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, null=True, blank=True, unique=True)
    facility_name = models.CharField(max_length=200, null=True, blank=True)
    facility_type = models.CharField(choices=FACILITY_TYPE, max_length=200, null=True, blank=True)
    court_type = models.CharField(choices=COURT_TYPE, max_length=200, null=True, blank=True)
    membership_type = models.CharField(choices=MEMBERSHIP_TYPE, max_length=200, null=True, blank=True)
    complete_address = models.TextField(null=True, blank=True,help_text="street, city, state, country, PIN-postal_code")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    number_of_courts = models.PositiveIntegerField()
    response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='facilityCreatedBy')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='facilityUpdatedBy')
    acknowledgement = models.BooleanField(default=False)
    # For not physically deleting
    is_view = models.BooleanField(default=False) 

    def __str__(self):
        return f"{self.facility_name} - {self.facility_type}"
    
class FacilityImage(models.Model):
    facility = models.ForeignKey(AdvertiserFacility, on_delete=models.CASCADE, related_name='facility_image')
    image = models.ImageField(upload_to="Facility_image/")

    def __str__(self):
        return f"{self.facility.facility_name}"

from apps.store.models import CustomerMerchandiseStoreProductBuy
class PaymentDetails(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(unique=True, max_length=250)
    payment_for = models.CharField(max_length=250, choices=CHARGE_FOR, null=True, blank=True)
    var_chargeamount = models.FloatField(null=True, blank=True)
    payment_for = models.CharField(max_length=250, blank=True, null=True)
    payment_for_id = models.TextField(blank=True, null=True)
    payment_by = models.CharField(max_length=250, blank=True, null=True)
    payment_amount = models.FloatField(null=True, blank=True)
    payment_status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    chargeamount = models.ForeignKey(ChargeAmount, on_delete=models.CASCADE, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    stripe_response = models.JSONField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    payment_for_ad = models.ForeignKey(Advertisement, on_delete=models.CASCADE, blank=True, null=True)
    payment_for_product = models.ManyToManyField(CustomerMerchandiseStoreProductBuy, blank=True)

    def __str__(self) :
        return f"{self.created_by.username} - Amount : {self.var_chargeamount}$ - Status : {self.payment_status}"

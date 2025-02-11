import uuid
from typing import Iterable

from django.db import models
from django.dispatch import receiver
from django.db.models import Count, F
from django.db.models.signals import post_save, post_delete, pre_save

from apps.user.models import *
from apps.team.models import *


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

ADD_TYPE = (
    ("Image", "Image"),
    ("Script", "Script"),
)
class Advertisement(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    name = models.CharField(max_length=250, null=True, blank=True)
    image = models.ImageField(upload_to='advertisement_image/', null=True, blank=True)
    script_text = models.TextField(null=True, blank=True)
    url = models.TextField(null=True, blank=True)
    approved_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='advertisementCreatedBy')
    description = models.TextField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    def __str__(self) :
        return f"{self.name} [{self.start_date} to {self.end_date}]"


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
        return f"{self.charge_for} - Amount : $ {self.charge_amount} - Time for {self.effective_time} months"


class Notifications(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    screen = models.CharField(max_length=250,choices=SCREEN_TYPE, null=True, blank=True)
    url = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self) :
        return f"{self.user.username} - Message : {self.message} - Status : {self.is_read}"


################################################### NEW #################################################

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

    def __str__(self):
        return f'{self.file} - {self.created_by.username}'

 
class AmbassadorsDetails(models.Model):
    ambassador = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, blank=True, related_name='ambassador')
    follower = models.ManyToManyField(User,related_name='ambassador_follower')
    following = models.ManyToManyField(User,related_name='ambassador_following')

    def __str__(self):
        return f'{self.ambassador.first_name} {self.ambassador.last_name} - {self.ambassador.username}'


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


CHARGE_FOR = (
    ("product_buy", "product_buy"),
    ("for_advertisement", "for_advertisement"),
)
class PaymentDetails(models.Model):
    uuid = models.UUIDField()
    secret_key = models.CharField(unique=True, max_length=250)
    payment_for = models.CharField(max_length=250, choices=CHARGE_FOR, null=True, blank=True)
    var_chargeamount = models.IntegerField()
    payment_for = models.CharField(max_length=250, blank=True, null=True)
    payment_for_id = models.TextField(blank=True, null=True)
    payment_by = models.CharField(max_length=250, blank=True, null=True)
    payment_amount = models.IntegerField()
    payment_status = models.BooleanField()
    created_at = models.DateTimeField()
    chargeamount = models.ForeignKey(ChargeAmount, on_delete=models.CASCADE, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    stripe_response = models.JSONField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    payment_for_ad = models.ForeignKey(Advertisement, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self) :
        return f"{self.created_by.username} - Amount : $ {self.var_chargeamount} - Status : {self.payment_status}"

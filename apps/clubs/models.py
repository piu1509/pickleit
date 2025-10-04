import uuid
import secrets
from django.db import models
from apps.user.models import User
from django.db.models import Avg
from geopy.distance import geodesic
from django.core.exceptions import ValidationError

curency = [
    ('USD','USD')
]

class Club(models.Model):
    diactivate = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    location = models.TextField()
    latitude = models.CharField(max_length=12)
    longitude = models.CharField(max_length=12)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    contact = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    is_vip = models.BooleanField(default=False)
    description = models.TextField()
    join_amount = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    unit = models.CharField(max_length=12, choices=curency, default="USD")
    overall_rating = models.FloatField(null=True, blank=True, default=0.0)

    def clean(self):
        if Club.objects.filter(user=self.user, name__iexact=self.name).exclude(id=self.id).exists():
            raise ValidationError("You already have a club with this name.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class ClubImage(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="club_image")


class ClubPackage(models.Model):
    deactivate = models.BooleanField(default=False)
    name = models.CharField(max_length=50)
    package_id = models.CharField(max_length=12, unique=True, editable=False)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    valid_start_date = models.DateField(blank=True, null=True)
    valid_end_date = models.DateField(blank=True, null=True)
    member = models.IntegerField(default=1)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=12, choices=curency, default="USD")
    member_ship_discount = models.DecimalField(max_digits=5, decimal_places=2, help_text="Enter the discount percentage (e.g., 10.50 for 10.5%).")

    def __str__(self):
        return f"{self.club.name} {self.price}"

    def save(self, *args, **kwargs):
        if not self.package_id:
            self.package_id = uuid.uuid4().hex[:12]  # Generate a 12-character unique ID
        super().save(*args, **kwargs)


class BookClub(models.Model):
    package = models.ForeignKey(ClubPackage, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField(null=True, blank=True)
    qr_data = models.CharField(max_length=20, unique=True, blank=True, null=True, editable=False)
    status = models.CharField(max_length=100, default="approved..")
    apply_date = models.DateTimeField(auto_now_add=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        date_str = self.date.strftime('%Y-%m-%d %H:%M:%S') if self.date else "N/A"
        return f"Booking by {self.user.username} for {self.package.club.name} on {date_str} - Status: {self.status}"

    def save(self, *args, **kwargs):
        self.qr_data = secrets.token_urlsafe(15)[:20]
        super().save(*args, **kwargs)


class ClubRating(models.Model):
    name = models.CharField(max_length=255)
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="club_rating", blank=True, null=True)

    def __str__(self):
        return f"Rating: {self.rating} for {self.club.name} by {self.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_club_rating()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.update_club_rating()

    def update_club_rating(self):
        """Updates the club's overall rating after saving or deleting a rating."""
        avg_rating = ClubRating.objects.filter(club=self.club).aggregate(Avg('rating'))['rating__avg']
        Club.objects.filter(id=self.club.id).update(overall_rating=avg_rating if avg_rating is not None else 0.0)


class JoinClub(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.BooleanField(default=False)
    block = models.BooleanField(default=False)
    join_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.club.name} {self.user.username}"
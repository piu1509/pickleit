from django.db import models
from apps.user.models import User
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Avg

class Courts(models.Model):
    name = models.CharField(max_length=255, unique=True)
    location = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    price = models.IntegerField()
    price_unit = models.CharField(max_length=255)
    offer_price = models.IntegerField(null=True, blank=True)
    about = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="courts_created")
    owner_name = models.CharField(max_length=100, null=True, blank=True)
    avg_rating = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.location}) - Rating: {self.overall_rating or 'N/A'}"

class CourtImage(models.Model):
    court = models.ForeignKey(Courts, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="courts_image")

    def __str__(self):
        return f"{self.court.name}"

class BookCourt(models.Model):
    court = models.ForeignKey(Courts, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=100, default="Pending..")
    apply_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking by {self.user.username} for {self.court.name} on {self.date.strftime('%Y-%m-%d %H:%M:%S') if self.date else 'N/A'} - Status: {self.status}"


class CourtRating(models.Model):
    court = models.ForeignKey(Courts, on_delete=models.CASCADE)
    text = models.TextField()
    rate = models.IntegerField()

    def __str__(self):
        return f"Rating for {self.court.name} - {self.rate}"



# Signals to update the average rating
@receiver(post_save, sender=CourtRating)
@receiver(post_delete, sender=CourtRating)
def update_court_avg_rating(sender, instance, **kwargs):
    court = instance.court
    avg_rating = CourtRating.objects.filter(court=court).aggregate(Avg('rate'))['rate__avg']
    court.avg_rating = round(avg_rating, 1) if avg_rating else None
    court.save()





##### clubs(vip/digital) ######



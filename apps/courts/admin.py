from django.contrib import admin
from apps.courts.models import *
# Register your models here.
admin.site.register(Courts)
admin.site.register(CourtImage)
admin.site.register(CourtRating)

admin.site.register(BookCourt)
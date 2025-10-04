from rest_framework import serializers
from .models import *

class AdvertisementSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    created_by_first_name = serializers.CharField(source='created_by.first_name', read_only=True)
    created_by_last_name = serializers.CharField(source='created_by.last_name', read_only=True)
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = Advertisement
        fields = [
            "id", "uuid", "secret_key", "name", "image", "script_text", "url",
            "approved_by_admin", "admin_approve_status", "description", "start_date",
            "end_date", "created_by_first_name", "created_by_last_name", "days_left",
            "view_count"
        ]

    def get_image(self, obj):
        # obj.image.url is already the relative path, e.g. "/media/…"
        return obj.image.url if obj.image else None

    def get_days_left(self, obj):
        if obj.end_date:
            today = datetime.now().date()
            end_date = obj.end_date.date()
            days_remaining = (end_date - today).days
            return max(days_remaining, 0)  # Ensures it doesn't return negative values
        return None

class FacilityImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityImage
        fields = "__all__"

class AdvertiserFacilitySerializer(serializers.ModelSerializer):
    facility_image = FacilityImageSerializer(many=True)

    class Meta:
        model = AdvertiserFacility
        fields = [
            'id',
            'uuid',
            'secret_key',
            'facility_name',
            'facility_type',
            'court_type',
            'membership_type',
            'complete_address',
            'latitude',
            'longitude',
            'number_of_courts',
            'response',
            'created_at',
            'created_by',
            'updated_at',
            'updated_by',
            'acknowledgement',
            'is_view',
            'facility_image'
        ]
from rest_framework import serializers
from apps.pickleitcollection.models import *


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
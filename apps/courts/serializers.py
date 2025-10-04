from rest_framework import serializers
from .models import *

class CourtImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourtImage
        fields = ['image']

class CourtRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourtRating
        fields = ['text', 'rate']

class CourtListSerializer(serializers.ModelSerializer):
    images = CourtImageSerializer(source='courtimage_set', many=True, read_only=True)

    class Meta:
        model = Courts
        fields = [
            'id', 'name', 'location', 'latitude', 'longitude', 'open_time', 'close_time',
            'price', 'price_unit', 'offer_price', 'about', 'owner_name', 'avg_rating', 'images'
        ]


class CourtDetailSerializer(serializers.ModelSerializer):
    images = CourtImageSerializer(source='courtimage_set', many=True, read_only=True)
    ratings = CourtRatingSerializer(source='courtrating_set', many=True, read_only=True)

    class Meta:
        model = Courts
        fields = [
            'id', 'name', 'location', 'latitude', 'longitude', 'open_time', 'close_time',
            'price', 'price_unit', 'offer_price', 'about', 'owner_name', 'avg_rating', 'images', 'ratings'
        ]

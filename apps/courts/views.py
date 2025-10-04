from django.shortcuts import render
from apps.courts.models import *
from apps.courts.serializers import *
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from rest_framework.pagination import PageNumberPagination
from django.core.cache import cache
from django.conf import settings
from apps.store.serializers import *
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from math import radians, sin, cos, sqrt, atan2

class CourtsPagination(PageNumberPagination):
    """Custom pagination for courts list"""
    page_size = 2  # Number of courts per page
    page_size_query_param = 'page_size'
    max_page_size = 26

@api_view(['POST'])
def add_court(request):
    """
    This function adds a court along with multiple images.
    """
    try:
        data = {}
        user_uuid = request.data.get('user_uuid')
        name = request.data.get('name')
        location = request.data.get('location')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        open_time = request.data.get('open_time')
        close_time = request.data.get('close_time')
        price = request.data.get('price')
        price_unit = request.data.get('price_unit')
        offer_price = request.data.get('offer_price')
        description = request.data.get('description')
        images = request.FILES.getlist('images')  # Get multiple images

        check_user = User.objects.filter(uuid=user_uuid)
        if check_user.exists():
            get_user = check_user.first()
            try:
                # Create the court instance
                court_inst = Courts.objects.create(
                    name=name, location=location, latitude=latitude, longitude=longitude,
                    open_time=open_time, close_time=close_time, price=price, 
                    price_unit=price_unit, offer_price=offer_price, 
                    about=description, created_by=get_user
                )

                # Save multiple images
                for image in images:
                    CourtImage.objects.create(court=court_inst, image=image)

                data['status'], data['message'] = status.HTTP_201_CREATED, "Court added successfully"
            except Exception as e:
                data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"Error: {e}"
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"Error: {e}"
    
    return Response(data)


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the Haversine distance between two points on the Earth.
    """
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    radius_earth_km = 6371  # Radius of Earth in kilometers
    return radius_earth_km * c


@api_view(('GET',))
def found_my_courts_list(request):
    """
    Fetch courts within a 100 km radius based on latitude and longitude with pagination.
    """
    try:
        user_uuid = request.query_params.get('user_uuid')
        name = request.query_params.get('name', None)
        latitude = request.query_params.get('latitude', None)
        longitude = request.query_params.get('longitude', None)
        radius_km = 100  # Radius in kilometers

        # Validate user
        user = User.objects.filter(uuid=user_uuid)
        if not user.exists():
            return Response({"count": 0, "next": None, "previous": None, "results": [], "message": "User does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        get_user = user.first()
        # Fetch all courts if no location or name is provided
        courts = Courts.objects.filter(created_by = get_user)
        if name:
            courts = courts.filter(name__icontains=name)

        # If latitude & longitude are provided, filter courts by distance
        if latitude and longitude:
            latitude = float(latitude)
            longitude = float(longitude)

            filtered_courts = []
            for court in courts:
                court_lat = float(court.latitude)
                court_lon = float(court.longitude)

                # Calculate distance using Haversine formula
                distance = calculate_distance(latitude, longitude, court_lat, court_lon)
                if distance <= radius_km:
                    filtered_courts.append(court)

            courts = filtered_courts

        # Apply pagination
        paginator = CourtsPagination()
        paginated_courts = paginator.paginate_queryset(courts, request)
        serializer = CourtListSerializer(paginated_courts, many=True)

        return paginator.get_paginated_response(serializer.data)

    except Exception as e:
        return Response({"count": 0, "next": None, "previous": None, "results": [], "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(('GET',))
def found_courts_list(request):
    """
    Fetch courts within a 100 km radius based on latitude and longitude with pagination.
    """
    try:
        user_uuid = request.query_params.get('user_uuid')
        name = request.query_params.get('name', None)
        latitude = request.query_params.get('latitude', None)
        longitude = request.query_params.get('longitude', None)
        radius_km = 100  # Radius in kilometers

        # Validate user
        user = User.objects.filter(uuid=user_uuid)
        if not user.exists():
            return Response({"count": 0, "next": None, "previous": None, "results": [], "message": "User does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        get_user = user.first()
        # Fetch all courts if no location or name is provided
        courts = Courts.objects.all()
        if name:
            courts = courts.filter(name__icontains=name)

        # If latitude & longitude are provided, filter courts by distance
        if latitude and longitude:
            latitude = float(latitude)
            longitude = float(longitude)

            filtered_courts = []
            for court in courts:
                court_lat = float(court.latitude)
                court_lon = float(court.longitude)

                # Calculate distance using Haversine formula
                distance = calculate_distance(latitude, longitude, court_lat, court_lon)
                if distance <= radius_km:
                    filtered_courts.append(court)

            courts = filtered_courts

        # Apply pagination
        paginator = CourtsPagination()
        paginated_courts = paginator.paginate_queryset(courts, request)
        serializer = CourtListSerializer(paginated_courts, many=True)

        return paginator.get_paginated_response(serializer.data)

    except Exception as e:
        return Response({"count": 0, "next": None, "previous": None, "results": [], "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def court_details(request, court_id):
    try:
        court = Courts.objects.get(id=court_id)
        serializer = CourtDetailSerializer(court)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Courts.DoesNotExist:
        return Response({'error': 'Court not found'}, status=status.HTTP_404_NOT_FOUND)




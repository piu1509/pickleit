import base64
import json
from rest_framework import serializers, generics, status
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404, render
from django.core.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
import stripe
from myproject import settings
from .models import *
from apps.user.models import AllPaymentsTable, TransactionFor, User, Wallet, WalletTransaction
from apps.team.views import notify_edited_player
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, date, timedelta
from django.db.models.functions import TruncDate
from django.db.models import Count
from django.utils.timezone import make_aware
from geopy.distance import geodesic
from django.db.models import Q
# Serializers
class ClubImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubImage
        fields = ["id", "image"]

class ClubRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubRating
        fields = ["id", "name", "rating", "comment"]

class ClubSerializer(serializers.ModelSerializer):
    images = ClubImageSerializer(many=True, read_only=True, source="clubimage_set")
    ratings = ClubRatingSerializer(many=True, read_only=True, source="clubrating_set")
    user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    user_last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_image = serializers.CharField(source="user.image", read_only=True)
    is_join = serializers.SerializerMethodField()
    class Meta:
        model = Club
        fields = "__all__"

    def get_is_join(self, obj):
        image = JoinClub.objects.filter(club=obj).first()
        return True if image else False

class ClubListSerializer(serializers.ModelSerializer):
    images = ClubImageSerializer(many=True, read_only=True, source="clubimage_set")
    
    class Meta:
        model = Club
        fields = ("id", "name", "location", "latitude", "longitude", "contact", "email", "overall_rating", "images", "is_vip", "diactivate")

class JoinClubSerializer(serializers.ModelSerializer):
    user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    user_last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_image = serializers.ImageField(source="user.image", read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    location = serializers.CharField(source="user.permanent_location", read_only=True)

    class Meta:
        model = JoinClub
        fields = ["id", "user_first_name", "user_last_name", "location" ,"user_image","club_name","status", "join_date"]

class ClubPackageSerializer(serializers.ModelSerializer):
    days_left = serializers.SerializerMethodField()
    booking_count = serializers.SerializerMethodField()  # New field for booking count

    class Meta:
        model = ClubPackage
        fields = [
            'id', 'package_id', 'name', 'valid_start_date', 'valid_end_date', 
            'member', 'description', 'price', 'unit', 'member_ship_discount', 
            'days_left', 'booking_count'  # Added booking_count to fields
        ]

    def get_days_left(self, obj):
        """Calculate the remaining days until the package expires"""
        if obj.valid_end_date:
            remaining_days = (obj.valid_end_date - date.today()).days
            return max(remaining_days, 0)  # Ensure no negative values
        return None

    def get_booking_count(self, obj):
        """Count the number of bookings for this package"""
        return BookClub.objects.filter(package=obj).count()

class BookClubSerializer(serializers.ModelSerializer):
    user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    user_last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_image = serializers.CharField(source="user.image", read_only=True)
    package_ins = ClubPackageSerializer(source="package", read_only=True)
    club = ClubListSerializer(source="package.club", read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = BookClub
        fields = [
            "id", 
            "user_first_name", 
            "user_last_name", 
            "user_image", 
            "club", 
            "package_ins", 
            "date", 
            "price", 
            "qr_data", 
            "apply_date",
            "is_expired"
        ]

    def get_is_expired(self, obj):
        # Check if booking date is before today
        return obj.date.date() < timezone.now().date()


# Pagination
class BasePagination(PageNumberPagination):
    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        # Force HTTPS in pagination links
        for link_type in ['next', 'previous']:
            link = response.data.get(link_type)
            if link:
                response.data[link_type] = link.replace('http://', 'https://')
        return response

class ClubPagination(BasePagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class JoinUserPagination(BasePagination):
    page_size = 10  # Number of items per page
    page_size_query_param = 'page_size'
    max_page_size = 50

class BookingUserPagination(BasePagination):
    page_size = 10  # Number of items per page
    page_size_query_param = 'page_size'
    max_page_size = 50

class JoinClubPagination(BasePagination):
    page_size = 10  # Adjust as needed
    page_size_query_param = 'page_size'
    max_page_size = 100

# Views
@api_view(['POST'])
def add_club(request):
    """API to create a new club."""
    try:
        data = request.data
        images = request.FILES.getlist('images')
        user = get_object_or_404(User, uuid=data.get("user_uuid"))
        club = Club(
            user=user,
            name=data["name"],
            location=data["location"],
            latitude=data.get("latitude", ""),
            longitude=data.get("longitude", ""),
            open_time=data.get("open_time"),
            close_time=data.get("close_time"),
            contact=data["contact"],
            email=data.get("email"),
            description=data["description"],
            join_amount = data["join_amount"],
            is_vip=data["is_vip"],

        )
        club.save()
        for image in images:
            ClubImage.objects.create(club=club, image=image)
        
        return Response({"message": "Club created successfully!"}, status=status.HTTP_201_CREATED)
    except ValidationError as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except KeyError as e:
        return Response({"message": f"Missing field: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
def my_club_list(request):
    user_uuid = request.query_params.get("user_uuid")
    search_text = request.query_params.get("search_text", None)
    user = get_object_or_404(User, uuid=user_uuid)
    
    clubs = Club.objects.filter(user=user, diactivate=False)  # Fixed `diactivate` typo
    if search_text:
        clubs = clubs.filter(Q(name__icontains=search_text) | Q(description__icontains=search_text))
    paginator = ClubPagination()
    result_page = paginator.paginate_queryset(clubs, request)
    
    serializer = ClubListSerializer(result_page, many=True)  # Added `many=True`
    return paginator.get_paginated_response(serializer.data)



@api_view(['GET'])
def view_club(request, club_id):
    """API to view a club's details including ratings."""
    club = get_object_or_404(Club, id=club_id)
    
    # Correct way to pass context
    serializer = ClubSerializer(club, context={"user_uuid": request.GET.get("user_uuid")})
    
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
def edit_club(request):
    """API to edit a club's details and update images."""
    try:
        data = request.data
        user = get_object_or_404(User, uuid=data.get("user_uuid"))
        club = get_object_or_404(Club, id=data.get("club_id"))

        # Check if the user is authorized to edit the club
        if club.user != user:
            return Response(
                {"message": "You are not authorized to edit this club."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update club fields
        club.name = data.get("name", club.name)
        club.location = data.get("location", club.location)
        club.latitude = data.get("latitude", club.latitude)
        club.longitude = data.get("longitude", club.longitude)
        club.open_time = data.get("open_time", club.open_time)
        club.close_time = data.get("close_time", club.close_time)
        club.contact = data.get("contact", club.contact)
        club.email = data.get("email", club.email)
        club.description = data.get("description", club.description)
        club.join_amount = float(data.get("join_amount", club.join_amount))
        club.is_vip = str(data.get("is_vip")).lower() == "true"

        # Optional fields (if they exist in your model)
        if hasattr(club, 'price'):
            club.price = data.get("price", club.price)
        if hasattr(club, 'price_unit'):
            club.price_unit = data.get("price_unit", club.price_unit)
        if hasattr(club, 'offer_price'):
            club.offer_price = data.get("offer_price", club.offer_price)

        # Save club to validate latitude/longitude
        club.save()

        # Handle image uploads
        if 'images' in request.FILES:
            images = request.FILES.getlist('images')  # Get list of uploaded images
            for image in images:
                ClubImage.objects.create(club=club, image=image)

        # Handle image deletions (optional)
        if 'delete_image_ids' in data:
            delete_ids = data.get('delete_image_ids', [])
            if isinstance(delete_ids, str):
                delete_ids = delete_ids.split(',')  # Handle comma-separated IDs
            ClubImage.objects.filter(club=club, id__in=delete_ids).delete()

        return Response(
            {"message": "Club details and images updated successfully!"},
            status=status.HTTP_200_OK
        )

    except ValidationError as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except KeyError as e:
        return Response({"message": f"Missing field: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


@api_view(['POST'])
def add_rating(request):
    """API to create a new club."""
    try:
        data = request.data
        user = get_object_or_404(User, uuid=data.get("user_uuid"))
        club = get_object_or_404(Club, id=data.get("club_id"))
        add_rate = ClubRating(name=user.first_name, rating=data.get("rating"), comment=data.get("comment"),club=club, image=request.FILES.get("image")) 
        add_rate.save()
        return Response({"message": "post your rating successfully!"}, status=status.HTTP_201_CREATED)
    except ValidationError as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except KeyError as e:
        return Response({"message": f"Missing field: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


"""
club join
club join list
club join request list
"""

stripe.api_key = settings.STRIPE_PUBLIC_KEY
@api_view(['POST'])
def join_club(request):
    """API to join a club with balance validation."""
    try:
        data = request.data
        user = get_object_or_404(User, uuid=data.get("user_uuid"))
        club = get_object_or_404(Club, id=data.get("club_id"))
        print(club.join_amount, "okjknj")
        # ✅ Check if user already joined
        if JoinClub.objects.filter(user=user, club=club).exists():
            return Response({"message": "Already joined in club"}, status=status.HTTP_200_OK)

        # ✅ Get User Wallet & Balance
        wallet = Wallet.objects.filter(user=user).first()
        club_wallet = Wallet.objects.filter(user=club.user).first()
        admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
        balance = wallet.balance if wallet else 0

        if club.join_amount in [0, 0.0, None, "0"]:
            # ✅ Create JoinClub Entry
            join = JoinClub(user=user, club=club)
            join.status = True
            join.save()
            return Response({"message": "Club joined successfully!"}, status=status.HTTP_201_CREATED)

        # ✅ Validate Join Price
        join_price = club.join_amount if club.join_amount not in [None, "null", "None"] else 0
        club_wonner_wallet = Wallet.objects.filter(user=club.user).first()
        
        join_details = {}
        join_details["club_id"] = club.id
        join_details["club_name"] = club.name
        join_details["join_user_id"] = user.id
        
        
        if balance >= join_price:
            club_amount = (club.join_amount * Decimal(settings.CLUB_PERCENTAGE)) / 100
            admin_amount = (club.join_amount * Decimal(settings.ADMIN_PERCENTAGE_CLUB)) / 100
            
            wallet_transaction = WalletTransaction.objects.create(
                sender = user,
                reciver = club.user,   
                reciver_cost = round(club_amount, 2),                  
                admin_cost= round(admin_amount, 2),
                getway_charge = 0,                        
                transaction_for="JoinClub",                                   
                transaction_type="debit",
                amount= club.join_amount,
                payment_id=None, 
                description=f"${club.join_amount} is debited from your PickleIt wallet for join {club.name} club."
                )
            # ✅ store join user details
            transaction_for = TransactionFor(transaction=wallet_transaction, details=join_details)
            transaction_for.save()
            wallet.balance -= join_price
            club_wallet.balance += club_amount
            admin_wallet.balance += admin_amount
            admin_wallet.save()
            club_wallet.save()
            wallet.save()
            club_wonner_wallet.balance = club_wonner_wallet.balance + join_price
            club_wonner_wallet.save()
            
            # ✅ Create JoinClub Entry
            join = JoinClub(user=user, club=club)
            join.status = True
            join.save()
            #update admin wallet balance
            admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
            if admin_wallet:
                admin_wallet.balance = Decimal(str(admin_wallet.balance)) + join_price
                admin_wallet.save()
            
            # ✅ Send Notification
            user_id = club.user.id
            message = f"{user.first_name} join your club: {club.name}"
            title = "User Join Club"
            notify_edited_player(user_id, title, message)
            
            return Response({"message": "Club joined successfully!"}, status=status.HTTP_201_CREATED)
        else:
            ## add fund balance
            pay_balance = round(float(join_price - balance), 2)
            ## stripe fees added
            stripe_fee = Decimal(pay_balance * 0.029) + Decimal(0.30)
            total_charge = Decimal(pay_balance) + stripe_fee
            total_charge = round(total_charge, 2)
            ### send the bill in stripe
            chage_amount = round(float(total_charge * 100))
            print(chage_amount)
            make_request_data = {"club_id":club.id,"user_id":user.id,"debited_wallet_balance":str(pay_balance), "join_details":join_details}
            json_bytes = json.dumps(make_request_data).encode('utf-8')
            my_data = base64.b64encode(json_bytes).decode('utf-8')
            product_name = f"Join {club.name} Club"
            product_description = "Payment received by Pickleit"
            stripe.api_key = settings.STRIPE_SECRET_KEY
            if user.stripe_customer_id :
                stripe_customer_id = user.stripe_customer_id
            else:
                customer = stripe.Customer.create(email=user.email).to_dict()
                stripe_customer_id = customer["id"]
                user.stripe_customer_id = stripe_customer_id
                user.save()
            stripe_fee = str(round(stripe_fee, 3))
            protocol = settings.PROTOCALL
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            main_url = f"{current_site}/clubs/store/join/club/stripe/payement/{stripe_fee}/{my_data}/"
            product = stripe.Product.create(name=product_name,description=product_description,).to_dict()
            price = stripe.Price.create(unit_amount=chage_amount,currency='usd',product=product["id"],).to_dict()
            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                line_items=[
                    {
                        # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                        'price': price["id"],
                        'quantity': 1,
                    },
                ],
                mode='payment',
                success_url= main_url + "{CHECKOUT_SESSION_ID}" + "/",
                cancel_url="https://example.com/success" + '/cancel.html',
            )
            return Response({"status": status.HTTP_200_OK,"payement": "stripe", "url": checkout_session.url,"add_amount":total_charge, "message": f"Please add ${total_charge} to your wallet to join the club."}) 
            # return Response({"message": "Not enough balance to join"}, status=status.HTTP_400_BAD_REQUEST)
    except ValidationError as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except KeyError as e:
        return Response({"message": f"Missing field: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

def store_join_club_stripe_payement(request, stripe_fee, my_data, checkout_session_id):
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        pay = stripe.checkout.Session.retrieve(checkout_session_id).to_dict()
        stripe_customer_id = pay.get("customer")
        payment_status = pay.get("payment_status") == "paid"
        amount_total = Decimal(pay.get("amount_total", 0)) / 100  # Convert to Decimal
        payment_method_types = pay.get("payment_method_types", [])

        # Decode and parse JSON data
        json_bytes = base64.b64decode(my_data)
        request_data = json.loads(json_bytes.decode('utf-8'))
        user_id = request_data.get("user_id")
        club_id = request_data.get("club_id")
        join_details = request_data.get("join_details")
        club = get_object_or_404(Club, id=club_id)
        get_user = get_object_or_404(User, id=request_data.get("user_id"))
        payment_for = f"join {club.name} club"
        wallet = Wallet.objects.filter(user_id=user_id).first()
        get_wallet = Wallet.objects.filter(user=club.user).first()
        admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
            
        existing_payment = AllPaymentsTable.objects.filter(user=get_user, checkout_session_id=checkout_session_id).exists()

        if not existing_payment and payment_status:
            AllPaymentsTable.objects.create(
                user=get_user,
                amount=club.join_amount,
                checkout_session_id=checkout_session_id,
                payment_mode=", ".join(payment_method_types),
                payment_for=payment_for,
                status="Completed" if payment_status else "Failed"
            )
            wallet.balance=0
            wallet.save()
            join = JoinClub(user=get_user, club=club)
            join.status = True
            join.save()
            
            
            # club_amount = (club.join_amount * Decimal(settings.CLUB_PERCENTAGE)) / 100
            # admin_amount = (club.join_amount * Decimal(settings.ADMIN_PERCENTAGE_CLUB)) / 100
            
            # if admin_amount is not None:
            #     admin_amount = round(float(admin_amount), 2)
            # if club_amount is not None:
            #     club_amount = round(float(club_amount), 2)
            club_amount = (club.join_amount * Decimal(settings.CLUB_PERCENTAGE)) / 100
            admin_amount = (club.join_amount * Decimal(settings.ADMIN_PERCENTAGE_CLUB)) / 100

            # Ensure rounding is done while keeping values as Decimal
            if admin_amount is not None:
                admin_amount = admin_amount.quantize(Decimal("0.01"))  # Keeps 2 decimal places
            if club_amount is not None:
                club_amount = club_amount.quantize(Decimal("0.01"))
            wallet_transaction = WalletTransaction.objects.create(
                sender=get_user,
                reciver=club.user,
                admin_cost=str(admin_amount),
                reciver_cost=str(club_amount),
                getway_charge=str(stripe_fee),
                transaction_for="JoinClub",
                transaction_type="debit",
                amount=Decimal(round(float(club.join_amount), 2)),
                payment_id=checkout_session_id,
                description=f"${amount_total} is debited from your PickleIt wallet for join club to {club.name}."
            )
            # ✅ store join user details
            transaction_for = TransactionFor(transaction=wallet_transaction, details=join_details)
            transaction_for.save()
            get_wallet.balance += club_amount
            admin_wallet.balance += admin_amount
            get_wallet.save()
            admin_wallet.save()
            

        if payment_status:
            return render(request, "club/success_payment_for_join_club.html")
        else:
            return render(request, "club/failed_payment_join_club.html")

    except Exception as e:
        print(f"Error in payment_for_team_registration: {str(e)}")
        return render(request, "club/failed_payment_join_club.html")



@api_view(['GET'])
def club_join_user_list(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    
    joined_users = JoinClub.objects.filter(club=club, status=True, block=False)

    paginator = JoinUserPagination()
    paginated_users = paginator.paginate_queryset(joined_users, request)

    serializer = JoinClubSerializer(paginated_users, many=True)
    return paginator.get_paginated_response(serializer.data)

"""
club packages
"""
@api_view(['POST'])
def add_package_for_myclub(request):
    """API to create a package for a club with validation."""
    try:
        data = request.data
        user = get_object_or_404(User, uuid=data.get("user_uuid"))
        club = get_object_or_404(Club, id=data.get("club_id"))

        name = data.get("name")
        description = data.get("description")
        valid_start_date = data.get("valid_start_date")
        valid_end_date = data.get("valid_end_date")
        member = data.get("member")
        price = data.get("price")
        membership_discount = data.get("membership_discount", 0)
        valid_start_date_format= None
        valid_end_date_format = None
        # Validate start and end date
        if valid_start_date:
            valid_start_date_format = datetime.strptime(valid_start_date, "%Y-%m-%d")
        if valid_end_date:        
            valid_end_date_format = datetime.strptime(valid_end_date, "%Y-%m-%d")

        if valid_start_date and valid_end_date:
            if valid_start_date_format >= valid_end_date_format:
                return Response({"message": "Start date must be before end date."}, status=status.HTTP_200_OK)

        if user == club.user:
            package = ClubPackage(
                name=name,
                club=club,
                member=member,
                description=description,
                price=price,
                member_ship_discount=membership_discount,
                valid_start_date=valid_start_date_format,
                valid_end_date=valid_end_date_format
            )
            package.save()
            return Response({"message": "Your package was created successfully!"}, status=status.HTTP_201_CREATED)

        return Response({"message": "You are not authorized to add a package for this club."}, status=status.HTTP_200_OK)

    except ValidationError as e:
        return Response({"message": str(e)}, status=status.HTTP_200_OK)
    except KeyError as e:
        return Response({"message": f"Missing field: {str(e)}"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_200_OK)


@api_view(['GET'])
def club_packages_list(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    packages = ClubPackage.objects.filter(club=club, deactivate=False)
    serializer = ClubPackageSerializer(packages, many=True)
    return Response({"message": "Done", "data": serializer.data}, status=status.HTTP_200_OK)

@api_view(['GET'])
def view_club_package(request, package_id):
    package = get_object_or_404(ClubPackage, id=package_id)
    serializer = ClubPackageSerializer(package)
    return Response({"message": "Done", "data": serializer.data}, status=status.HTTP_200_OK)

@api_view(['POST'])
def edit_club_package(request, package_id):
    package = get_object_or_404(ClubPackage, id=package_id)
    
    serializer = ClubPackageSerializer(package, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "Package updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)
    
    return Response({"message": "Failed to update package", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def deactivate_club_package(request, package_id):
    package = get_object_or_404(ClubPackage, id=package_id)
    package.deactivate = True
    package.save()
    return Response({"message": "Package deactivated successfully",}, status=status.HTTP_200_OK)



"""
book club's package
"""
@api_view(['POST'])
def book_club(request):
    """API to join a club with balance validation."""
    try:
        data = request.data
        date_today = timezone.now()
        user = get_object_or_404(User, uuid=data.get("user_uuid"))
        club_package = get_object_or_404(ClubPackage, id=data.get("club_package_id"))
        date_str = data.get("booking_date")
        if not date_str:
            return Response({"message": "not proper date"}, status=status.HTTP_400_BAD_REQUEST)
        date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")  # Adjust format as needed
        date = make_aware(date)
        if date_today >= date:
            return Response({"message": "please select proper date"}, status=status.HTTP_400_BAD_REQUEST)
        # ✅ Check if user already joined
        if JoinClub.objects.filter(user=user, club=club_package.club).exists():
            discount = club_package.member_ship_discount
            if not discount:
                discount = 0
            pay_amount = club_package.price - (club_package.price*discount)/100
        else:
            pay_amount = club_package.price
        # ✅ Get User Wallet & Balance
        wallet = Wallet.objects.filter(user=user).first()
        balance = wallet.balance if wallet else 0
        
        if pay_amount in [0, 0.00, None, "0.0"]:
            join = BookClub(user=user, package=club_package, price=pay_amount, date=date)
            join.status = True
            join.save()
            return Response({"message": "Club Booked successfully!"}, status=status.HTTP_201_CREATED)

        club_wallet = Wallet.objects.filter(user=club_package.club.user).first()
        admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
        
        join_details = {}
        join_details["club_id"] = club_package.club.id
        join_details["club_name"] = club_package.club.name
        join_details["package_id"] = club_package.id
        join_details["package_name"] = club_package.name
        join_details["join_user_id"] = user.id

        if balance >= pay_amount:
            club_amount = (pay_amount * Decimal(settings.CLUB_PERCENTAGE)) / 100
            admin_amount = (pay_amount * Decimal(settings.ADMIN_PERCENTAGE_CLUB)) / 100
            if admin_amount is not None:
                admin_amount = admin_amount.quantize(Decimal("0.01"))  # Keeps 2 decimal places
            if club_amount is not None:
                club_amount = club_amount.quantize(Decimal("0.01"))
            wallet_transaction = WalletTransaction.objects.create(
                sender = user,
                reciver = club_package.club.user, 
                reciver_cost =  str(club_amount),                      
                admin_cost= str(admin_amount),
                getway_charge = 0,                        
                transaction_for="BookClub",                                   
                transaction_type="debit",
                amount=pay_amount,
                payment_id=None, 
                description=f"${pay_amount} is debited from your PickleIt wallet for Booking {club_package.name} package from {club_package.club.name} club."
                )
            transaction_for = TransactionFor(transaction=wallet_transaction, details=join_details)
            transaction_for.save()
            wallet.balance -= pay_amount
            wallet.save()
            club_wallet.balance += club_amount
            club_wallet.save()
            admin_wallet.balance += admin_amount
            admin_wallet.save()
            # ✅ Create JoinClub Entry
            join = BookClub(user=user, package=club_package, price=pay_amount, date=date)
            join.status = True
            join.save()
            # ✅ Send Notification
            user_id = club_package.club.user.id
            message = f"{user.first_name} booked your club: {club_package.club.name} at {date}"
            title = "User Booked Club"
            notify_edited_player(user_id, title, message)
            return Response({"message": "Club Booked successfully!"}, status=status.HTTP_201_CREATED)
        else:
            ## add fund balance
            pay_balance = round(float(pay_amount - balance), 2)
            ## stripe fees added
            stripe_fee = Decimal(pay_balance * 0.029) + Decimal(0.30)
            total_charge = Decimal(pay_balance) + stripe_fee
            total_charge = round(total_charge, 2)
            ### send the bill in stripe
            chage_amount = round(float(total_charge * 100))
            make_request_data = {"package_id":club_package.id,"club_id":club_package.club.id,"user_id":user.id,"debited_wallet_balance":str(pay_balance), "booking_date":str(date_str), "pay_amount":str(pay_amount), "join_details":join_details}
            json_bytes = json.dumps(make_request_data).encode('utf-8')
            my_data = base64.b64encode(json_bytes).decode('utf-8')
            product_name = f"Book {club_package.name} package in {club_package.club.name} Club"
            product_description = "Payment received by Pickleit"
            stripe.api_key = settings.STRIPE_SECRET_KEY
            if user.stripe_customer_id :
                stripe_customer_id = user.stripe_customer_id
            else:
                customer = stripe.Customer.create(email=user.email).to_dict()
                stripe_customer_id = customer["id"]
                user.stripe_customer_id = stripe_customer_id
                user.save()
            stripe_fee = str(round(stripe_fee, 3))
            protocol = settings.PROTOCALL
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            main_url = f"{current_site}/clubs/store/book/club/stripe/payement/{stripe_fee}/{my_data}/"
            product = stripe.Product.create(name=product_name,description=product_description,).to_dict()
            price = stripe.Price.create(unit_amount=chage_amount,currency='usd',product=product["id"],).to_dict()
            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                line_items=[
                    {
                        # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                        'price': price["id"],
                        'quantity': 1,
                    },
                ],
                mode='payment',
                success_url= main_url + "{CHECKOUT_SESSION_ID}" + "/",
                cancel_url="https://example.com/success" + '/cancel.html',
            )
            return Response({"status": status.HTTP_200_OK,"payement": "stripe", "url": checkout_session.url,"add_amount":total_charge, "message": f"Please add ${total_charge} to your wallet to book the club."}) 
    except ValidationError as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except KeyError as e:
        return Response({"message": f"Missing field: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

def store_book_club_stripe_payement(request, stripe_fee, my_data, checkout_session_id):
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        pay = stripe.checkout.Session.retrieve(checkout_session_id).to_dict()
        stripe_customer_id = pay.get("customer")
        payment_status = pay.get("payment_status") == "paid"
        amount_total = Decimal(pay.get("amount_total", 0)) / 100  # Convert to Decimal
        payment_method_types = pay.get("payment_method_types", [])

        # Decode and parse JSON data
        json_bytes = base64.b64decode(my_data)
        request_data = json.loads(json_bytes.decode('utf-8'))
        # debited_wallet_balance = request_data.get("debited_wallet_balance")
        booking_date = request_data.get("booking_date")
        join_details = request_data.get("join_details")
        date = datetime.strptime(booking_date, "%Y-%m-%d %H:%M:%S")  # Adjust format as needed
        pay_amount_ = round(float(request_data.get("pay_amount")), 2)
        club_id = request_data.get("club_id")
        package_id = request_data.get("package_id")
        user = get_object_or_404(User, id=request_data.get("user_id"))
        package = get_object_or_404(ClubPackage, id=package_id)
        club = get_object_or_404(Club, id=club_id)
        get_user = get_object_or_404(User, id=request_data.get("user_id"))
        payment_for = f"join {club.name} club"
        user_wallet = Wallet.objects.filter(user=user).first()
        get_wallet = Wallet.objects.filter(user=club.user).first()
        admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
        existing_payment = AllPaymentsTable.objects.filter(user=get_user, checkout_session_id=checkout_session_id).exists()

        if not existing_payment and payment_status:
            AllPaymentsTable.objects.create(
                user=get_user,
                amount=pay_amount_,
                checkout_session_id=checkout_session_id,
                payment_mode=", ".join(payment_method_types),
                payment_for=payment_for,
                status="Completed" if payment_status else "Failed"
            )
            join = BookClub(user=get_user, package=package, price=package.price, date=date)
            join.status = True
            join.save()
            ###
            # try:
            club_amount = (package.price * Decimal(settings.CLUB_PERCENTAGE)) / 100
            admin_amount = (package.price * Decimal(settings.ADMIN_PERCENTAGE_CLUB)) / 100
            
            if admin_amount is not None:
                admin_amount = admin_amount.quantize(Decimal("0.01"))  # Keeps 2 decimal places
            if club_amount is not None:
                club_amount = club_amount.quantize(Decimal("0.01"))
            
            wallet_transaction = WalletTransaction.objects.create(
                sender=get_user,
                reciver=club.user,
                admin_cost=str(admin_amount),
                reciver_cost=str(club_amount),
                getway_charge=stripe_fee,
                transaction_for="BookClub",
                transaction_type="debit",
                amount=package.price,
                payment_id=checkout_session_id,
                description=f"${package.price} is debited from your PickleIt wallet for booking club to {club.name}."
            )
            transaction_for = TransactionFor(transaction=wallet_transaction, details=join_details)
            transaction_for.save()
            get_wallet.balance += club_amount
            admin_wallet.balance += admin_amount
            get_wallet.save()
            admin_wallet.save()
            user_wallet.balance = 0.0
            user_wallet.save()
            #need to add notification
            reword_user = User.objects.filter(id=club.user.id).first()
            message = f"{get_user.first_name} booked your club: {club.name} at {date}"
            title = "User Booked Club"
            notify_edited_player(reword_user.id, title, message)
            club_user = User.objects.filter(id=club.user.id).first()
            message2 = f"{get_user.first_name} booked your club: {club.name} at {date}"  
            notify_edited_player(club_user.id, title, message2)
        if payment_status:
            return render(request, "club/success_payment_for_booking_club.html")
        else:
            return render(request, "club/failed_payment_join_club.html")

    except Exception as e:
        print(f"Error in payment_for_team_registration: {str(e)}")
        return render(request, "club/failed_payment_join_club.html")



"""
club booking list
"""
@api_view(['GET'])
def club_booking_list(request):
    date = timezone.now()
    club_id = request.GET.get("club_id", None)
    filter_key = request.GET.get("filter", None)
    user = get_object_or_404(User, uuid=request.GET.get("user_uuid"))
    club = get_object_or_404(Club, id=club_id, user=user)
    booking_list = BookClub.objects.filter(package__club__user=user, package__club = club)


    if filter_key == "expire":
        booking_list = booking_list.filter(date__lt=date)
    elif filter_key == "today": 
        booking_list = booking_list.filter(date__date=date.date())
    elif filter_key == "future":   
        booking_list = booking_list.filter(date__gt=date)
    
    

    # Paginate results
    paginator = BookingUserPagination()
    paginated_bookings = paginator.paginate_queryset(booking_list, request)

    # Serialize the data
    serializer = BookClubSerializer(paginated_bookings, many=True)
    return paginator.get_paginated_response(serializer.data)



"""
my join club list
"""
class JoinClubListSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="club.name", read_only=True)
    image = serializers.SerializerMethodField()
    id = serializers.IntegerField(source="club.id", read_only=True)
    location = serializers.CharField(source="club.location", read_only=True)
    latitude = serializers.CharField(source="club.latitude", read_only=True)
    longitude = serializers.CharField(source="club.longitude", read_only=True)
    is_vip = serializers.BooleanField(source="club.is_vip", read_only=True)
    diactivate = serializers.BooleanField(source="club.diactivate", read_only=True)
    contact = serializers.CharField(source="club.contact", read_only=True)
    email = serializers.CharField(source="club.email", read_only=True)
    overall_rating = serializers.CharField(source="club.overall_rating", read_only=True)

    class Meta:
        model = JoinClub
        fields = ["id", "name", "image", "location", "latitude", "longitude" ,"contact", "email", "overall_rating" ,"is_vip" , "status", "join_date", "diactivate"]
    
    def get_image(self, obj):
        image = ClubImage.objects.filter(club=obj.club).values("image")
        return image if image else []



@api_view(['GET'])
def user_club_join_list(request):
    search_text = request.GET.get("user_uuid", None)
    user_uuid = request.GET.get("user_uuid")
    user = get_object_or_404(User, uuid=user_uuid)
    join_list = JoinClub.objects.filter(user=user, block=False)
    paginator = JoinClubPagination()
    paginated_join_list = paginator.paginate_queryset(join_list, request)
    if search_text:
        join_list = join_list.filter(Q(club__name__icontains=search_text) | Q(club__description__icontains=search_text))
    serializer = JoinClubListSerializer(paginated_join_list, many=True)
    return paginator.get_paginated_response(serializer.data)




"""
user show her/him booking clubs cupon list
"""
@api_view(['GET'])
def user_booking_list(request):
    data = request.GET
    user = get_object_or_404(User, uuid=data.get("user_uuid"))
    booking_list = BookClub.objects.filter(user=user).order_by('-date')[:10]
    paginator = BookingUserPagination()
    paginated_bookings = paginator.paginate_queryset(booking_list, request)
    serializer = BookClubSerializer(paginated_bookings, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)




"""
search the clubs using location and keyword
"""
class SearchClubListSerializer(serializers.ModelSerializer):
    images = ClubImageSerializer(many=True, read_only=True, source="clubimage_set")
    is_joined = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = ("id", "name", "location", "latitude", "longitude", "contact", "email", "overall_rating", "images", "is_vip", "diactivate", "is_joined")

    def get_is_joined(self, obj):
        user_uuid = self.context.get("user_uuid")
        user = get_object_or_404(User, uuid=user_uuid)
        if user.is_authenticated:
            return JoinClub.objects.filter(club=obj, block=False).exists()
        return False


class ClubSearchAPIView(ListAPIView):
    serializer_class = SearchClubListSerializer
    pagination_class = ClubPagination

    def get_queryset(self):
        keyword = self.request.GET.get("keyword", "").strip()
        latitude = self.request.GET.get("latitude")
        longitude = self.request.GET.get("longitude")
        user_uuid = self.request.GET.get("user_uuid")
        
        # If no filters, return all active clubs
        if not keyword and not latitude and not longitude:
            return Club.objects.filter(diactivate=False)

        clubs = Club.objects.filter(diactivate=False)

        # Apply keyword filter
        if keyword:
            clubs = clubs.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))

        # Apply distance filter only if lat & long are provided
        if latitude and longitude:
            user_location = (float(latitude), float(longitude))
            max_distance_km = 100  # Search radius in km

            # Filter clubs by distance using geopy
            clubs = [club for club in clubs if geodesic(user_location, (float(club.latitude), float(club.longitude))).km <= max_distance_km]

        return clubs

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True, context={"user_uuid": self.request.GET.get("user_uuid")})
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)








"""
club weekly join details
"""
@api_view(['GET'])
def weekly_join_details(request):
    data = request.GET
    today = timezone.now().date()
    user = get_object_or_404(User, uuid=data.get("user_uuid"))
    club = get_object_or_404(Club, id=data.get("club_id"))

    start_date = today - timedelta(days=6)

    # Get JoinClub counts per day in the 7-day range
    joins = (
        JoinClub.objects.filter(
            club=club,
            join_date__date__range=[start_date, today]
        )
        .annotate(day=TruncDate('join_date'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    join_counts = {item['day']: item['count'] for item in joins}

    weekly_data = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        weekly_data.append(join_counts.get(day, 0))

    total = sum(weekly_data)

    return Response({
        'weekly_data': weekly_data,
        'total': total
    }, status=status.HTTP_200_OK)


"""
club weekly booking details
"""
@api_view(['GET'])
def weekly_booking_details(request):
    data = request.GET
    today = timezone.now().date()
    user = get_object_or_404(User, uuid=data.get("user_uuid"))
    # Optional: filter by package or club if needed
    # package = get_object_or_404(ClubPackage, id=data.get("package_id"))

    start_date = today - timedelta(days=6)
    
    bookings = (
        BookClub.objects.filter(  
            date__date__range=[start_date, today]
        )
        .annotate(day=TruncDate('date'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    booking_counts = {item['day']: item['count'] for item in bookings}

    weekly_data = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        weekly_data.append(booking_counts.get(day, 0))

    total = sum(weekly_data)

    return Response({
        'weekly_data': weekly_data,
        'total': total
    }, status=status.HTTP_200_OK)






class ClubTransectionSerializer(serializers.ModelSerializer):
    sender_full_name = serializers.SerializerMethodField()
    reciver_full_name = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = [
            'id',
            'transaction_id',
            'sender_full_name',
            'reciver_full_name',
            'transaction_type',
            'transaction_for',
            'amount',
            'description',
            'created_at',
            'details',
        ]

    def get_sender_full_name(self, obj):
        return f"{obj.sender.first_name} {obj.sender.last_name}".strip()

    def get_reciver_full_name(self, obj):
        if obj.reciver:
            return f"{obj.reciver.first_name} {obj.reciver.last_name}".strip()
        return None

    def get_details(self, obj):
        da = {}
        try:
            transactionfor = TransactionFor.objects.filter(transaction=obj)
            if transactionfor.exists():
                transactionfor = transactionfor.first()
                da = transactionfor.details      
            return da
        except Exception:
            return da


@api_view(['GET'])
def club_transection_list(request):
    user_uuid = request.GET.get("user_uuid")
    club_id = request.GET.get("club_id")
    user = get_object_or_404(User, uuid=user_uuid)
    club = get_object_or_404(Club, id=club_id)
    if user != club.user:
        return Response({"message": "You are not authorized to view this club's transactions."}, status=status.HTTP_403_FORBIDDEN)
    transection = WalletTransaction.objects.filter(reciver=club.user).filter(Q(transaction_for="JoinClub") | Q(transaction_for="BookClub")).order_by("-id")
    serializer = ClubTransectionSerializer(transection, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
def club_qr_code_scanning(request):
    """API to join a club with balance validation."""
    try:
        data = request.data
        user = get_object_or_404(User, uuid=data.get("user_uuid"))
        club = get_object_or_404(Club, id=data.get("club_id"))
        qr_data = data.get("qr_data")
        today = timezone.now().date()
        if not qr_data:
            return Response({"scanning_status":False, "details":{}, "message": "QR data is required"}, status=status.HTTP_400_BAD_REQUEST)
        scanning = BookClub.objects.filter(qr_data=qr_data, package__club=club, date__date=today)
        if not scanning.exists():
            return Response({"scanning_status":False, "details":{}, "message": "QR code is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        scanning = scanning.first()
        scanning_details = {
            "user": scanning.user.first_name + " " + scanning.user.last_name,
            "club": scanning.package.club.name,
            "package_name": scanning.package.name,
            "package": scanning.package.name,
            "date": scanning.date.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return Response({"scanning_status":True, "details":scanning_details, "message": "QR code is valid"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"scanning_status":False, "details":{}, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)





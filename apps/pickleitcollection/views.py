import base64
import random
import mimetypes
import stripe, json
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from phonenumber_field.phonenumber import PhoneNumber
import boto3
import uuid
from django.conf import settings
from apps.team.models import *
from apps.user.helpers import *
from apps.store.serializers import *
from apps.pickleitcollection.models import *
from apps.pickleitcollection.serializers import *
from apps.store.models import *
from apps.team.views import notify_edited_player
import re
from django.conf import settings
from django.core.cache import cache
from django.db.models.functions import Cast
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.db.models import Q, CharField
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.shortcuts import render, HttpResponse
from django.utils.timezone import now
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import serializers, status
from rest_framework.pagination import PageNumberPagination
protocol = settings.PROTOCALL
api_key = settings.MAP_API_KEY
stripe.api_key = settings.STRIPE_PUBLIC_KEY
CACHE_TTL = getattr(settings, 'CACHE_TTL', DEFAULT_TIMEOUT)


"""
here is the working use api 

"""
@api_view(('GET',))
def advertisement_rate_list(request):
    """
    Fetches the list of advertisement rates per duration.    
    """
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response(
                {"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access", "data": []}
            )
        
        rate_list = AdvertisementDurationRate.objects.all().values()
        data["status"] = status.HTTP_200_OK
        data["message"] = "Rates fetched successfully."
        data["data"] = rate_list

        return Response(data)
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        return Response(data)
    
@api_view(('POST',))
def advertisement_add(request):
    """
    Creates an advertisement and charges fees for creating it.    
    """
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')

        advertisement_name = request.data.get('advertisement_name')
        description = request.data.get('description')
        image = request.FILES.get('image')
        script_text = request.data.get('script_text')
        url = request.data.get('url')
        start_date = request.data.get('start_date')
        rate_id = request.data.get('rate_id', None)
        company_name = request.data.get('company_name')
        company_website = request.data.get('company_website')        
        
        start_date = datetime.strptime(start_date, '%m/%d/%Y').strftime('%Y-%m-%d')       
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response(
                {"status": status.HTTP_401_UNAUTHORIZED, "message": "Unauthorized access", "data": []}
            )
        get_user = check_user.first()    

        check_wallet = Wallet.objects.filter(user=get_user)
        if not check_wallet.exists():
            return Response(
                {"status": status.HTTP_404_NOT_FOUND, "message": "No wallet found.", "data": []}
            )
        
        get_wallet = check_wallet.first()
        balance = get_wallet.balance
        if rate_id:
            duration_instance = AdvertisementDurationRate.objects.filter(id=int(rate_id)).first()
            rate = duration_instance.rate
            if float(balance) >= float(rate):
                obj = GenerateKey()
                advertisement_key = obj.gen_advertisement_key()
                ad = Advertisement.objects.create(
                        secret_key=advertisement_key,
                        name=advertisement_name,
                        image=image,
                        url=url,
                        created_by_id=get_user.id,
                        description=description,
                        script_text=script_text,
                        start_date=start_date,
                        company_name=company_name,
                        company_website=company_website,
                        duration=duration_instance)
                
                WalletTransaction.objects.create(
                    sender = get_user,
                    reciver = None,                        
                    admin_cost=Decimal(rate),
                    getway_charge = 0,                        
                    transaction_for="Advertisement",                                   
                    transaction_type="debit",
                    amount=Decimal(rate),
                    payment_id=None, 
                    description=f"${rate} is debited from your PickleIt wallet for creating advertisement."
                    )
                balance = float(balance) - float(rate)
                get_wallet.balance = Decimal(balance)
                get_wallet.save()

                admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
                admin_balance = float(admin_wallet.balance) + float(rate)
                admin_wallet.balance = Decimal(admin_balance)
                admin_wallet.save()
                
                # send notification to admin
                admin_users = User.objects.filter(is_admin=True).values_list('id', flat=True)
                title = "New Advertisement created."
                message = f"{get_user.first_name} {get_user.last_name} has created an advertisement named {ad.name}. Please review this."
                for user_id in admin_users:
                    notify_edited_player(user_id, title, message)
                
                data['status'] = status.HTTP_200_OK
                data["message"] = f"You have successfully created the advertisement {ad.name} and ${rate} has been deducted from your wallet for this."
        
            else:
                remaining_amount = float(rate) - float(balance)
                data['status'] = status.HTTP_200_OK
                data["message"] = f"Please add ${remaining_amount} to your wallet to creating the advertisement."             
        else:
            obj = GenerateKey()
            advertisement_key = obj.gen_advertisement_key()
            ad = Advertisement.objects.create(
                    secret_key=advertisement_key,
                    name=advertisement_name,
                    image=image,
                    url=url,
                    created_by_id=get_user.id,
                    description=description,
                    script_text=script_text,
                    start_date=start_date,
                    company_name=company_name,
                    company_website=company_website,
                )
            ad.save()
            data['status'] = status.HTTP_200_OK
            data["message"] = f"You have successfully created the advertisement {ad.name}"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

@api_view(('POST',))
def edit_advertisement(request):
    data = {'status':'', 'message':''}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        advertisement_id = request.data.get("advertisement_id")
        advertisement_name = request.data.get('advertisement_name')
        description = request.data.get('description')
        image = request.FILES.get('image')
        script_text = request.data.get('script_text')
        url = request.data.get('url')
        company_name = request.data.get('company_name')
        company_website = request.data.get('company_website')
        user = get_object_or_404(User, uuid=user_uuid)
        advertisement = get_object_or_404(Advertisement, id=advertisement_id)
        # print(type(user.id), type(advertisement.created_by.id))
        if user.id == advertisement.created_by.id:
            advertisement.name = advertisement_name
            if image:
                advertisement.image = image
            advertisement.script_text = script_text
            advertisement.url = url
            advertisement.company_name = company_name
            advertisement.company_website = company_website
            advertisement.description = description
            advertisement.save()
            data['status'], data['message'] = status.HTTP_200_OK, f"Successfully edit you advaticement"
        else:
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"bad request"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

@api_view(('POST',))
def repromote_advertisement(request):
    data = {'status': '', 'message': ''}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        advertisement_id = request.data.get("advertisement_id")
        duration_id = request.data.get("duration_id")
        start_date_str = request.data.get("start_date")  # Date as string
        end_date_str = request.data.get("end_date")  # Date as string

        # Convert date format from 'DD/MM/YYYY' to 'YYYY-MM-DD'
        start_date = datetime.strptime(start_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")

        user = get_object_or_404(User, uuid=user_uuid)
        advertisement = get_object_or_404(Advertisement, id=advertisement_id)
        duration = get_object_or_404(AdvertisementDurationRate, id=duration_id)
        wallet = Wallet.objects.filter(user=user)

        if user == advertisement.created_by and duration:
            if int(duration.rate) != 0:
                if wallet.exists():
                    get_wallet = wallet.first()
                    balance = get_wallet.balance
                else:
                    Wallet.objects.create(user=user)
                    data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "Insufficient Balance in your wallet"
                    return Response(data)

                if balance < duration.rate:
                    data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "Insufficient Balance in your wallet"
                    return Response(data)

                get_wallet.balance -= duration.rate

                WalletTransaction.objects.create(
                    sender=user,
                    reciver=None,                        
                    admin_cost=Decimal(duration.rate),
                    getway_charge=0,                        
                    transaction_for="Advertisement",                                   
                    transaction_type="debit",
                    amount=Decimal(duration.rate),
                    payment_id=None, 
                    description=f"${duration.rate} is debited from your PickleIt wallet for creating advertisement."
                )

                admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
                admin_wallet.balance += Decimal(duration.rate)
                admin_wallet.save()
                get_wallet.save()

            advertisement.duration = duration
            advertisement.start_date = start_date
            advertisement.end_date = end_date
            advertisement.save()
            data['status'], data['message'] = status.HTTP_200_OK, "Successfully promoted your advertisement"
        else:
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "Bad request"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)

    return Response(data)


@api_view(('GET',))
def view_advertisement(request):
    """
    Displays the details of an advertisement.
    """
    data = {'status':'','data':'','message':'', 'is_expire':False}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        ad_uuid = request.GET.get('ad_uuid')
        ad_secret_key = request.GET.get('ad_secret_key')
        host = request.get_host()
        base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_ad = Advertisement.objects.filter(uuid=ad_uuid,secret_key=ad_secret_key)
        if check_user.exists() and check_ad.exists():            
            get_advertisement = check_ad.first()
            ad_data = check_ad.values("id","uuid","secret_key","name","image","script_text"
                                                                                        ,"url","approved_by_admin","admin_approve_status","description","start_date",
                                                                                        "end_date","created_by__first_name","created_by__last_name")
            if ad_data[0]["image"] not in ["", " ", "null", None]:
                ad_data[0]["image"] = base_url + ad_data[0]["image"]
            data["is_expire"] = get_advertisement.end_date.date() < timezone.now().date()
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, ad_data,"data found"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User or Advertisement not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(["GET"])
def list_advertisement(request):
    """
    Fetches the list of all advertisements for a user, ordered by name,
    and includes numeric previous_page/next_page.
    """
    user_uuid   = request.query_params.get("user_uuid")
    user_secret = request.query_params.get("user_secret_key")
    user = User.objects.filter(uuid=user_uuid, secret_key=user_secret).first()

    if not user:
        return Response(
            {"status": status.HTTP_404_NOT_FOUND,
             "data": [],
             "message": "User not found",
             "previous_page": None,
             "next_page": None},
            status=status.HTTP_404_NOT_FOUND
        )

    qs = Advertisement.objects.filter(created_by=user).order_by("-id")
    paginator = PageNumberPagination()
    paginator.page_size = 10
    page = paginator.paginate_queryset(qs, request)  # returns a Page object list

    # Access the underlying Page object
    page_obj = paginator.page

    current = page_obj.number
    prev_num = current - 1 if page_obj.has_previous() else None
    next_num = current + 1 if page_obj.has_next() else None

    serializer = AdvertisementSerializer(page, many=True, context={"request": request})
    return Response(
        {
            "status": status.HTTP_200_OK,
            "count": paginator.page.paginator.count,
            "previous_page": prev_num,
            "next_page": next_num,
            "data": serializer.data,
            "message": "Data found"
        },
        status=status.HTTP_200_OK
    )



@api_view(('GET',))
def list_advertisement_for_app(request):
    """
    Displays the shuffled advertisement list.
    """
    data = {'status': '', 'data': '', 'message': ''}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        host = request.get_host()
        base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        
        if check_user.exists():
            get_user = check_user.first()
            today_date = datetime.now()
            ad_list_cache_key = "advertisement_list"

            advertisement_list = cache.get(ad_list_cache_key)

            if advertisement_list:
                print("from cache............")
            else:
                print("from db...............")

                all_ads = list(Advertisement.objects.filter(approved_by_admin=True, end_date__gte=today_date).values())

                for ad in all_ads:
                    ad['image'] = base_url + ad['image']

                cache.set(ad_list_cache_key, all_ads, timeout=60 * 60) 
                advertisement_list = all_ads

            random.shuffle(advertisement_list)

            final_advertisements = advertisement_list[:5]

            data["status"] = status.HTTP_200_OK
            data["data"] = final_advertisements
            data["message"] = "Data Found"
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

@api_view(['POST'])
def delete_advertisement(request):
    try:
        user_uuid = request.data.get('user_uuid')
        advertisement_id = request.data.get("advertisement_id")

        # Validate inputs
        if not user_uuid or not advertisement_id:
            return Response(
                {"status": status.HTTP_400_BAD_REQUEST, "message": "Missing required fields"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = get_object_or_404(User, uuid=user_uuid)
        advertisement = get_object_or_404(Advertisement, id=advertisement_id)

        # Check if the user is the creator of the advertisement
        if user == advertisement.created_by:
            advertisement.delete()
            return Response(
                {"status": status.HTTP_200_OK, "message": "Successfully deleted your advertisement"},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"status": status.HTTP_403_FORBIDDEN, "message": "You do not have permission to delete this advertisement"},
                status=status.HTTP_403_FORBIDDEN
            )

    except Exception as e:
        return Response(
            {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


"""
old and unuse api
"""
# Not using anymore
@api_view(('GET',))
def screen_type_list(request):
    """
    Displays the screens.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            screen_type = []
            added_screen_lst = [i["screen"] for i in Advertisement.objects.all().values("screen")]

            for _, value in SCREEN_TYPE:
                if value in added_screen_lst :
                    pass
                else:
                    screen_type.append(value)
            # data["data"] = {"screen_type":["Team Create","Leauge Register"],"advertisement_type":["Image","Script"]}
            data["data"] = {"screen_type":screen_type,"advertisement_type":["Image","Script"]}
            data['status'], data['message'] = status.HTTP_200_OK, "Role Admin"
            
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# Not using anymore
@api_view(('POST',))
def add_advertisement(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        advertisement_name = request.data.get('advertisement_name')
        description = request.data.get('description')
        image = request.FILES.get('image')
        script_text = request.data.get('script_text')
        url = request.data.get('url')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        start_date = datetime.strptime(start_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%m/%d/%Y').strftime('%Y-%m-%d')

        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            if get_user.is_admin or get_user.is_sponsor:
                obj = GenerateKey()
                advertisement_key = obj.gen_advertisement_key()
                Advertisement.objects.create(
                    secret_key=advertisement_key,
                    name=advertisement_name,
                    image=image,
                    url=url,
                    created_by_id=get_user.id,
                    script_text=script_text,
                    description = description,
                    start_date=start_date,
                    end_date=end_date
                    )
                data["status"], data["message"] = status.HTTP_200_OK,"Advertisement created successfully"
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND,"User is not Admin or Sponsor"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using anymore
@api_view(('POST',))
def create_advertisement(request):
    """
    Creates an advertisement and charges fees for creating it. 
    Only admin user or sponsor user can create an advertisement.
    """
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        advertisement_name = request.data.get('advertisement_name')
        description = request.data.get('description')
        image = request.FILES.get('image')
        script_text = request.data.get('script_text')
        url = request.data.get('url')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        start_date = datetime.strptime(start_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            if get_user.is_admin or get_user.is_sponsor:
                obj = GenerateKey()
                advertisement_key = obj.gen_advertisement_key()
                image_path = default_storage.save(image.name, ContentFile(image.read()))
                make_request_data = {"secret_key":advertisement_key,"name":advertisement_name,"image":image_path,
                                     "url":url,"created_by_id":get_user.id,"description":description,
                                     "script_text":script_text,"start_date":start_date,"end_date":end_date}
        
                #json bytes
                json_bytes = json.dumps(make_request_data).encode('utf-8')
                
                # Encode bytes to base64
                my_data = base64.b64encode(json_bytes).decode('utf-8')
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
                date_gap = end_date - start_date
                gap_in_days = date_gap.days
                duration = gap_in_days
                charge_amount = int(duration)*int(settings.PER_DAY_CHARGE_FOR_AD)*100  
                charge_for = "for_advertisement"          
                product_name = "Payment For Adding Advertisement"
                product_description = "Payment received by Pickleit"
                stripe.api_key = settings.STRIPE_SECRET_KEY
                
                if get_user.stripe_customer_id :
                    stripe_customer_id = get_user.stripe_customer_id
                else:
                    customer = stripe.Customer.create(email=get_user.email).to_dict()
                    stripe_customer_id = customer["id"]
                    get_user.stripe_customer_id = stripe_customer_id
                    get_user.save() 
                host = request.get_host()
                current_site = f"{protocol}://{host}"
                main_url = f"{current_site}/accessories/9671103725bb2e332ec083861133f7c0dad8e72b039e76bcdff4a102d453b66a/{charge_for}/{my_data}/"
                product = stripe.Product.create(name=product_name,description=product_description,).to_dict()
                price = stripe.Price.create(unit_amount=charge_amount,currency='usd',product=product["id"],).to_dict()
                checkout_session = stripe.checkout.Session.create(
                    customer=stripe_customer_id,
                    line_items=[
                        {
                            'price': price["id"],
                            'quantity': 1,
                        },
                    ],
                    mode='payment',
                    success_url= main_url + "{CHECKOUT_SESSION_ID}" + "/",
                    cancel_url="https://example.com/success" + '/cancel.html',
                )
                return Response({"strip_url":checkout_session.url})
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND,"User is not Admin or Sponsor"
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using anymore
def payment_for_advertisement(request,charge_for,my_data,checkout_session_id):
    """
    Take care of the payment part for creating an advertisement.
    """
    context ={}
    try:        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        pay = stripe.checkout.Session.retrieve(checkout_session_id).to_dict()    
        stripe_customer_id = pay["customer"]
        payment_status = pay["payment_status"]
        expires_at = pay["expires_at"]
        amount_total = float(pay["amount_total"]) / 100
        payment_method_types = pay["payment_method_types"]
        json_bytes = base64.b64decode(my_data)
        request_data = json.loads(json_bytes.decode('utf-8'))
        print(request_data)
        expiry_date = request_data["end_date"]
        payment_status = True if payment_status == "paid" else False
       
        check_customer = User.objects.filter(stripe_customer_id=stripe_customer_id).first()
        obj = GenerateKey ()
        secret_key = obj.gen_payment_key()
        check_same_payment = PaymentDetails.objects.filter(payment_for_id=checkout_session_id,payment_for=charge_for)
        if check_same_payment.exists() :
            
            get_same_payment = check_same_payment.first()
            if get_same_payment.payment_status :
                context["charge_for"] = get_same_payment.payment_for
                context["expires_time"] = get_same_payment.expires_at
                return render(request,"success_payment.html",context)
            else:                
                context["charge_for"] = get_same_payment.payment_for
                return render(request,"failed_payment.html",context)
        if not check_same_payment.exists(): 
            save_payment = PaymentDetails(secret_key=secret_key,payment_for=charge_for,payment_for_id=checkout_session_id,payment_by=payment_method_types,
                                        payment_amount=amount_total,payment_status=payment_status,stripe_response=pay,var_chargeamount=amount_total,
                                        created_by_id=check_customer.id,expires_at=expiry_date)
            save_payment.save()
        
        if payment_status is True:
            ad = Advertisement.objects.create(
                    secret_key=request_data["secret_key"],
                    name=request_data["name"],
                    image=request_data["image"],
                    url=request_data["url"],
                    created_by_id=request_data["created_by_id"],
                    description=request_data["description"],
                    script_text=request_data["script_text"],
                    start_date=None,
                    end_date=None,
                    approved_by_admin=False)
            save_payment.payment_for_ad = ad
            save_payment.save()
            context["charge_for"] = save_payment.payment_for
            context["expires_time"] = save_payment.expires_at
    
            return render(request,"success_payment.html", context)
        else: 
            return render(request,"failed_payment.html")
    except:
        return render(request,"failed_payment.html")


#not work
@api_view(('POST',))
def advertisement_approved_by_admin(request):
    """
    Allows admin user to approve or not approve the advertisements.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        advertisement_id = request.data.get('advertisement_id')
        advertisement_status = request.data.get('advertisement_status')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_advertisement = Advertisement.objects.filter(id=advertisement_id)
        if check_user.exists() :
            get_user = check_user.first()
            if get_user.is_admin and check_advertisement.exists() :
                get_advertisement = check_advertisement.first()
                advertisement_status = True if advertisement_status == "True" else False
                approve_status = "Approved" if advertisement_status == "True" else "Rejected"
                get_advertisement.approved_by_admin = advertisement_status
                get_advertisement.admin_approve_status = approve_status
                get_advertisement.save()
                
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, "",f"{get_advertisement.name} is updated successfully"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not admin or Advertisement is undefined"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# Not using
@api_view(('POST','GET'))
def add_charge_amount(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            if get_user.is_admin :
                check_charge_for = ChargeAmount.objects.all().values("charge_for")
                
                charge_for_data = {"Organizer":"Organizer","Sponsors":"Sponsors"}
                for i in check_charge_for :
                    if i["charge_for"] in charge_for_data.values() :
                        charge_for_data.pop(i["charge_for"])

                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, charge_for_data,"charge for"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not Admin"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
        if request.method == "POST":
            user_uuid = request.data.get('user_uuid')
            user_secret_key = request.data.get('user_secret_key')
            charge_for = request.data.get('charge_for')
            charge_amount = request.data.get('charge_amount')
            effective_time = request.data.get('effective_time')
            check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
            if check_user.exists() :
                get_user = check_user.first()
                if get_user.is_admin :
                    obj = GenerateKey()
                    c_amount_key = obj.gen_charge_amount()
                    check_charge_for = ChargeAmount.objects.filter(charge_for=charge_for).values("charge_for")
                    if not charge_for or not charge_amount or not effective_time :
                        data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "",f"charge amount,charge for, effective time  is required"
                        return Response(data)
                    if check_charge_for.exists():
                        data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "",f"{charge_for} charge amount is already exists"
                        return Response(data)
                    var_effective_time = f"{effective_time} 00:00:00"
                    save_ca = ChargeAmount(secret_key=c_amount_key,charge_for=charge_for,charge_amount=charge_amount,
                                 effective_time=var_effective_time,created_by_id=get_user.id)
                    save_ca.save()
                    data["status"], data["data"], data["message"] = status.HTTP_201_CREATED, "",f"{charge_for} charge amount is added successfully"
                else:
                    data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not Admin"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"

    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using
def format_duration(duration):
    days, seconds = duration.days, duration.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"


# Not using
@api_view(('GET',))
def list_charge_amount(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            if get_user.is_admin :
                check_charge_for = ChargeAmount.objects.all().values("id","uuid","secret_key","charge_for","charge_amount","effective_time",)
                for i in check_charge_for :
                    var = format_duration(i["effective_time"])
                    i["effective_time"] = var
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, check_charge_for,"Data found"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not Admin"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# Not using
@api_view(('GET',))
def view_charge_amount(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        charge_id = request.GET.get('charge_id')
        check_charge_for = ChargeAmount.objects.filter(id=charge_id).values("id","uuid","secret_key","charge_for","charge_amount","effective_time",)
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() and check_charge_for.exists() :
            get_user = check_user.first()
            if get_user.is_admin :
                for i in check_charge_for :
                    var = format_duration(i["effective_time"])
                    i["effective_time"] = var
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, check_charge_for,"Data found"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not Admin"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User or ChargeAmount not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# Not using
@api_view(('POST',))
def edit_charge_amount(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        charge_id = request.data.get('charge_id')

        charge_amount = request.data.get('charge_amount')
        effective_time = request.data.get('effective_time')
        check_charge_for = ChargeAmount.objects.filter(id=charge_id)
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() and check_charge_for.exists() :
            get_user = check_user.first()
            get_ca = check_charge_for.first()
            if get_user.is_admin :
                if not charge_amount or not effective_time :
                    data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "",f"charge id, charge amount, charge for, effective time  is required"
                    return Response(data)
                
                var_effective_time = f"{effective_time} 00:00:00"
                get_ca.charge_amount = charge_amount
                get_ca.effective_time = var_effective_time
                get_ca.save()
                data["status"], data["data"], data["message"] = status.HTTP_201_CREATED, "",f"{get_ca.charge_for} charge amount is updated successfully"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not Admin"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User or ChargeAmount not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using
@api_view(('POST',))
def allow_to_make_organizer(request):
    """
    Allows user to become organizer.
    """
    data={'status':'', 'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            get_user.is_organizer = True
            get_user.save()
            data['status'], data['message'] = status.HTTP_200_OK, f"Now you are an organizer."
        else:
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# Not using
def payment(request,charge_for,checkout_session_id):
    context ={}
    stripe.api_key = settings.STRIPE_SECRET_KEY
    context['stripe_api_key'] = settings.STRIPE_PUBLIC_KEY
    pay = stripe.checkout.Session.retrieve(checkout_session_id).to_dict()    
    stripe_customer_id = pay["customer"]
    payment_status = pay["payment_status"]
    expires_at = pay["expires_at"]
    amount_total = float(pay["amount_total"]) / 100

    payment_method_types = pay["payment_method_types"]
    
    payment_status = True if payment_status == "paid" else False
    check_customer = User.objects.filter(stripe_customer_id=stripe_customer_id).first()
    obj = GenerateKey ()
    secret_key = obj.gen_payment_key()
    check_charge = ChargeAmount.objects.filter(charge_for=charge_for)
    check_same_paymnet = PaymentDetails.objects.filter(payment_for_id=checkout_session_id,payment_for=charge_for)
    if check_same_paymnet.exists() :
        get_same_paymnet = check_same_paymnet.first()
        if get_same_paymnet.payment_status :
            context["charge_for"] = get_same_paymnet.payment_for
            context["expires_time"] = get_same_paymnet.expires_at
            return render(request,"success_payment.html",context)
        else:
            context["charge_for"] = get_same_paymnet.payment_for
            return render(request,"failed_payment.html",context)
        
    elif check_charge.exists() and not check_same_paymnet.exists():
        get_charge = check_charge.first()
        expires_duration = get_charge.effective_time.days
        current_time = datetime.now()
        expires_time = current_time + timedelta(days=expires_duration)
        save_payment = PaymentDetails(secret_key=secret_key,chargeamount_id=get_charge.id,var_chargeamount=get_charge.charge_amount,
                                    payment_for=charge_for,payment_for_id=checkout_session_id,payment_by=payment_method_types,
                                    payment_amount=amount_total,payment_status=payment_status,stripe_response=pay,
                                    created_by_id=check_customer.id,expires_at=expires_time)
        save_payment.save()
        if charge_for == "Organizer" :
            check_customer.is_organizer = True
            check_customer.is_organizer_expires_at = expires_time
            check_customer.save()
            
        elif charge_for == "Sponsors" :
            check_customer.is_sponsor = True
            check_customer.is_sponsor_expires_at = expires_time
            check_customer.save()
            
        elif charge_for == "Ambassador" :
            check_customer.is_ambassador = True
            check_customer.is_ambassador_expires_at = expires_time
            check_customer.save()
        context["charge_for"] = save_payment.payment_for
        context["expires_time"] = save_payment.expires_at
        return render(request,"success_payment.html",context)
    else: 
        message = f"error .."
        return render(request,"failed_payment.html")


# Not using
@api_view(('POST','GET'))
def checkout(request):
    context={}
    stripe.api_key = settings.STRIPE_SECRET_KEY
    context['stripe_api_key'] = settings.STRIPE_PUBLIC_KEY
    if request.method == 'POST':
        charge_for = request.data.get('charge_for')
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        # This is for Organizer
        if charge_for == "Organizer" and check_user.exists():
            check_product = ChargeAmount.objects.filter(charge_for = "Organizer")
            if check_product.exists():
                get_user = check_user.first()
                get_product = check_product.first()
                product_name = f"To Become an Organizer"
                get_days = str(get_product.effective_time).split(" ")[0]
                product_description = f"This is a subscription for {get_days} days"
                unit_amount = (get_product.charge_amount) * 100
            else:
                return HttpResponse("Not a vaild request")
        # This is for Sponsors
        elif charge_for == "Sponsors" and check_user.exists() :
            check_product = ChargeAmount.objects.filter(charge_for = "Sponsors")
            if check_product.exists():
                get_user = check_user.first()
                get_product = check_product.first()
                product_name = f"To Become a Sponsors"
                get_days = str(get_product.effective_time).split(" ")[0]
                product_description = f"This is a subscription for {get_days} days"
                unit_amount = (get_product.charge_amount) * 100
            else:
                return HttpResponse("Not a vaild request")
        # This is for Sponsors
        elif charge_for == "Ambassador" and check_user.exists() :
            check_product = ChargeAmount.objects.filter(charge_for = "Ambassador")
            if check_product.exists():
                get_user = check_user.first()
                get_product = check_product.first()
                product_name = f"To Become an Ambassador"
                get_days = str(get_product.effective_time).split(" ")[0]
                product_description = f"This is a subscription for {get_days} days"
                unit_amount = (get_product.charge_amount) * 100
            else:
                return HttpResponse("Not a vaild request")
        else:
            return HttpResponse("Not a vaild request")
        # creating customer 
        if get_user.stripe_customer_id :
            stripe_customer_id = get_user.stripe_customer_id
        else:
            customer = stripe.Customer.create(email=get_user.email).to_dict()
            stripe_customer_id = customer["id"]
            get_user.stripe_customer_id = stripe_customer_id
            get_user.save()
        
        host = request.get_host()
        current_site = f"{protocol}://{host}"
        main_url = f"{current_site}/accessories/040ffd5925d40e11c67b7238a7fc9957850b8b9a46e9729fab88c24d6a98aff2/{charge_for}/"
        
        product = stripe.Product.create(name=product_name,description=product_description,).to_dict()

        price = stripe.Price.create(unit_amount=unit_amount,currency='usd',product=product["id"],).to_dict()
                    
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
        return Response({"strip_url":checkout_session.url})
        
    return HttpResponse("Get method not supported")


# Not using
@api_view(('GET',))
def list_payments(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            if get_user.is_admin :
                all_payment = PaymentDetails.objects.all().order_by('-id').values("created_by__first_name","created_by__last_name",
                                                        "created_by__email","payment_status","created_at","payment_for","payment_for_id",
                                                        "payment_by","payment_amount")
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, all_payment,"Data found"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not Admin"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# Not using
@api_view(('GET',))
def show_notifications(request):
    data = {'status':'','notifications_data':'','user_data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            main_role = get_user.get_role()
            user_data = []
            user_data.append("team_manager") if get_user.is_team_manager or get_user.is_coach else None
            user_data.append("player") if get_user.is_player else None

            all_noti = Notifications.objects.filter(user_id = get_user.id,is_read=False).values("id","message","screen","url","timestamp")
            data["status"], data["notifications_data"], data["message"] = status.HTTP_200_OK, all_noti,"Data Found"
            # user check for organizer
            if get_user.is_organizer :
                user_data.append("organizer")
               
            # user check for sponsor
            if get_user.is_sponsor :
                user_data.append("sponsor")
                
            data["user_data"] = {"main_role":main_role,"user_sub_role":user_data}
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# Not using
@api_view(('POST',))
def update_notifications(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        notifications = request.data.get('notifications')
        
        # [{"id":1,"message":"You are Now organizer."},{"id":2,"message":"message"}]
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            notifications_list = json.loads(notifications)
            for i in notifications_list :
                check_noti = Notifications.objects.filter(id=i["id"],message=i["message"],user_id=get_user.id)
                if check_noti.exists():
                    get_noti = check_noti.first()
                    get_noti.is_read = True
                    get_noti.save()
                else:
                    pass
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, "","Data Updated"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# Not using
@api_view(('POST',))
def allow_to_make_ambassador(request):
    """
    Allows a user to become ambassador.
    """
    responsee = {}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        player_uuid = request.data.get('player_uuid')
        player_secret_key = request.data.get('player_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_payer = Player.objects.filter(uuid=player_uuid, secret_key=player_secret_key)
        
        if check_user.exists() and check_payer.exists():
            user_instance = check_user.first()
            if user_instance.is_admin or user_instance.is_organizer:
                payer=check_payer.first().player.id
                User.objects.filter(id=int(payer)).update(is_ambassador = True)
                check__am = AmbassadorsDetails.objects.filter(ambassador_id=payer)
                
                if len(check__am)==0:
                    AmbassadorsDetails.objects.create(ambassador_id=payer)
                player_name= check_payer.first().player.first_name
                responsee = {'status': status.HTTP_200_OK, 'message': f'Now {player_name} is Ambassador'}
            else:
                responsee = {'status': status.HTTP_200_OK, 'message': 'User not admin or organiger'}
        else:
            responsee = {'status': status.HTTP_400_BAD_REQUEST, 'message': 'Not found user or player'}     
        return Response(responsee)
    except Exception as e:
        responsee = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
        return Response(responsee, status=responsee['status'])

# Not using
@api_view(('POST',))
def allow_to_make_ambassador_to_player(request):
    """
    Allows to make an ambassador to player again.
    """
    responsee = {}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        player_uuid = request.data.get('player_uuid')
        player_secret_key = request.data.get('player_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_payer = Player.objects.filter(uuid=player_uuid, secret_key=player_secret_key)
        if check_user.exists() and check_payer.exists():
            user_instance = check_user.first()
            if user_instance.is_admin or user_instance.is_organizer:
                payer=check_payer.first().player.id
                User.objects.filter(id=int(payer)).update(is_ambassador = False)
                player_name= check_payer.first().player.first_name
                responsee = {'status': status.HTTP_200_OK, 'message': f'Now {player_name} is Removed from Ambassador'}
            else:
                responsee = {'status': status.HTTP_200_OK, 'message': 'User not admin or organiger'}
        else:
            responsee = {'status': status.HTTP_400_BAD_REQUEST, 'message': 'Not found user or player'}     
        return Response(responsee)
    except Exception as e:
        responsee = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
        return Response(responsee, status=responsee['status'])

# Not using
@api_view(('GET',))
def ambassador_list(request):
    """
    Displays the list of all ambassadors.
    """
    data = {'status': '', 'data': [], 'message': ''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
                get_user = check_user.first()
                if get_user.is_admin or get_user.is_organizer:
                    if not search_text:
                        all_players = Player.objects.filter(player__is_ambassador=True).values()
                    else:
                        all_players = Player.objects.filter(player__is_ambassador=True).filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text)).values()
                elif get_user.is_team_manager or get_user.is_coach:
                    if not search_text:
                        all_players = Player.objects.filter(created_by_id=get_user.id,player__is_ambassador=True).values()
                    else:
                        all_players = Player.objects.filter(created_by_id=get_user.id,player__is_ambassador=True).filter(Q(player_first_name__icontains=search_text) | Q(player_last_name__icontains=search_text)).values()
                
                for player_data in all_players:
                    player_id = player_data["id"]
                    user_id = player_data["player_id"]
                    phone_number = player_data['player_phone_number']
                    if isinstance(phone_number, PhoneNumber):
                        player_data['player_phone_number'] = str(phone_number)
                    user_image = User.objects.filter(id=user_id).values()
                    ambassador = AmbassadorsDetails.objects.filter(ambassador_id=user_image[0]["id"]).first()
                    posts = AmbassadorsPost.objects.filter(created_by_id=user_image[0]["id"])
                    try:
                        player_data["user_uuid"] = user_image[0]["uuid"]
                        player_data["user_secret_key"] = user_image[0]["secret_key"]
                        player_data["follower"] = ambassador.follower.all().count()
                        player_data["following"] = ambassador.following.all().count()
                        player_data["total_post"] = posts.count()
                    except:
                        player_data["user_uuid"] = "error to find"
                        player_data["user_secret_key"] = "error to find"
                        player_data["follower"] = 0
                        player_data["following"] = 0
                        player_data["total_post"] = posts.count()

                    if user_image[0]["image"] is not None or user_image[0]["image"] != "":
                        player_data["player_image"] = user_image[0]["image"]
                    else:
                        player_data["player_image"] = None 
                    player_data["is_edit"] = player_data["created_by_id"] == get_user.id
                    player_instance = Player.objects.get(id=player_id)
                    team_ids = list(player_instance.team.values_list('id', flat=True))
                    player_data["team"] = []
                    for team_id in team_ids:
                        team = Team.objects.filter(id=team_id).values()
                        if team.exists():
                            player_data["team"].append(list(team))

                data["status"] = status.HTTP_200_OK
                data["data"] = list(all_players)
                data["message"] = "Data found"
        else:
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"
        return Response(data, status=data['status'])
    except Exception as e:
        data = {'status': status.HTTP_400_BAD_REQUEST, 'data':[], 'message': str(e)}
        return Response(data, status=data['status'])
    
# Not using
@api_view(('GET',))
def ambassador_profile_view(request):
    """
    Displays the profile details of an ambassador.
    """
    data = {'status': '', 'data': [],"ambassador_posts":[], 'message': '', "follower": '', 'following':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        ambassador_uuid = request.GET.get('ambassador_uuid')
        ambassador_secret_key = request.GET.get('ambassador_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            player_=Player.objects.filter(uuid=ambassador_uuid, secret_key=ambassador_secret_key)
            player_details = player_.annotate(player_phone_number_str=Cast('player_phone_number', CharField())).values('uuid','secret_key','player_full_name','player_email','player_phone_number_str','player_ranking','created_by__first_name','created_by__first_name')
            created_by = User.objects.filter(id=player_.first().player.id).first()
            all_post = AmbassadorsPost.objects.filter(created_by=created_by).values()
            data["status"] = status.HTTP_200_OK
            data["data"] = player_details
            data["ambassador_posts"] = list(all_post)
            ambassadorsDetails = AmbassadorsDetails.objects.filter(ambassador=created_by)
            if ambassadorsDetails.exists():
                ambassadorsDetails = ambassadorsDetails.first()
                data["follower"] = len(ambassadorsDetails.follower.all())
                data["following"] = len(ambassadorsDetails.following.all())
            else:
                data["follower"] = 0
                data["following"] = 0
            data["message"] = "Data found"
        else:
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"
        return Response(data)
    except Exception as e:
        responsee = {'status': status.HTTP_400_BAD_REQUEST, 'data':[],"ambassador_posts":[], 'message': str(e),  "follower": '', 'following':''}
        return Response(responsee, status=responsee['status'])
    

# Not using   
@api_view(('POST',))
def ambassador_follow_or_unfollow(request):
    """
    Is used for a user to follow or unfollow an ambassador.
    """
    data = {"status":"", "message":""}
    try:        
        user_uuid = request.data.get('user_uuid')
        profile_uuid = request.data.get('profile_uuid')
        user = get_object_or_404(User, uuid=user_uuid)
        profile_player = get_object_or_404(Player, uuid=profile_uuid)
        if user and profile_player:
            player = Player.objects.filter(player=user).first()
            if user in profile_player.follower.all():
                profile_player.follower.remove(user)
                player.following.remove(profile_player.player)
                data['status'] = status.HTTP_200_OK
                data['message'] = "unfollow"
            else:
                profile_player.follower.add(user)
                player.following.add(profile_player.player)
                data['status'] = status.HTTP_200_OK
                data['message'] = "follow"
        else:
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"
        return Response(data)            
    except Exception as e:
        data = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
        return Response(data)
    
# Not using
@api_view(('GET',))
def check_ambassador_following_or_not(request):
    """
    Fetches the details if a user is following an ambassador or not.
    """
    data = {"status":"", "message":"", "data":[], "follow": ""}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        ambassador_uuid = request.GET.get('ambassador_uuid')
        ambassador_secret_key = request.GET.get('ambassador_secret_key')
        
        user = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key) 
        profile = get_object_or_404(User, uuid=ambassador_uuid, secret_key=ambassador_secret_key)
            
        profile_player = get_object_or_404(Player, player_email=profile.email)    
                
                
        if user in profile_player.follower.all():
            all_followers = profile_player.follower.all().values("id","uuid","secret_key","username","email","first_name","last_name","phone","user_birthday","image","gender","street","city","state","country","postal_code","is_player","is_organizer","is_sponsor","is_ambassador","is_admin")
            data["status"] = status.HTTP_200_OK
            data["data"] ={"ambassador_followers": list(all_followers)}
            data["follow"] = True
            data["message"] = "You are following this player."
        else:
            data["status"] = status.HTTP_200_OK
            data["follow"] = False
            data["message"] = "You are not following this player."
            
        return Response(data)            
    except Exception as e:
        data = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
        return Response(data)

# Not using
class AmbassadorsPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmbassadorsPost
        fields = '__all__'


# Not using
@api_view(['POST'])
def ambassadors_create_post(request):
    """
    Is used for an ambassador to add a post.
    """
    try:
        # Get data from request
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        post_text = request.data.get('post_text')
        file = request.FILES.get("file")
        thumbnail = request.FILES.get("thumbnail")

        # Check if file is provided
        if not file and not thumbnail:
            return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'File and thumbnail not provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Check the MIME type of the file
        detected_mime_type, _ = mimetypes.guess_type(file.name)
        if not detected_mime_type.startswith('video/'):
            return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'Uploaded file is not a video'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if the user exists and is an ambassador
        user_instance = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key)
        if not user_instance.is_ambassador:
            return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'User is not an ambassador'}, status=status.HTTP_400_BAD_REQUEST)

        # Upload the file to S3 and get the URL
        uploaded_url = upload_file_to_s3(file)        
        thumbnail_url = upload_file_to_s3(thumbnail)
        print(uploaded_url, thumbnail_url)
        if not uploaded_url:
            return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'Failed to upload file to S3'}, status=status.HTTP_400_BAD_REQUEST)
        if not thumbnail_url:
            return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'Failed to upload thumbnail to S3'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the post
        secret_key = GenerateKey().gen_ambassadorsPost_key()
        post = AmbassadorsPost.objects.create(
            secret_key=secret_key,
            file=uploaded_url,
            thumbnail=thumbnail_url,
            post_text=post_text,
            created_by=user_instance
        )
        serializer = AmbassadorsPostSerializer(post)
        return Response({'status': status.HTTP_200_OK, 'message': 'Post successfully uploaded', 'data': serializer.data}, status=status.HTTP_200_OK)
    
    except FileNotFoundError:
        return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'File not found'}, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Not using
@api_view(('GET',))
def ambassadors_view(request):
    """
    Is used to view the details of a post or the list of posts created by the ambassador.
    """
    response_data = {}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        post_id = request.GET.get('post_id')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        user_instance = check_user.first()
        #protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        # Construct the complete URL for media files
        media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        if check_user and user_instance.is_ambassador:
            if post_id is not None:
                data = AmbassadorsPost.objects.filter(id = int(post_id), created_by_id=user_instance.id).values("id", "file", "post_text", "approved_by_admin", "likes")
                data[0]["file"] = media_base_url + data[0]["file"]
                response_data["status"] = status.HTTP_200_OK
                response_data["data"] = list(data)
                response_data["message"] = "View Your Post"
            else:
                data = AmbassadorsPost.objects.filter(created_by_id=user_instance.id).order_by("-id").values("id", "file", "post_text", "approved_by_admin","likes")
                for i in data:
                    i["file"] = media_base_url + i["file"]
                response_data["status"] = status.HTTP_200_OK
                response_data["data"] = list(data)
                response_data["message"] = "View Your Posts"
        else:
            response_data["status"] = status.HTTP_400_BAD_REQUEST
            response_data["data"] = []
            response_data["message"] = "User does not exist or is not an ambassador"

        return Response(response_data)
    except Exception as e:
        response_data = {'status': status.HTTP_400_BAD_REQUEST, 'data': [], 'message': str(e)}
        return Response(response_data)

# Not using
@api_view(('POST',))
def ambassadors_edit_post(request):
    """
    Is used for an ambassador to edit his post.
    """
    response_data = {}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        edit_id = request.data.get('edit_id')
        file = request.FILES.get("file")
        post_text = request.data.get('post_text')
        
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
            
        if check_user.exists():
            user_instance = check_user.first()
            check_user_ambassadors = user_instance.is_ambassador
            
            if check_user_ambassadors:
                # Update only if the file is provided in the request
                if file:
                    update_file = "ambassadors_post/" + file.name
                    AmbassadorsPost.objects.filter(id=edit_id).update(file=update_file)
                
                # Update other fields
                AmbassadorsPost.objects.filter(id=edit_id).update(post_text=post_text)
                
                response_data["status"] = status.HTTP_200_OK
                response_data["message"] = "Post Successfully Edited"
            else:
                response_data["status"] = status.HTTP_400_BAD_REQUEST
                response_data["message"] = "This user is not an ambassador"
        else:
            response_data["status"] = status.HTTP_400_BAD_REQUEST
            response_data["message"] = "User does not exist"
        
        return Response(response_data)
    except Exception as e:
        response_data = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
        return Response(response_data)

# Not using
@api_view(('POST',))
def ambassadors_delete_post(request, del_id):
    """
    Is used for an ambassador to delete his post.
    """
    response_data = {}
    try:        
        # Check if the post with the given ID exists
        post_to_delete = AmbassadorsPost.objects.filter(id=del_id).first()
        
        if post_to_delete:
            post_to_delete.delete()
            response_data["status"] = status.HTTP_200_OK
            response_data["message"] = f"Post with ID {del_id} deleted successfully."
        else:
            response_data["status"] = status.HTTP_404_NOT_FOUND
            response_data["message"] = f"Post with ID {del_id} does not exist."

        return Response(response_data)
    except Exception as e:
        response_data = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
        return Response(response_data)

# Not using
@api_view(('POST',))
def admin_allow_ambassadors_post(request):
    """
    Allows admin to approve or not approve a post.
    """
    response_data = {}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        approved_by_admin = request.data.get('approved_by_admin')
        apr_id = request.data.get('apr_id')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        
        if check_user.exists():
            user_instance = check_user.first()
            check_user_admin = user_instance.is_admin
            if check_user_admin:
                if approved_by_admin is not None:
                    AmbassadorsPost.objects.filter(id=int(apr_id)).update(approved_by_admin=approved_by_admin)
                    response_data["status"] = status.HTTP_400_BAD_REQUEST
                    response_data["message"] = "Approved the post"
                else:
                    response_data["status"] = status.HTTP_400_BAD_REQUEST
                    response_data["message"] = "Not approved the post"
            else:
                response_data["status"] = status.HTTP_400_BAD_REQUEST
                response_data["message"] = "User not Admin"
        else:
            response_data["status"] = status.HTTP_400_BAD_REQUEST
            response_data["message"] = "User does not exist"
        return Response(response_data)
    except Exception as e:
        response_data = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
        return Response(response_data)

# Not using
@api_view(('GET',))
def ambassadors_view_all_allow_post(request):
    """
    Displays the list of all posts.
    """
    response_data = {}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        #protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        # Construct the complete URL for media files
        media_base_url = f"{protocol}://{host}"
        if check_user.exists():
            get_user = check_user.first()
            data = list(AmbassadorsPost.objects.all())
            random.shuffle(data)
            paginator = PageNumberPagination()
            paginator.page_size = 10  # Adjust as needed
            result_page = paginator.paginate_queryset(data, request)
            serialized_data = AmbassadorsPostSerializer(result_page, many=True)
            for post in serialized_data.data:
                if post['file']:
                    post['file'] = post['file']
                if post["thumbnail"]:
                    post["thumbnail"] = post["thumbnail"]
                else:
                    post["thumbnail"] = "https://pickleitmedia.s3.amazonaws.com/Reels/PickleIt_logo.png_7908482601214a24bf2f1bbbb3432381.png"
                user_details = User.objects.filter(id=post['created_by']).values("id","uuid", "secret_key", "first_name", "last_name", "image")
                for user in user_details:
                    user['image'] = media_base_url + '/media/' +user['image']
                post['created_by'] = list(user_details)
                post_created_by_id = post["created_by"][0]["id"]
                post['total_likes_count']  = len(post['likes'])
                post_created_by = User.objects.filter(id=post_created_by_id).first()
                if get_user.id in post["likes"]:
                    post["is_liked"] = True
                else:
                    post["is_liked"] = False
                check_ambassador = AmbassadorsDetails.objects.filter(ambassador__id=post_created_by.id)
                if check_ambassador.exists():
                    get_ambassador = check_ambassador.first()
                else:
                    get_ambassador = AmbassadorsDetails.objects.create(ambassador__id=post_created_by.id)
                if get_user in get_ambassador.follower.all():
                    post["is_following"] = True
                else:
                    post["is_following"] = False
            return paginator.get_paginated_response(serialized_data.data)
        else:
            response_data["status"] = status.HTTP_400_BAD_REQUEST
            response_data["result"] = []
            response_data["message"] = "User does not exist"
            return Response(response_data)
    except Exception as e:
        response_data = {'status': status.HTTP_400_BAD_REQUEST, 'result': [], 'message': str(e)}
        return Response(response_data)

# Not using
@api_view(('POST',))
def ambassador_post_like_dislike(request):
    """
    Is used for user to like or unlike a post.
    """
    data = {}
    try:        
        user_uuid = request.data.get("user_uuid")
        user_secret_key = request.data.get("user_secret_key")
        post_uuid = request.data.get("post_uuid")
        post_secret_key = request.data.get("post_secret_key")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            check_post = AmbassadorsPost.objects.filter(uuid=post_uuid, secret_key=post_secret_key)
            if check_post.exists():
                get_post = check_post.first()
                if get_user in get_post.likes.all():
                    get_post.likes.remove(get_user)
                    data["status"], data["message"] = status.HTTP_200_OK, f"Successfully disliked the post."
                else:
                    get_post.likes.add(get_user)
                    data["status"], data["message"] = status.HTTP_200_OK, f"Successfully liked the post."
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"Post not found."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using
@api_view(('GET',))
def chech_post_liked_or_not(request):
    """
    Fetches the details if a user has liked a post or not.
    """
    data = {}
    try:        
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        post_id = request.GET.get("post_id")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            check_post = AmbassadorsPost.objects.filter(id=post_id)
            if check_post.exists():
                get_post = check_post.first()
                total_likes = get_post.likes.all().count()
                liked_status = False
                if get_user in get_post.likes.all():
                    liked_status = True
                    data["status"], data["message"], data["liked_status"], data["total_likes"] = status.HTTP_200_OK, "", liked_status, total_likes
                else:
                    data["status"], data["message"], data["liked_status"], data["total_likes"] = status.HTTP_200_OK, "", liked_status, total_likes
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"Post not found."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# Not using
@api_view(('POST',))
def add_advertiser_facility(request):
    """
    Is used for a sponsor to add any advertiser facility.
    """
    data = {}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        
        facility_name = request.data.get('facility_name')
        facility_type = request.data.get('facility_type')
        court_type = request.data.get('court_type')
        membership_type = request.data.get('membership_type')
        number_of_courts = request.data.get('number_of_courts')
        complete_address = request.data.get('complete_address')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        images = request.FILES.getlist('images')
        # print("images", images)
        if not complete_address or not latitude or not longitude or not images:
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "'complete_address, latitude, longitude and images' are must be needed"
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_sponsor == True:
                obj = GenerateKey()
                facility_key = obj.gen_facility_key()
                facility = AdvertiserFacility(secret_key=facility_key, facility_name=facility_name, facility_type=facility_type, court_type=court_type, membership_type=membership_type, number_of_courts=number_of_courts, complete_address=complete_address, created_by=get_user)
                facility.latitude = latitude
                facility.longitude = longitude
                facility.save()
                for image in images:
                    f_img = FacilityImage(facility=facility, image = image)
                    f_img.save()
                data['status'], data['message'] = status.HTTP_201_CREATED, "Facility created successfully."
            else:
                data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User is not a sponsor, so does not have permission."
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using
@api_view(('GET',))
def advertiser_facility_list(request):
    """
    Displays the list of all facilities added by sponsor.
    """
    data = {}
    try:
        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)        
        if check_user.exists():
            facility = AdvertiserFacility.objects.filter(created_by=check_user.first())
            facility_list = AdvertiserFacilitySerializer(facility, many=True)
            data['data'] = facility_list.data
            data['status'] = status.HTTP_200_OK
            data['message'] = "Data found."
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using
@api_view(('GET',))
def advertiser_facility_list_for_all(request):
    """
    Displays the list of all advertiser facilities.
    """
    data = {}
    try:        
        all_facility = AdvertiserFacility.objects.all()
        facility_list = AdvertiserFacilitySerializer(all_facility, many=True)
        data['data'] = facility_list.data
        data['status'] = status.HTTP_200_OK
        data['message'] = "Data found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using
@api_view(('POST',))
def edit_advertiser_facility(request):
    """
    Is used for sponsor to edit the details of an advertiser facility.
    """
    data = {}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        facility_uuid = request.data.get('facility_uuid')
        facility_secret_key = request.data.get('facility_secret_key')        
        facility_name = request.data.get('facility_name')
        facility_type = request.data.get('facility_type')
        court_type = request.data.get('court_type')
        membership_type = request.data.get('membership_type')
        number_of_courts = request.data.get('number_of_courts')
        images = request.FILES.getlist('images')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)        
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_sponsor:
                check_facility = AdvertiserFacility.objects.get(uuid=facility_uuid)
                if check_facility:
                    check_facility.facility_name = facility_name
                    check_facility.facility_type = facility_type
                    check_facility.court_type = court_type
                    check_facility.membership_type = membership_type
                    check_facility.number_of_courts = number_of_courts
                    
                    # Save the new images
                    for image in images:
                        f_img = FacilityImage(facility=check_facility, image=image)
                        f_img.save()
                        
                    check_facility.save()
                    data['status'], data['message'] = status.HTTP_200_OK, "Facility edited successfully."
                else:
                    data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "Facility not found."
            else:
                data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User is not a sponsor, so does not have permission."
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using
@api_view(('POST',))
def delete_advertiser_facility(request):
    """
    Is used for sponsor to delete an advertiser facility.
    """
    data = {}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        facility_uuid = request.data.get('facility_uuid')
        facility_secret_key = request.data.get('facility_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)        
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_sponsor == True:
                check_facility = AdvertiserFacility.objects.filter(uuid=facility_uuid, secret_key=facility_secret_key)
                if check_facility.exists():
                    get_facility = check_facility.first()
                    get_facility.delete()
                    data["status"], data["message"] = status.HTTP_204_NO_CONTENT, "Facility deleted successfully."
                else:
                    data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Facility not found."
            else:
                data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User is not a sponsor, so does not have permission."
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using
@api_view(('POST',))
def delete_facility_image(request):
    """
    Is used for sponsor to delete an advertiser facility.
    """
    data = {}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        facility_uuid = request.data.get('facility_uuid')
        image_id = request.data.getlist('image_id')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)        
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_sponsor == True:
                check_facility = AdvertiserFacility.objects.filter(uuid=facility_uuid)
                if check_facility.exists():
                    for _id in image_id:
                        FacilityImage.objects.filter(id = _id ).delete()
                    data["status"], data["message"] = status.HTTP_204_NO_CONTENT, "Facility Image deleted successfully."
                else:
                    data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Facility not found."
            else:
                data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User is not a sponsor, so does not have permission."
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)

# Not using
@api_view(('GET',))
def view_advertiser_facility(request):
    """
    Displays the details of an advertiser facility.
    """
    data = {}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        facility_uuid = request.GET.get('facility_uuid')
        facility_secret_key = request.GET.get('facility_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key) 
        if check_user.exists():
            check_facility = AdvertiserFacility.objects.filter(uuid=facility_uuid, secret_key=facility_secret_key)
            
            if check_facility.exists():
                data['status'] = status.HTTP_200_OK
                get_facility = check_facility.first()
                facility_data = AdvertiserFacilitySerializer(get_facility)
                data['data'] = facility_data.data            
                data['message'] = "Data found"
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "Facility not found"
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


################ Reels part new updated ####################
def extract_tags(text):
    return re.findall(r'#\w+', text)

def check_tags(tag_list):
    try:
        for tag in tag_list:
            get_tag = Tags.objects.filter(name=tag).first()
            if get_tag:
                get_tag.number_of_use = get_tag.number_of_use + 1
                get_tag.save()
            else:
                Tags.objects.create(name=tag, number_of_use=1)
        return True
    except:
        return False


@api_view(['POST'])
def create_post(request):
    """
    Is used for an ambassador to add a post.
    Only allowed if user is subscribed to Pro or Enterprise plan.
    """
    try:
        # Step 1: Extract input
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        post_text = request.data.get('post_text')
        file = request.FILES.get("file")
        thumbnail = request.FILES.get("thumbnail")
        tags = request.data.get("tags", None)
        if tags:
            tag_list = extract_tags(tags)
        else:
            tag_list = []

        tag_json = {"tag_list":tag_list}
        check_tags_entry = check_tags(tag_list)
        # Step 2: Validate user credentials
        user_instance = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key)

        # Step 3: Check subscription using get_object_or_404
        subscription = get_object_or_404(
            Subscription,
            user=user_instance,
            is_active=True,
            end_date__gte=now(),
            plan__name__in=["Pro Version", "Enterprise Version"]
        )

        # Step 4: Validate file input
        if not file or not thumbnail:
            return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'File and thumbnail not provided'}, status=status.HTTP_400_BAD_REQUEST)

        detected_mime_type, _ = mimetypes.guess_type(file.name)
        if not detected_mime_type or not detected_mime_type.startswith('video/'):
            return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'Uploaded file is not a video'}, status=status.HTTP_400_BAD_REQUEST)

        # Step 5: Upload to S3
        uploaded_url = upload_file_to_s3(file)
        thumbnail_url = upload_file_to_s3(thumbnail)

        if not uploaded_url or not thumbnail_url:
            return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'Failed to upload to S3'}, status=status.HTTP_400_BAD_REQUEST)

        # Step 6: Create the post
        secret_key = GenerateKey().gen_ambassadorsPost_key()
        post = AmbassadorsPost.objects.create(
            secret_key=secret_key,
            file=uploaded_url,
            thumbnail=thumbnail_url,
            post_text=post_text,
            created_by=user_instance,
            tags = tag_list
        )

        serializer = AmbassadorsPostSerializer(post)
        return Response({'status': status.HTTP_200_OK, 'message': 'Post successfully uploaded', 'data': serializer.data}, status=status.HTTP_200_OK)

    except FileNotFoundError:
        return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'File not found'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PostUserSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    player_uuid = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'uuid', 'secret_key', "username",'first_name', 'last_name', "image", 'player_uuid']

    def get_username(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def get_player_uuid(self, obj):
        # Check if a Player instance is related to the user
        player_qs = obj.player.all()  # related_name='player' on the ForeignKey
        if player_qs.exists():
            return str(player_qs.first().uuid)
        return None

class PostCommentSerializer(serializers.ModelSerializer):
    user = PostUserSerializer(read_only=True)

    class Meta:
        model = PostComment
        fields = ['id', 'post', 'user', 'comment_text', 'parent_comment', 'created_at']

class PostDetailsSerializer(serializers.ModelSerializer):
    created_by = PostUserSerializer()
    comments = PostCommentSerializer(many=True, read_only=True, source="reel_comment")
    is_liked = serializers.SerializerMethodField()  # Field to check if the user liked the post
    thumbnail = serializers.SerializerMethodField()
    number_like = serializers.SerializerMethodField()

    class Meta:
        model = AmbassadorsPost
        fields = [
            'id',
            'uuid',
            'secret_key',
            'created_by',
            'post_text',
            'number_comment',
            'tags',
            'number_like',
            'created_at',
            'file',
            'thumbnail',
            'comments',
            'likes',
            'is_liked'
        ]

    def get_is_liked(self, obj):
        """Check if the user with given user_uuid has liked the post"""
        user_uuid = self.context.get('user_uuid')
        
        if user_uuid:
            user = User.objects.filter(uuid=user_uuid).first()
            if user:
                
                return user in obj.likes.all()
        return False

    def get_number_like(self, obj):
        return obj.likes.count()
    
    def get_thumbnail(self, obj):
        return obj.thumbnail or "https://pickleitmedia.s3.amazonaws.com/Reels/PickleIt_logo.png_7908482601214a24bf2f1bbbb3432381.png"

@api_view(('GET',))
def view_post(request):
    """
    Is used to view the details of a post.
    """
    user_uuid = request.GET.get('user_uuid')
    user_secret_key = request.GET.get('user_secret_key')
    post_id = request.GET.get('post_id')

    # Validate user
    user_instance = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key)
    post = get_object_or_404(AmbassadorsPost, id=int(post_id))
    serializer = PostDetailsSerializer(post, context={'user_uuid': user_uuid})
    return Response(serializer.data)

class PostListSerializer(serializers.ModelSerializer):
   
    created_by = PostUserSerializer(read_only=True)  # Nested user serializer
    is_liked = serializers.SerializerMethodField()  # Field to check if the user liked the post
    thumbnail = serializers.SerializerMethodField()
    total_likes_count = serializers.SerializerMethodField()

    class Meta:
        model = AmbassadorsPost
        fields = ['id', 'uuid', 'secret_key','created_by', 'post_text', 'number_comment','tags', 'total_likes_count', 'created_at', 'file', 'thumbnail', 'likes', 'is_liked']

    def get_is_liked(self, obj):
        """Check if the user with given user_uuid has liked the post"""
        user_uuid = self.context.get('user_uuid')
        
        if user_uuid:
            user = User.objects.filter(uuid=user_uuid).first()
            if user:
                
                return user in obj.likes.all()
        return False
    
    def get_total_likes_count(self, obj):
        return obj.likes.count()

    def get_thumbnail(self, obj):
        return obj.thumbnail or "https://pickleitmedia.s3.amazonaws.com/Reels/PickleIt_logo.png_7908482601214a24bf2f1bbbb3432381.png"
    
class AmbassadorPostPagination(PageNumberPagination):
    page_size = 5  # Default items per page
    page_size_query_param = 'per_page'  # Allow clients to set page size via query param
    max_page_size = 100  # Maximum items per page

    def get_paginated_response(self, data):
        # Get next and previous links
        next_link = self.get_next_link()
        previous_link = self.get_previous_link()
        
        # Force HTTPS in links if they exist
        if next_link:
            next_link = next_link.replace('http://', 'https://')
        if previous_link:
            previous_link = previous_link.replace('http://', 'https://')
        
        return Response({
            'count': self.page.paginator.count,
            'next': next_link,
            'previous': previous_link,
            'results': data
        })
    
@api_view(['GET'])
def post_list(request):
    """
    Displays the list of all posts (paginated).
    Requires valid user credentials to get `is_liked` context.
    """
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')

        # Validate user
        user_instance = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key)

        # Fetch all posts, shuffle order
        posts = list(AmbassadorsPost.objects.all())
        random.shuffle(posts)

        # Paginate posts
        paginator = AmbassadorPostPagination()
        result_page = paginator.paginate_queryset(posts, request)

        # Serialize with context for is_liked logic
        serializer = PostListSerializer(result_page, many=True, context={'user_uuid': user_uuid})

        return paginator.get_paginated_response(serializer.data)

    except Exception as e:
        return Response({
            'status': status.HTTP_400_BAD_REQUEST,
            'result': [],
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def my_post_list(request):
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')

        # Validate user
        user_instance = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key)

        # Fetch all posts, shuffle order
        posts = AmbassadorsPost.objects.filter(created_by=user_instance).order_by('-created_at')
        

        # Paginate posts
        paginator = AmbassadorPostPagination()
        result_page = paginator.paginate_queryset(posts, request)

        # Serialize with context for is_liked logic
        serializer = PostListSerializer(result_page, many=True, context={'user_uuid': user_uuid})

        return paginator.get_paginated_response(serializer.data)

    except Exception as e:
        return Response({
            'status': status.HTTP_400_BAD_REQUEST,
            'result': [],
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(('POST',))
def edit_post(request):
    """
    Is used for an user to edit his post.
    """
 
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        post_id = request.data.get('post_id')
        file = request.FILES.get("file")
        thumbnail = request.FILES.get("thumbnail")
        post_text = request.data.get('post_text')
        tags = request.data.get("tags", None)
        if tags:
            tag_list = extract_tags(tags)
        else:
            tag_list = []

        tag_json = {"tag_list":tag_list}
        check_tags_entry = check_tags(tag_list)
        # Step 2: Validate user credentials
        user_instance = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key)
        post_instance = get_object_or_404(AmbassadorsPost, id=int(post_id), created_by=user_instance)

        # Step 3: Check subscription using get_object_or_404
        subscription = get_object_or_404(
            Subscription,
            user=user_instance,
            is_active=True,
            end_date__gte=now(),
            plan__name__in=["Pro Version", "Enterprise Version"]
        )

        if file:
            detected_mime_type, _ = mimetypes.guess_type(file.name)
            if not detected_mime_type or not detected_mime_type.startswith('video/'):
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': 'Uploaded file is not a video'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            uploaded_url = upload_file_to_s3(file)
            if not uploaded_url:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': 'Failed to upload video file to S3'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            post_instance.file = uploaded_url

        if thumbnail:
            thumbnail_url = upload_file_to_s3(thumbnail)
            if not thumbnail_url:
                return Response({
                    'status': status.HTTP_400_BAD_REQUEST,
                    'message': 'Failed to upload thumbnail to S3'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            post_instance.thumbnail = thumbnail_url

        # Step 4: Always update text if provided
        if post_text:
            post_instance.post_text = post_text
        if tags:
            post_instance.tags = tag_list
        post_instance.save()

        serializer = AmbassadorsPostSerializer(post_instance)
        return Response({'status': status.HTTP_200_OK, 'message': 'Post successfully updated', 'data': serializer.data}, status=status.HTTP_200_OK)

    except FileNotFoundError:
        return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': 'File not found'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(('POST',))
def delete_post(request):
    """
    Is used for an user to delete his post.
    """

    try:     
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        post_id = request.data.get('post_id')   
        
        # Step 2: Validate user credentials
        user_instance = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key)
        post_instance = get_object_or_404(AmbassadorsPost, id=int(post_id), created_by=user_instance)
        
        post_instance.delete()
        return Response({'status': status.HTTP_200_OK, 'message': 'Post successfully deleted.'}, status=status.HTTP_200_OK)    

    except Exception as e:
        return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['POST'])
def generate_video_presigned_url(request):
    try:
        file_name = request.data.get("file_name")
        file_type = request.data.get("file_type")  # e.g., 'video/mp4'

        if not file_name or not file_type:
            return Response({'message': 'Missing video file info'}, status=400)

        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.ACCESS_KEY_ID,
            aws_secret_access_key=settings.SECRET_ACCESS_KEY
        )

        unique_id = uuid.uuid4().hex
        key = f"{settings.FOLDER_NAME}/{unique_id}_{file_name}"

        upload_url = s3_client.generate_presigned_url(
            ClientMethod='put_object',
            Params={'Bucket': settings.BUCKET_NAME, 'Key': key, 'ContentType': file_type},
            ExpiresIn=3600
        )

        return Response({
            'status': 200,
            'video': {
                'upload_url': upload_url,
                'file_url': f"https://{settings.BUCKET_NAME}.s3.amazonaws.com/{key}"
            }
        })

    except Exception as e:
        return Response({'status': 400, 'message': str(e)}, status=400)
    

@api_view(['POST'])
def generate_thumbnail_presigned_url(request):
    try:
        thumbnail_name = request.data.get("thumbnail_name")
        thumbnail_type = request.data.get("thumbnail_type")  # e.g., 'image/jpeg'

        if not thumbnail_name or not thumbnail_type:
            return Response({'message': 'Missing thumbnail info'}, status=400)

        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.ACCESS_KEY_ID,
            aws_secret_access_key=settings.SECRET_ACCESS_KEY
        )

        unique_id = uuid.uuid4().hex
        key = f"{settings.FOLDER_NAME}/{unique_id}_{thumbnail_name}"

        upload_url = s3_client.generate_presigned_url(
            ClientMethod='put_object',
            Params={'Bucket': settings.BUCKET_NAME, 'Key': key, 'ContentType': thumbnail_type},
            ExpiresIn=3600
        )

        return Response({
            'status': 200,
            'thumbnail': {
                'upload_url': upload_url,
                'file_url': f"https://{settings.BUCKET_NAME}.s3.amazonaws.com/{key}"
            }
        })

    except Exception as e:
        return Response({'status': 400, 'message': str(e)}, status=400)


@api_view(['POST'])
def create_post_new(request):
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        post_text = request.data.get('post_text')
        file_url = request.data.get("file")
        thumbnail_url = request.data.get("thumbnail")

        if not file_url or not thumbnail_url:
            return Response({'status': 400, 'message': 'Missing uploaded file URLs'}, status=400)

        user_instance = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key)
        # Step 3: Check subscription using get_object_or_404
        subscription = get_object_or_404(
            Subscription,
            user=user_instance,
            is_active=True,
            end_date__gte=now(),
            plan__name__in=["Pro Version", "Enterprise Version"]
        )

        secret_key = GenerateKey().gen_ambassadorsPost_key()
        post = AmbassadorsPost.objects.create(
            secret_key=secret_key,
            file=file_url,
            thumbnail=thumbnail_url,
            post_text=post_text,
            created_by=user_instance
        )

        serializer = AmbassadorsPostSerializer(post)
        return Response({'status': 200, 'message': 'Post created successfully', 'data': serializer.data}, status=200)

    except Exception as e:
        return Response({'status': 400, 'message': str(e)}, status=400)

###tags search
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tags
        fields = ['id', 'name', 'number_of_use']

@api_view(['GET'])
def tag_search(request):
    """
    GET /api/tags/?search=foo
    Returns all tags whose name contains "foo" (case-insensitive), ordered by number_of_use desc.
    If no `search` param is provided, returns all tags ordered by popularity.
    """
    search_term = request.GET.get('search')
    qs = Tags.objects.all()
    if search_term:
        qs = qs.filter(name__icontains=search_term)
    qs = qs.order_by('-number_of_use')
    serializer = TagSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)





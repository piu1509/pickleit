import random
import base64
import mimetypes
import stripe, time, json
from datetime import datetime, timedelta
from phonenumber_field.phonenumber import PhoneNumber

from django.conf import settings
from django.core.cache import cache
from django.db.models.functions import Cast
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.db.models import CharField, F, Value, Q, Sum
from django.shortcuts import render, redirect, HttpResponse
from django.core.cache.backends.base import DEFAULT_TIMEOUT

from apps.team.models import *
from apps.store.models import *
from apps.user.helpers import *
from apps.store.serializers import *
from apps.pickleitcollection.models import *
from apps.pickleitcollection.serializers import *

from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination

stripe.api_key = settings.STRIPE_PUBLIC_KEY
protocol = settings.PROTOCALL
api_key = settings.MAP_API_KEY
CACHE_TTL = getattr(settings, 'CACHE_TTL', DEFAULT_TIMEOUT)


#sponsor part start
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
                    start_date=request_data["start_date"],
                    end_date=request_data["end_date"],
                    approved_by_admin=True)
            save_payment.payment_for_ad = ad
            save_payment.save()
            context["charge_for"] = save_payment.payment_for
            context["expires_time"] = save_payment.expires_at
    
            return render(request,"success_payment.html", context)
        else: 
            return render(request,"failed_payment.html")
    except:
        return render(request,"failed_payment.html")


@api_view(('GET',))
def view_advertisement(request):
    """
    Displays the details of an advertisement.
    """
    data = {'status':'','data':'','message':''}
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
            get_user = check_user.first()
            if get_user.is_admin or get_user.is_sponsor or get_user.is_organizer:
                ad_data = Advertisement.objects.filter(id=check_ad.first().id).values("id","uuid","secret_key","name","image","script_text"
                                                                                            ,"url","approved_by_admin","description","start_date",
                                                                                            "end_date","created_by__first_name","created_by__last_name")
                if ad_data[0]["image"] != "":
                    ad_data[0]["image"] = base_url + ad_data[0]["image"]
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, ad_data,"data found"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","You are not a Sponsor"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def list_advertisement(request):
    """
    Fetches the list of all advertisements ordered by their name.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)       
        host = request.get_host()
        base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_admin:
                all_add = Advertisement.objects.all().order_by("name").values()
                for ad in all_add:
                    ad['image'] = base_url + ad['image']
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, all_add,"Data Found"
            else:
                all_add = Advertisement.objects.filter(created_by=get_user).order_by("name").values("id","uuid","secret_key","name","image","script_text"
                                                                                            ,"url","approved_by_admin","description","start_date","end_date","created_by__first_name","created_by__last_name")
                for ad in all_add:
                    ad['image'] = base_url + ad['image']
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, all_add,"Data Found"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


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
            all_ads = Advertisement.objects.filter(approved_by_admin=True, end_date__gte=today_date).order_by("-id")
            
            data_list = list(all_ads.values())
            random.shuffle(data_list)

            for ad in data_list:
                ad['image'] = base_url + ad['image']
            ad_list = "advertisement_list"
            if cache.get(ad_list):
                print("from cache............")
                advertisement_list = cache.get(ad_list)
            else:
                print("from db...............")
                advertisement_list = data_list
                cache.set(ad_list, advertisement_list)

            data["status"] = status.HTTP_200_OK
            data["data"] = advertisement_list
            data["message"] = "Data Found"
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


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
                get_advertisement.approved_by_admin = advertisement_status
                get_advertisement.save()
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, "",f"{get_advertisement.name} is updated successfully"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not admin or Advertisement is undefined"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)
#sponsor part end


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


# @api_view(('POST',))
# def allow_to_make_ambassador(request):
#     try:
#         responsee = {}
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         player_uuid = request.data.get('player_uuid')
#         player_secret_key = request.data.get('player_secret_key')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         check_payer = Player.objects.filter(uuid=player_uuid, secret_key=player_secret_key)
#         print(check_payer)
#         if check_user.exists() and check_payer.exists():
#             user_instance = check_user.first()
#             if user_instance.is_admin or user_instance.is_organizer:
#                 payer=check_payer.first().player.id
#                 User.objects.filter(id=int(payer)).update(is_ambassador = True)
#                 player_name= check_payer.first().player.first_name
#                 responsee = {'status': status.HTTP_200_OK, 'message': f'Now {player_name} is Ambassador'}
#             else:
#                 responsee = {'status': status.HTTP_200_OK, 'message': 'User not admin or organiger'}
#         else:
#             responsee = {'status': status.HTTP_400_BAD_REQUEST, 'message': 'Not found user or player'}     
#         return Response(responsee)
#     except Exception as e:
#         responsee = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
#         return Response(responsee, status=responsee['status'])


#change
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
    

# Added    
@api_view(('POST',))
def ambassador_follow_or_unfollow(request):
    """
    Is used for a user to follow or unfollow an ambassador.
    """
    data = {"status":"", "message":""}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        profile_uuid = request.data.get('profile_uuid')
        profile_secret_key = request.data.get('profile_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            check_ambassador = User.objects.filter(uuid=profile_uuid, secret_key=profile_secret_key)
            if check_ambassador.exists():
                get_ambassador=check_ambassador.first()
                check_ambassador_details = AmbassadorsDetails.objects.filter(ambassador=get_ambassador)
                if check_ambassador_details.exists():
                    ambassador = check_ambassador_details.first()
                else:
                    ambassador = AmbassadorsDetails.objects.create(ambassador=get_ambassador)
                if get_user in ambassador.follower.all():
                    ambassador.follower.remove(get_user)
                    
                    check_unfollower_details = AmbassadorsDetails.objects.filter(ambassador=get_user)  
                    if check_unfollower_details.exists():
                        unfollower = check_unfollower_details.first()
                    else:
                        unfollower = AmbassadorsDetails.objects.create(ambassador=get_user)              
                    unfollower.following.remove(get_ambassador)
                    data['status'] = status.HTTP_200_OK
                    data['message'] = "Successfully unfollowed."
                else:
                    ambassador.follower.add(get_user)
                    check_follower_details = AmbassadorsDetails.objects.filter(ambassador=get_user) 
                    if check_follower_details.exists():
                        follower = check_follower_details.first()
                    else:
                        follower = AmbassadorsDetails.objects.create(ambassador=get_user)               
                    follower.following.add(get_ambassador)
                    data['status'] = status.HTTP_200_OK
                    data['message'] = "Successfully followed."
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "Ambassador not found."                
        else:
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"
        return Response(data)            
    except Exception as e:
        data = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
        return Response(data)
    

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
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            check_ambassador = User.objects.filter(uuid=ambassador_uuid, secret_key=ambassador_secret_key)
            if check_ambassador.exists():
                get_ambassador=check_ambassador.first()
                check_ambassador_details = AmbassadorsDetails.objects.filter(ambassador=get_ambassador)
                if check_ambassador_details.exists():
                    get_ambassador_details = check_ambassador_details.first()
                else:
                    get_ambassador_details = AmbassadorsDetails.objects.create(ambassador=get_ambassador)
                if get_user in get_ambassador_details.follower.all():
                    all_followers = get_ambassador_details.follower.all().values("id","uuid","secret_key","username","email","first_name","last_name","phone","user_birthday","image","gender","street","city","state","country","postal_code","is_player","is_organizer","is_sponsor","is_ambassador","is_admin")
                    data["status"] = status.HTTP_200_OK
                    data["data"] ={"ambassador_followers": list(all_followers)}
                    data["follow"] = True
                    data["message"] = "You are following this ambassador."
                else:
                    data["status"] = status.HTTP_200_OK
                    data["follow"] = False
                    data["message"] = "You are not following this ambassador."
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "Ambassador not found."                
        else:
            data['status'] = status.HTTP_401_UNAUTHORIZED
            data['message'] = "Unauthorized access"
        return Response(data)            
    except Exception as e:
        data = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
        return Response(data)


class AmbassadorsPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmbassadorsPost
        fields = '__all__'


# @api_view(['POST'])
# def ambassadors_create_post(request):
#     try:
#         response_data = {}
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         post_text = request.data.get('post_text')
        
#         # Access the uploaded file
#         file = request.FILES.get("file")
        
#         if file:  # Check if the file is provided
#             # Get the MIME type from the file itself
#             mime_type = file.content_type
            
#             # if mime_type.startswith('video'):
#             if mime_type == 'video/mp4':
#                 # Check if the user exists
#                 user_instance = get_object_or_404(User, uuid=user_uuid, secret_key=user_secret_key)
#                 player_instance = Player.objects.filter(player=user_instance)
#                 # print(user_instance)
#                 # print(player_instance)
#                 # print(user_instance.is_ambassador)
#                 # Check if the user is an ambassador
#                 if user_instance.is_ambassador and player_instance.exists():
#                     # Create the post
#                     obj = GenerateKey()  # Assuming this is a function you have defined elsewhere
#                     secret_key = obj.gen_ambassadorsPost_key()
#                     post = AmbassadorsPost.objects.create(
#                         secret_key=secret_key,
#                         file=file, 
#                         post_text=post_text, 
#                         created_by=user_instance
#                     )
#                     # Save the file reference in the database
#                     post.save()
#                     serializer = AmbassadorsPostSerializer(post)
#                     response_data["status"] = status.HTTP_200_OK
#                     response_data["message"] = "Post successfully uploaded"
#                     response_data["data"] = serializer.data
#                 else:
#                     response_data["status"] = status.HTTP_400_BAD_REQUEST
#                     response_data["data"] = []
#                     response_data["message"] = "This user is not an ambassador or not in player list"
#             else:
#                 response_data["status"] = status.HTTP_400_BAD_REQUEST
#                 response_data["data"] = []
#                 response_data["message"] = "Uploaded file is not a video"
#         else:
#             response_data["status"] = status.HTTP_400_BAD_REQUEST
#             response_data["data"] = []
#             response_data["message"] = "File not provided"
            
#         return Response(response_data)
#     except Exception as e:
#         response_data = {'status': status.HTTP_400_BAD_REQUEST, 'message': str(e)}
#         return Response(response_data, status=response_data['status'])


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

# @api_view(('GET',))
# def ambassadors_view_all_allow_post(request):
#     response_data = {}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        
#         # Get the protocol and host from the request
#         protocol = 'https' if request.is_secure() else 'http'
#         host = request.get_host()
        
#         # Construct the complete URL for media files
#         media_base_url = f"{protocol}://{host}"
        
#         if check_user.exists():
#             data = AmbassadorsPost.objects.all()
#             paginator = PageNumberPagination()
#             paginator.page_size = 2  # Adjust as needed
#             result_page = paginator.paginate_queryset(data, request)
#             serialized_data = AmbassadorsPostSerializer(result_page, many=True)
            
#             for post in serialized_data.data:
#                 if post['file']:
#                     # Prepare file data in the format you specified
#                     filename = post['file'].split("/")[-1]
#                     file_path = post['file'].replace(media_base_url, '')
#                     path = f".{file_path}"
#                     file_data = [(filename, open(path, 'rb'), 'application/octet-stream')]
#                     # print(file_data)
#                     post['file_data_str'] = str(file_data)
                    
#                 # Adjust user image URL
#                 user_details = User.objects.filter(id=post['created_by']).values("uuid", "secret_key", "first_name", "last_name", "image")
#                 for user in user_details:
#                     user['image'] = media_base_url + '/media/' + user['image']
#                 post['created_by'] = list(user_details)
                
#                 # Calculate total likes count
#                 post['total_likes_count'] = len(post['likes'])
            
#             return paginator.get_paginated_response(serialized_data.data)
#         else:
#             response_data["status"] = status.HTTP_400_BAD_REQUEST
#             response_data["result"] = []
#             response_data["message"] = "User does not exist"
#             return Response(response_data)
#     except Exception as e:
#         response_data = {'status': status.HTTP_400_BAD_REQUEST, 'result': [], 'message': str(e)}
#         return Response(response_data)


# ##piu
# @api_view(('POST',))
# def add_advertiser_facility(request):
#     """
#     Is used for a sponsor to add any advertiser facility.
#     """
#     data = {}
#     try:
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
        
#         facility_name = request.data.get('facility_name')
#         facility_type = request.data.get('facility_type')
#         court_type = request.data.get('court_type')
#         membership_type = request.data.get('membership_type')
#         number_of_courts = request.data.get('number_of_courts')
#         complete_address = request.data.get('complete_address')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
#         if check_user.exists():
#             get_user = check_user.first()
#             if get_user.is_sponsor == True:
#                 full_address = complete_address
#                 state, country, pincode, latitude , longitude = get_address_details(full_address, api_key)

#                 obj = GenerateKey()
#                 facility_key = obj.gen_facility_key()
#                 facility = AdvertiserFacility.objects.create(secret_key=facility_key, facility_name=facility_name, facility_type=facility_type, court_type=court_type, membership_type=membership_type, number_of_courts=number_of_courts, complete_address=complete_address, created_by=get_user)
#                 facility.latitude = latitude
#                 facility.longitude = longitude
#                 facility.save()
#                 data['status'], data['message'] = status.HTTP_201_CREATED, "Facility created successfully."
#             else:
#                 data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User is not a sponsor, so does not have permission."
#         else:
#             data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)


# @api_view(('GET',))
# def advertiser_facility_list(request):
#     """
#     Displays the list of all facilities added by sponsor.
#     """
#     data = {}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)        
#         if check_user.exists():
#             data['data'] = AdvertiserFacility.objects.filter(created_by=check_user.first()).values()
#             data['status'] = status.HTTP_200_OK
#             data['message'] = "Data found."
#         else:
#             data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)


# @api_view(('GET',))
# def advertiser_facility_list_for_all(request):
#     """
#     Displays the list of all advertiser facilities.
#     """
#     data = {}
#     try:
#         data['data'] = AdvertiserFacility.objects.all().values()
#         data['status'] = status.HTTP_200_OK
#         data['message'] = "Data found."
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)



# @api_view(('POST',))
# def edit_advertiser_facility(request):
#     """
#     Is used for sponsor to edit the details of an advertiser facility.
#     """
#     data = {}
#     try:
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         facility_uuid = request.data.get('facility_uuid')
#         facility_secret_key = request.data.get('facility_secret_key')        
#         facility_name = request.data.get('facility_name')
#         facility_type = request.data.get('facility_type')
#         court_type = request.data.get('court_type')
#         membership_type = request.data.get('membership_type')
#         number_of_courts = request.data.get('number_of_courts')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)        
#         if check_user.exists():
#             get_user = check_user.first()
#             if get_user.is_sponsor == True:
#                 check_facility = AdvertiserFacility.objects.filter(uuid=facility_uuid, secret_key=facility_secret_key)
#                 if check_facility.exists():
#                     check_facility.update(facility_name=facility_name, facility_type=facility_type, court_type=court_type, membership_type=membership_type, number_of_courts=number_of_courts)
#                     data['status'], data['message'] = status.HTTP_200_OK, "Facility edited successfully."
#                 else:
#                     data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "Facility not found."
#             else:
#                 data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User is not a sponsor, so does not have permission.."
#         else:
#             data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)


# @api_view(('POST',))
# def delete_advertiser_facility(request):
#     """
#     Is used for sponsor to delete an advertiser facility.
#     """
#     data = {}
#     try:
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         facility_uuid = request.data.get('facility_uuid')
#         facility_secret_key = request.data.get('facility_secret_key')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)        
#         if check_user.exists():
#             get_user = check_user.first()
#             if get_user.is_sponsor == True:
#                 check_facility = AdvertiserFacility.objects.filter(uuid=facility_uuid, secret_key=facility_secret_key)
#                 if check_facility.exists():
#                     get_facility = check_facility.first()
#                     get_facility.delete()
#                     data["status"], data["message"] = status.HTTP_204_NO_CONTENT, "Facility deleted successfully."
#                 else:
#                     data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "Facility not found."
#             else:
#                 data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User is not a sponsor, so does not have permission."
#         else:
#             data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)



# @api_view(('GET',))
# def view_advertiser_facility(request):
#     """
#     Displays the details of an advertiser facility.
#     """
#     data = {}
#     try:
#         user_uuid = request.GET.get('user_uuid')
#         user_secret_key = request.GET.get('user_secret_key')
#         facility_uuid = request.GET.get('facility_uuid')
#         facility_secret_key = request.GET.get('facility_secret_key')
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key) 
#         if check_user.exists():
#             check_facility = AdvertiserFacility.objects.filter(uuid=facility_uuid, secret_key=facility_secret_key)
#             if check_facility.exists():
#                 data['status'] = status.HTTP_200_OK
#                 data['data'] = check_facility.values()                
#                 data['message'] = "Data found"
#             else:
#                 data['status'] = status.HTTP_404_NOT_FOUND
#                 data['message'] = "Facility not found"
#         else:
#             data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found."
#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)


# def cron_job():
#     # Your code for the periodic task goes here
#     # For example, you might update a database record or send an email
#     check_organizer = User.objects.filter(is_organizer=True)
#     for i in range(len(check_organizer)):
#         get_organizer = check_organizer[i]
#         expires_time = datetime.fromisoformat(str(get_organizer.is_organizer_expires_at))
#         current_time = datetime.fromisoformat(str(datetime.now())+ "+00:00")
#         if expires_time < current_time:
#             get_organizer.is_organizer = False
#             get_organizer.is_organizer_expires_at = None
#             get_organizer.save()
#             print(f"expires_time - {expires_time} is earlier than current_time - {current_time}")
#         else:
#             print(f"{expires_time} is not earlier than {current_time}")
#     print("cron_job..............................cron_job")

# schedule.every(1).seconds.do(cron_job)

# def cron_job_wrapper():
#     while True:
#         schedule.run_pending()
#         time.sleep(55)

# # Run the cron_job_wrapper in a separate thread
# cron_thread = threading.Thread(target=cron_job_wrapper)
# cron_thread.daemon = True
# cron_thread.start()

# # This part will only be executed when using the development server.
# if __name__ == "__main__":
#     # Start the development server
#     from django.core.management import execute_from_command_line
#     execute_from_command_line(["manage.py", "runserver"])


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


## #update #Riju
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

## #update #Riju
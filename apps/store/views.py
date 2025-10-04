import stripe, json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404

from apps.team.models import *
from apps.user.helpers import *
from apps.store.models import *
from apps.store.serializers import *
from apps.pickleitcollection.models import *
from apps.team.views import notify_edited_player

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Sum, F, Min, Max
from django.core.cache.backends.base import DEFAULT_TIMEOUT

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination

protocol = settings.PROTOCALL
api_key = settings.MAP_API_KEY
stripe.api_key = settings.STRIPE_PUBLIC_KEY


@api_view(('POST',))
def store_category_add(request):
    """
    Adds a new merchandise category for product.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        category_name = request.data.get('category_name')
        category_image = request.FILES.get('category_image')
        print("category_image",category_image)
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            if get_user.is_admin :
                if category_name and len(category_name) > 0 :
                    obj = GenerateKey()
                    category_key = obj.gen_category_key()
                    cat = MerchandiseStoreCategory(secret_key=category_key,name=category_name,created_by_id=get_user.id,
                                                   image=category_image)
                    cat.save()
                    data["status"], data["data"], data["message"] = status.HTTP_200_OK, "",f"{category_name} created successfully"
                else:
                    data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","Category name is undefined"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not Admin"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def store_category_edit(request):
    """
    Is used to edit the details of merchandise category for product.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        category_id = request.data.get('category_id')
        category_name = request.data.get('category_name')
        category_image = request.FILES.get('category_image')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_cat = MerchandiseStoreCategory.objects.filter(id=category_id)
        if check_user.exists() :
            get_user = check_user.first()
            if get_user.is_admin :
                get_cat = check_cat.first()
                get_cat.name = category_name
                get_cat.image = category_image
                get_cat.save()
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, "",f"{category_name} edited successfully"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","Category undefined or User is not Admin"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def store_category_view(request):
    """
    Displays the details of a merchandise category.
    """
    data = {'status':'','data':[],'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        cat_id = request.GET.get('cat_id')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_category = MerchandiseStoreCategory.objects.filter(id=cat_id)
        if check_user.exists() and check_category.exists():            
            get_category = check_category.first()
            serializer = MerchandiseStoreCategorySerializer(get_category)
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, serializer.data,"Data Found"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, [],"User or category not found."
    except Exception as e :
        data['status'], data["data"], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(('GET',))
def store_category_list(request):
    """
    Displays the list of all merchandise category.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            all_category = MerchandiseStoreCategory.objects.all().order_by("id")
            serializer = MerchandiseStoreCategorySerializer(all_category, many=True)
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, serializer.data,"Data Found"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, [],"User not found"
    except Exception as e :
        data['status'], data["data"], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


# @api_view(('POST',))
# def store_product_add(request):
#     """
#     An admin or an organizer can add a store product.
#     """
#     data = {'status': '', 'data': [], 'message': ''}
#     # try:
#     user_uuid = request.data.get('user_uuid')
#     user_secret_key = request.data.get('user_secret_key')
#     category_id = request.data.get('category_id')
#     product_name = request.data.get('product_name')
#     store_name = request.data.get('store_name')
#     leagues_for_id = request.data.getlist('leagues_for_id')
#     product_description = request.data.get('product_description')
#     product_specifications = request.data.get('product_specifications')
#     advertisement_image = request.FILES.get('advertisement_image')
#     if advertisement_image is not None:
#         image = advertisement_image
#     else:
#         image = None
#     # Validate user
#     check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key).first()
#     if not check_user:
#         data["status"] = status.HTTP_404_NOT_FOUND
#         data["message"] = "User not found"
#         return Response(data)

#     if not (check_user.is_admin or check_user.is_organizer):
#         data["status"] = status.HTTP_403_FORBIDDEN
#         data["message"] = "User is not Admin or Organizer"
#         return Response(data)

#     # Validate category
#     get_category = MerchandiseStoreCategory.objects.filter(id=category_id).first()
#     if not get_category:
#         data["status"] = status.HTTP_404_NOT_FOUND
#         data["message"] = "Category not found"
#         return Response(data)

#     # Generate product key
#     obj = GenerateKey()
#     product_key = obj.gen_product_key()

#     # Create product
#     save_product = MerchandiseStoreProduct.objects.create(
#         secret_key=product_key,
#         category=get_category,
#         name=product_name,
#         description=product_description,
#         specifications=product_specifications,
#         created_by=check_user,
#         advertisement_image=image
#     )

#     if store_name not in ['null', None, ""]:
#         save_product.store_name = store_name
#         save_product.save()
#     # Add specifications
#     specifications_data = json.loads(request.data.get('specifications_data', '[]'))
#     for spec_data in specifications_data:
#         product_specification = MerchandiseProductSpecification.objects.create(
#             product=save_product,
#             size=spec_data.get('size'),
#             old_price=spec_data.get('oldPrice'),
#             current_price=spec_data.get('currentPrice'),
#             total_product=spec_data.get('totalProduct'),
#         )

#         # Add highlights for each specification
#         highlights_data = spec_data.get('highlights', [])
#         for highlight in highlights_data:
#             ProductSpecificationHighlights.objects.create(
#                 specification=product_specification,
#                 highlight_key=highlight.get('key'),
#                 highlight_des=highlight.get('description'),
#             )

#     # Add images
#     for image in request.FILES.getlist('images'):
#         MerchandiseProductImages.objects.create(product=save_product, image=image)

#     # Add leagues
#     for league_id in leagues_for_id:
#         get_league = Leagues.objects.filter(id=league_id).first()
#         if get_league:
#             save_product.leagues_for.add(get_league)

#     product_list_name = f'{check_user.id}_product_list'
#     if cache.get(product_list_name):
#         cache.delete(product_list_name)
        
#     data["status"] = status.HTTP_200_OK
#     data["data"] = {'product': save_product.id}
#     data["message"] = f"{product_name} created successfully"

#     # except Exception as e:
#     #     data['status'] = status.HTTP_400_BAD_REQUEST
#     #     data['message'] = str(e)

#     return Response(data)



@api_view(('POST',))
def store_product_add(request):
    """
    An admin or an organizer can add a store product.
    """
    data = {'status': '', 'data': [], 'message': ''}
    # try:
    user_uuid = request.data.get('user_uuid')
    user_secret_key = request.data.get('user_secret_key')
    category_id = request.data.get('category_id')
    product_name = request.data.get('product_name')
    store_name = request.data.get('store_name')
    # leagues_for_id = request.data.getlist('leagues_for_id')
    product_description = request.data.get('product_description')
    product_specifications = request.data.get('product_specifications')
    advertisement_image = request.FILES.get('advertisement_image', None)
    leagues_for_id = request.data.get('leagues_for_id')

    # Normalize and sanitize input
    if isinstance(leagues_for_id, str):
        leagues_for_id = [x.strip() for x in leagues_for_id.split(',') if x.strip()]
    elif isinstance(leagues_for_id, list):
        leagues_for_id = [str(x).strip() for x in leagues_for_id if str(x).strip()]
    else:
        leagues_for_id = []

    # Validate user
    check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key).first()
    if not check_user:
        data["status"] = status.HTTP_404_NOT_FOUND
        data["message"] = "User not found"
        return Response(data)

    # Validate category
    get_category = MerchandiseStoreCategory.objects.filter(id=category_id).first()
    if not get_category:
        data["status"] = status.HTTP_404_NOT_FOUND
        data["message"] = "Category not found"
        return Response(data)

    # Specifications
    specifications_data = json.loads(request.data.get('specifications_data', '[]'))
    seen_combinations = set()
    for spec in specifications_data:
        size = (spec.get('size') or '').strip().lower() or None
        color = (spec.get('color') or '').strip().lower() or None

        if size and color:
            key = f'{size}-{color}'
        elif size and not color:
            key = f'{size}-none'
        elif color and not size:
            key = f'none-{color}'
        else:
            key = 'none-none'

        if key in seen_combinations:
            return Response({
                "status": 200,
                "data": [],
                "message": "Duplicate specification detected: each size/color combination must be unique (case-insensitive)."
            })

        seen_combinations.add(key)

    # Generate product key
    obj = GenerateKey()
    product_key = obj.gen_product_key()

    # Create product
    save_product = MerchandiseStoreProduct.objects.create(
        secret_key=product_key,
        category=get_category,
        name=product_name,
        description=product_description,
        specifications=product_specifications,
        created_by=check_user,
        advertisement_image=advertisement_image
    )
        
    if store_name not in ['null', None, ""]:
        save_product.store_name = store_name
        save_product.save()
    
    has_single_spec = request.data.get('has_single_spec', 'false').lower() == 'true'
    save_product.has_single_spec = has_single_spec
    save_product.save()

    # Handle single-spec product (only the first spec will be saved)
    if has_single_spec:
        if specifications_data:
            spec_data = specifications_data[0]  # Only first specification
            product_specification = MerchandiseProductSpecification.objects.create(
                product=save_product,
                size=spec_data.get('size', ''),  # Size can be blank
                color=spec_data.get('color', ''), # color can be blank
                old_price=spec_data.get('oldPrice'),  # regular price
                current_price=spec_data.get('currentPrice'),# sale price 
                total_product=spec_data.get('totalProduct'),
            )
            highlights_data = spec_data.get('highlights', [])
            for highlight in highlights_data:
                ProductSpecificationHighlights.objects.create(
                    specification=product_specification,
                    highlight_key=highlight.get('key'),
                    highlight_des=highlight.get('description'),
                )
    else:
        # Allow multiple specifications
        for spec_data in specifications_data:
            product_specification = MerchandiseProductSpecification.objects.create(
                product=save_product,
                size=spec_data.get('size', ''),
                color=spec_data.get('color', ''), 
                old_price=spec_data.get('oldPrice'),  # regular price
                current_price=spec_data.get('currentPrice'),# sale price 
                total_product=spec_data.get('totalProduct'),
            )
            highlights_data = spec_data.get('highlights', [])
            for highlight in highlights_data:
                ProductSpecificationHighlights.objects.create(
                    specification=product_specification,
                    highlight_key=highlight.get('key'),
                    highlight_des=highlight.get('description'),
                )

    # Add images
    for image in request.FILES.getlist('images'):
        MerchandiseProductImages.objects.create(product=save_product, image=image)

    # Add leagues
    for league_id in leagues_for_id:
        try:
            league = Leagues.objects.filter(id=int(league_id)).first()
            if league:
                save_product.leagues_for.add(league)
        except (ValueError, TypeError):
            continue

    data["status"] = status.HTTP_200_OK
    data["data"] = {'product': save_product.id}
    data["message"] = f"{product_name} created successfully"

    # except Exception as e:
    #     data['status'] = status.HTTP_400_BAD_REQUEST
    #     data['message'] = str(e)

    return Response(data)


@api_view(['GET'])
def get_product_details(request):
    """
    Retrieves detailed info for one store product, only if requested by its creator.
    """
    resp = {'status': None, 'data': {}, 'message': ''}

    # 1) Required params
    user_uuid  = request.GET.get('user_uuid')
    product_id = request.GET.get('product_id')
    if not user_uuid or not product_id:
        resp.update(
            status=status.HTTP_400_BAD_REQUEST,
            message="`user_uuid` and `product_id` are required."
        )
        return Response(resp)

    # 2) Fetch user
    try:
        user = User.objects.get(uuid=user_uuid)
    except User.DoesNotExist:
        resp.update(status=status.HTTP_404_NOT_FOUND, message="User not found.")
        return Response(resp)

    # 3) Fetch product with related data
    try:
        qs = MerchandiseStoreProduct.objects.select_related('category').prefetch_related(
            'leagues_for',
            'specificProduct__specificHighlight',
            'productImages'
        )
        product = qs.get(id=product_id)
    except MerchandiseStoreProduct.DoesNotExist:
        resp.update(status=status.HTTP_404_NOT_FOUND, message="Product not found.")
        return Response(resp)

    # 4) Permission check
    if product.created_by_id != user.id:
        resp.update(
            status=status.HTTP_403_FORBIDDEN,
            message="You do not have permission to view this product."
        )
        return Response(resp)

    # 5) Build payload
    try:
        # Basic info
        payload = {
            "id":               product.id,
            "uuid":             str(product.uuid),
            "secret_key":       product.secret_key,
            "category_id":      product.category.id if product.category else None,
            "category_name":    product.category.name if product.category else None,
            "name":             product.name,
            "store_name":       product.store_name,
            "description":      product.description,
            "has_single_spec":  product.has_single_spec,
            "rating":           product.rating,
            "rating_count":     product.rating_count,
            "specifications" :  product.specifications,
            "leagues_for_id":   product.leagues_for.all().first().id if product.leagues_for.exists() else None,
            "leagues_for_name": product.leagues_for.all().first().name if product.leagues_for.exists() else None,
            "advertisement_image": product.advertisement_image.url if product.advertisement_image else None,
            "product_varity_data": [],
            "product_images": [
                img.image.url
                for img in product.productImages.all()
            ],
        }

        # Specifications + highlights
        for spec in product.specificProduct.all():
            payload["product_varity_data"].append({
                "id":               spec.id,
                "size":             spec.size,
                "color":            spec.color,
                "old_price":        spec.old_price,
                "current_price":    spec.current_price,
                "discount":         spec.discount,
                "total_product":    spec.total_product,
                "available_product":spec.available_product,
                "highlights": list(
                    spec.specificHighlight.all().values('id', 'highlight_key', 'highlight_des')
                )
            })

        resp.update(
            status=status.HTTP_200_OK,
            message="Product details found.",
            data=payload
        )
        return Response(resp)

    except Exception as e:
        # Catch-all for unexpected errors
        resp.update(
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"An error occurred: {str(e)}"
        )
        return Response(resp)     



@api_view(('GET',))
def store_product_list(request):
    """
    Displays the list of all store products.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            all_product = MerchandiseStoreProduct.objects.filter().order_by("name")
            paginator = PageNumberPagination()
            paginator.page_size = 20  # Set the page size to 20
            result_page = paginator.paginate_queryset(all_product, request)
            serializer = ProductListSerializer(result_page, many=True)
            serialized_data = serializer.data
            for item in serialized_data:
                if get_user.id in item["is_love"]:
                    item["wishlist_status"] = True
                else:
                    item["wishlist_status"] = False
            if not serialized_data:
                data["status"] = status.HTTP_200_OK
                data["count"] = 0
                data["previous"] = None
                data["next"] = None
                data["data"] = []
                data["message"] = "No Result found"
            else:
                paginated_response = paginator.get_paginated_response(serialized_data)
                data["status"] = status.HTTP_200_OK
                data["count"] = paginated_response.data["count"]
                data["previous"] = paginated_response.data["previous"]
                data["next"] = paginated_response.data["next"]
                data["data"] = paginated_response.data["results"]
                data["message"] = "Data found"
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, serializer.data,"Data Found"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, [],"User not found"
    except Exception as e :
        data['status'], data['data'], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)


@api_view(('GET',))
def my_store_product_list(request):
    """
    Displays the list of store products added by the user itself.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            all_product = MerchandiseStoreProduct.objects.filter(created_by=get_user).order_by("-id")
            paginator = PageNumberPagination()
            paginator.page_size = 20  # Set the page size to 20
            result_page = paginator.paginate_queryset(all_product, request)
            serializer = ProductListSerializer(result_page, many=True)
            serialized_data = serializer.data
            if not serialized_data:
                data["status"] = status.HTTP_200_OK
                data["count"] = 0
                data["previous"] = None
                data["next"] = None
                data["data"] = []
                data["message"] = "No Result found"
            else:
                paginated_response = paginator.get_paginated_response(serialized_data)
                data["status"] = status.HTTP_200_OK
                data["count"] = paginated_response.data["count"]
                data["previous"] = paginated_response.data["previous"]
                data["next"] = paginated_response.data["next"]
                data["data"] = paginated_response.data["results"]
                data["message"] = "Data found"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, [], "User not found"
    except Exception as e :
        data['status'], data["data"], data['message'] = status.HTTP_400_BAD_REQUEST, [], f"{e}"
    return Response(data)




@api_view(('POST',))
def store_product_delete(request):
    """
    Allows an admin or an organizer to delete a store product.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        product_id = request.data.get('product_id')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            check_product = MerchandiseStoreProduct.objects.filter(id=product_id)
            if get_user.is_admin or get_user.is_organizer:
                if not check_product.exists():
                    data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","Product is not found"
                    return Response(data) 
                else:
                    check_product.delete()
                    data["status"], data["message"] = status.HTTP_200_OK, "Product deleted successfully"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not Admin or Organizer"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)



@api_view(('GET',))
def store_product_view(request):
    """
    Displays the details of a particular store product.
    """
    data = {'status':'','data':[],'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        product_uuid = request.GET.get('product_uuid')
        product_secret_key = request.GET.get('product_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_product = MerchandiseStoreProduct.objects.filter(uuid=product_uuid,secret_key=product_secret_key)       
        if check_user.exists() :
            get_user = check_user.first()
            if check_product.exists() :
                get_product = check_product.first()
                serializer = MerchandiseStoreProductSerializer(get_product)
                serializer_data = serializer.data
                if get_user.id in serializer_data['is_love']:
                    serializer_data['wishlist_status'] = True
                else:
                    serializer_data['wishlist_status'] = False
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, serializer_data,"Data Found"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, [],"Product is undefined"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, [],"User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# @api_view(['GET'])
# def product_color_size_varieties(request):
#     data = {'status': '', 'message': ''}
#     try:
#         product_id = request.GET.get('product_id')
#         selected_color = request.GET.get('color')
#         selected_size = request.GET.get('size')

#         if not product_id:
#             data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "product_id is required"
#             return Response(data)

#         product = MerchandiseStoreProduct.objects.filter(id=product_id).first()
#         if not product:
#             data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "Product not found"
#             return Response(data)

#         specifications = MerchandiseProductSpecification.objects.filter(product=product)

#         size_order = ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL']

#         # Get distinct non-null colors and sizes
#         all_colors = list(
#             specifications.exclude(color__isnull=True).exclude(color__exact='').values_list('color', flat=True).distinct()
#         )
#         all_sizes = list(
#             specifications.exclude(size__isnull=True).exclude(size__exact='').values_list('size', flat=True).distinct()
#         )

#         # Determine selected spec
#         selected_spec = None
#         if selected_color and selected_size:
#             selected_spec = specifications.filter(color__iexact=selected_color, size__iexact=selected_size).first()
#         elif selected_color:
#             selected_spec = specifications.filter(color__iexact=selected_color).first()
#         elif selected_size:
#             selected_spec = specifications.filter(size__iexact=selected_size).first()
#         elif specifications.exists():
#             selected_spec = random.choice(list(specifications))

#         if selected_spec:
#             selected_color = selected_spec.color
#             selected_size = selected_spec.size

#         # Determine enabled sets
#         enabled_sizes = set(
#             specifications.filter(color__iexact=selected_color).values_list('size', flat=True)
#         ) if selected_color else set(all_sizes)

#         enabled_colors = set(
#             specifications.filter(size__iexact=selected_size).values_list('color', flat=True)
#         ) if selected_size else set(all_colors)

#         # Sort sizes based on defined order
#         sorted_sizes = sorted(
#             all_sizes, key=lambda x: size_order.index(x) if x in size_order else 999
#         )

#         # Construct final color and size lists
#         color_list = [
#             {
#                 'value': color,
#                 'enabled': color in enabled_colors,
#                 'selected': color.lower() == selected_color.lower() if selected_color else False
#             }
#             for color in all_colors
#         ]

#         size_list = [
#             {
#                 'value': size,
#                 'enabled': size in enabled_sizes,
#                 'selected': size.lower() == selected_size.lower() if selected_size else False
#             }
#             for size in sorted_sizes
#         ]

#         # Response data
#         data['status'] = status.HTTP_200_OK
#         data['product_id'] = product_id
#         data['available_colors'] = color_list
#         data['available_sizes'] = size_list

#         if selected_spec:
#             data['selected_color'] = selected_spec.color
#             data['selected_size'] = selected_spec.size
#             data['old_price'] = selected_spec.old_price
#             data['current_price'] = selected_spec.current_price
#             data['available_product'] = selected_spec.available_product
#             data['discount'] = round(selected_spec.discount, 2) if selected_spec.discount else 0
#         else:
#             data['selected_color'] = selected_color
#             data['selected_size'] = selected_size
#             data['available_product'] = None
#             data['old_price'] = None
#             data['current_price'] = None
#             data['discount'] = 0

#         data['message'] = 'Specifications retrieved successfully'

#     except Exception as e:
#         data['status'], data['message'] = status.HTTP_500_INTERNAL_SERVER_ERROR, str(e)

#     return Response(data)


@api_view(['GET'])
def product_color_size_varieties(request):
    data = {'status': '', 'message': ''}
    try:
        product_id = request.GET.get('product_id')
        selected_color = request.GET.get('color')
        selected_size = request.GET.get('size')

        if not product_id:
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "product_id is required"
            return Response(data)

        product = MerchandiseStoreProduct.objects.filter(id=product_id).first()
        if not product:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "Product not found"
            return Response(data)

        specifications = MerchandiseProductSpecification.objects.filter(product=product)

        named_size_order = ['Xxs', 'Xs', 'S', 'M', 'L', 'Xl', 'Xxl', 'Xxxl']

        def normalize(val):
            return val.strip().capitalize() if val else None

        def size_sort_key(size):
            try:
                return (0, int(size))  # Numeric size
            except ValueError:
                return (1, named_size_order.index(size) if size in named_size_order else 999)

        # Normalize and collect all sizes/colors
        all_colors_raw = [
            normalize(spec.color)
            for spec in specifications
            if spec.color
        ]
        all_sizes_raw = [
            normalize(spec.size)
            for spec in specifications
            if spec.size
        ]

        all_colors_set = set(all_colors_raw)
        all_sizes_set = set(all_sizes_raw)

        # Check if all sizes are numeric
        is_all_numeric = all(size.isdigit() for size in all_sizes_set)

        # Sort sizes
        if is_all_numeric:
            all_sizes = sorted(all_sizes_set, key=lambda x: int(x))
        else:
            all_sizes = sorted(all_sizes_set, key=size_sort_key)

        # Sort colors alphabetically
        all_colors = sorted(all_colors_set)

        # Normalize selected input
        selected_color = normalize(selected_color)
        selected_size = normalize(selected_size)

        # Determine selected spec
        selected_spec = None
        if selected_color and selected_size:
            selected_spec = specifications.filter(color__iexact=selected_color, size__iexact=selected_size).first()
        elif selected_color:
            selected_spec = specifications.filter(color__iexact=selected_color).first()
        elif selected_size:
            selected_spec = specifications.filter(size__iexact=selected_size).first()
        elif specifications.exists():
            selected_spec = random.choice(list(specifications))

        if selected_spec:
            selected_color = normalize(selected_spec.color)
            selected_size = normalize(selected_spec.size)

        # Enabled sizes and colors
        enabled_sizes = set(
            normalize(spec.size)
            for spec in specifications
            if spec.color and normalize(spec.color) == selected_color
        ) if selected_color else set(all_sizes)

        enabled_colors = set(
            normalize(spec.color)
            for spec in specifications
            if spec.size and normalize(spec.size) == selected_size
        ) if selected_size else set(all_colors)

        # Construct response lists
        color_list = [
            {
                'value': color,
                'enabled': color in enabled_colors,
                'selected': color == selected_color
            }
            for color in all_colors
        ]

        size_list = [
            {
                'value': size,
                'enabled': size in enabled_sizes,
                'selected': size == selected_size
            }
            for size in all_sizes
        ]

        # Prepare final response
        data['status'] = status.HTTP_200_OK
        data['product_id'] = product_id
        data['available_colors'] = color_list
        data['available_sizes'] = size_list

        if selected_spec:
            data.update({
                'selected_color': selected_color,
                'selected_size': selected_size,
                'old_price': selected_spec.old_price,
                'current_price': selected_spec.current_price,
                'available_product': selected_spec.available_product,
                'discount': round(selected_spec.discount, 2) if selected_spec.discount else 0
            })
        else:
            data.update({
                'selected_color': selected_color,
                'selected_size': selected_size,
                'available_product': None,
                'old_price': None,
                'current_price': None,
                'discount': 0
            })

        data['message'] = 'Specifications retrieved successfully'

    except Exception as e:
        data['status'], data['message'] = status.HTTP_500_INTERNAL_SERVER_ERROR, str(e)

    return Response(data)


@api_view(('GET',))
def category_wise_product_filter(request):
    """
    Filters out the store products for a given category.
    """
    data = {'status':'','data':[],'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        category_id = request.GET.get('category_id')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            get_product = MerchandiseStoreProduct.objects.filter(category_id=category_id).order_by("name")
            
            serializer = ProductListSerializer(get_product, many=True)
            serialized_data = serializer.data
            for item in serialized_data:
                if get_user.id in item["is_love"]:
                    item["wishlist_status"] = True
                else:
                    item["wishlist_status"] = False
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, serialized_data,"Data Found"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, [],"User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def search_wise_product_filter(request):
    """
    Filters the list of products according to search.
    """
    data = {'status':'','data':[],'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_name = request.GET.get('search_name')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            products = MerchandiseStoreProduct.objects.all()
            print(products)
            get_product = MerchandiseStoreProduct.objects.filter(
                Q(category__name__icontains=search_name) | Q(name__icontains=search_name) |
                Q(leagues_for__name__icontains=search_name) |Q(description__icontains=search_name) |
                Q(specifications__icontains=search_name) | Q(rating__icontains=search_name) |
                Q(store_name__icontains=search_name)
                ).order_by("name").distinct()
            for product in get_product:
                search_log, created = ProductSearchLog.objects.get_or_create(product=product)
                if not created:
                    search_log.search_count = F('search_count') + 1
                    search_log.save()

            paginator = PageNumberPagination()
            paginator.page_size = 5 
            result_page = paginator.paginate_queryset(get_product, request)
            serializer = ProductListSerializer(result_page, many=True)
            serialized_data = serializer.data
            
            for item in serialized_data:
                if get_user.id in item["is_love"]:
                    item["wishlist_status"] = True
                else:
                    item["wishlist_status"] = False
            paginated_response = paginator.get_paginated_response(serialized_data)
            data["status"] = status.HTTP_200_OK
            data["count"] = paginated_response.data["count"]
            data["previous"] = paginated_response.data["previous"]
            data["next"] = paginated_response.data["next"]
            data["data"] = paginated_response.data["results"]
            data["message"] = "Products are fetched successfully."
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, [],"User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# @api_view(('POST',))
# def store_product_edit(request):
#     """
#     An admin or an organizer can edit the details of a product.
#     """
#     data = {'status':'','data':'','message':''}
#     try:        
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         category_id = request.data.get('category_id')
#         product_id = request.data.get('product_id')
#         product_name = request.data.get('product_name')
        
#         product_description = request.data.get('product_description')
#         product_specifications = request.data.get('product_specifications')
#         product_price = request.data.get('product_price')
#         product_image = request.FILES.get('product_image')
#         product_size = request.data.get('product_size')
#         product_size = json.loads(product_size)
        
#         check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
#         if check_user.exists() :
#             get_user = check_user.first()
#             check_category = MerchandiseStoreCategory.objects.filter(id=category_id)
#             check_product = MerchandiseStoreProduct.objects.filter(id=product_id)
#             if get_user.is_admin or get_user.is_organizer:
#                 if not check_product.exists() or not check_category.exists() or not product_name or not product_price :
#                     data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","Category name or Product Name or Product Price is undefined"
#                     return Response(data) 
#                 else:
#                     get_product = check_product.first()
#                     get_product.category_id = category_id
#                     get_product.name = product_name
#                     get_product.description = product_description
#                     get_product.specifications = product_specifications
#                     get_product.price = product_price
#                     get_product.image = product_image
#                     get_product.size = product_size
#                     get_product.save()
                    
#                     data["status"], data["data"], data["message"] = status.HTTP_200_OK, "",f"{product_name} updated successfully"
#             else:
#                 data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User is not Admin or Organizer"
#         else:
#             data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
#     except Exception as e :
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)      


# @api_view(('PUT',))
# def store_product_edit_new(request, product_id):
#     """
#     An admin or an organizer can edit a store product.
#     """
#     data = {'status': '', 'data': [], 'message': ''}
#     try:
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         category_id = request.data.get('category_id')
#         product_name = request.data.get('product_name')
#         store_name = request.data.get('store_name')
#         leagues_for_id = request.data.getlist('leagues_for_id')
#         product_description = request.data.get('product_description')
#         product_specifications = request.data.get('product_specifications')
#         advertisement_image = request.FILES.get('advertisement')
        
#         # Validate user
#         check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key).first()
#         if not check_user:
#             data["status"] = status.HTTP_404_NOT_FOUND
#             data["message"] = "User not found"
#             return Response(data)

#         if not (check_user.is_admin or check_user.is_organizer):
#             data["status"] = status.HTTP_403_FORBIDDEN
#             data["message"] = "User is not Admin or Organizer"
#             return Response(data)

#         # Validate product
#         product = MerchandiseStoreProduct.objects.filter(id=product_id).first()
#         if not product:
#             data["status"] = status.HTTP_404_NOT_FOUND
#             data["message"] = "Product not found"
#             return Response(data)

#         # Validate category (if provided)
#         if category_id:
#             get_category = MerchandiseStoreCategory.objects.filter(id=category_id).first()
#             if not get_category:
#                 data["status"] = status.HTTP_404_NOT_FOUND
#                 data["message"] = "Category not found"
#                 return Response(data)
#             product.category = get_category
#         else:
#             product.category = product.category
#         # Update product details
#         product.name = product_name if product_name else product.name
#         product.store_name = store_name if store_name else product.store_name
#         product.description = product_description if product_description else product.description
#         product.specifications = product_specifications if product_specifications else product.specifications
#         product.advertisement_image = advertisement_image if advertisement_image else product.advertisement_image
#         product.save()

#         # Update leagues (clear existing and add new ones)
#         if leagues_for_id:
#             product.leagues_for.clear()
#             for league_id in leagues_for_id:
#                 get_league = Leagues.objects.filter(id=league_id).first()
#                 if get_league:
#                     product.leagues_for.add(get_league)

#         # Update specifications
#         specifications_data = json.loads(request.data.get('specifications_data', '[]'))
#         for spec_data in specifications_data:
#             spec_id = spec_data.get('spec_id')
#             if spec_id:
#                 # Update existing specification
#                 product_specification = MerchandiseProductSpecification.objects.filter(id=spec_id, product=product).first()
#                 if product_specification:
#                     product_specification.size = spec_data.get('size', product_specification.size)
#                     product_specification.old_price = spec_data.get('oldPrice', product_specification.old_price)
#                     product_specification.current_price = spec_data.get('currentPrice', product_specification.current_price)
#                     product_specification.total_product = spec_data.get('totalProduct', product_specification.total_product)
#                     product_specification.available_product = spec_data.get('availableProduct', product_specification.available_product)
#                     product_specification.save()

#                     # Update highlights for the specification
#                     highlights_data = spec_data.get('highlights', [])
#                     for highlight_data in highlights_data:
#                         highlight_id = highlight_data.get('highlight_id')
#                         if highlight_id:
#                             # Update existing highlight
#                             highlight = ProductSpecificationHighlights.objects.filter(id=highlight_id, specification=product_specification).first()
#                             if highlight:
#                                 highlight.highlight_key = highlight_data.get('key', highlight.highlight_key)
#                                 highlight.highlight_des = highlight_data.get('description', highlight.highlight_des)
#                                 highlight.save()
#                         else:
#                             # Create new highlight
#                             ProductSpecificationHighlights.objects.create(
#                                 specification=product_specification,
#                                 highlight_key=highlight_data.get('key'),
#                                 highlight_des=highlight_data.get('description'),
#                             )
#             else:
#                 # Create new specification and highlights
#                 product_specification = MerchandiseProductSpecification.objects.create(
#                     product=product,
#                     size=spec_data.get('size'),
#                     old_price=spec_data.get('oldPrice'),
#                     current_price=spec_data.get('currentPrice'),
#                     total_product=spec_data.get('totalProduct'),
                    
#                 )
#                 highlights_data = spec_data.get('highlights', [])
#                 for highlight in highlights_data:
#                     ProductSpecificationHighlights.objects.create(
#                         specification=product_specification,
#                         highlight_key=highlight.get('key'),
#                         highlight_des=highlight.get('description'),
#                     )

#         # Update images (optional - remove existing and add new ones)
#         if request.FILES.getlist('images'):
#             product.productImages.all().delete()
#             for image in request.FILES.getlist('images'):
#                 MerchandiseProductImages.objects.create(product=product, image=image)

#         data["status"] = status.HTTP_200_OK
#         data["data"] = {'product': product.id}
#         data["message"] = f"{product.name} updated successfully"

#     except Exception as e:
#         data['status'] = status.HTTP_400_BAD_REQUEST
#         data['message'] = str(e)

#     return Response(data)




@api_view(('POST',))
def store_product_edit_new(request):
    """
    An admin or an organizer can edit a store product.
    """
    data = {'status': '', 'data': [], 'message': ''}

    try:
        # ---------- Grab fields ----------
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        category_id = request.data.get('category_id')
        product_name = request.data.get('product_name')
        product_id = request.data.get('product_id')
        store_name = request.data.get('store_name')
        product_description = request.data.get('product_description')
        product_specifications = request.data.get('product_specifications')
        advertisement_image = request.FILES.get('advertisement_image', None)
        leagues_for_id = request.data.get('leagues_for_id')

        # Echo request payload (unchanged)
        import json
        fields_json = {
            "user_uuid": request.data.get("user_uuid"),
            "user_secret_key": request.data.get("user_secret_key"),
            "category_id": request.data.get("category_id"),
            "product_name": request.data.get("product_name"),
            "product_id": request.data.get("product_id"),
            "store_name": request.data.get("store_name"),
            "product_description": request.data.get("product_description"),
            "product_specifications": request.data.get("product_specifications"),
            "leagues_for_id": request.data.getlist("leagues_for_id")
                if hasattr(request.data, "getlist") else request.data.get("leagues_for_id"),
            "advertisement_image": request.FILES.get("advertisement_image").name
                if request.FILES.get("advertisement_image") else None
        }
        # fields_json_str = json.dumps(fields_json, ensure_ascii=False)

        # ---------- Normalize leagues ----------
        if isinstance(leagues_for_id, str):
            leagues_for_id = [x.strip() for x in leagues_for_id.split(',') if x.strip()]
        elif isinstance(leagues_for_id, list):
            leagues_for_id = [str(x).strip() for x in leagues_for_id if str(x).strip()]
        else:
            leagues_for_id = []

        # ---------- Validate user ----------
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key).first()
        if not check_user:
            data.update({"status": status.HTTP_404_NOT_FOUND,
                         "message": "User not found",
                         "request": fields_json})
            return Response(data)

        # ---------- Validate product ----------
        product = MerchandiseStoreProduct.objects.filter(id=int(product_id)).first()
        if not product:
            data.update({"status": status.HTTP_404_NOT_FOUND,
                         "message": "Product not found",
                         "request": fields_json})
            return Response(data)

        # ---------- Spec duplicate checks ----------
        specifications_data = json.loads(request.data.get('specifications_data', '[]'))
        seen_combos = set()
        for spec in specifications_data:
            spec_id = spec.get('spec_id')
            size = (spec.get('size') or '').strip().lower() or None
            color = (spec.get('color') or '').strip().lower() or None

            if size and color:
                combo_key = f'{size}-{color}'
                filter_kwargs = {'product': product, 'size__iexact': size, 'color__iexact': color}
            elif size:
                combo_key = f'{size}-none'
                filter_kwargs = {'product': product, 'size__iexact': size, 'color__isnull': True}
            elif color:
                combo_key = f'none-{color}'
                filter_kwargs = {'product': product, 'size__isnull': True, 'color__iexact': color}
            else:
                combo_key = 'none-none'
                filter_kwargs = {'product': product, 'size__isnull': True, 'color__isnull': True}

            if combo_key in seen_combos:
                data.update({"status": status.HTTP_200_OK,
                             "message": f"Duplicate specification detected: size/color combo '{size or '-'}'/'{color or '-'}' appears multiple times.",
                             "request": fields_json})
                return Response(data)
            seen_combos.add(combo_key)

            existing_spec_qs = MerchandiseProductSpecification.objects.filter(**filter_kwargs)
            if spec_id:
                existing_spec_qs = existing_spec_qs.exclude(id=spec_id)
            if existing_spec_qs.exists():
                data.update({"status": status.HTTP_200_OK,
                             "message": f"This specification with size '{size or '-'}' and color '{color or '-'}' already exists for this product.",
                             "request": fields_json})
                return Response(data)

        # ---------- Category ----------
        if category_id:
            get_category = MerchandiseStoreCategory.objects.filter(id=int(category_id)).first()
            if not get_category:
                data.update({"status": status.HTTP_404_NOT_FOUND,
                             "message": "Category not found",
                             "request": fields_json})
                return Response(data)
            product.category = get_category

        # ---------- Update product fields (guard None) ----------
        update_fields = []
        if product_name is not None:
            product.name = product_name
            update_fields.append('name')

        if store_name is not None:
            product.store_name = store_name
            update_fields.append('store_name')

        if product_description is not None:
            product.description = product_description
            update_fields.append('description')

        if product_specifications is not None:
            product.specifications = product_specifications
            update_fields.append('specifications')

        if advertisement_image is not None:
            product.advertisement_image = advertisement_image
            update_fields.append('advertisement_image')

        has_single_spec = str(request.data.get('has_single_spec', 'false')).lower() == 'true'
        product.has_single_spec = has_single_spec
        update_fields.append('has_single_spec')

        # Save once
        product.save(update_fields=update_fields)

        # ---------- Update leagues ----------
        product.leagues_for.clear()
        for league_id in leagues_for_id:
            try:
                league = Leagues.objects.filter(id=int(league_id)).first()
                if league:
                    product.leagues_for.add(league)
            except (ValueError, TypeError):
                continue

        # ---------- Specs write/update ----------
        if has_single_spec:
            all_specs = product.specificProduct.all()
            existing_spec = all_specs.first()
            spec_data = specifications_data[0] if specifications_data else {}

            if existing_spec:
                existing_spec.size = spec_data.get('size', existing_spec.size)
                existing_spec.color = spec_data.get('color', existing_spec.color)
                existing_spec.old_price = spec_data.get('oldPrice', existing_spec.old_price)
                existing_spec.current_price = spec_data.get('currentPrice', existing_spec.current_price)
                existing_spec.total_product = spec_data.get('totalProduct', existing_spec.total_product)
                existing_spec.available_product = spec_data.get('availableProduct', existing_spec.available_product)
                existing_spec.save()
                product_specification = existing_spec
                all_specs.exclude(id=existing_spec.id).delete()
            else:
                product_specification = MerchandiseProductSpecification.objects.create(
                    product=product,
                    size=spec_data.get('size', ''),
                    color=spec_data.get('color', ''),
                    old_price=spec_data.get('oldPrice'),
                    current_price=spec_data.get('currentPrice'),
                    total_product=spec_data.get('totalProduct'),
                )

            highlights_data = spec_data.get('highlights', [])
            for h in highlights_data:
                highlight_id = h.get('highlight_id')
                if highlight_id:
                    highlight = ProductSpecificationHighlights.objects.filter(
                        id=highlight_id, specification=product_specification
                    ).first()
                    if highlight:
                        highlight.highlight_key = h.get('highlight_key', highlight.highlight_key)
                        highlight.highlight_des = h.get('highlight_des', highlight.highlight_des)
                        highlight.save()
                else:
                    ProductSpecificationHighlights.objects.create(
                        specification=product_specification,
                        highlight_key=h.get('highlight_key'),
                        highlight_des=h.get('highlight_des'),
                    )

        else:
            for spec_data in specifications_data:
                spec_id = spec_data.get('spec_id')
                if spec_id:
                    product_spec = MerchandiseProductSpecification.objects.filter(
                        id=spec_id, product=product
                    ).first()
                    if product_spec:
                        product_spec.size = spec_data.get('size', product_spec.size)
                        product_spec.color = spec_data.get('color', product_spec.color)
                        product_spec.old_price = spec_data.get('oldPrice', product_spec.old_price)
                        product_spec.current_price = spec_data.get('currentPrice', product_spec.current_price)
                        product_spec.total_product = spec_data.get('totalProduct', product_spec.total_product)
                        product_spec.available_product = spec_data.get('availableProduct', product_spec.available_product)
                        product_spec.save()
                        product_specification = product_spec
                else:
                    product_specification = MerchandiseProductSpecification.objects.create(
                        product=product,
                        size=spec_data.get('size', ''),
                        color=spec_data.get('color', ''),
                        old_price=spec_data.get('oldPrice'),
                        current_price=spec_data.get('currentPrice'),
                        total_product=spec_data.get('totalProduct'),
                    )

                highlights_data = spec_data.get('highlights', [])
                for h in highlights_data:
                    highlight_id = h.get('highlight_id')
                    if highlight_id:
                        highlight = ProductSpecificationHighlights.objects.filter(
                            id=highlight_id, specification=product_specification
                        ).first()
                        if highlight:
                            highlight.highlight_key = h.get('highlight_key', highlight.highlight_key)
                            highlight.highlight_des = h.get('highlight_des', highlight.highlight_des)
                            highlight.save()
                    else:
                        ProductSpecificationHighlights.objects.create(
                            specification=product_specification,
                            highlight_key=h.get('highlight_key'),
                            highlight_des=h.get('highlight_des'),
                        )

        # ---------- Images ----------
        if request.FILES.getlist('images'):
            product.productImages.all().delete()
            for image in request.FILES.getlist('images'):
                MerchandiseProductImages.objects.create(product=product, image=image)

        data.update({
            "status": status.HTTP_200_OK,
            "data": {"product": product.id},
            "message": f"{product.name} updated successfully",
            "request": fields_json
        })
    except Exception as e:
        data.update({
            'status': status.HTTP_400_BAD_REQUEST,
            'message': str(e),
            'request': fields_json
        })

    return Response(data)

@api_view(('POST',))
def store_product_love_byUser(request):
    """
    Allows a user to add a product to his wishlist.
    """
    data = {'status':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        product_id = request.data.get('product_id')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_product = MerchandiseStoreProduct.objects.filter(id=product_id)
        if check_user.exists() and check_product.exists() :
            get_user = check_user.first()
            get_product = check_product.first()
            check_love = check_product.filter(is_love__id=get_user.id)
            product_name = get_product.name
            if check_love.exists() :
                get_product.is_love.remove(get_user.id)
                data["message"] = f"{product_name} is removed from your wishlist"
            else:
                get_product.is_love.add(get_user.id)
                data["message"] = f"{product_name} is added to your wishlist"
                
            data["status"] = status.HTTP_200_OK
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND,"User or Product not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(['POST'])
def rate_product(request):
    data = {'status': '', 'data': [], 'message': ''}
    try:
        user_uuid = request.data.get("user_uuid")
        user_secret_key = request.data.get("user_secret_key")
        product_id = request.data.get("product_id")
        
        rating_value = request.data.get('rating')
        comment = request.data.get('comment', '')
        images = request.FILES.getlist('images')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_product = MerchandiseStoreProduct.objects.filter(id=product_id)

        if check_user and check_product:
            user = check_user.first()
            product = check_product.first()

            if not 1 <= float(rating_value) <= 5:
                data["status"], data["data"], data["message"] = status.HTTP_400_BAD_REQUEST, [], "Rating must be between 1 and 5."
                return Response(data)

            rating, created = ProductRating.objects.update_or_create(
                user=user,
                product=product,
                defaults={'rating': rating_value, 'comment': comment}
            )

            # Save associated images
            for image in images:
                RatingImages.objects.create(product_rating=rating, image=image)

            serializer = ProductRatingSerializer(rating)
            data["status"] = status.HTTP_200_OK if not created else status.HTTP_201_CREATED
            data["data"] = serializer.data
            data["message"] = "Product rated successfully."
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, [], "User or Product not found"
    except Exception as e:
        data['status'], data["data"], data['message'] = status.HTTP_400_BAD_REQUEST, [], str(e)

    return Response(data)   
  

@api_view(("GET",))
def wishlisted_products(request):
    data = {"status":"","message":"","data":[]}
    try:        
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            wishlisted_products = []
            all_products = MerchandiseStoreProduct.objects.all()
            for product in all_products:
                if get_user in product.is_love.all():                    
                    wishlisted_products.append(product)

            product_list_name = f'{get_user.id}_wish_list'
            if cache.get(product_list_name):
                print("from cache.........")
                product_list = cache.get(product_list_name)
            else:
                print("from db...........")
                product_list = wishlisted_products
                cache.set(product_list_name, product_list)

            paginator = PageNumberPagination()
            paginator.page_size = 5 
            result_page = paginator.paginate_queryset(product_list, request)
            serializer = ProductListSerializer(result_page, many=True)
            serialized_data = serializer.data
            if not serialized_data:
                data["status"] = status.HTTP_200_OK
                data["count"] = 0
                data["previous"] = None
                data["next"] = None
                data["data"] = []
                data["message"] = "No Result found"
            else:
                paginated_response = paginator.get_paginated_response(serialized_data)
                data["status"] = status.HTTP_200_OK
                data["count"] = paginated_response.data["count"]
                data["previous"] = paginated_response.data["previous"]
                data["next"] = paginated_response.data["next"]
                data["data"] = paginated_response.data["results"]
                data["message"] = "Data found"
            
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, [], f"User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(("GET",))
def check_store_product_liked_or_not(request):
    """
    Displays if a product is in the wishlist of a user or not.
    """
    data = {}
    try:        
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        product_id = request.GET.get("product_id")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            check_product = MerchandiseStoreProduct.objects.filter(id=product_id)
            if check_product.exists():
                get_product = check_product.first()
                liked_status = False
                if get_user in get_product.is_love.all():
                    liked_status = True
                    data["status"], data["message"], data["liked_status"] = status.HTTP_200_OK, "", liked_status
                else:
                    data["status"], data["message"], data["liked_status"] = status.HTTP_200_OK, "", liked_status
            else:
                data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"Product not found."
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def user_add_delivery_address(request):
    """
    Allows a user to add delivery address.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        street = request.data.get('street')
        city = request.data.get('city')
        state = request.data.get('state')
        postal_code = request.data.get('postal_code')
        country = request.data.get('country')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            if street and city and state and postal_code and country :
                obj = GenerateKey()
                delivery_address_key = obj.gen_delivery_address_sk()
                # complete_address = f'{street}, {city}, {state}, {country}, PIN-{postal_code}'
                save_delivery_address = ProductDeliveryAddress(secret_key=delivery_address_key,
                                        street=street,city=city,state=state,postal_code=postal_code,
                                        country=country,created_by_id=get_user.id)
                                        
                save_delivery_address.save()            
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, "","New address added successfully"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_403_FORBIDDEN, "","Street, City, State, Postal Code are mandatory"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def user_edit_delivery_address(request):
    """
    Allows a user to edit his delivery address.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        address_id = request.data.get('address_id')
        street = request.data.get('street')
        city = request.data.get('city')
        state = request.data.get('state')
        postal_code = request.data.get('postal_code')
        country = request.data.get('country')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_delivery_address = ProductDeliveryAddress.objects.filter(id=address_id)
        if check_user.exists() and check_delivery_address.exists():
            # get_user = check_user.first()
            get_delivery_address= check_delivery_address.first()
            if street and city and state and postal_code and country :
                # complete_address = f'{street}, {city}, {state}, {country}, PIN-{postal_code}'
                get_delivery_address.street = street
                get_delivery_address.city = city
                get_delivery_address.state = state
                get_delivery_address.postal_code = postal_code
                # get_delivery_address.complete_address = complete_address
                get_delivery_address.save()
                data["status"], data["data"], data["message"] = status.HTTP_200_OK, "","Address updated successfully"
            else:
                data["status"], data["data"], data["message"] = status.HTTP_403_FORBIDDEN, "","Street, City, State, Postal Code are mandatory"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('GET',))
def user_delivery_address(request):
    """
    Displays the details of delivery address of a user.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            addresses = ProductDeliveryAddress.objects.filter(created_by_id=get_user.id)
            valid_addresses = []
            for address in addresses:
                if address.street != "null" and address.city != "null" and address.state != "null" and address.postal_code != "null" and address.country != "null":
                    valid_addresses.append({
                        "id": address.id,
                        "street": address.street,
                        "city": address.city,
                        "state": address.state,
                        "postal_code": address.postal_code,
                        "country": address.country,
                        "complete_address": address.complete_address,
                        "default_address": address.default_address,
                        "created_by__first_name": address.created_by.first_name,
                        "created_by__last_name": address.created_by.last_name
                    })

            data['status'] = status.HTTP_200_OK
            data['data'] = valid_addresses
            data['message'] = 'Data Found'
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def user_delivery_address_change(request):
    """
    Allows user to change delivery address.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        address_id = request.data.get('address_id')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_delivery_address = ProductDeliveryAddress.objects.filter(id=address_id)
        if check_user.exists() and check_delivery_address.exists():
            get_delivery_address= check_delivery_address.first()
            get_delivery_address.default_address = True
            get_delivery_address.save()
            all_delivery_address = ProductDeliveryAddress.objects.filter(created_by_id=get_delivery_address.created_by.id).exclude(id=address_id)
            for i in all_delivery_address:
                i.default_address = False
                i.save()
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, "","Address updated successfully"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_403_FORBIDDEN, "","User or Address not found"
                
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# @api_view(('POST',))
# def product_add_to_cart(request):
#     """
#     Allows user to add a product to his cart.
#     """
#     data = {'status':'','data':'','message':''}
#     try:        
#         user_uuid = request.data.get('user_uuid')
#         user_secret_key = request.data.get('user_secret_key')
#         product_id = request.data.get('product_id')
#         quantity = request.data.get('quantity')
#         size = request.data.get('size')
#         check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
#         check_product = MerchandiseStoreProduct.objects.filter(id=product_id)        

#         if check_user.exists() and check_product.exists() :
#             get_user = check_user.first()
#             get_product = check_product.first()                
#             obj2 = GenerateKey()
#             p_sk = obj2.gen_buy_product_sk()
#             product_specification = MerchandiseProductSpecification.objects.filter(product=get_product, size=size).first()
#             total_price = int(product_specification.current_price) * int(quantity)
            
#             CustomerMerchandiseStoreProductBuy.objects.create(secret_key=p_sk,product_id=get_product.id,price_per_product=product_specification.current_price,
#                                        quantity=quantity,total_price=total_price,status="CART",
#                                        created_by_id=get_user.id,size=size)
            
#             data["status"], data["data"], data["message"] = status.HTTP_200_OK, "",f"{get_product.name} successfully added to cart"
#         else:
#             data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User or Product not found"
#     except Exception as e :
#         data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
#     return Response(data)  


@api_view(('POST',))
def product_add_to_cart(request):
    """
    Allows user to add a product to his cart.
    """
    data = {'status': '', 'data': '', 'message': ''}
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity')
        size = request.data.get('size')  # Optional
        color = request.data.get('color')  # Optional

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        check_product = MerchandiseStoreProduct.objects.filter(id=product_id)

        if check_user.exists() and check_product.exists():
            get_user = check_user.first()
            get_product = check_product.first()

            # Filter based on available specs
            spec_filter = {'product': get_product}
            if size is not None and size.strip() != "":
                spec_filter['size__iexact'] = size

            if color is not None and color.strip() != "":
                spec_filter['color__iexact'] = color

            product_specification = MerchandiseProductSpecification.objects.filter(**spec_filter).first()
            if not product_specification:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "Product specification with given size/color not found"
                return Response(data)

            obj2 = GenerateKey()
            p_sk = obj2.gen_buy_product_sk()
            total_price = int(product_specification.current_price) * int(quantity)

            CustomerMerchandiseStoreProductBuy.objects.create(
                secret_key=p_sk,
                product_id=get_product.id,
                price_per_product=product_specification.current_price,
                quantity=quantity,
                total_price=total_price,
                status="CART",
                created_by_id=get_user.id,
                size=size,
                color=color  # Only works if your model has a 'color' field
            )

            data["status"] = status.HTTP_200_OK
            data["message"] = f"{get_product.name} successfully added to cart"
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User or Product not found"
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)

    return Response(data)


#### Old##########
@api_view(('GET',))
def cart_list(request):
    """
    Displays the cart list of a user.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        coupon_code = request.GET.get('coupon_code')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.exists() :
            get_user = check_user.first()
            check_coupon = CouponCode.objects.filter(coupon_code=coupon_code)           
            if check_coupon.exists():   
                card_products = CustomerMerchandiseStoreProductBuy.objects.filter(created_by_id=get_user.id,status="CART").order_by("-id").annotate(
                    total_price=F('product__price') * F('quantity')
                ).values("id", "uuid", "secret_key", "product__name", "product__price", "quantity", "product__image", "total_price","size")

                total_price = card_products.aggregate(total_prices=Sum("total_price", default=0))['total_prices']
                get_coupon = check_coupon.first().percentage
                price_after_discount = int(total_price - (total_price*get_coupon/100))
                data["coupon_status"] = "Successfully applied."
                data["discount"] = int(total_price*get_coupon/100)
                data["total_price"] = price_after_discount
            else:
                card_products = CustomerMerchandiseStoreProductBuy.objects.filter(created_by_id=get_user.id,status="CART").order_by("-id").annotate(
                    total_price=F('product__price') * F('quantity')
                ).values("id", "uuid", "secret_key", "product__name", "product__price", "quantity", "product__image", "total_price","size")

                total_price = card_products.aggregate(total_prices=Sum("total_price", default=0))['total_prices']
                data["coupon_status"] = "Coupon code does not exist."
                data["discount"] = 0
                data["total_price"] = total_price
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, card_products,f"Data found"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)  


###############Updated#################
@api_view(("GET",))
def cart_list_new(request):
    data = {'status':'', 'data':[], 'message':'', 'coupon_status': False}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        coupon_code = request.GET.get('coupon_code')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        
        coupon_applied = False 
        original_total_price = 0
        discount_amount = 0
        if check_user.exists():
            get_user = check_user.first()
            cart_products = CustomerMerchandiseStoreProductBuy.objects.filter(created_by=get_user, status='CART')           
            
            for product in cart_products:
                product_price = product.price_per_product * product.quantity
                original_total_price += product_price
                if coupon_code:
                    check_coupon = CouponCode.objects.filter(coupon_code=coupon_code, product=product.product,
                                                                start_date__lte=timezone.now(), end_date__gte=timezone.now())
                    if check_coupon.exists():
                        coupon = check_coupon.first()
                        discount = (coupon.percentage / 100) * product_price
                        product_price -= discount
                        discount_amount += discount 
                        coupon_applied = True     
                
            total_price = original_total_price - discount_amount
            serializer = CustomerMerchandiseStoreProductBuySerializer(cart_products, many=True)
            
            if coupon_applied:
                coupon_status = f"Coupon code '{coupon_code}' was successfully applied."
            else:
                coupon_status = "No valid coupon code was applied."
            data['status'] = status.HTTP_200_OK
            data['message'] = 'Data fetched successfully.'
            data['data'] = serializer.data
            data['coupon_status'] = coupon_status
            data['total_price'] = total_price
            data['discount'] = discount_amount
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = 'User not found'
            data['data'] = serializer.data
            data['coupon_status'] = coupon_status
            data['total_price'] = 0
            data['discount'] = discount_amount
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f'{str(e)}'
    return Response(data)    


@api_view(('POST',))
def cart_edit(request):
    """
    Allows a user to edit his cart.
    """
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        cart_id = request.data.get('cart_id')
        quantity = request.data.get('quantity')
        
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_cart = CustomerMerchandiseStoreProductBuy.objects.filter(id=cart_id)
        if check_user.exists() and check_cart.exists():
            get_cart = check_cart.first()
            get_cart.quantity = int(quantity)
            get_cart.save()
            data["status"], data["data"], data["message"] = status.HTTP_200_OK, "","Cart updated successfully"
        else:
            data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User or Cart Product not found"
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def cart_delete(request):
    """
    Allows a user to delete product from his cart.
    """
    # try:
    data = {'status':'','data':'','message':''}
    user_uuid = request.data.get('user_uuid')
    user_secret_key = request.data.get('user_secret_key')
    cart_id = request.data.get('cart_id')
    
    check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
    check_cart = CustomerMerchandiseStoreProductBuy.objects.filter(id=cart_id)
    if check_user.exists() and check_cart.exists():
        get_cart = check_cart.first()
        get_cart.delete()
        data["status"], data["data"], data["message"] = status.HTTP_200_OK, "",f"{get_cart.product.name} is removed from cart."
    else:
        data["status"], data["data"], data["message"] = status.HTTP_404_NOT_FOUND, "","User or Cart Product not found"
    # except Exception as e :
    #     data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


# ################ payement part start ################
# directly buy the product
@api_view(('POST',))
def buy_now_product(request):
    """
    Allows a user to directly buy any product from product list.
    """
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        delivery_address_main = None
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if not check_user.exists():            
            return Response({'message': 'User does not exist.', 'status': status.HTTP_404_NOT_FOUND})
        
        get_user = check_user.first()
        delivery_address_main = request.data.get('delivery_address_main_id')
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity'))
        size = request.data.get('size')
        color = request.data.get('color')
        coupon_code = request.data.get('coupon_code')
        check_coupon = CouponCode.objects.filter(coupon_code=coupon_code, start_date__lte=datetime.now(), end_date__gte=datetime.now()).first()
        product = MerchandiseStoreProduct.objects.filter(id=int(product_id)).first()
        if not product:
            return Response({"status": status.HTTP_404_NOT_FOUND, "message": "Product not found."})

        spec_filter = {'product': product}
        if size is not None and size.strip() != "":
            spec_filter['size__iexact'] = size

        if color is not None and color.strip() != "":
            spec_filter['color__iexact'] = color

        product_specification = MerchandiseProductSpecification.objects.filter(**spec_filter).first()
        if not product_specification:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "Product specification with given size/color not found"
            return Response(data)
        
        price = product_specification.current_price
        if delivery_address_main is None:            
            delivery_address = f"{get_user.street},{get_user.city},{get_user.state},{get_user.postal_code}, Latitude:{get_user.latitude}, Longitude:{get_user.longitude}"
        else:
            
            delivery_address = ProductDeliveryAddress.objects.filter(id=delivery_address_main,created_by=check_user.first()).first().complete_address
        obj = GenerateKey ()
        secret_key = obj.gen_payment_key()
        if check_coupon and product in check_coupon.product.all():
            unit_amount = (int(price)-(int(price)*int(check_coupon.percentage))/100)*int(quantity)*100
        else:
            unit_amount = int(quantity)*int(price)*100
        add_buy = CustomerMerchandiseStoreProductBuy.objects.create(
            secret_key = secret_key,            
            product_id = product_id,
            price_per_product = price,
            quantity = quantity,
            status = "BuyNow",
            total_price = int(quantity)*int(price),
            delivery_address_main_id = delivery_address_main,
            delivery_address = delivery_address,
            created_by = get_user,
            size = size,
            color=color
        )
        charge_for = "product_buy"
        cart_id = add_buy.id
        product_name_ = add_buy.product.name
        product_name = f"Your merchandise product {product_name_}"
               
        product_description = "Payment received by Pickleit"
        if get_user.stripe_customer_id :
            stripe_customer_id = get_user.stripe_customer_id
        else:
            customer = stripe.Customer.create(email=get_user.email).to_dict()
            stripe_customer_id = customer["id"]
            get_user.stripe_customer_id = stripe_customer_id
            get_user.save()
        
        host = request.get_host()
        current_site = f"{protocol}://{host}"

        main_url = f"{current_site}/accessories/694b0ce98afc6fa28631622bc70971b3ca40d25490634a60dcd53a5ff04843f3/{charge_for}/{cart_id}/"
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
    except Exception as e :
        data = {}
        data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
        return Response(data)


# store buy product payment details store.
def buy_now_product_payment(request,charge_for,cart_id,checkout_session_id):
    """
    Handles the payment part for directly buying any product.
    """
    context ={}
    stripe.api_key = settings.STRIPE_SECRET_KEY
    # context['stripe_api_key'] = settings.STRIPE_PUBLIC_KEY
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
    check_charge = CustomerMerchandiseStoreProductBuy.objects.filter(id=cart_id, status="BuyNow", is_paid=False)
    if check_charge.exists():
        get_charge = check_charge.first()
        per_product_amount = int(get_charge.price_per_product)
        total_product = int(get_charge.quantity)
        charge_amount = (per_product_amount*total_product)
        expires_time = None
        save_payment = PaymentDetails(
            secret_key=secret_key,
            var_chargeamount=charge_amount,              
            payment_for=charge_for,
            payment_for_id=checkout_session_id,
            payment_by=payment_method_types,
            payment_amount=amount_total,
            payment_status=payment_status,
            stripe_response=pay,
            created_by_id=check_customer.id,
            expires_at=expires_time
            )
        save_payment.save()
        product_ = CustomerMerchandiseStoreProductBuy.objects.get(id=cart_id)
        save_payment.payment_for_product.add(product_)
        obj = GenerateKey ()
        genarate_cart_id = obj.generate_cart_unique_id()
        
        if payment_status is True:
            CustomerMerchandiseStoreProductBuy.objects.filter(id=cart_id).update(is_paid=True,status="ORDER PLACED",cart_idd=genarate_cart_id)

            # Send notification to the user placing order about successfull payment and order placement.
            title1 = "Successfull order placement."
            message1 = f"You have successfully made pyment and placed order for {product_.product.name}"
            notify_edited_player(product_.created_by.id, title1, message1)

            # Send notification to the product owner about new order.

            title2 = "New order received."
            message2 = f"{product_.created_by.first_name} has successfully made payment and placed order for {product_.product.name}"
            notify_edited_player(product_.product.created_by.id, title2, message2)

            return render(request,"success_payment_for_buy.html",context)
        else:
            CustomerMerchandiseStoreProductBuy.objects.filter(id=cart_id).update(status="CANCEL",cart_idd=genarate_cart_id)
            message = f"error .."
            return render(request,"failed_payment.html")
    else: 
        return render(request,"failed_payment.html")


#buy all cart product
@api_view(('POST',))
def buy_all_cart_product(request):
    """
    Allows a user to buy all their cart products and apply a coupon code if provided, only for eligible products.
    """
    stripe.api_key = settings.STRIPE_SECRET_KEY
    user_uuid = request.data.get('user_uuid')
    user_secret_key = request.data.get('user_secret_key')
    coupon_code = request.data.get('coupon_code')

    # Validate user
    check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
    if not check_user.exists():
        return Response({'message': 'User not exists'})

    get_user = check_user.first()
    user_id = get_user.id

    # Get all cart products
    all_cart_product = CustomerMerchandiseStoreProductBuy.objects.filter(created_by_id=user_id, status="CART", is_paid=False)
    
    if not all_cart_product.exists():
        return Response({'message': 'No items in cart'})

    card_id_list = []
    all_product_string = "Your merchandise product "
    total_price = 0
    delivery_address_main = ProductDeliveryAddress.objects.filter(created_by=get_user, default_address=True).first()
    obj = GenerateKey()
    generate_cart_id = obj.generate_cart_unique_id()

    eligible_products = set()
    if coupon_code:
        # Fetch eligible products for the coupon
        coupon = CouponCode.objects.filter(coupon_code=coupon_code, start_date__lte=datetime.now(), end_date__gte=datetime.now()).first()
        if coupon:
            eligible_products = set(coupon.product.values_list('id', flat=True))
        else:
            coupon_code = None  # Invalid coupon, ignore

    for cpd in all_cart_product:
        card_id_list.append(cpd.id)
        p_name = cpd.product.name
        total_price += cpd.price_per_product * cpd.quantity
        all_product_string += p_name + ", "
        complete_address = f"{delivery_address_main.street}, {delivery_address_main.city}, {delivery_address_main.state}, {delivery_address_main.country}, PIN-{delivery_address_main.postal_code}" if delivery_address_main else ""
        CustomerMerchandiseStoreProductBuy.objects.filter(uuid=cpd.uuid).update(delivery_address_main=delivery_address_main, delivery_address=complete_address, cart_idd=generate_cart_id)

    all_product_string = all_product_string.rstrip(", ")

    # Apply coupon discount if valid and applicable
    unit_amount = int(total_price * 100)  # Convert to cents
    discount_percentage = 0
    if coupon_code:
        discount_eligible_total = sum(
            (cpd.price_per_product * cpd.quantity) 
            for cpd in all_cart_product 
            if cpd.product.id in eligible_products
        )
        discount_percentage = coupon.percentage
        unit_amount -= int(discount_eligible_total * (discount_percentage / 100))

    # Stripe product and price creation
    product = stripe.Product.create(name=all_product_string, description="Payment received by Pickleit").to_dict()
    price = stripe.Price.create(unit_amount=unit_amount, currency='usd', product=product["id"]).to_dict()

    # Create Stripe checkout session
    protocol = "https" if request.is_secure() else "http"
    host = request.get_host()
    current_site = f"{protocol}://{host}"
    main_url = f"{current_site}/accessories/7417d36367fa2fab97cf476a626b989b2fb842eddc47f55b50e877bd57c97a00/product_buy/"
    checkout_session = stripe.checkout.Session.create(
        customer=get_user.stripe_customer_id,
        line_items=[{'price': price["id"], 'quantity': 1}],
        mode='payment',
        success_url=f"{main_url}{{CHECKOUT_SESSION_ID}}/",
        cancel_url=f"{current_site}/cancel.html",
    )

    return Response({"stripe_url": checkout_session.url})


#payment for buy all cart product details
def buy_all_cart_product_payment(request,charge_for,checkout_session_id):
    """
    Handles the payment for buying all cart products.
    """
    context ={}
    stripe.api_key = settings.STRIPE_SECRET_KEY
    pay = stripe.checkout.Session.retrieve(checkout_session_id).to_dict()    
    stripe_customer_id = pay["customer"]
    payment_status = pay["payment_status"]
    expires_at = pay["expires_at"]
    amount_total = float(pay["amount_total"]) / 100

    payment_method_types = pay["payment_method_types"]
    
    payment_status = True if payment_status == "paid" else False
    check_customer = User.objects.filter(stripe_customer_id=stripe_customer_id).first()
    check_charge = CustomerMerchandiseStoreProductBuy.objects.filter(created_by=check_customer.id, status="CART").values_list("id", flat=True)
    obj = GenerateKey ()
    secret_key = obj.gen_payment_key()
    cart_list = list(check_charge)
    cart_to_add_ = CustomerMerchandiseStoreProductBuy.objects.filter(id__in=cart_list)
    expires_time = None
    save_payment = PaymentDetails(
        secret_key=secret_key,
        var_chargeamount=amount_total,              
        payment_for=charge_for,
        payment_for_id=checkout_session_id,
        payment_by=payment_method_types,
        payment_amount=amount_total,
        payment_status=payment_status,
        stripe_response=pay,
        created_by_id=check_customer.id,
        expires_at=expires_time
        )
    save_payment.save()
    save_payment.payment_for_product.add(*cart_to_add_)
    if payment_status is True:
        for kl in cart_list:
            CustomerMerchandiseStoreProductBuy.objects.filter(id=kl).update(is_paid=True,status="ORDER PLACED")
            product_ = CustomerMerchandiseStoreProductBuy.objects.filter(id=kl).first()

            # Send notification to the user placing order about successfull payment and order placement.
            title1 = "Successfull order placement."
            message1 = f"You have successfully made pyment and placed order for {product_.product.name}"
            notify_edited_player(product_.created_by.id, title1, message1)

            # Send notification to the product owner about new order.

            title2 = "New order received."
            message2 = f"{product_.created_by.first_name} has successfully made payment and placed order for {product_.product.name}"
            notify_edited_player(product_.product.created_by.id, title2, message2)
            
        return render(request,"success_payment_for_buy.html",context)
    else:
        for kl in cart_list:
            CustomerMerchandiseStoreProductBuy.objects.filter(id=kl).update(is_paid=False,status="CART")
        message = f"error .."
        return render(request,"failed_payment.html")


#################################### payement part end #############################################
   
# class MerchandiseStoreProductBuySerializer(serializers.ModelSerializer):
#     total_price = serializers.IntegerField(source='total_price', read_only=True)
#     product_name = serializers.CharField(source='product.name', read_only=True)
#     address = serializers.CharField(source='delivery_address_main.complete_address', read_only=True)
    
#     class Meta:
#         model = CustomerMerchandiseStoreProductBuy
#         exclude = ["id"]
        # fields = ["id", "cart_idd", "product_name", "price_per_product", "quantity", "total_price", "status", "is_paid", "delivery_address", "created_at","address"]


class MyOrderActive(APIView):
    def get(self, request, *args, **kwargs):
        data = {"status":"", "data":[], "message":""}
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
            
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user:
            user = check_user.first()
            order_data = CustomerMerchandiseStoreProductBuy.objects.filter(created_by_id=user.id, status__in=["ORDER PLACED"], is_delivered=False)
            paginator = PageNumberPagination()
            paginator.page_size = 50  # You can customize or use `request.GET.get("page_size")`
            result_page = paginator.paginate_queryset(order_data, request)

            serializer = CustomerMerchandiseStoreProductBuySerializer(result_page, many=True)
            serialized_data = serializer.data

            if not serialized_data:
                data["status"] = status.HTTP_200_OK
                data["count"] = 0
                data["previous"] = None
                data["next"] = None
                data["data"] = []
                data["message"] = "No order found"
            else:
                paginated_response = paginator.get_paginated_response(serialized_data)
                data["status"] = status.HTTP_200_OK
                data["count"] = paginated_response.data.get("count")
                data["previous"] = paginated_response.data.get("previous")
                data["next"] = paginated_response.data.get("next")
                data["data"] = paginated_response.data.get("results")
                data["message"] = "Orders fetched successfully."
        else:
            data["status"] = status.HTTP_200_OK
            data["data"] = []
            data["message"] = "User not found"
        return Response(data)


class MyOrderCompleted(APIView):
    def get(self, request, *args, **kwargs):
        data = {"status":"", "data":[], "message":""}
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
            
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user:
            user = check_user.first()
            order_data = CustomerMerchandiseStoreProductBuy.objects.filter(created_by_id=user.id, status__in=["DELIVERED","CANCEL"])
            paginator = PageNumberPagination()
            paginator.page_size = 50  # You can customize or use `request.GET.get("page_size")`
            result_page = paginator.paginate_queryset(order_data, request)

            serializer = CustomerMerchandiseStoreProductBuySerializer(result_page, many=True)
            serialized_data = serializer.data

            if not serialized_data:
                data["status"] = status.HTTP_200_OK
                data["count"] = 0
                data["previous"] = None
                data["next"] = None
                data["data"] = []
                data["message"] = "No order found"
            else:
                paginated_response = paginator.get_paginated_response(serialized_data)
                data["status"] = status.HTTP_200_OK
                data["count"] = paginated_response.data.get("count")
                data["previous"] = paginated_response.data.get("previous")
                data["next"] = paginated_response.data.get("next")
                data["data"] = paginated_response.data.get("results")
                data["message"] = "Orders fetched successfully."
        else:
            data["status"] = status.HTTP_200_OK
            data["data"] = []
            data["message"] = "User not found"
        return Response(data)


from dateutil.relativedelta import relativedelta  # use this for months

class MyOrderReceived(APIView):
    def get(self, request, *args, **kwargs):
        data = {"status": "", "data": [], "message": ""}
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        filter_type = request.GET.get('filter_type')
        delivery_status = request.GET.get('status', 'pending')

        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            user = check_user.first()

            orders = CustomerMerchandiseStoreProductBuy.objects.filter(
                product__created_by=user
            )
            if delivery_status == "delivered":
                orders = orders.filter(is_delivered=True, status__in=["DELIVERED"])

            elif delivery_status == "cancelled":  # Default and fallback
                orders = orders.filter(status__in=["CANCEL"])

            elif delivery_status == "shipped":
                orders = orders.filter(status__in=["SHIPPED"])
            else:
                orders = orders.filter(is_delivered=False, status__in=["ORDER PLACED"])

            now = datetime.now()            
            start = None

            if filter_type == "today":
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif filter_type == "last_3_days":
                start = now - timedelta(days=3)
            elif filter_type == "last_7_days":
                start = now - timedelta(days=7)
            elif filter_type == "last_15_days":
                start = now - timedelta(days=15)
            elif filter_type == "last_1_month":
                start = now - relativedelta(months=1)
            elif filter_type == "last_6_months":
                start = now - relativedelta(months=6)
            elif filter_type == "last_1_year":
                start = now - relativedelta(years=1)

            if start:
                orders = orders.filter(created_at__gte=start)

            paginator = PageNumberPagination()
            paginator.page_size = 50
            result_page = paginator.paginate_queryset(orders, request)

            serializer = CustomerMerchandiseStoreProductBuySerializer(result_page, many=True)
            serialized_data = serializer.data

            if not serialized_data:
                data["status"] = status.HTTP_200_OK
                data["count"] = 0
                data["previous"] = None
                data["next"] = None
                data["data"] = []
                data["message"] = "No Result found"
            else:
                paginated_response = paginator.get_paginated_response(serialized_data)
                data["status"] = status.HTTP_200_OK
                data["count"] = paginated_response.data.get("count")
                data["previous"] = paginated_response.data.get("previous")
                data["next"] = paginated_response.data.get("next")
                data["data"] = paginated_response.data.get("results")
                data["message"] = "Received orders fetched successfully."
        else:
            data["status"] = status.HTTP_200_OK
            data["data"] = []
            data["message"] = "User not found"

        return Response(data)


@api_view(("POST",))
def update_delivery_status(request):
    data = {"status": "", "message": ""}

    user_uuid = request.data.get("user_uuid")
    user_secret_key = request.data.get("user_secret_key")
    order_id = request.data.get("order_id")
    delivery_status = request.data.get("status")  
    
    # Validate user
    user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key).first()
    if not user:
        data["status"] = status.HTTP_404_NOT_FOUND
        data["message"] = "Invalid user credentials."
        return Response(data)

    # Validate order
    try:
        order = CustomerMerchandiseStoreProductBuy.objects.get(id=order_id, product__created_by=user)
    except CustomerMerchandiseStoreProductBuy.DoesNotExist:
        data["status"] = status.HTTP_404_NOT_FOUND
        data["message"] = "Order not found."
        return Response(data)

    # Update status
    if delivery_status == "cancelled":
        order.status = "CANCEL"
    elif delivery_status == "shipped":
        order.status = "SHIPPED"
    elif delivery_status == "delivered":
        order.status = "DELIVERED"
        order.is_delivered = True

    order.save()

    data["status"] = status.HTTP_200_OK
    data["message"] = "Order status updated successfully."
    data["order_status"] = order.status
    return Response(data)


@api_view(("GET",))
def filtered_product_list(request):
    data = {"status":"","message":"", "data":[]}
    try:        
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        size = request.GET.get("size")
        min_price = request.GET.get("min_price")
        max_price = request.GET.get("max_price")
        category = request.GET.get("category")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            all_products = MerchandiseStoreProduct.objects.all()
            if category:
                all_products = all_products.filter(category__name__icontains=category)
            if size:
                specifications = MerchandiseProductSpecification.objects.filter(size=size)
                all_products = all_products.filter(specificProduct__in=specifications).distinct()
            if min_price and max_price:
                specifications = MerchandiseProductSpecification.objects.filter(current_price__gte=min_price, current_price__lte=max_price)
                all_products = all_products.filter(specificProduct__in=specifications).distinct()
            
            serializer = ProductListSerializer(all_products, many=True)
            serialized_data = serializer.data
            for item in serialized_data:
                if get_user.id in item["is_love"]:
                    item["wishlist_status"] = True
                else:
                    item["wishlist_status"] = False
            paginator = PageNumberPagination()
            paginator.page_size = 10  # Set the page size to 20
            products_data = paginator.paginate_queryset(serialized_data, request)
            paginated_response = paginator.get_paginated_response(products_data)
            data["status"] = status.HTTP_200_OK
            data["count"] = paginated_response.data["count"]
            data["previous"] = paginated_response.data["previous"]
            data["next"] = paginated_response.data["next"]
            data["data"] = paginated_response.data["results"]
            data["message"] = "Products are fetched successfully."

        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, f"User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(['GET'])
def category_details(request):
    data = {"status": "", "message": "", "data": []}
    try:
        all_categories = MerchandiseStoreCategory.objects.all()
        
        categories_list = []
        for category in all_categories:
            # Get all products in the category
            products = category.productCategory.all()
            
            # Initialize variables for min price, max price, and sizes
            min_price = None
            max_price = None
            sizes = set()

            for product in products:
                # Get min and max prices from specifications
                product_specifications = product.specificProduct.all()
                product_min_price = product_specifications.aggregate(Min('current_price'))['current_price__min']
                product_max_price = product_specifications.aggregate(Max('current_price'))['current_price__max']

                # Update the overall min and max prices
                if product_min_price is not None:
                    min_price = min(min_price, product_min_price) if min_price is not None else product_min_price
                if product_max_price is not None:
                    max_price = max(max_price, product_max_price) if max_price is not None else product_max_price

                # Collect all unique sizes
                sizes.update(product_specifications.values_list('size', flat=True).distinct())

            details = {
                "id": category.id, 
                "name": category.name,
                "min_price": min_price,
                "max_price": max_price,
                "sizes": list(sizes),
            }
            categories_list.append(details)
        
        data["status"] = status.HTTP_200_OK
        data["data"] = categories_list
        data["message"] = "Category details fetched successfully."
            
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = str(e)

    return Response(data)


@api_view(("GET",))
def sorted_product_list(request):
    data = {"status": "", "message": "", "data": []}
    try:
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        sort_by = request.GET.get('sort_by')
        search_text = request.GET.get('search_text')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user:
            get_user = check_user.first()
            products = MerchandiseStoreProduct.objects.all()

            if search_text:
                product_filters = Q(category__name__icontains=search_text) | \
                                 Q(name__icontains=search_text) | \
                                 Q(leagues_for__name__icontains=search_text) | \
                                 Q(description__icontains=search_text) | \
                                 Q(specifications__icontains=search_text) | \
                                 Q(rating__icontains=search_text)
                
                products = products.filter(product_filters).distinct('id')
                for product in products:
                    search_log, created = ProductSearchLog.objects.get_or_create(product=product)
                    if not created:
                        search_log.search_count = F('search_count') + 1
                        search_log.save()
            if sort_by == 'price':
                products = products.sort_by_price()
            elif sort_by == 'price_desc':
                products = products.sort_by_price_desc()
            elif sort_by == 'popularity':
                products = products.sort_by_popularity()
            elif sort_by == 'newest':
                products = products.sort_by_newest()

           
            serializer = ProductListSerializer(products, many=True)
            serialized_data = serializer.data
            for item in serialized_data:
                if get_user.id in item["is_love"]:
                    item["wishlist_status"] = True
                else:
                    item["wishlist_status"] = False
            paginator = PageNumberPagination()
            paginator.page_size = 10  # Set the page size to 20
            products_data = paginator.paginate_queryset(serialized_data, request)            
            paginated_response = paginator.get_paginated_response(products_data)
            data["status"] = status.HTTP_200_OK
            data["count"] = paginated_response.data["count"]
            data["previous"] = paginated_response.data["previous"]
            data["next"] = paginated_response.data["next"]
            data["data"] = paginated_response.data["results"]
            data["message"] = "Products are fetched successfully."
        else:   
            data["status"] = status.HTTP_404_NOT_FOUND
            data["data"] = []
            data["message"] = "User not found."
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data["data"] = []
        data['message'] = str(e)
    return Response(data)
     

@api_view(("GET",))
def top_discount_products(request):
    data = {"status": "", "message": "", "data": []}
    try:
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user:
            get_user = check_user.first()
            top_five_products = MerchandiseStoreProduct.objects.annotate(max_discount=Max('specificProduct__discount')).order_by('-max_discount')[:5]
            serializer = ProductListSerializer(top_five_products, many=True)
            serialized_data = serializer.data
            for item in serialized_data:
                if get_user.id in item["is_love"]:
                    item["wishlist_status"] = True
                else:
                    item["wishlist_status"] = False
            data["status"] = status.HTTP_200_OK
            data["message"] = "Top discount products fetched successfully."
            data["data"] = serialized_data
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found"
            data["data"] = []
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data["data"] = []
        data['message'] = str(e)
    return Response(data)


@api_view(("GET",))
def top_discount_product_ad_images(request):
    data = {"status": "", "message": "", "data": []}
    try:
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user:
            get_user = check_user.first()
            top_five_products = MerchandiseStoreProduct.objects.annotate(max_discount=Max('specificProduct__discount')).order_by('-max_discount')[:5]
            ad_images = [product.advertisement_image.url if product.advertisement_image else None for product in top_five_products]
            data["status"] = status.HTTP_200_OK
            data["message"] = "Top discount products fetched successfully."
            data["data"] = ad_images
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found"
            data["data"] = []
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data["data"] = []
        data['message'] = str(e)
    return Response(data)


@api_view(("GET",))
def top_rated_products(request):
    data = {"status": "", "message": "", "data": []}
    try:
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user:
            get_user = check_user.first()
            top_rated_products = MerchandiseStoreProduct.objects.order_by('-rating', '-rating_count')[:10]
            serializer = ProductListSerializer(top_rated_products, many=True)
            serialized_data = serializer.data
            for item in serialized_data:
                if get_user.id in item["is_love"]:
                    item["wishlist_status"] = True
                else:
                    item["wishlist_status"] = False
            data["status"] = status.HTTP_200_OK
            data["message"] = "Top rated products fetched successfully."
            data["data"] = serialized_data
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found"
            data["data"] = []
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data["data"] = []
        data['message'] = str(e)
    return Response(data)


@api_view(("GET",))
def most_searched_products(request):
    data = {"status": "", "message": "", "data": []}
    try:
        user_uuid = request.GET.get("user_uuid")
        user_secret_key = request.GET.get("user_secret_key")
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user:
            get_user = check_user.first()
            most_searched_products = MerchandiseStoreProduct.objects.filter(searchLogs__isnull=False).annotate(total_searches=models.Sum('searchLogs__search_count')).order_by('-total_searches')[:10]
            serializer = ProductListSerializer(most_searched_products, many=True)
            serialized_data = serializer.data
            for item in serialized_data:
                if get_user.id in item["is_love"]:
                    item["wishlist_status"] = True
                else:
                    item["wishlist_status"] = False
            data["status"] = status.HTTP_200_OK
            data["message"] = "Most searched fetched successfully."
            data["data"] = serialized_data
        else:
            data["status"] = status.HTTP_404_NOT_FOUND
            data["message"] = "User not found"
            data["data"] = []
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data["data"] = []
        data['message'] = str(e)
    return Response(data)

    
@api_view(('POST',))
def buy_now(request):
    """
    Allows a user to directly buy any product from product list.
    """
    data = {"status": "", "message": ""}
    try:        
        delivery_address_main = None
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        delivery_address_main = request.data.get('delivery_address_main_id')
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity'))
        size = request.data.get('size')
        coupon_code = request.data.get('coupon_code')
        check_coupon = CouponCode.objects.filter(coupon_code=coupon_code, start_date__lte=datetime.now(), end_date__gte=datetime.now()).first()
        product = MerchandiseStoreProduct.objects.filter(id=int(product_id)).first()
        price = MerchandiseProductSpecification.objects.filter(product=product, size=size).first().current_price

        if not check_user.exists():            
            return Response({'message': 'User does not exist.', 'status': status.HTTP_404_NOT_FOUND})
        
        get_user = check_user.first()
        
        if delivery_address_main is None:
            user_street = check_user.first().street
            user_city = check_user.first().city
            user_state = check_user.first().state
            user_postal_code = check_user.first().postal_code
            delivery_address = f"{user_street},{user_city},{user_state},{user_postal_code}"
        else:
            
            delivery_address = ProductDeliveryAddress.objects.filter(id=delivery_address_main,created_by=get_user).first().complete_address
        obj = GenerateKey ()
        secret_key = obj.gen_payment_key()

        if check_coupon and product in check_coupon.product.all():
            unit_amount = (int(price)-(int(price)*int(check_coupon.percentage))/100)*int(quantity)
        else:
            unit_amount = int(quantity)*int(price)

        add_buy = CustomerMerchandiseStoreProductBuy.objects.create(
            secret_key = secret_key,            
            product_id = product_id,
            price_per_product = price,
            quantity = quantity,
            status = "BuyNow",
            total_price = int(quantity)*int(price),
            delivery_address_main_id = delivery_address_main,
            delivery_address = delivery_address,
            created_by = get_user,
            size = size
        )
        
        check_wallet = Wallet.objects.filter(user=get_user)
        if not check_wallet.exists():
            return Response(
                {"status": status.HTTP_404_NOT_FOUND, "message": "No wallet found.", "data": []}
            )
        
        get_wallet = check_wallet.first()
        balance = get_wallet.balance
        
        if float(balance) >= float(unit_amount):
            add_buy.is_paid=True
            add_buy.status="ORDER PLACED"
            add_buy.save()

            merchandise_cost = (settings.ORGANIZER_PERCENTAGE * unit_amount) /100
            admin_cost = (settings.ADMIN_PERCENTAGE * unit_amount) /100
            print(merchandise_cost, admin_cost)
            WalletTransaction.objects.create(
                    sender = get_user,
                    reciver = add_buy.product.created_by,
                    reciver_cost = Decimal(merchandise_cost),
                    amount = Decimal(unit_amount),
                    admin_cost = Decimal(admin_cost),
                    getway_charge = 0,
                    transaction_type="debit",
                    transaction_for="Store",
                    payment_id=None,  
                    description=f"${unit_amount} is debited from your PickleIt wallet for {add_buy.product.name} purchase."
                    )
            get_wallet.balance = Decimal(float(get_wallet.balance) - float(unit_amount))
            get_wallet.save()

            admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
            admin_balance = float(admin_wallet.balance) + float(admin_cost)
            admin_wallet.balance = Decimal(admin_balance)
            admin_wallet.save()

            merchant_wallet = Wallet.objects.filter(user=add_buy.product.created_by).first()
            merchant_balance = float(merchant_wallet.balance) + float(merchandise_cost)
            merchant_wallet.balance = Decimal(merchant_balance)
            merchant_wallet.save()

            # send notification to merchant            
            title = "Merchandise product order placed."
            message = f"{get_user.first_name} {get_user.last_name} has placed an order for buying {add_buy.product.name}."
            
            notify_edited_player(add_buy.product.created_by.id, title, message)
        
            data['status'] = status.HTTP_200_OK
            data["message"] = f"You have successfully placed order for {add_buy.product.name} and ${unit_amount} has been deducted from your wallet."

        else:
            remaining_amount = float(unit_amount) - float(balance)
            data['status'] = status.HTTP_200_OK
            data["message"] = f"Please add ${remaining_amount} to your wallet to buy these products." 

        return Response(data) 

    except Exception as e:
        return Response({"status": status.HTTP_400_BAD_REQUEST, "message": str(e)})
        

#buy all cart product
@api_view(('POST',))
def buy_cart_products(request):
    """
    Allows a user to buy all their cart products and apply a coupon code if provided, only for eligible products.
    """
    data = {"status":'', }
    try:
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        coupon_code = request.data.get('coupon_code')

        # Validate user
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            return Response({'message': 'User does not exist.', 'status': status.HTTP_404_NOT_FOUND})

        get_user = check_user.first()    

        # Get all cart products
        all_cart_product = CustomerMerchandiseStoreProductBuy.objects.filter(created_by_id=get_user.id, status="CART", is_paid=False)
        
        if not all_cart_product.exists():
            return Response({'message': 'No items in cart', 'status': status.HTTP_404_NOT_FOUND})

        card_id_list = []
        all_product_string = "Your merchandise product "
        total_price = 0
        delivery_address_main = ProductDeliveryAddress.objects.filter(created_by=get_user, default_address=True).first()
        obj = GenerateKey()
        generate_cart_id = obj.generate_cart_unique_id()

        eligible_products = set()
       
        discount_percentage = 0
        if coupon_code:            
            coupon = CouponCode.objects.filter(
                coupon_code=coupon_code, start_date__lte=datetime.now(), end_date__gte=datetime.now()
            ).first()
            if coupon:
                eligible_products = set(coupon.product.values_list('id', flat=True))
                discount_percentage = coupon.percentage
            else:
                coupon_code = None  

        product_prices = {}  
        
        for cpd in all_cart_product:
            card_id_list.append(cpd.id)
            p_name = cpd.product.name
            original_price = cpd.price_per_product * cpd.quantity

            final_price = original_price
            if cpd.product.id in eligible_products and coupon_code:
                discount_amount = original_price * (discount_percentage / 100)
                final_price -= discount_amount

            product_prices[cpd.id] = final_price  
            total_price += final_price

            all_product_string += p_name + ", "
            complete_address = (
                f"{delivery_address_main.street}, {delivery_address_main.city}, "
                f"{delivery_address_main.state}, {delivery_address_main.country}, "
                f"PIN-{delivery_address_main.postal_code}"
                if delivery_address_main else ""
            )
            CustomerMerchandiseStoreProductBuy.objects.filter(uuid=cpd.uuid).update(
                delivery_address_main=delivery_address_main,
                delivery_address=complete_address,
                cart_idd=generate_cart_id
            )

        check_wallet = Wallet.objects.filter(user=get_user)
        if not check_wallet.exists():
            return Response(
                {"status": status.HTTP_404_NOT_FOUND, "message": "No wallet found.", "data": []}
            )
        
        get_wallet = check_wallet.first()
        balance = get_wallet.balance
        print(product_prices)
        if float(balance) >= float(total_price):

            for kl in card_id_list:
                product= CustomerMerchandiseStoreProductBuy.objects.filter(id=kl).first()
                product.is_paid=True
                product.status="ORDER PLACED"
                product.save()

                price = product_prices[kl]
                merchandise_cost = (settings.ORGANIZER_PERCENTAGE * price) /100
                admin_cost = (settings.ADMIN_PERCENTAGE * price) /100
                print(merchandise_cost, admin_cost)
                WalletTransaction.objects.create(
                        sender = get_user,
                        reciver = product.created_by,
                        reciver_cost = Decimal(merchandise_cost),
                        amount = Decimal(price),
                        admin_cost = Decimal(admin_cost),
                        getway_charge = 0,
                        transaction_type="debit",
                        transaction_for="Store",
                        payment_id=None,  
                        description=f"${price} is debited from your PickleIt wallet for {product.product.name} purchase."
                        )
                get_wallet.balance = Decimal(float(get_wallet.balance) - float(price))
                get_wallet.save()

                admin_wallet = Wallet.objects.filter(user__is_superuser=True).first()
                admin_balance = float(admin_wallet.balance) + float(admin_cost)
                admin_wallet.balance = Decimal(admin_balance)
                admin_wallet.save()

                merchant_wallet = Wallet.objects.filter(user=product.product.created_by).first()
                merchant_balance = float(merchant_wallet.balance) + float(merchandise_cost)
                merchant_wallet.balance = Decimal(merchant_balance)
                merchant_wallet.save()

                # send notification to merchant                
                title = "Merchandise product order placed."
                message = f"{get_user.first_name} {get_user.last_name} has placed an order for buying {product.product.name}."
                
                notify_edited_player(product.product.created_by.id, title, message)
            
            data['status'] = status.HTTP_200_OK
            data["message"] = f"You have successfully placed order for your cart products and ${total_price} has been deducted from your wallet."

        else:
            remaining_amount = float(total_price) - float(balance)
            data['status'] = status.HTTP_200_OK
            data["message"] = f"Please add ${remaining_amount} to your wallet to buy the cart products." 

        return Response(data) 

    except Exception as e:
        return Response({"status": status.HTTP_400_BAD_REQUEST, "message": str(e)})
   
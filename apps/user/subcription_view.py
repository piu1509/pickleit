from datetime import timedelta, timezone
from django.shortcuts import get_object_or_404, render
import requests
import json, stripe
from decimal import Decimal
import datetime
from apps.team.views import notify_edited_player
from django.utils.timezone import now
from myproject import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Transaction, Subscription, SubscriptionPlan, User, Wallet, WalletTransaction, TransactionFor, AllPaymentsTable
from django.utils import timezone
from datetime import timedelta
import base64
import logging
logger = logging.getLogger('myapp')

def create_permition_user(data):
    # Sort plans by price (convert to float for correct numerical sorting)
    plans = sorted(data, key=lambda x: float(x['price']))

    # Initialize a dictionary to store feature names and their lowest plan
    feature_plan_map = {}
    current_plan = None
    # Iterate through each plan
    for plan in plans:
        plan_name = plan['product_id']
        if plan["is_active"] == True:
            current_plan = plan
        # Iterate through each feature in the plan
        for feature in plan['features']:
            feature_name = feature['name']
            # Only consider features where is_show is True
            if feature['is_show']:
                # If feature not in map, update it
                if feature_name not in feature_plan_map:
                    feature_plan_map[feature_name] = plan_name

    # Convert to list of objects, including is_access based on plan's is_active
    if current_plan:
        feature_name_list = [fe["name"] for fe in current_plan["features"] if fe["is_show"] in ["True", True, "true"]]
    result = [
        {
            "name": name,
            "lowest_plan": plan,
            "is_access": name in feature_name_list
        }
        for name, plan in sorted(feature_plan_map.items())
    ]
    
    return result

def user_subscription_data(user_uuid, platform):
    try:
        user = get_object_or_404(User, uuid=user_uuid)
        
        if not platform or platform not in ['google', 'apple']:
            return Response({"error": "Invalid or missing platform (ios/android)"}, status=400)
        
        # Fetch all plans for the platform
        plans = SubscriptionPlan.objects.filter(platform=platform).order_by("id").values(
            "id", "name", "price", "description", "duration_days", "product_id", "features"
        )
        
        if not plans.exists():
            return Response({"error": f"No subscription plans found for platform: {platform}"}, status=404)
        
        plan_list = []
        active_subscription = Subscription.objects.filter(user=user, end_date__gte=now()).last()
        
        
        if active_subscription:
            plan_name = active_subscription.plan.name
            plan_id_list = list(SubscriptionPlan.objects.filter(name=plan_name).values_list("product_id", flat=True))
            current = False
            for plan in plans:
                plan["price"] = str(plan["price"])
                is_active = plan["product_id"] in plan_id_list
                is_desable = not current
                expire_on = active_subscription.end_date.strftime("%m/%d/%Y") if is_active and not current else None
                if is_active and not current:
                    current = True
                if expire_on:
                    expire_on = str(expire_on)
                plan_list.append({
                    **plan,
                    "is_desable": is_desable,
                    "is_active": is_active,
                    "expire_on": expire_on,
                })
        else:
            default_plan_id = "PICKLEIT"
            for plan in plans:
                plan["price"] = str(plan["price"])
                is_active = default_plan_id == plan["product_id"]
                is_desable = default_plan_id == plan["product_id"]
                expire_on = None
                plan_list.append({
                    **plan,
                    "is_desable": is_desable,
                    "is_active": is_active,
                    "expire_on": expire_on,
                })
        
        return plan_list
    except Exception as e:
        print(f"Error in user_subscription_data: {e}")
        return []



@api_view(['POST'])
def validate_iap(request):
    """
    Validates an Apple or Google IAP receipt and activates the subscription.
    """
    user = get_object_or_404(User, uuid=request.data.get("user_uuid"))
    receipt_data = request.data.get("receipt_data")
    platform = request.data.get("platform")  # 'apple' or 'google'
    product_id = request.data.get("product_id")

    if not receipt_data or not platform:
        return Response({"error": "Missing required fields"}, status=400)

    # Validate base64 format
    try:
        base64.b64decode(receipt_data, validate=True)
    except Exception as e:
        logger.error(f"Invalid base64 receipt_data: {str(e)}")
        return Response({"error": "Invalid receipt format", "details": str(e)}, status=400)

    try:
        plan = SubscriptionPlan.objects.get(product_id=product_id, platform=platform)
    except SubscriptionPlan.DoesNotExist:
        return Response({"error": "Invalid product ID"}, status=400)

    if platform == 'apple':
        APPLE_SANDBOX_URL = "https://sandbox.itunes.apple.com/verifyReceipt"
        APPLE_PRODUCTION_URL = "https://buy.itunes.apple.com/verifyReceipt" # Use sandbox for testing
        try:
            response = requests.post(APPLE_SANDBOX_URL, json={"receipt-data": receipt_data, 'password': 'cda8b344d1f1426086b06bd1413a0642',}, timeout=10)
            response.raise_for_status()  # Raise an error for bad HTTP status
            response_data = response.json()

            if response_data.get("status") == 0:  # Valid receipt
                latest_receipt_info = response_data.get("latest_receipt_info", [])
                if not latest_receipt_info:
                    logger.error("No transaction info in Apple receipt")
                    return Response({"error": "No transaction info in receipt", "apple_response": response_data}, status=400)
                transaction_id = latest_receipt_info[0].get("transaction_id")
                if not transaction_id:
                    logger.error("Missing transaction ID in Apple receipt")
                    return Response({"error": "Missing transaction ID in receipt", "apple_response": response_data}, status=400)
            else:
                logger.error(f"Invalid Apple receipt: status {response_data.get('status')}, response: {response_data}")
                return Response(
                    {
                        "error": "Invalid Apple receipt",
                        "status": response_data.get("status"),
                        "apple_response": response_data
                    },
                    status=400
                )
        except requests.RequestException as e:
            logger.error(f"Error communicating with Apple server: {str(e)}")
            return Response({"error": "Error communicating with Apple server", "details": str(e)}, status=500)
        except ValueError as e:
            logger.error(f"Invalid response from Apple server: {str(e)}")
            return Response({"error": "Invalid response from Apple server", "details": str(e)}, status=400)

    elif platform == 'google':
        transaction_id = request.data.get("transaction_id")
        if not transaction_id:
            return Response({"error": "Missing transaction ID for Google"}, status=400)
    else:
        return Response({"error": "Invalid platform"}, status=400)

    # Create a Transaction
    try:
        Transaction.objects.create(
            user=user,
            plan=plan,
            transaction_id=transaction_id,
            receipt_data=receipt_data,
            platform=platform,
            status="success",
        )
    except Exception as e:
        logger.error(f"Error creating transaction: {str(e)}")
        return Response({"error": "Failed to create transaction", "details": str(e)}, status=500)

    # Activate Subscription
    try:
        end_date = timezone.now() + timedelta(days=plan.duration_days)
        check_plan = Subscription.objects.filter(user=user, plan=plan)
        if check_plan.exists():
            get_plan = check_plan.first()
            get_plan.end_date = end_date
            get_plan.save()
        else:
            Subscription.objects.create(user=user, plan=plan, end_date=end_date)
    except Exception as e:
        logger.error(f"Error activating subscription: {str(e)}")
        return Response({"error": "Failed to activate subscription", "details": str(e)}, status=500)

    return Response({"message": "Subscription activated successfully!"}, status=200)

@api_view(["GET"])
def get_user_subcription_permition(request):
    try:
        platform = request.GET.get("platform")
        user_uuid = request.GET.get("user_uuid")
        
        if not user_uuid:
            return Response({"error": "Missing user_uuid"}, status=400)
        platform = "google"
        result = user_subscription_data(user_uuid, platform)
        if isinstance(result, Response):
            return result  # Propagate error responses from user_subscription_data
        
        if not result:
            return Response({"message": "Something is wrong", "data": []}, status=200)
        
        final_result = create_permition_user(result)
        return Response(final_result, status=200)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
def get_subscription_plans(request):
    
    """
    Returns all subscription plans, marking the free plan as active if the user has no subscription.
    """
    platform = request.GET.get("platform")  # 'google', 'apple'
    user_uuid = request.GET.get("user_uuid")

    result = user_subscription_data(user_uuid, platform)
    return Response(result, status=200)

@api_view(['GET'])
def get_next_plans(request):
    """
    Returns the next subscription plan after the current active plan.
    If the user has no active subscription, marks the free plan as current.
    """
    platform = request.GET.get("platform")
    user_uuid = request.GET.get("user_uuid")

    # Validate inputs
    if not platform or platform not in ['google', 'apple']:
        return Response({"error": "Invalid or missing platform (google/apple)"}, status=400)
    if not user_uuid:
        return Response({"error": "Missing user_uuid"}, status=400)

    # Fetch user
    user = get_object_or_404(User, uuid=user_uuid)

    # Initialize result
    result = {
        "name": None,
        "product_id": None,
        "current_plan": None,
        "current_plan_id": None
    }

    # Get the latest active subscription
    active_subscription = Subscription.objects.filter(
        user=user, end_date__gte=timezone.now()
    ).order_by('-end_date').first()

    # Determine current plan
    if active_subscription:
        current_plan = SubscriptionPlan.objects.filter(
            platform=platform, name=active_subscription.plan.name
        ).first()
    else:
        # Assume "PICKLEIT" is the default/free plan
        current_plan = SubscriptionPlan.objects.filter(
            platform=platform, product_id="PICKLEIT"
        ).first()

    if current_plan:
        result["current_plan"] = current_plan.name
        result["current_plan_id"] = current_plan.product_id

        # Get the next plan (ordered by id, assuming sequential progression)
        next_plan = SubscriptionPlan.objects.filter(
            platform=platform, id__gt=current_plan.id
        ).order_by('id').values("name", "product_id").first()

        if next_plan:
            result["name"] = next_plan["name"]
            result["product_id"] = next_plan["product_id"]

    return Response(result, status=200)



@api_view(['POST'])
def get_subscription_payment_link(request):
    user_uuid = request.data.get("user_uuid")
    platform = request.data.get("platform")
    product_id = request.data.get("product_id")

    if not all([user_uuid, platform, product_id]):
        return Response({"error": "Missing required fields"}, status=400)

    user = get_object_or_404(User, uuid=user_uuid)
    selected_plan = get_object_or_404(SubscriptionPlan, product_id=product_id, platform='google')

    selected_plan_price = Decimal(selected_plan.price)

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY

        if not user.stripe_customer_id:
            customer = stripe.Customer.create(email=user.email)
            user.stripe_customer_id = customer.id
            user.save()

        stripe_product = stripe.Product.create(
            name=selected_plan.name,
            description=f"Subscription for {selected_plan.name} on {platform}"
        )

        stripe_price = stripe.Price.create(
            unit_amount=int(selected_plan_price * 100),
            currency='usd',
            product=stripe_product.id
        )

        protocol = settings.PROTOCALL
        host = request.get_host()
        current_site = f"{protocol}://{host}"

        transaction_id = f"txn_{user_uuid}_{timezone.now().strftime('%Y%m%d%H%M%S')}_stripe"
        payment_data = {
            "product_id": product_id,
            "user_id": user.id,
            "deducted_amount": str(selected_plan_price),
            "payment_date": str(timezone.now()),
            "transaction_id": transaction_id
        }

        encoded_data = base64.urlsafe_b64encode(json.dumps(payment_data).encode('utf-8')).decode('utf-8')
        success_url = f"{current_site}/user/plan/subscription/payment/{encoded_data}/{{CHECKOUT_SESSION_ID}}/"
        cancel_url = f"{current_site}/user/plan/subscription/cancel/"

        session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            line_items=[{'price': stripe_price.id, 'quantity': 1}],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url
        )

        Transaction.objects.create(
            user=user,
            plan=selected_plan,
            transaction_id=transaction_id,
            receipt_data=f"payment through stripe for plan {selected_plan_price}",
            platform=platform,
            status="pending"
        )

        AllPaymentsTable.objects.create(
            user=user,
            amount=selected_plan_price,
            checkout_session_id=session.id,
            payment_for=f"selected plan {selected_plan.name}",
            payment_mode="stripe",
            status="Pending"
        )

        return Response({"message": "Proceed to payment", "url": session.url})

    except Exception as e:
        logger.error(f"Stripe error: {str(e)}")
        return Response({"error": f"Failed to create payment link - {str(e)}"}, status=400)

@api_view(['GET'])
def get_subscription_payment_link_verify(request, encoded_data, session_id):
    """
    Verifies Stripe payment and activates subscription upon successful payment.
    Renders done_payment.html on success or failed_payment.html on failure.
    """
    try:
        # Decode payment data
        decoded_data = base64.urlsafe_b64decode(encoded_data).decode('utf-8')
        data = json.loads(decoded_data)

        user_id = data.get("user_id")
        product_id = data.get("product_id")
        deducted_amount = Decimal(data.get("deducted_amount", "0.00"))
        transaction_id = data.get("transaction_id")

        user = get_object_or_404(User, id=user_id)
        selected_plan = get_object_or_404(SubscriptionPlan, product_id=product_id, platform='google')

        logger.debug(f"Verifying plan: {selected_plan.name}, duration_days={selected_plan.duration_days}")

        # Handle missing duration safely
        duration_days = selected_plan.duration_days or 30
        now_time = timezone.now()

        transaction = Transaction.objects.filter(
            user=user,
            plan=selected_plan,
            status="pending"
        ).last()

        payment = AllPaymentsTable.objects.filter(
            user=user,
            checkout_session_id=session_id,
            status="Pending"
        ).last()

        if not transaction or not payment:
            # Try to find any past ones (fallback)
            payment = AllPaymentsTable.objects.filter(
                user=user,
                checkout_session_id=session_id
            ).last()

            transaction = Transaction.objects.filter(
                user=user,
                plan=selected_plan
            ).last()

            if payment and transaction:
                return render(request, "plan/done_payment.html", {"message": "Subscription activated successfully!"})
            else:
                return render(request, "plan/failed_payment.html", {"error": "Payment not found or already processed"})

        # Check Stripe session
        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.retrieve(session_id)

        if session.payment_status != "paid":
            transaction.status = "failed"
            payment.status = "Failed"
            transaction.save()
            payment.save()
            return render(request, "plan/failed_payment.html", {"error": "Payment not completed"})

        # Record wallet transaction
        wallet_txn = WalletTransaction.objects.create(
            sender=user,
            transaction_type="credit",
            transaction_for="Plan",
            admin_cost=str(deducted_amount),
            payment_id=transaction_id,
            json_response={"session_id": session_id},
            amount=deducted_amount,
            description=f"Subscription payment for {selected_plan.name}"
        )

        TransactionFor.objects.create(
            transaction=wallet_txn,
            details=data
        )

        transaction.status = "success"
        transaction.save()

        payment.status = "Completed"
        payment.json_response = {"session_id": session_id}
        payment.save()
        # Create or update subscription
        check_plan = Subscription.objects.filter(user=user, plan=selected_plan)
        if check_plan:
            get_plan = check_plan.first()
            get_plan.start_date = now_time
            get_plan.end_date = now_time + timedelta(days=duration_days)
            get_plan.is_active = True
            get_plan.save()
        else:
            Subscription.objects.create(user=user, plan=selected_plan, start_date = now_time, end_date = now_time + timedelta(days=duration_days),is_active = True)

        # Notify user
        notify_edited_player(
            user.id,
            "Your subscription has been activated successfully!",
            "Subscription Activated"
        )

        return render(request, "plan/done_payment.html", {"message": "Subscription activated successfully!"})

    except Exception as e:
        logger.error(f"Error verifying payment link: {str(e)}")
        return render(request, "plan/failed_payment.html", {"error": f"Failed to verify payment: {str(e)}"})


@api_view(['GET'])
def get_subscription_payment_cancel(request):
    try:
        session_id = request.GET.get("session_id")
        if not session_id:
            return render(request, "plan/failed_payment.html", {"error": "No session ID provided"})

        payment = AllPaymentsTable.objects.filter(checkout_session_id=session_id, status="Pending").first()
        if payment:
            payment.status = "Failed"
            payment.json_response = {"session_id": session_id, "status": "Failed"}
            payment.save()

            transaction = Transaction.objects.filter(
                user=payment.user,
                plan__name__icontains=payment.payment_for.split()[-1],
                status="pending"
            ).first()
            if transaction:
                transaction.status = "Failed"
                transaction.save()

        return render(request, "plan/failed_payment.html", {"message": "Payment canceled"})

    except Exception as e:
        logger.error(f"Payment cancel error: {str(e)}")
        return render(request, "plan/failed_payment.html", {"error": f"Failed to process cancellation: {str(e)}"})




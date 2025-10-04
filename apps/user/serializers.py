from apps.user.models import *
from rest_framework import serializers


# class FeaturesSerializer(serializers.ModelSerializer):
#     """
#     Serializer for Features model, showing which plans include each feature.
#     """
#     status = serializers.SerializerMethodField()

#     class Meta:
#         model = Features
#         fields = ['id', 'name', 'description', 'status']

#     def get_status(self, obj):
#         """
#         Returns a list of plan names that include this feature.
#         """
#         plan = self.context.get('plan')  # Get the plan from the context
#         if not plan:
#             return False
#         return obj.plan.filter(id=plan.id).exists()


# class SubscriptionPlanSerializer(serializers.ModelSerializer):
#     """
#     Serializer for SubscriptionPlan model, showing its features and calculated prices.
#     """
#     features = serializers.SerializerMethodField() 
#     monthly_price = serializers.SerializerMethodField()
#     annual_price = serializers.SerializerMethodField()
#     is_subscribed = serializers.SerializerMethodField()  
#     is_button = serializers.SerializerMethodField()


#     class Meta:
#         model = SubscriptionPlan
#         fields = ['id', 'name', 'price', 'description', 'duration_days', 'monthly_price', 'annual_price', 'features', 'is_subscribed', 'is_button']
    
#     def get_features(self, obj):
#         """
#         Fetches only the features related to this specific plan and determines their status.
#         """
#         features = Features.objects.all()
#         first_five = features[:5]
#         last_five = features.order_by('-id')[:5]  
#         last_five = list(last_five)[::-1]  

#         selected_features = list(first_five) + list(last_five)
#         return FeaturesSerializer(selected_features, many=True, context={'plan': obj}).data

#     def get_monthly_price(self, obj):
#         """
#         Calculates the approximate monthly price based on the duration.
#         Assumes 30 days in a month.
#         """
#         if obj.duration_days >= 30:  
#             return round((obj.price / obj.duration_days) * 30, 2)  
#         return obj.price  

#     def get_annual_price(self, obj):
#         """
#         Calculates the approximate annual price based on the duration.
#         Assumes 365 days in a year.
#         """
#         if obj.duration_days < 365:  
#             return round((obj.price / obj.duration_days) * 365, 2)
#         return obj.price
    
#     def get_is_subscribed(self, obj):
#         """Checks if the authenticated user is subscribed to this plan."""
#         user = self.context.get('user')  

#         if not user:
#             return False  

#         return Subscription.objects.filter(user=user, plan=obj, end_date__gte=now()).exists()
    
#     def get_is_button(self, obj):
#         """Determines if the upgrade button should be enabled for this plan."""
#         user = self.context.get('user')
#         if not user:
#             return False 

#         user_subscription = Subscription.objects.filter(
#             user=user, end_date__gte=now()
#         ).select_related('plan').first()

#         if not user_subscription:
#             return True  

#         user_plan_name = user_subscription.plan.name 
#         plan_order = {  
#             'Free': 1,
#             'Paid with upgrade': 2,
#             'Pro': 3,
#             'Enterprise': 4
#         }

#         user_plan_rank = plan_order.get(user_plan_name, 0)  
#         current_plan_rank = plan_order.get(obj.name, 0)  

#         if current_plan_rank > user_plan_rank:
#             return True 
        
#         return False



class WalletTransactionSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    reciver_name = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = [
            'transaction_id', 'sender', 'sender_name', 'reciver', 'reciver_name', 
            'transaction_type', 'transaction_for', 'reciver_cost', 'admin_cost', 
            'getway_charge', 'amount', 'payment_id', 'json_response', 'description', 
            'created_at'
        ]

    def get_sender_name(self, obj):
        if obj.sender:
            return f"{obj.sender.first_name} {obj.sender.last_name}".strip()
        return None

    def get_reciver_name(self, obj):
        if obj.reciver:
            return f"{obj.reciver.first_name} {obj.reciver.last_name}".strip()
        return None


class WithdrawalRquestSerializer(serializers.ModelSerializer):

    class Meta:
        model = WithdrawalRequest
        fields = "__all__"

class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = "__all__"
        
from django.db import models
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from phonenumber_field.modelfields import PhoneNumberField
from django.dispatch import receiver
from django.db.models.signals import post_save
from datetime import timedelta, timezone
from django.utils.timezone import now
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password
# Create your models here.

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        return self.create_user(email, password, **extra_fields)

GENDER_STATUS_CHOICES = (
    ('Male', 'Male'),
    ('Female', 'Female'),
    ('Other', 'Other'),
)

class User(AbstractBaseUser, PermissionsMixin):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    email = models.EmailField(max_length=250, unique=True, null=True, blank=True)
    username = models.CharField(max_length=250, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=250, null=True, blank=True)
    last_name = models.CharField(max_length=250, null=True, blank=True)
    phone = models.CharField(max_length=20,null = True, blank = True)
    role = models.ForeignKey('Role',on_delete=models.SET_NULL, null=True, blank=True)
    user_birthday = models.DateField(null=True, blank=True)
    bio = models.CharField(max_length=255, null=True, blank=True)
    image = models.ImageField(upload_to='user_images/', null=True, blank=True)
    gender = models.CharField(choices=GENDER_STATUS_CHOICES, max_length=250, null=True, blank=True)
    street = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)
    permanent_location = models.TextField(null=True, blank=True)
    current_location = models.TextField(null=True, blank=True)
    # rank = models.PositiveIntegerField(default=0)
    latitude = models.CharField(max_length=255, null=True, blank=True)
    longitude = models.CharField(max_length=255, null=True, blank=True)
    rank = models.CharField(max_length=255, default="1")
    is_rank = models.BooleanField(default=False)
    fb_link = models.TextField(null=True, blank=True)
    twitter_link = models.TextField(null=True, blank=True)
    youtube_link = models.TextField(null=True, blank=True)
    tictok_link = models.TextField(null=True, blank=True)
    instagram_link = models.TextField(null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=250, blank=True, null=True)
    is_admin = models.BooleanField(default=False)
    is_team_manager = models.BooleanField(default=False)
    is_coach = models.BooleanField(default=False)
    is_player = models.BooleanField(default=False)
    is_organizer  = models.BooleanField(default=False)
    is_organizer_expires_at  = models.DateTimeField(null=True, blank=True)
    is_ambassador  = models.BooleanField(default=False)
    is_ambassador_expires_at  = models.DateTimeField(null=True, blank=True)
    is_merchant = models.BooleanField(default=False)
    is_sponsor  = models.BooleanField(default=False)
    is_sponsor_expires_at  = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    password_raw = models.CharField(max_length=250, null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    generated_otp = models.CharField(max_length=250, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_screen = models.BooleanField(default=False)
    availability = models.JSONField(default=dict, null=True, blank=True)
    is_updated = models.BooleanField(default=False)
    
    USERNAME_FIELD = 'username'

    REQUIRED_FIELDS = ['email']

    objects = UserManager()
    def __str__(self):
        if self.username:
            username = self.username
        else:
            username = None
        return f'Username : {username}; Role : {self.role}'
    
    def get_role(self):
        return f'{self.role}'
    
    def save(self, *args, **kwargs):
        if self.password_raw:
            self.password = make_password(self.password_raw)
        super().save(*args, **kwargs)
        
    def get_full_name(self):
        first_name = str(self.first_name).capitalize()
        last_name = str(self.last_name).capitalize()
        return f'{first_name} {last_name}'
    
class Role(models.Model):
    """Database model for role"""
    role = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.role}'

APPROVE_STATUS_CHOICES = (
    ('True', 'True'),
    ('False', 'False'),
    ('Rejected', 'Rejected'),
)

class ProductSellerRequest(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=APPROVE_STATUS_CHOICES, default='False')

    def __str__(self):
        return f'{self.user.email} --> {self.status}'
    
    def save(self, *args, **kwargs):
        # Check if the status is being set to 'approved'
        if self.status == 'True':
            # Update the user's is_merchant attribute to True
            self.user.is_merchant = True
            self.user.save()
        super().save(*args, **kwargs)

# class ProductSellerDoc(models.Model):
#     file = models.FileField(upload_to="ProductSellerDoc")
#     approval = models.ForeignKey(ProductSellerRequest, on_delete=models.CASCADE)

#     def __str__(self):
#         return f'{self.approval.user.email}'

class IsSponsorDetails(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4)
    secret_key = models.CharField(max_length=250, unique=True)
    sponsor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sponsor')
    sponsor_added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sponsor_added_by')
    league_uuid = models.CharField(max_length=250, null=True, blank=True)
    league_secret_key = models.CharField(max_length=250, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f'{self.id}'

class AppUpdate(models.Model):
    update = models.CharField(max_length=100)
    updated_users = models.ManyToManyField(User, related_name='app_updates', blank=True)


QUESTIONS_FOR = (
    ('Beginner', 'Beginner'),
    ('Intermediate', 'Intermediate'),
    ('Advanced', 'Advanced'),
    ('All', 'All'),
)

class BasicQuestionsUser(models.Model):
    question = models.TextField()
    options = models.JSONField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='child_questions')
    question_for = models.CharField(choices=QUESTIONS_FOR, max_length=25, null=True, blank=True)
    when_ans = models.CharField(max_length=25, null=True, blank=True)
    is_last = models.BooleanField(default=False)
    
    def __str__(self):
        return self.question

class UserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questions_user')
    question = models.ForeignKey(BasicQuestionsUser, on_delete=models.CASCADE, related_name='user_answers')
    answer = models.CharField(max_length=15)

    def __str__(self):
        return f'User: {self.user.username}, Question: {self.question.question}, Answer: {self.answer}'


class PDFFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='download_user',null=True, blank=True)
    file = models.FileField(upload_to='pdf_files')
    filename = models.CharField(max_length=100)
    tournament = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return self.user.first_name
        

GENDER_CHOICES = (
    ("Male","Male"),
    ("Female","Female"),
    ("Others", "Others"),
)

TeamType = (
    ('Single', 'Single'),
    ('Double', 'Double'),
    ('Co-ed', 'Co-ed')
)
class MatchingDetails(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="matching_player")
    from_rank = models.CharField(max_length=5, null=True, blank=True)
    to_rank = models.CharField(max_length=5, null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    search_availability = models.JSONField(default=dict, null=True, blank=True)
    from_age = models.IntegerField(null=True, blank=True)
    to_age = models.IntegerField(null=True, blank=True)
    redious = models.IntegerField(null=True, blank=True)
    team_type = models.CharField(max_length=20,choices=TeamType, null=True, blank=True)

    def __str__(self):
        return self.user.first_name
    


class FCMTokenStore(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    fcm_token = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.user.first_name
    

class LogEntry(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]

    user = models.CharField(max_length=150, null=True, blank=True)  
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    instance_id = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name} {self.instance_id} at {self.timestamp}"
    

class AppVersionUpdate(models.Model):
    version = models.CharField(max_length=5, null=True, blank=True)
    release_date = models.DateTimeField()
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    updated_users = models.ManyToManyField(User, blank=True)

    def __str__(self):
        return f"Version {self.version} : {self.release_date}"
    
@receiver(post_save, sender=AppVersionUpdate)
def notification_for_version_update(sender, instance, created, **kwargs):
    if created:
        title = "New App Version Released!"
        message = f"Version {instance.version} is now available. Check it out!"
        from apps.chat.views import notify_all_users
        notify_all_users(title, message)


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Wallet - Balance: ${self.balance}"
    
    def save(self, *args, **kwargs):       
        if self.user.is_superuser:
            if Wallet.objects.filter(user__is_superuser=True).exclude(id=self.id).exists():
                raise ValidationError("Only one superuser can have a wallet.")

        super().save(*args, **kwargs)

    def deposit(self, amount):
        """Add funds to the wallet."""
        self.balance += amount
        self.save()

    def withdraw(self, amount):
        """Deduct funds from the wallet if sufficient balance is available."""
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            return True
        return False


@receiver(post_save, sender=User)
def create_wallet(sender, instance, created, **kwargs):
    """
    Creates a wallet when a new user is created.
    If the user is updated and does not have a wallet, a wallet is created.
    """
    if created or not hasattr(instance, 'wallet'):
        Wallet.objects.get_or_create(user=instance)
        

class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]

    TRANSACTION_FOR = [
        ('Subscription', 'Subscription'),
        ('AddMoney', 'AddMoney'),
        ('TeamRegistration', 'TeamRegistration'),
        ('Advertisement', 'Advertisement'),
        ('Plan', 'Plan'),
        ('Store', 'Store'),
        ('BookClub', 'BookClub'),
        ('JoinClub', 'JoinClub'),
        ('Withdraw', 'Withdraw'),
    ]
    transaction_id = models.CharField(max_length=15, unique=True, null=True, blank=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wallet_sender_user")
    reciver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wallet_reciver_user", blank=True, null=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    transaction_for = models.CharField(max_length=20, choices=TRANSACTION_FOR)
    reciver_cost = models.CharField(max_length=15, blank=True, null=True)
    admin_cost = models.CharField(max_length=15, blank=True, null=True)
    getway_charge = models.CharField(max_length=15, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_id = models.CharField(max_length=255, null=True, blank=True)
    json_response = models.JSONField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.sender.username} - {self.transaction_type} - ${self.amount}"

    def save(self, *args, **kwargs):
        """Generate a unique transaction ID and update wallet balance when saving a transaction."""

        if not self.created_at:  # Set created_at only on creation
            self.created_at = now()

        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()

        # if not self.pk:  
        #     if self.transaction_type == "credit":
        #         self.reciver.wallet.deposit(self.amount)  # Assuming Wallet model exists
        #     elif self.transaction_type == "debit":
        #         success = self.sender.wallet.withdraw(self.amount)
        #         if not success:
        #             raise ValueError("Insufficient wallet balance")
        
        super().save(*args, **kwargs)

    @staticmethod
    def generate_transaction_id():
        """Generate a unique transaction ID with a 15-character limit."""
        return str(uuid.uuid4().hex[:15]).upper()

class TransactionFor(models.Model):
    transaction = models.OneToOneField(WalletTransaction, on_delete=models.CASCADE)
    details = models.JSONField(default=dict)




class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawal_request')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Request {self.id} - {self.user.username} ({self.status})"
    
    def save(self, *args, **kwargs):
       
        if self.pk:
            old_instance = WithdrawalRequest.objects.get(pk=self.pk)
            if old_instance.status != "approved" and self.status == "approved":
               
                wallet = self.user.wallet
                if wallet.balance >= self.amount:
                    wallet.withdraw(self.amount)                      
                   
                    WalletTransaction.objects.create(
                        transaction_id=WalletTransaction.generate_transaction_id(),
                        sender=self.user,
                        reciver = self.user,
                        transaction_type="debit",
                        transaction_for="Withdraw",
                        amount=self.amount,
                        description=f"Withdrawal of ${self.amount} approved",
                        created_at=now()
                    )
                else:
                    raise ValidationError("Insufficient wallet balance for withdrawal.")

        super().save(*args, **kwargs)


class AllPaymentsTable(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    checkout_session_id = models.TextField(blank=True, null=True)
    payment_for = models.CharField(max_length=255, null=True, blank=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_mode = models.CharField(max_length=255, null=True, blank=True)
    json_response = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Completed', 'Completed'), ('Failed', 'Failed')])

    def __str__(self):
        return f"{self.user.username} : ${self.amount} - for {self.payment_for}, {self.payment_date}"
    

class AdminWallet(models.Model):
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    last_updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Ensure only one instance of AdminWallet exists. Raise error if more than one instance is attempted to be created."""
        
        if not self.pk and AdminWallet.objects.exists():
            raise ValidationError("Only one AdminWallet instance is allowed.")

        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        """Retrieve the single AdminWallet instance, creating it if necessary."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Admin Wallet - Balance: ${self.balance}"

    class Meta:
        verbose_name = "Admin Wallet"
        verbose_name_plural = "Admin Wallet"


class AdminWalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]

    wallet = models.ForeignKey('AdminWallet', on_delete=models.CASCADE, related_name='admin_transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(null=True, blank=True)
    payment_id = models.CharField(max_length=255, null=True, blank=True)
    json_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Automatically update the AdminWallet balance when a transaction is saved."""
        if not self.pk:  
            admin_wallet = AdminWallet.get_instance() 

            if self.transaction_type == 'credit':
                admin_wallet.balance += self.amount
            elif self.transaction_type == 'debit':
                admin_wallet.balance -= self.amount

            admin_wallet.save()  

        super().save(*args, **kwargs) 

    def __str__(self):
        return f"{self.transaction_type.capitalize()} - ${self.amount} - {self.description}"

    class Meta:
        verbose_name = "Admin Wallet Transaction"
        verbose_name_plural = "Admin Wallet Transactions"
        ordering = ['-created_at'] 



### subcription model
from django.utils.timezone import now
from datetime import timedelta
class SubscriptionPlan(models.Model):
    APPLE = 'apple'
    GOOGLE = 'google'
    
    PLATFORM_CHOICES = [
        (APPLE, 'Apple'),
        (GOOGLE, 'Google'),
    ]

    name = models.CharField(max_length=20)
    product_id = models.CharField(max_length=100)  # Apple/Google IAP product ID
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, null=True)
    duration_days = models.IntegerField(default=30)  # Duration of the subscription
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default=APPLE)
    features = models.JSONField(blank=True)

    def __str__(self):
        return f"{self.name} - ${self.price} - {self.platform}"


class Transaction(models.Model):
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILED = 'failed'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (SUCCESS, 'Success'),
        (FAILED, 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=255, unique=True, null=True, blank=True)  # Apple/Google transaction ID
    receipt_data = models.TextField(blank=True, null=True)  # Store Apple receipt or Google purchase token
    platform = models.CharField(max_length=10, choices=SubscriptionPlan.PLATFORM_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.status})"




class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
        super().save(*args, **kwargs)

    def renew_subscription(self, additional_days):
        """Extend subscription when renewed"""
        self.end_date += timedelta(days=additional_days)
        self.save()

    def is_valid(self):
        """Check if the subscription is still active"""
        return self.end_date >= now()

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} (Expires: {self.end_date.date()})"

role_call = [('viewer', 'viewer'),('admin', 'admin')]

class StoreCallId(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="call_id_user")
    call_id = models.TextField()
    role = models.CharField(max_length=10, choices=role_call)
    token = models.TextField()
    description = models.TextField(null=True, blank=True)
    start_time = models.DateTimeField()
    video_url = models.TextField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username}"


PromocodeType = [
    ('team_registration', 'Team Registration'),
    ('advertisement', 'Advertisement'),
    ('add_fund', 'Add Fund'),
    ('club_booking', 'Club Booking')
]

class PromoCode(models.Model):
    code = models.CharField(unique=True, max_length=12)
    discount = models.CharField(max_length=6)
    codefor = models.CharField(max_length=20, choices=PromocodeType)  # Increased length

    def __str__(self):
        return f"{self.discount}% discount for {self.codefor}"
import uuid
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save


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
        if self.status == 'True':            
            self.user.is_merchant = True
            self.user.save()
        super().save(*args, **kwargs)


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


PREFERENCE_CHOICE = (
    ("Singles","Singles"),
    ("Doubles","Doubles"),
    ("Co-ed", "Co-ed"),
)

class MatchingPlayers(models.Model):
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matching_player", null=True, blank=True)
    available_from = models.DateField(null=True, blank=True)
    available_to = models.DateField(null=True, blank=True)
    preference = models.CharField(choices=PREFERENCE_CHOICE, max_length=25, null=True, blank=True)
    self_rank = models.CharField(max_length=5,default=1, null=True, blank=True)
    rank1_range = models.CharField(max_length=5,null=True, blank=True)
    rank2_range = models.CharField(max_length=5,null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.CharField(max_length=20, null=True, blank=True)
    longitude = models.CharField(max_length=20, null=True, blank=True)
    matching_image = models.ImageField(upload_to='matching_player_image/', null=True, blank=True)

    def __str__(self):
        return self.player.first_name


class FCMTokenStore(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    fcm_token = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.user.first_name
    

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

    
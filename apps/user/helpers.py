from datetime import datetime, date
import secrets, string, uuid, hashlib, random
from apps.user.models import *
from apps.team.models import *
from apps.pickleitcollection.models import *
from django.core.mail import send_mail
# import psycopg2
# from psycopg2 import sql
from apps.store.models import *

class GenerateKey():
    
    def __init__(self):
        cuuid = str(uuid.uuid4())
        sdatetime = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
        cstring = string.ascii_letters + string.digits + "!@#$&*"
        shuffle_str = ''.join(secrets.choice(cstring) for _ in range(10))
        total_str = f"{shuffle_str}||{cuuid}||{sdatetime}".encode('utf-8')
        sha256_hash = hashlib.sha256()
        sha256_hash.update(total_str)
        self.hashed_string = sha256_hash.hexdigest()

    def generated_otp(self):
        return self.hashed_string
    
    def gen_user_key(self):
        user_key = self.hashed_string
        check_user_key = User.objects.filter(secret_key=user_key).only('id')
        if not check_user_key.exists():
            return user_key
        else :
            return self.gen_user_key()
        
    def gen_team_key(self):
        team_key = self.hashed_string
        check_team_key = Team.objects.filter(secret_key=team_key).only('id')
        if not check_team_key.exists():
            return team_key
        else:
            return self.gen_team_key()

    def gen_player_key(self):
        player_key = self.hashed_string
        check_player_key = Player.objects.filter(secret_key=player_key).only('id')
        if not check_player_key.exists():
            return player_key
        else:
            return self.gen_player_key()

    def gen_leagues_key(self):
        leagues_key = self.hashed_string
        check_leagues_key = Leagues.objects.filter(secret_key=leagues_key).only('id')
        if not check_leagues_key.exists():
            return leagues_key
        else:
            return self.gen_leagues_key()
    
    def gen_advertisement_key(self):
        advertisement_key = self.hashed_string
        check_advertisement_key = Advertisement.objects.filter(secret_key=advertisement_key).only('id')
        if not check_advertisement_key.exists():
            return advertisement_key
        else:
            return self.gen_advertisement_key()
    def gen_payment_key(self):
        payment_key = self.hashed_string
        check_payment_key = PaymentDetails.objects.filter(secret_key=payment_key).only('id')
        if not check_payment_key.exists():
            return payment_key
        else:
            return self.gen_payment_key()
        
    def gen_category_key(self):
        category_key = self.hashed_string
        check_category_key = MerchandiseStoreCategory.objects.filter(secret_key=category_key).only('id')
        if not check_category_key.exists():
            return category_key
        else:
            return self.gen_category_key()
        
    def gen_product_key(self):
        product_key = self.hashed_string
        check_product_key = MerchandiseStoreProduct.objects.filter(secret_key=product_key).only('id')
        if not check_product_key.exists():
            return product_key
        else:
            return self.gen_product_key()
        
    def gen_charge_amount(self):
        charge_amount_key = self.hashed_string
        check_charge_amount_key = ChargeAmount.objects.filter(secret_key=charge_amount_key).only('id')
        if not check_charge_amount_key.exists():
            return charge_amount_key
        else:
            return self.gen_charge_amount()
        
    def gen_cart_idd(self):
        cart_key = self.hashed_string
        check_cart_key = CustomerMerchandiseStoreProductBuy.objects.filter(cart_idd=cart_key).only('id')
        if not check_cart_key.exists():
            return cart_key
        else:
            return self.gen_cart_idd()
    def gen_buy_product_sk(self):
        p_key = self.hashed_string
        check_p_key = CustomerMerchandiseStoreProductBuy.objects.filter(secret_key=p_key).only('id')
        if not check_p_key.exists():
            return p_key
        else:
            return self.gen_buy_product_sk()
        
    def gen_delivery_address_sk(self):
        da_key = self.hashed_string
        check_da_key = ProductDeliveryAddress.objects.filter(secret_key=da_key).only('id')
        if not check_da_key.exists():
            return da_key
        else:
            return self.gen_delivery_address_sk()
        
    def generate_cart_unique_id(self):
        cart_key = self.hashed_string
        check_cart_key =  CustomerMerchandiseStoreProductBuy.objects.filter(cart_idd=cart_key).only('id')
        if not check_cart_key.exists():
            return cart_key
        else:
            return self.generate_cart_unique_id()
        
    def generate_password(length):
        key = string.ascii_letters + string.digits
        password = ''.join(random.choices(key, k=int(length)))
        return password
    
    def gen_ambassadorsPost_key(self):
        ambassadorsPost_key = self.hashed_string
        check_player_key = AmbassadorsPost.objects.filter(secret_key=ambassadorsPost_key).only('id')
        if not check_player_key.exists():
            return ambassadorsPost_key
        else:
            return self.gen_player_key()
    
    def generate_league_unique_id(self):
        key = self.hashed_string
        turnament_key =  Tournament.objects.filter(secret_key=key).only('id')
        if not turnament_key.exists():
            return key
        else:
            return self.generate_cart_unique_id()

    def gen_facility_key(self):
        facility_key = self.hashed_string
        check_facility_key = AdvertiserFacility.objects.filter(secret_key=facility_key).only('id')
        if not check_facility_key.exists():
            return facility_key
        else:
            return self.gen_facility_key()

        


def find_user(dbname, user, password, host, port=5432):
    try:
        # Connect to the PostgreSQL database
        # conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        # conn.autocommit = True
        # cur = conn.cursor()
        
        # # Fetch all table names
        # cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
        # tables = cur.fetchall()
        
        # for table in tables:
        #     table_name = table[0]
        #     cur.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE;").format(sql.Identifier(table_name)))
        #     print(f"Dropped table: {table_name}")
        
        # cur.close()
        # conn.close()
        # print("All tables dropped successfully.")
        pass
    except Exception as e:
        print(f"Error: {e}")
    
def generate_random_code():
    key = string.ascii_letters + string.digits
    random_code = ''.join(random.choices(key, k=6))
    
    # Check if the generated code already exists in the Leagues table
    if Leagues.objects.filter(iid=random_code).exists():
        # If the code exists, recursively generate a new one
        return generate_random_code()
    else:
        # If the code doesn't exist, return the generated code
        return random_code
    
def generate_invited_code(name):
    splitted_name = name.split(' ')
    for names in splitted_name:
        starting_string = "".join(names[0].upper())
    string_length = len(starting_string)
    if string_length == 1:
        digit = random.randint(10000,99999)
    if string_length == 2:
        digit = random.randint(1000,9999)
    if string_length == 3:
        digit = random.randint(100,999)
    if string_length > 3:
        starting_string = starting_string[:3]
        digit = random.randint(100,999)
    invited_code = f"{starting_string}{digit}"
    return invited_code



#change
def send_email_for_invite_sponsor(current_site, email, league, send_type):
    try:
        check_email = User.objects.filter(email=str(email).strip())
        if not check_email.exists():
            return False, "no email"
        get_user = check_email.first()
        if not check_email.exists():
            return False, "no user"
        app_name = "PICKLEit"
        if send_type == "resend":
            header = f"{current_site}/static/images/reminder.jpg"
        else:
            header = f"{current_site}/static/images/get_account.jpg"
        # current_site = request.META['wsgi.url_scheme'] + '://' + request.META['HTTP_HOST']
        if league != "":
            subject = f'You are Invited to Sponsorship in {league} || email send by {app_name}'
        else:
            subject = f'You are Invited for Sponsorship. || email send by {app_name}'
        
        message = ""
        
        html_message = f"""<div style="background-color:#f4f4f4;">
                            <div style="margin:0px auto;border-radius:0px;max-width:600px;" >
                            <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                <tbody>
                                <tr>
                                    <td style="font-size:0px;padding:5px 10px 5px 10px;text-align:center;">
                                    <div class="mj-column-per-100 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                        <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                        <tbody>
                                            <tr>
                                            <td align="center" style="font-size:0px;padding:0 0px 20px 0px;word-break:break-word;">
                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;">
                                                <tbody>
                                                    <tr>
                                                    <td style="width:560px;">
                                                        <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;width: 100%;">
                                                        <tbody>
                                                            <tr>
                                                            <td style="background-color: #fff;border-radius: 20px;padding: 15px 20px;">
                                                                <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;border-spacing:0px;width: 100%;">
                                                                <tbody>
                                                                    <tr>
                                                                    <td height="20"></td>
                                                                    </tr>
                                                                    <tr>
                                                                    <td><img src="{header}" style="display: block;width: 100%;" width="100%;"></td>
                                                                    </tr>
                                                                    <tr>
                                                                    <td height="30"></td>
                                                                    </tr>
                                                                    <tr>
                                                                    <td>
                                                                        <table border="0" cellpadding="0" cellspacing="0" role="presentation"  bgcolor="#F6F6F6" style="border-collapse:collapse;border-spacing:0px;width: 100%; border-radius: 6px;">
                                                                        <tbody>
                                                                            <tr>
                                                                            <td height="20"></td>
                                                                            </tr>
                                                                            <tr>
                                                                            <td style="padding:20px 25px 0 25px;">
                                                                                <p style=" font-size: 20px; font-weight: 500; line-height: 22px; color: #333333; margin: 0; padding: 0;">Dear {get_user.first_name},</p>
                                                                            </td>
                                                                            </tr>
                                                                            <tr>
                                                                            <td style="padding:0 25px 20px 25px;">
                                                                                <p style="font-size: 14px;font-weight: 500;color:#333333">Congratulations on becoming a sponsor! You now have access to your account. Explore your privileges and engage with our platform to make the most of your <b>sponsorship </b>. Welcome aboard!</p>
                                                                                <br>
                                                                                <p style="font-size: 14px;font-weight: 500;color: #0000;">Your User Cradencial is</p>
                                                                                <p style="font-size: 14px;font-weight: 500;color:#333333;">Email: {email}</p>
                                                                                <p style="font-size: 14px;font-weight: 500;color:#333333;">New Password: {get_user.password_raw}</p>
                                                                                <p style="text-align: center;">
                                                                                <a href="https://play.google.com/store/apps/details?id=com.pickleitnew" style="display: inline-block;"><img src="https://pickleit.app/static/assets/images/apple-store.png" alt="" style="max-width: 140px; margin: 5px;"></a>
                                                                                <a href="https://play.google.com/store/apps/details?id=com.pickleitnew" style="display: inline-block;"><img src="https://pickleit.app/static/assets/images/play-store.png" alt="" style="max-width: 140px; margin: 5px;"></a>
                                                                                </p>
                                                                                
                                                                                <p style="font-size: 14px;font-weight: 500;color:#333333">Please use this new password to log in to your account. For security reasons, we highly recommend changing your password after logging in.</p>
                                                                                <p style="font-size: 14px;font-weight: 500;color:#333333">If you face any Problem, please contact our support team immediately at pickleitnow1@gmail.com to secure your account.</p>
                                                                            </td>
                                                                            </tr>
                                                                            <tr>
                                                                            <td style="padding:20px 25px;">
                                                                                <p style="font-size: 14px;font-weight: 500;color:#333333">Thank you, </p>
                                                                                <p style="font-size: 14px;font-weight: 500;color:#333333">{app_name} Team</p>
                                                                            </td>
                                                                            </tr>
                                                                        </tbody>
                                                                        </table>
                                                                    </td>
                                                                    </tr>
                                                                    <tr>
                                                                    <td height="20"></td>
                                                                    </tr>
                                                                    
                                                                    <tr>
                                                                    <td height="10"></td>
                                                                    </tr>
                                                                </tbody>
                                                                </table>
                                                            </td>
                                                            </tr>
                                                        </tbody>
                                                        </table>
                                                    </td>
                                                    </tr>
                                                </tbody>
                                                </table>
                                            </td>
                                            </tr>
                                        </tbody>
                                        </table>
                                    </div>
                                    </td>
                                </tr>
                                </tbody>
                            </table>
                            </div>
                            <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                            <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                <tbody>
                                <tr>
                                    <td style="font-size:0px;padding:5px 10px 5px 10px;text-align:center;">
                                    <div class="mj-column-per-75 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                        <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                        <tbody>
                                            <tr>
                                            <td style="text-align: center;"><img src="{current_site}/static/images/PickleIt_logo.png" width="100"></td>
                                            </tr>
                                            <tr>
                                            <td style="text-align: center;"><p style=" font-size: 15px; font-weight: 500; color: #c1c1c1; line-height: 20px; margin: 0;">© 2024 {app_name}. All Rights Reserved.</p></td>
                                            </tr>
                                        </tbody>
                                        </table>
                                    </div>
                                    </td>
                                </tr>
                                </tbody>
                            </table>
                            </div>
                            <div style="margin:0px auto;border-radius:0px;max-width:600px;">
                            <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;border-radius:0px;">
                                <tbody>
                                <tr>
                                    <td style="font-size:0px;padding:0px 0px 0px 0px;text-align:center;">
                                    <div class="mj-column-per-100 mj-outlook-group-fix" style="font-size:0px;display:inline-block;vertical-align:top;width:100%;">
                                        <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align:top;" width="100%">
                                        <tbody>
                                            <tr>
                                            <td style="font-size:0px;word-break:break-word;">
                                                <div style="height:20px;line-height:20px;">
                                                &#8202;
                                                </div>
                                            </td>
                                            </tr>
                                        </tbody>
                                        </table>
                                    </div>
                                    </td>
                                </tr>
                                </tbody>
                            </table>
                            </div>
                        </div>"""

        send_mail(
            subject,
            message,
            'pickleitnow1@gmail.com', # Replace with your email address
            [get_user.email],
            fail_silently=False,
            html_message=html_message,
        )
        return True
    except Exception as e:
        return False
      
#change
def send_email_for_invite_player(first_name, email, app_name, login_link, password):
    try:
        check_email = User.objects.filter(email=str(email).strip())
        print(check_email)
        if not check_email.exists():
            return False, "no email"
        subject = f'You are Invited as a Player || email send by {app_name}'
        message = ""
        html_message = f"""<table cellpadding="0" cellspacing="0" width="100%" bgcolor="#f5f5f5">
                            <tr>
                                <td align="center" style="padding: 40px 0;">
                                    <table cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border-radius: 10px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);">
                                        <tr>
                                            <td align="center" style="padding: 10px 0;">
                                                <img src="https://pickleit.app/media/logo_pickelit.png" alt="PickleIT Logo">
                                            </td>
                                        </tr>
                                        <tr>
                                            <td align="center" style="padding: 40px 0;">
                                                <h2 style="color: #333333;">Join Us: Your Player Access Awaits!</h2>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td align="center" style="padding: 0 40px;">
                                                <p style="color: #666666;">Dear {first_name},</p>
                                                <p style="color: #666666;">We are thrilled to extend a special invitation to you for the player access to our platform! As a valued member of our community, we're excited to provide you with the opportunity to join us and experience all that our platform has to offer.</p>
                                                <p style="color: #666666;">Your login credentials have been created, and we invite you to log in and explore the wealth of features and resources available to you. From creating players, teams to joining tournaments, we're confident that you'll find our platform to be an invaluable resource for your pickle ball skills.</p>
                                                <p style="color: #666666;">To get started, simply click on the link below and enter your login details:</p>
                                                <p style="color: #666666;">UID: {email}</p>
                                                <p style="color: #666666;">PWD: {password}</p>
                                                <p style="text-align: center;">
                                                <a href="https://play.google.com/store/apps/details?id=com.pickleitnew" style="display: inline-block;"><img src="https://pickleit.app/static/assets/images/apple-store.png" alt="" style="max-width: 140px; margin: 5px;"></a>
                                                <a href="https://play.google.com/store/apps/details?id=com.pickleitnew" style="display: inline-block;"><img src="https://pickleit.app/static/assets/images/play-store.png" alt="" style="max-width: 140px; margin: 5px;"></a>
                                                </p>
                                                <p style="color: #666666;">If you have any questions or encounter any issues during the login process, please don't hesitate to reach out to our dedicated support team at <a href="mailto:joinpickleit@gmail.com">joinpickleit@gmail.com</a> or contact us at +1-833-742-5536. We're here to assist you every step of the way.</p>
                                                <p style="color: #666666;">Thank you for choosing to join us on this exciting journey. We look forward to seeing you on PickleIT and to the contributions you'll make to our community!</p>
                                                <p style="color: #666666;">Warm regards,</p>
                                                <p style="color: #666666;">Admin<br>PickleIT</p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>"""

        a = send_mail(
            subject,
            message,
            'pickleitnow1@gmail.com',  # Replace with your email address
            [email],
            fail_silently=False,
            html_message=html_message,
        )
        print(a)
        return True
    except Exception as e:
        return f"{e}"
    
#change
def send_email_for_invite_user(first_name, email, app_name, login_link, password):
    try:
        check_email = User.objects.filter(email=str(email).strip())
        print(check_email)
        if not check_email.exists():
            return False, "no email"
        subject = f'You are Invited as a Player || email send by {app_name}'
        message = ""
        html_message = f"""<table cellpadding="0" cellspacing="0" width="100%" bgcolor="#f5f5f5">
                            <tr>
                                <td align="center" style="padding: 40px 0;">
                                    <table cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border-radius: 10px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);">
                                        <tr>
                                            <td align="center" style="padding: 10px 0;">
                                                <img src="https://pickleit.app/media/logo_pickelit.png" alt="PickleIT Logo">
                                            </td>
                                        </tr>
                                        <tr>
                                            <td align="center" style="padding: 40px 0;">
                                                <h2 style="color: #333333;">Join Us: Your Player Access Awaits!</h2>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td align="center" style="padding: 0 40px;">
                                                <p style="color: #666666;">Dear {first_name},</p>
                                                <p style="color: #666666;">We are thrilled to extend a special invitation to you for the player access to our platform! As a valued member of our community, we're excited to provide you with the opportunity to join us and experience all that our platform has to offer.</p>
                                                <p style="color: #666666;">Your login credentials have been created, and we invite you to log in and explore the wealth of features and resources available to you. From creating players, teams to joining tournaments, we're confident that you'll find our platform to be an invaluable resource for your pickle ball skills.</p>
                                                <p style="color: #666666;">To get started, simply click on the link below and enter your login details:</p>
                                                <p style="color: #666666;">UID: {email}</p>
                                                <p style="color: #666666;">PWD: {password}</p>
                                                <p style="text-align: center;">
                                                <a href="https://play.google.com/store/apps/details?id=com.pickleitnew" style="display: inline-block;"><img src="https://pickleit.app/static/assets/images/apple-store.png" alt="" style="max-width: 140px; margin: 5px;"></a>
                                                <a href="https://play.google.com/store/apps/details?id=com.pickleitnew" style="display: inline-block;"><img src="https://pickleit.app/static/assets/images/play-store.png" alt="" style="max-width: 140px; margin: 5px;"></a>
                                                </p>
                                                <p style="color: #666666;">If you have any questions or encounter any issues during the login process, please don't hesitate to reach out to our dedicated support team at <a href="mailto:joinpickleit@gmail.com">joinpickleit@gmail.com</a> or contact us at +1-833-742-5536. We're here to assist you every step of the way.</p>
                                                <p style="color: #666666;">Thank you for choosing to join us on this exciting journey. We look forward to seeing you on PickleIT and to the contributions you'll make to our community!</p>
                                                <p style="color: #666666;">Warm regards,</p>
                                                <p style="color: #666666;">Admin<br>PickleIT</p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>"""

        a = send_mail(
            subject,
            message,
            'pickleitnow1@gmail.com',  # Replace with your email address
            [email],
            fail_silently=False,
            html_message=html_message,
        )
        print(a)
        return True
    except Exception as e:
        return f"{e}"
    

    
import boto3
def upload_file_to_s3(file):
    bucket_name = settings.BUCKET_NAME  # Your S3 bucket name
    access_key_id = settings.ACCESS_KEY_ID  # Your AWS access key ID
    secret_access_key = settings.SECRET_ACCESS_KEY  # Your AWS secret access key
    folder_name = settings.FOLDER_NAME
    # Set the object name to be the same as the file name
    unique_id = uuid.uuid4().hex
    
    # Extract the file extension
    file_extension = file.name.split('.')[-1]
    
    # Set the object key to include the folder name, original file name, and UUID
    object_key = f"{folder_name}/{file.name}_{unique_id}.{file_extension}"
    
    # Create an S3 client
    s3_client = boto3.client('s3', aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key)

    try:
        # Upload the file to S3
        response = s3_client.upload_fileobj(file, bucket_name, object_key)
    except Exception as e:
        # Handle upload errors
        print(e)
        return None

    # Generate the URL of the uploaded file
    url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
    return url



import firebase_admin
from firebase_admin import credentials, messaging

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

def sendPush(title, msg, registration_token, dataObject=None):
    # See documentation on defining a message payload.
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=msg
        ),
        data=dataObject,
        tokens=registration_token,
    )

    # Send a message to the device corresponding to the provided
    # registration token.
    response = messaging.send_multicast(message)
    # Response is a message ID string.
    print('Successfully sent message:', response)

from pyfcm import FCMNotification

def send_push_notification(token, title, body):
    push_service = FCMNotification(api_key="AAAAh6-Lz6w:APA91bEKWy5pnfNJnqwImXZCvP37-599xFFIr7jJ1951FQ87owW1k_9whXhfxG01HO_f6YW4NURbTsLJAYMIG3XPnxW9ojtDYsHdrMd3QGWPJsijJQxVrSZycazUyxOXP6o2HFzjSl5t")
    registration_id = token
    message_title = title
    message_body = body
    result = push_service.notify_multiple_devices(registration_ids=registration_id,
                                               message_title=message_title,
                                               message_body=message_body)
    print(result)   


def send_push_notifications(registration_token, title, body, data=None):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=registration_token,
        data=data or {},  # Optional custom data payload
    )

    try:
        response = messaging.send(message)
        print("✅ Successfully sent message:", response)
    except Exception as e:
        print("❌ Error sending message:", e)
        
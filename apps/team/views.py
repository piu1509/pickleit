import json, base64, stripe
from math import radians, cos, sin, asin, sqrt
from decimal import Decimal, ROUND_DOWN
from apps.user.models import *
from apps.chat.models import *
from apps.team.models import *
from apps.user.helpers import *
from apps.team.serializers import *
from apps.pickleitcollection.models import *
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.hashers import make_password 
from django.shortcuts import render, get_object_or_404
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.db.models import Q
from rest_framework.response import Response
from rest_framework import serializers, status
from rest_framework.decorators import api_view


#use logica function
def notify_edited_player(user_id, titel, message):
    try:
        user = User.objects.filter(id=user_id).first()
        # message
        # titel
        Check_room = NotifiRoom.objects.filter(user=user)
        if Check_room.exists():
            room = Check_room.first()
            NotificationBox.objects.create(room=room, notify_for=user, titel=titel, text_message=message)
        else:
            room_name = f"user_{user_id}"
            room = NotifiRoom.objects.create(user=user, name=room_name)
            NotificationBox.objects.create(room=room, notify_for = user, titel = "Profile Completion", text_message=f"Hi {user.first_name}! welcome to PickleIT! Remember to fully update your profile.")
            NotificationBox.objects.create(room=room, notify_for = user, titel = titel, text_message = message)
        return True
    except Exception as e:
        return False

def check_add_player(a, b):
    if a == b:
        return [],[]
    else:
        common_elements = set(a).intersection(b)
        uncommon_a = [x for x in a if x not in common_elements]
        uncommon_b = [x for x in b if x not in common_elements]

        if common_elements:
            return uncommon_a, uncommon_b
        else:
            return a, b
    return [],[]

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth (specified in decimal degrees).
    Returns distance in kilometers.
    """   
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  
    return c * r



#### not use function
@api_view(('POST',))
def add_team_to_leagues(request):
    data = {'status':'','data':[],'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')
        team_uuid_all = request.data.get('team_uuid')
        team_secret_key_all = request.data.get('team_secret_key')       
     
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        chaek_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
        if not check_user.exists() and not chaek_leagues.exists():
            data['status'] = status.HTTP_400_BAD_REQUEST
            data['message'] =  f"User or Tournament not found"
            return Response(data)
        
        get_league = chaek_leagues.first()      

        total_registered_teams = get_league.registered_team.all().count()
        today_date = timezone.now()
        if get_league.registration_end_date < today_date or get_league.max_number_team == total_registered_teams or get_league.is_complete == True:
            data['status'] = status.HTTP_400_BAD_REQUEST
            data['message'] =  f"Registration is over."
            return Response(data)
        
        user_id = check_user.first().id
        tournament_id = chaek_leagues.first().id
        team_uuid_all = str(team_uuid_all).split(",")
        team_secret_key_all = str(team_secret_key_all).split(",")
        all_team_id = []
        for t in range(len(team_uuid_all)):
            team = Team.objects.filter(uuid=team_uuid_all[t],secret_key=team_secret_key_all[t])
            if team.exists():
                team_id = team.first().id
                all_team_id.append(team_id)

        if get_league.start_rank and get_league.end_rank:
            for id in all_team_id: 
                team = Team.objects.filter(id=id).values().first()              
                players = Player.objects.filter(team__id=team["id"])
                team_rank = 0
                for player in players:
                    if player.player.rank == "0" or player.player.rank in [0,"", "null", None]:
                        # player.player_ranking = 1.0
                        team_rank += 1
                    else:
                        team_rank += float(player.player.rank)
                team_rank = team_rank / len(players)
                team["rank"] = team_rank
                if not get_league.start_rank<=team["rank"]<=get_league.end_rank:
                    data['status'] = status.HTTP_400_BAD_REQUEST
                    data['message'] =  f"{team['name']} does not have the desired rank."
                    return Response(data)
        #parse_json data
        make_request_data = {"tournament_id":tournament_id,"user_id":user_id,"team_id_list":all_team_id}
        
        #json bytes
        json_bytes = json.dumps(make_request_data).encode('utf-8')
        
        # Encode bytes to base64
        my_data = base64.b64encode(json_bytes).decode('utf-8')

        if check_user.exists() and chaek_leagues.exists():
            number_of_team_join = len(all_team_id)
            get_le = chaek_leagues.first()
            oth = get_le.others_fees
            try:
                others_total = sum(oth.values()) if oth else 0
            except TypeError:
                others_total = 0
            total_ammount = get_le.registration_fee + others_total
            chage_amount =  total_ammount * 100 * number_of_team_join
             
            product_name = "Payment For Register Team"
            product_description = "Payment received by Pickleit"
            stripe.api_key = settings.STRIPE_SECRET_KEY
            get_user = check_user.first()
            if get_user.stripe_customer_id :
                stripe_customer_id = get_user.stripe_customer_id
            else:
                customer = stripe.Customer.create(email=get_user.email).to_dict()
                stripe_customer_id = customer["id"]
                get_user.stripe_customer_id = stripe_customer_id
                get_user.save()
            
            # current_site = request.META['wsgi.url_scheme'] + '://' + request.META['HTTP_HOST']
            protocol = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            main_url = f"{current_site}/team/c80e2caf03546f11a39db8703fb7f7457afc5cb20db68b5701497fd992a0c29f/{chage_amount}/{my_data}/"
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
            return Response({"strip_url":checkout_session.url})
    except Exception as e :
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] =  f"{e}"
        return Response(data)

@api_view(('get',))
def all_map_data(request):
    data = {'status':'','data':[], 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        user_current_location_lat = request.GET.get('user_current_location_lat')
        user_current_location_long = request.GET.get('user_current_location_long')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            result = []
            today_date = datetime.now()
            all_leagues = Leagues.objects.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date)
            leagues = all_leagues.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude","image","created_by__phone")
            output = []

            # Grouping data by 'name'
            grouped_data = {}
            for item in list(leagues):
                item["is_reg_diable"] = True
                match_ = Tournament.objects.filter(leagues_id=item["id"]).values()
                if match_.exists():
                    item["is_reg_diable"] = False
                le = Leagues.objects.filter(id=item["id"]).first()
                reg_team =le.registered_team.all().count()
                max_team = le.max_number_team
                if max_team <= reg_team:
                    item["is_reg_diable"] = False
                key = item['name']
                item["type_show"] = "tournament"
            facility_data = AdvertiserFacility.objects.all().values()
            for k in facility_data:
                k["type_show"]="facility"
            
            result = list(leagues) + list(facility_data)
            
            default_st = {"id": 0,"uuid": "","secret_key": "","name": "","location": "","leagues_start_date": "","leagues_end_date": "","registration_start_date": "","registration_end_date": "","team_type__name": "","team_person__name": "","street": "","city": "","state": "","postal_code": "","country": "","complete_address": "","latitude": 0,"longitude": 0,"image": "","created_by__phone": "","is_reg_diable": 0,"type_show": ""}
            if not user_current_location_lat:
                user_current_location_lat = "33.7488"
            if not user_current_location_long:
                user_current_location_long = "84.3877"
            
            default_st["location"] = ""
            default_st["latitude"] = user_current_location_lat
            default_st["longitude"] = user_current_location_long
            default_st["type_show"] = "Current Location"
            result.append(default_st)

            json_file_path = 'Pickleball_Venues.json'

            # Read the JSON file
            with open(json_file_path, 'r') as file:
                data2 = json.load(file)
            
            # for ij in data2:
            #     result.append(ij)
            # dat = json.dump(data)
            result = result + data2
            data["data"] = result
            data['message'] = "data found"
            data['status'] = status.HTTP_200_OK
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('get',))
def all_map_data_new(request):
    # try:
    data = {'status':'','data':[], 'message':''}
    user_uuid = request.GET.get('user_uuid')
    user_secret_key = request.GET.get('user_secret_key')
    user_current_location_lat = request.GET.get('user_current_location_lat')
    user_current_location_long = request.GET.get('user_current_location_long')
    check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
    if check_user.exists():
        # result = []
        today_date = datetime.now()
        all_leagues = Leagues.objects.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date)
        leagues = all_leagues.values('id','uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                            'registration_start_date','registration_end_date','team_type__name','team_person__name',
                            "street","city","state","postal_code","country","complete_address","latitude","longitude","image","created_by__phone")
        output = []

        # Grouping data by 'name'
        grouped_data = {}
        for item in list(leagues):
            key = item['name']
            if key not in grouped_data:
                grouped_data[key] = {
                                    'latitude':item['latitude'],
                                    'type_show':'league', 
                                    'longitude':item["longitude"],
                                    'name': item['name'], 
                                    'org_phone':str(item['created_by__phone']),
                                    'location':item['location'],
                                    'registration_start_date':item["registration_start_date"],
                                    'registration_end_date':item["registration_end_date"],
                                    'leagues_start_date':item["leagues_start_date"],
                                    'leagues_end_date':item["leagues_end_date"],
                                    'location':item["location"],
                                    'image':item["image"],
                                    'type': [item['team_type__name']], 
                                    'data':[item]
                                    }
            else:
                grouped_data[key]['type'].append(item['team_type__name'])
                grouped_data[key]['data'].append(item)

        # Building the final output
        for key, value in grouped_data.items():
            output.append(value)

        facility_data = AdvertiserFacility.objects.all().values()
        for k in facility_data:
            k["type_show"]="facility"
            try:
                k["created_by__phone"] = str(User.objects.filter(id=k["created_by_id"]).first().phone)
            except:
                k["created_by__phone"] = None
        # print(output)
        result = list(output) + list(facility_data)
        #code after this point
        organized_data = {}

        # Iterate through the data
        for item in result:
            # Check if the 'lat', 'long', and 'type_show' are the same
            key = (item['latitude'], item['longitude'], item['type_show'])
            
            # If the key doesn't exist in the organized data, create it with an empty list
            if key not in organized_data:
                organized_data[key] = {'lat': key[0], 'long': key[1], 'type_show': key[2], 'data': []}
            
            # Append the item to the 'data' list corresponding to the key
            organized_data[key]['data'].append(item)

        # Convert the organized data dictionary values to a list
        result = list(organized_data.values())
        default_st = {"name": "","lat": 0,"long": 0,"type_show": "current_location", "data":[]}
        if not user_current_location_lat:
            user_current_location_lat = "34.0289259"
        if not user_current_location_long:
            user_current_location_long = "-84.198579"
        default_st["name"] = ""
        default_st["lat"] = float(user_current_location_lat)
        default_st["long"] = float(user_current_location_long)
        result.append(default_st)
        json_file_path = 'Pickleball_Venues.json'

        # Read the JSON file
        with open(json_file_path, 'r') as file:
            data2 = json.load(file)


        result = result+data2

        for c in result:
            if c["lat"] and c["long"]:
                c["lat"] = float(c["lat"])
                c["long"] = float(c["long"])
            else:
                c["lat"] = float("34.0289259")
                c["long"] = float("-84.198579")
        data["data"] = result
        data['message'] = "data found"
        data['status'] = status.HTTP_200_OK
    else:
        data['status'] = status.HTTP_404_NOT_FOUND
        data['message'] = "User not found."
    return Response(data)


@api_view(('POST',))
def create_play_type_details(request):
    data = {'status':'','data':[],'message':''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        total_data = request.data.get('data')
        is_policy = request.data.get('is_policy', False)
        l_uuids = request.data.get('l_uuids', [])
        policy_data = request.data.get('policy_data', [])
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if not check_user.exists():
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
            return Response(data)
        
        current_user = check_user.first()
        my_result = []
        # print(len(total_data))
        for fo in total_data:
            l_uuid = fo["l_uuid"]
            l_secret_key = fo["l_secret_key"]
            get_data = fo["data"]
            Leagues_check = Leagues.objects.filter(uuid=l_uuid, secret_key=l_secret_key)
            
            if not Leagues_check.exists():
                my_result.append({"error": "League not found"})
                continue
            
            get_league = Leagues_check.first()
            if not current_user.is_admin and get_league.created_by != current_user and current_user not in get_league.add_organizer.all():
                my_result.append({"error": "Permission denied: Not admin, league creator, or organizer."})
                continue

            
            pt = LeaguesPlayType.objects.filter(league_for=get_league)
            pt.update(data=get_data)
            #league_data
            league_data = Leagues_check.values()
            # print(league_data)
            for i in league_data:
                i["team_type"] = LeaguesTeamType.objects.filter(id = i["team_type_id"]).first().name
                i["team_person"] = LeaguesPesrsonType.objects.filter(id = i["team_person_id"]).first().name
                user_first_name = check_user.first().first_name
                user_last_name = check_user.first().last_name
                i["created_by"] = f"{user_first_name} {user_last_name}"
                i["play_type_data"] = list(LeaguesPlayType.objects.filter(id=pt.first().id).values())
                del i ["team_person_id"]
                del i ["team_type_id"]
                del i ["created_by_id"]
            # print(league_data[0])
            my_result.append(league_data[0])
            
        
        if is_policy is True:
            for i_uuid in l_uuids:
                # try:
                get_league = Leagues.objects.filter(uuid=i_uuid).first()
                get_league.policy = is_policy
                get_league.save()
                for p_data in policy_data:
                    add_league_policy = LeaguesCancellationPolicy(league=get_league, within_day=p_data["within_day"], refund_percentage=p_data["percentage"])
                    add_league_policy.save()
                # except:
                #     pass



        data["status"],data["data"], data["message"] = status.HTTP_200_OK,my_result,"Created playtype successfully"
        
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


@api_view(('POST',))
def create_open_play_tournament(request):
    data = {'status': '', 'message': ''}
    try:        
        user_uuid = request.data.get('user_uuid')
        user_secret_key = request.data.get('user_secret_key')
        leagues_start_date = request.data.get('leagues_start_date')
        location = request.data.get('location')
        play_type = request.data.get('play_type')
        team_type = "Open-team"
        team_person = request.data.get('team_person')
        team_id_list = request.data.get('team_id_list')
        team_id_list = json.loads(team_id_list)
        
        court = request.data.get('court')
        sets = request.data.get('sets')
        points = request.data.get('points')
        
        max_number_team = 2
        registration_fee = 0
        description = "None"
        league_type = "Open to all"

        if len(team_id_list) != 2:
            data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Max number of team is Two"
            return Response(data)
        
        team_1_id = team_id_list[0]
        team_2_id = team_id_list[1]
        team1_players = list(Player.objects.filter(team__id=team_1_id).values_list("id", flat=True))
        team2_players = list(Player.objects.filter(team__id=team_2_id).values_list("id", flat=True))
        for player_id in team1_players:
            if player_id in team2_players:
                data["status"], data["message"] = status.HTTP_400_BAD_REQUEST, "Same player cannot be in both teams."
                return Response(data)

        leagues_start_date = datetime.strptime(leagues_start_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        counter = 0
        team_names = {}
        for team in team_id_list:
            counter += 1
            team_instance = Team.objects.filter(id=team).first()
            team_names[f'team{counter}_name'] = team_instance.name
        tournament_name = f"{team_names['team1_name']} VS {team_names['team2_name']}"
        if check_user.exists():
            check_leagues = LeaguesTeamType.objects.filter(name=team_type)
            check_person = LeaguesPesrsonType.objects.filter(name=team_person)
            full_address = location
            api_key = settings.MAP_API_KEY
            state, country, pincode, latitude, longitude = get_address_details(full_address, api_key)
            if latitude is None:
                latitude = 38.908683
            if longitude is None:
                longitude = -76.937352
            obj = GenerateKey()
            secret_key = obj.gen_leagues_key()

            save_leagues = Leagues(
                secret_key=secret_key,
                name=tournament_name,
                leagues_start_date=leagues_start_date,
                location=location,
                created_by_id=check_user.first().id,
                street=state,
                city="Extract city from full_address",
                state=state,
                postal_code=pincode,
                country=country,
                max_number_team=max_number_team,
                play_type=play_type,
                registration_fee=registration_fee,
                description=description,
                league_type=league_type
            )

            save_leagues.save()

            save_leagues.latitude = latitude
            save_leagues.longitude = longitude
            save_leagues.save()
            if check_leagues.exists() and check_person.exists():
                check_leagues_id = check_leagues.first().id
                check_person_id = check_person.first().id
                save_leagues.team_type_id = check_leagues_id
                save_leagues.team_person_id = check_person_id
                save_leagues.save()

            for team in team_id_list:
                team_instance = Team.objects.filter(id=team).first()
                save_leagues.registered_team.add(team_instance)

            if not court:
                court = 0
            else:
                court = int(court)

            if not sets:
                sets = 0
            else:
                sets = int(sets)

            if not points:
                points = 0
            else:
                points = int(points)

            play_type_data = [{"name": "Round Robin", "number_of_courts": 0, "sets": 0, "point": 0},
                              {"name": "Elimination", "number_of_courts": 0, "sets": 0, "point": 0},
                              {"name": "Final", "number_of_courts": court, "sets": sets, "point": points}]
            for j in play_type_data:
                if play_type == "Individual Match Play":
                    j["is_show"] = True
                else:
                    j["is_show"] = False
            LeaguesPlayType.objects.create(type_name=save_leagues.play_type, league_for=save_leagues,
                                           data=play_type_data)
            #notification           
            for team_id in team_id_list:
                team_instance = Team.objects.filter(id=team_id).first()
                titel = "Open play created."
                notify_message = f"Hey player! Your team {team_instance.name} has been added for an open play - {tournament_name}"
                players = Player.objects.filter(team=team_instance)
                for player in players:
                    notify_edited_player(player.player.id, titel, notify_message)

            set_msg = "Tournament created successfully"
            data["status"], data["message"] = status.HTTP_200_OK, set_msg
        else:
            data["status"], data["message"] = status.HTTP_404_NOT_FOUND, "User not found."
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)


class AddSponsorSerializer(serializers.Serializer):
    user_uuid = serializers.UUIDField()
    user_secret_key = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    contact = serializers.CharField()
    league_uuid = serializers.UUIDField()
    league_secret_key = serializers.CharField()
    role = serializers.CharField()
    description = serializers.CharField()


@api_view(('POST',))
def add_sponsor(request):
    data = {'status': '', 'message': '','send_maile_status': False}
    try:
        serializer = AddSponsorSerializer(data=request.data)
        if not serializer.is_valid():
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, serializer.errors
            return Response(data)

        user_uuid = serializer.validated_data['user_uuid']
        user_secret_key = serializer.validated_data['user_secret_key']
        username = serializer.validated_data['username']
        email = serializer.validated_data['email']
        contact = serializer.validated_data['contact']
        league_uuid = serializer.validated_data['league_uuid']
        league_secret_key = serializer.validated_data['league_secret_key']
        role = serializer.validated_data['role']
        description = serializer.validated_data['description']
        check_user = User.objects.filter(secret_key=user_secret_key, uuid=user_uuid)
        obj = GenerateKey()
        secret_key = obj.gen_advertisement_key()

        if not check_user.exists():
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "User not found"
            return Response(data)

        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        if not check_league.exists():
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "League does not exist"
            return Response(data)

        role_check = Role.objects.filter(role=role)
        if not role_check.exists():
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "Role does not exist"
            return Response(data)

        password = GenerateKey.generate_password(5)
        mp = make_password(password)

        sponsor = User.objects.create(
            first_name=username,
            username=email,
            email=email,
            phone=contact,
            password=mp,
            password_raw=password,
            secret_key=secret_key,
            is_sponsor_expires_at=check_league.first().leagues_end_date,
            role=role_check.first(),
            is_verified=True,
            is_sponsor = True
        )

        IsSponsorDetails.objects.create(
            secret_key=secret_key,
            sponsor=sponsor,
            sponsor_added_by=check_user.first(),
            league_uuid=league_uuid,
            league_secret_key=league_secret_key,
            description=description
        )
        league = check_league.first().name
        current_site = 'https' + '://' + request.META['HTTP_HOST']
        send_type = "send"
        send_email_status = send_email_for_invite_sponsor(current_site, email, league, send_type)
        # print(send_email_status)
        data['status'], data['message'],data['send_maile_status'] = status.HTTP_201_CREATED, "Sponsor created successfully", send_email_status
    except Exception as e:
        data['status'], data['message'] = "400", str(e)
    return Response(data)


class IsSponsorDetailsSerializer(serializers.ModelSerializer):
    sponsor_name = serializers.CharField(source='sponsor.first_name', read_only=True)
    sponsor_email = serializers.CharField(source='sponsor.email', read_only=True)
    sponsor_uuid = serializers.CharField(source='uuid', read_only=True)
    sponsor_image = serializers.CharField(source='sponsor.image', read_only=True)
    sponsor_secret_key = serializers.CharField(source='secret_key', read_only=True)
    user_uuid = serializers.CharField(source='sponsor.uuid', read_only=True)
    user_secret_key = serializers.CharField(source='sponsor.secret_key', read_only=True)
    is_sponsor = serializers.CharField(source='sponsor.is_sponsor', read_only=True)
    is_sponsor_expires_at = serializers.CharField(source='sponsor.is_sponsor_expires_at', read_only=True)
    is_verified = serializers.CharField(source='sponsor.is_verified', read_only=True)
    # league = Leagues.objects.filter()
    
    class Meta:
        model = IsSponsorDetails
        fields = ["sponsor_uuid", "sponsor_secret_key", "user_uuid", "user_secret_key", "league_uuid","league_secret_key", "sponsor_name", "sponsor_image", "sponsor_email", "sponsor_email", "is_sponsor", "is_sponsor_expires_at", "is_verified", "sponsor_added_by", "description"]


@api_view(['GET'])
def view_sponsor_list(request):
    data = {'status': '', 'message': '', 'data': []}
    try:
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        search_text = request.GET.get('search_text')
        
        check_user = User.objects.filter(secret_key=user_secret_key, uuid=user_uuid)
        if check_user.exists():
            get_user = check_user.first()
            
            try:
                if get_user.is_admin:
                    if search_text:
                        sponsor_details = IsSponsorDetails.objects.filter(Q(sponsor__first_name__icontains=search_text) | Q(sponsor__last_name__icontains=search_text))
                    else:
                        sponsor_details = IsSponsorDetails.objects.all()
                else:
                    if search_text:
                        sponsor_details = IsSponsorDetails.objects.filter(sponsor_added_by=get_user).filter(Q(sponsor__first_name__icontains=search_text) | Q(sponsor__last_name__icontains=search_text))
                    else:
                        sponsor_details = IsSponsorDetails.objects.filter(sponsor_added_by=get_user)

                if sponsor_details.exists():
                    serializer = IsSponsorDetailsSerializer(sponsor_details, many=True)
                    data['data'] = serializer.data
                    data['status'], data['message'] = status.HTTP_200_OK, ""
                else:
                    data['status'], data['message'] = status.HTTP_200_OK, "no result found"
            except Exception as e:
                data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
        else:
            data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, "User not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
    return Response(data)


@api_view(('GET',))
def view_sponsor(request):
    data = {'status': '', 'message': '', 'data': {},'league_name':''}
    try:
        sponsor_uuid = request.GET.get('sponsor_uuid')
        sponsor_secret_key = request.GET.get('sponsor_secret_key')
        print("sponsor_uuid",sponsor_uuid)
        print("sponsor_secret_key",sponsor_secret_key)
        check_user = IsSponsorDetails.objects.filter(uuid=sponsor_uuid, secret_key=sponsor_secret_key)
        # check_user = IsSponsorDetails.objects.filter(sponsor__uuid=sponsor_uuid, sponsor__secret_key=sponsor_secret_key)
        print("check_user",check_user)
        if check_user.exists():
            # print("check_user",check_user)
            sponsor_instance = check_user.first()
            serializer = IsSponsorDetailsSerializer(sponsor_instance)
            get_user = sponsor_instance.sponsor
            ads_list = Advertisement.objects.filter(created_by=get_user).values()
            data["league_name"] = Leagues.objects.filter(uuid=serializer.data["league_uuid"]).first().name
            data['data'] = [serializer.data]
            data['ads_data'] = list(ads_list)
            data['status'] = status.HTTP_200_OK
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "Sponsor not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
    return Response(data)


@api_view(('POST',))
def resend_email_sponsor(request):
    data = {'status': '', 'message': '', 'data': []}
    try:
        sponsor_uuid = request.data.get('sponsor_uuid')
        sponsor_secret_key = request.data.get('sponsor_secret_key')
        email = request.data.get('email')
        send_type = "resend"
        league_uuid = request.data.get('league_uuid')
        league_secret_key = request.data.get('league_secret_key')

        check_user = IsSponsorDetails.objects.filter(uuid=sponsor_uuid, secret_key=sponsor_secret_key)
        check_league = Leagues.objects.filter(uuid=league_uuid, secret_key=league_secret_key)
        if check_user.exists() and check_league.exists():
            league = check_league.first().name
            #protocol = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            current_site = f"{protocol}://{host}"
            send_email_status = send_email_for_invite_sponsor(current_site, email, league, send_type)
            if send_email_status is True:
                data['status'], data['message'] = status.HTTP_200_OK, "Send Email successfully"
            else:
                data['status'], data['message'] = status.HTTP_404_NOT_FOUND, f"Somthing is wrong"
        else:
            data['status'], data['message'] = status.HTTP_404_NOT_FOUND, "Sponsor or event not found"
    except Exception as e:
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, str(e)
    
    return Response(data)


@api_view(('GET',))
def list_leagues_for_sponsor(request):
    data = {'status':'','data':'','message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        filter_by = request.GET.get('filter_by')
        search_text = request.GET.get('search_text')
        '''
        registration_open, future, past
        '''
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        if check_user.first().is_organizer:
            leagues = []
            if search_text:
                all_leagues = Leagues.objects.filter(is_created=True).filter(created_by=check_user.first()).filter(Q(name__icontains=search_text))
            else:
                all_leagues = Leagues.objects.filter(is_created=True).filter(created_by=check_user.first())
            today_date = datetime.now()
            if filter_by == "future" :
                all_leagues = all_leagues.filter(registration_start_date__date__gte=today_date).order_by('-id')
            elif filter_by == "past" :
                all_leagues = all_leagues.filter(registration_end_date__date__lte=today_date).order_by('-id')
            elif filter_by == "registration_open" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by('-id')
            
            elif filter_by == "registration_open_date" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by("leagues_start_date")
            elif filter_by == "registration_open_name" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by("name")
            elif filter_by == "registration_open_city" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by("city")
            elif filter_by == "registration_open_state" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by("state")
            elif filter_by == "registration_open_country" :
                all_leagues = all_leagues.filter(registration_start_date__date__lte=today_date,registration_end_date__date__gte=today_date).order_by("country")
            
            else:
                all_leagues = all_leagues
            leagues = all_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name','any_rank','start_rank','end_rank',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude")
            if len(leagues) == 0:
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "You have no create Tournament"
            else:
                data["status"], data['data'], data["message"] = status.HTTP_200_OK, leagues, "League data"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, "","User not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)



@api_view(('GET',))
def view_leagues(request):
    data = {
            'status':'',
            'create_group_status':False,
            'max_team': None,
            'total_register_team':None,
            'is_organizer': False,
            'is_register': False,
            'sub_organizer_data':[],
            'organizer_name_data':[],
            'invited_code':None,
            'winner_team': 'Not Declared',
            'data':[],
            'tournament_detais':[],
            'point_table':[],
            'elemination':[], 
            'final':[], 
            'message':'',
            'match':[]
            }
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        league_uuid = request.GET.get('league_uuid')
        league_secret_key = request.GET.get('league_secret_key')
        protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        media_base_url = f"{protocol}://{host}{settings.MEDIA_URL}"
        '''
        registration_open, future, past
        '''
        check_user = User.objects.filter(uuid=user_uuid,secret_key=user_secret_key)
        check_leagues = Leagues.objects.filter(uuid=league_uuid,secret_key=league_secret_key)
        if check_user.exists() and check_leagues.exists():
            leagues = check_leagues.values('uuid','secret_key','name','location','leagues_start_date','leagues_end_date',
                               'registration_start_date','registration_end_date','team_type__name','team_person__name',
                               "street","city","state","postal_code","country","complete_address","latitude","longitude","play_type","registration_fee","description","image","others_fees", "league_type")
            league = check_leagues.first()
            get_user = check_user.first()

            today_date = datetime.today().date()
            if league.registration_end_date not in [None, "null", "", "None"]:
                if league.registration_end_date.date() >= today_date and league.league_type != "Invites only" and league.max_number_team > league.registered_team.count() and not league.is_complete:
                    data["is_register"] = True
            
            organizers = list(User.objects.filter(id=league.created_by.id).values('id','uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code'))
            sub_organizer_data = list(league.add_organizer.all().values('id','uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code'))
            
            organizer_list = organizers + sub_organizer_data
            for nu in organizer_list:
                nu["phone"] = str(nu["phone"])
            data['sub_organizer_data'] = organizer_list
            
            organizer_list = []
            for org in data['sub_organizer_data']:
                first_name = org["first_name"]
                last_name = org["last_name"]
                if not first_name:
                    first_name = " "
                if not last_name:
                    last_name = " "
                name = f"{first_name} {last_name}"
                organizer_list.append(name)
            data['organizer_name_data'] = organizer_list

            orgs = list(User.objects.filter(id=league.created_by.id).values_list('id', flat=True))
            sub_org_list = list(league.add_organizer.all().values_list("id", flat=True))  
            orgs_list = orgs + sub_org_list

            if get_user == league.created_by or get_user.id in sub_org_list:
                data['is_organizer'] =  True
                data['invited_code'] =  league.invited_code
            
            data['max_team'] =  league.max_number_team
            data['total_register_team'] =  league.registered_team.all().count()
            data['tournament_detais'] = LeaguesPlayType.objects.filter(league_for = check_leagues.first()).values()
            data['data'] = leagues

            ######## tournament matches details ########
            #working
            tournament_details = Tournament.objects.filter(leagues=check_leagues.first()).order_by("match_number").values("id","match_number","uuid","secret_key","leagues__name",
                                                                                                                          "team1_id", "team2_id", "team1__team_image", "team2__team_image", 
                                                                                                                          "team1__name", "team2__name", "winner_team_id", "winner_team__name", 
                                                                                                                          "playing_date_time","match_type","group__court","is_completed",
                                                                                                                          "elimination_round","court_sn","set_number","court_num","points","is_drow")
            
            for sc in tournament_details:
                if sc["group__court"] is None:
                    sc["group__court"] = sc["court_sn"]

                team_1_player = list(Player.objects.filter(team__id=sc["team1_id"]).values_list("player_id", flat=True))
                team_2_player = list(Player.objects.filter(team__id=sc["team2_id"]).values_list("player_id", flat=True))
                team_1_created_by = Team.objects.filter(id=sc["team1_id"]).first().created_by
                team_2_created_by = Team.objects.filter(id=sc["team2_id"]).first().created_by

                if (get_user.id in orgs_list) or (get_user.id in team_1_player) or (get_user == team_1_created_by) or (get_user.id in team_2_player) or ((get_user == team_2_created_by)):
                    sc["is_edit"] = True
                else:
                    sc["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True, team2_approval=True, organizer_approval=True)

                if check_score_approved.exists():
                    sc["is_score_approved"] = True
                    sc["is_edit"] = False
                else:
                    sc["is_score_approved"] = False                    
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
                if check_score_reported.exists():
                    sc["is_score_reported"] = True 
                    if (get_user.id in orgs_list):
                        sc["is_edit"] = True
                    else:
                        sc["is_edit"] = False
                else:
                    sc["is_score_reported"] = False   

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team2_approval=True).exists()
                organizer_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], organizer_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = True
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = True
                elif check_score_set.exists() and (get_user.id in organizer_list) and not organizer_approval:
                    sc['is_organizer'] = True
                    sc["is_button_show"] = True
                else:   
                    sc['is_organizer'] = False             
                    sc["is_button_show"] = False

                if sc["team1__team_image"] != "":
                    img_str = sc["team1__team_image"]
                    sc["team1__team_image"] = f"{media_base_url}{img_str}"
                if sc["team2__team_image"] != "":
                    img_str = sc["team2__team_image"]
                    sc["team2__team_image"] = f"{media_base_url}{img_str}"
                #"set_number","court_num","points"
                set_list_team1 = []
                set_list_team2 = []
                score_list_team1 = []
                score_list_team2 = []
                win_status_team1 = []
                win_status_team2 = []
                is_completed_match = sc["is_completed"]
                is_win_match_team1 = False
                is_win_match_team2 = False
                team1_name = sc["team1__name"]
                team2_name = sc["team2__name"]
                if sc["team1_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                    is_win_match_team1 = True
                    is_win_match_team2 = False
                elif sc["team2_id"] == sc["winner_team_id"] and sc["winner_team_id"] is not None:
                    is_win_match_team2 = True
                    is_win_match_team1 = False
                # else:
                #     is_win_match_team2 = False
                #     is_win_match_team1 = False
                for s in range(sc["set_number"]):
                    index = s+1
                    set_str = f"s{index}"
                    set_list_team1.append(set_str)
                    set_list_team2.append(set_str)
                    score_details_for_set = TournamentSetsResult.objects.filter(tournament_id=sc["id"],set_number=index).values()
                    if len(score_details_for_set)!=0:
                        team_1_score = score_details_for_set[0]["team1_point"]
                        team_2_score = score_details_for_set[0]["team2_point"]
                    else:
                        team_1_score = None
                        team_2_score = None
                    score_list_team1.append(team_1_score)
                    score_list_team2.append(team_2_score)
                    if team_1_score is not None and team_2_score is not None:
                        if team_1_score >= team_2_score:
                            win_status_team1.append(True)
                            win_status_team2.append(False)
                        else:
                            win_status_team1.append(False)
                            win_status_team2.append(True)
                    else:
                        win_status_team1.append(False)
                        win_status_team2.append(False)
                score = [
                    {
                     "name": team1_name,"set": set_list_team2,
                     "score": score_list_team1,"win_status": win_status_team1,
                     "is_win": is_win_match_team1,"is_completed": is_completed_match
                     },
                    {
                    "name": team2_name,"set": set_list_team2,
                    "score": score_list_team2,"win_status": win_status_team1,
                    "is_win": is_win_match_team2,"is_completed": is_completed_match
                    }
                    ]
                sc["score"] = score
                # print(score)
            
              
            data['match'] = tournament_details
            ######## tournament matches details ########

            ########### Knock Out part ####################

            #this data for Elimination Round   
            knock_out_tournament_elimination_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Elimination Round").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                            ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
            for ele_tour in knock_out_tournament_elimination_data:
                # ele_tour["is_edit"] = get_user.is_organizer and check_leagues.first().created_by == get_user or ele_tour["team1_id"] == get_user.id or ele_tour["team2_id"] == get_user.id
                if (get_user.id in orgs_list) or (get_user.id in team_1_player) or (get_user == team_1_created_by) or (get_user.id in team_2_player) or ((get_user == team_2_created_by)):
                    sc["is_edit"] = True
                else:
                    sc["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True, team2_approval=True, organizer_approval=True)

                if check_score_approved.exists():
                    sc["is_score_approved"] = True
                    sc["is_edit"] = False
                else:
                    sc["is_score_approved"] = False                    
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
                if check_score_reported.exists():
                    sc["is_score_reported"] = True 
                    if (get_user.id in orgs_list):
                        sc["is_edit"] = True
                    else:
                        sc["is_edit"] = False
                else:
                    sc["is_score_reported"] = False   

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team2_approval=True).exists()
                organizer_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], organizer_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = True
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = True
                elif check_score_set.exists() and (get_user.id in organizer_list) and not organizer_approval:
                    sc['is_organizer'] = True
                    sc["is_button_show"] = True
                else:   
                    sc['is_organizer'] = False             
                    sc["is_button_show"] = False

                score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
                if ele_tour["team1_id"] == ele_tour["winner_team_id"] and ele_tour["winner_team_id"] is not None:
                    score[0]["is_win"] = True
                    score[1]["is_win"] = False
                elif ele_tour["team2_id"] == ele_tour["winner_team_id"] and ele_tour["winner_team_id"] is not None:
                    score[1]["is_win"] = True
                    score[0]["is_win"] = False
                else:
                    score[1]["is_win"] = None
                    score[0]["is_win"] = None
                score_details = TournamentSetsResult.objects.filter(tournament_id=ele_tour["id"]).values()
                score[0]["name"] = ele_tour["team1__name"]
                score[1]["name"] = ele_tour["team2__name"]
                score[0]["set"] = ["s1","s2","s3"]
                score[1]["set"] = ["s1","s2","s3"]
                for l__ in range(3):
                    
                    if l__ < len(score_details):
                        l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                    else:
                        l = {"team1_point":None,"team2_point":None}
                    
                    score[0]["score"].append(l["team1_point"])
                    score[1]["score"].append(l["team2_point"])
                    
                    if l["team1_point"] == None or l["team1_point"] == None:
                        score[0]["win_status"].append(None)
                        score[1]["win_status"].append(None)
                    elif l["team1_point"] > l["team2_point"]:
                        score[0]["win_status"].append(True)
                        score[1]["win_status"].append(False)
                    else:
                        score[0]["win_status"].append(False)
                        score[1]["win_status"].append(True)
                ele_tour["score"] = score
            data['elemination'] = list(knock_out_tournament_elimination_data)

            #this data for Semi Final   
            knock_out_semifinal_tournament_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Semi Final").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                            ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
            for semi_tour in knock_out_semifinal_tournament_data:
                if (get_user.id in orgs_list) or (get_user.id in team_1_player) or (get_user == team_1_created_by) or (get_user.id in team_2_player) or ((get_user == team_2_created_by)):
                    sc["is_edit"] = True
                else:
                    sc["is_edit"] = False
                
                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True, team2_approval=True, organizer_approval=True)

                if check_score_approved.exists():
                    sc["is_score_approved"] = True
                    sc["is_edit"] = False
                else:
                    sc["is_score_approved"] = False                    
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
                if check_score_reported.exists():
                    sc["is_score_reported"] = True 
                    if (get_user.id in orgs_list):
                        sc["is_edit"] = True
                    else:
                        sc["is_edit"] = False
                else:
                    sc["is_score_reported"] = False   

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team2_approval=True).exists()
                organizer_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], organizer_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = True
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = True
                elif check_score_set.exists() and (get_user.id in organizer_list) and not organizer_approval:
                    sc['is_organizer'] = True
                    sc["is_button_show"] = True
                else:   
                    sc['is_organizer'] = False             
                    sc["is_button_show"] = False

                score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
                if semi_tour["team1_id"] == semi_tour["winner_team_id"] and semi_tour["winner_team_id"] is not None:
                    score[0]["is_win"] = True
                    score[1]["is_win"] = False
                elif semi_tour["team2_id"] == semi_tour["winner_team_id"] and semi_tour["winner_team_id"] is not None:
                    score[1]["is_win"] = True
                    score[0]["is_win"] = False
                else:
                    score[1]["is_win"] = None
                    score[0]["is_win"] = None
                score_details = TournamentSetsResult.objects.filter(tournament_id=semi_tour["id"]).values()
                score[0]["name"] = semi_tour["team1__name"]
                score[1]["name"] = semi_tour["team2__name"]
                score[0]["set"] = ["s1","s2","s3"]
                score[1]["set"] = ["s1","s2","s3"]
                for l__ in range(3):
                    
                    if l__ < len(score_details):
                        l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                    else:
                        l = {"team1_point":None,"team2_point":None}
                    
                    score[0]["score"].append(l["team1_point"])
                    score[1]["score"].append(l["team2_point"])
                    
                    if l["team1_point"] == None or l["team1_point"] == None:
                        score[0]["win_status"].append(None)
                        score[1]["win_status"].append(None)
                    elif l["team1_point"] > l["team2_point"]:
                        score[0]["win_status"].append(True)
                        score[1]["win_status"].append(False)
                    else:
                        score[0]["win_status"].append(False)
                        score[1]["win_status"].append(True)
                semi_tour["score"] = score
            data['semi_final'] = list(knock_out_semifinal_tournament_data)

            #this data for Final 
            knock_out_final_tournament_data = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Final").values("id","uuid","secret_key","match_number","match_type","elimination_round","team1__name", "team1_id", "team2_id"
                                                                                                            ,"team1__team_image","team2__name","team2__team_image","winner_team__name", "winner_team_id", "loser_team_id", "winner_team__team_image","loser_team__name","loser_team__team_image","is_completed","play_ground_name")
            for final_tour in knock_out_final_tournament_data:
                if (get_user.id in orgs_list) or (get_user.id in team_1_player) or (get_user == team_1_created_by) or (get_user.id in team_2_player) or ((get_user == team_2_created_by)):
                    sc["is_edit"] = True
                else:
                    sc["is_edit"] = False

                check_score_approved = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True, team2_approval=True)

                if check_score_approved.exists():
                    sc["is_score_approved"] = True
                    sc["is_edit"] = False
                else:
                    sc["is_score_approved"] = False                    
                
                check_score_reported = TournamentScoreReport.objects.filter(tournament__id=sc["id"], status="Pending")
                if check_score_reported.exists():
                    sc["is_score_reported"] = True 
                    if (get_user.id in orgs_list):
                        sc["is_edit"] = True
                    else:
                        sc["is_edit"] = False
                else:
                    sc["is_score_reported"] = False   

                team1_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team1_approval=True).exists()
                team2_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], team2_approval=True).exists()
                organizer_approval = TournamentScoreApproval.objects.filter(tournament__id=sc["id"], organizer_approval=True).exists()
                check_score_set = TournamentSetsResult.objects.filter(tournament__id=sc["id"])

                if check_score_set.exists() and not team1_approval and ((get_user.id in team_1_player) or (get_user == team_1_created_by)) and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = True
                
                elif check_score_set.exists() and not team2_approval and ((get_user.id in team_2_player) or (get_user == team_2_created_by)) and not check_score_reported.exists():
                    sc['is_organizer'] = False
                    sc["is_button_show"] = True
                elif check_score_set.exists() and (get_user.id in organizer_list) and not organizer_approval:
                    sc['is_organizer'] = True
                    sc["is_button_show"] = True
                else:   
                    sc['is_organizer'] = False             
                    sc["is_button_show"] = False

                score = [{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True},{"name": "","set": [],"score": [],"win_status": [],"is_win": True,"is_completed": True}]
                
                if final_tour["team1_id"] == final_tour["winner_team_id"] and final_tour["winner_team_id"] is not None:
                    score[0]["is_win"] = True
                    score[1]["is_win"] = False
                elif final_tour["team2_id"] == final_tour["winner_team_id"] and final_tour["winner_team_id"] is not None:
                    score[1]["is_win"] = True
                    score[0]["is_win"] = False
                else:
                    score[1]["is_win"] = None
                    score[0]["is_win"] = None
                score_details = TournamentSetsResult.objects.filter(tournament_id=final_tour["id"]).values()
                score[0]["name"] = final_tour["team1__name"]
                score[1]["name"] = final_tour["team2__name"]
                score[0]["set"] = ["s1","s2","s3"]
                score[1]["set"] = ["s1","s2","s3"]
                for l__ in range(3):
                    
                    if l__ < len(score_details):
                        l = {"team1_point":score_details[l__]["team1_point"],"team2_point":score_details[l__]["team2_point"]}
                    else:
                        l = {"team1_point":None,"team2_point":None}
                    
                    score[0]["score"].append(l["team1_point"])
                    score[1]["score"].append(l["team2_point"])
                    
                    if l["team1_point"] == None or l["team1_point"] == None:
                        score[0]["win_status"].append(None)
                        score[1]["win_status"].append(None)
                    elif l["team1_point"] > l["team2_point"]:
                        score[0]["win_status"].append(True)
                        score[1]["win_status"].append(False)
                    else:
                        score[0]["win_status"].append(False)
                        score[1]["win_status"].append(True)
                final_tour["score"] = score
            data['final'] = list(knock_out_final_tournament_data)

            ########### Knock Out part ####################
            
            ########### declear winner team and update ##########
            play_type_check_win = league.play_type
            if play_type_check_win == "Group Stage" or play_type_check_win == "Single Elimination":
                check_final = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Final",is_completed=True)
                if check_final.exists():
                    final_match = check_final.first()
                    winner_team = final_match.winner_team
                    winner_team_name = final_match.winner_team.name
                    league.winner_team = winner_team
                    league.is_complete = True
                    league.save()
                    data["winner_team"] = winner_team_name
                else:
                    pass

            else:
                check_final = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Individual Match Play",is_completed=True)
                if check_final.exists():
                    final_match = check_final.first()
                    if not final_match.is_drow:
                        winner_team = final_match.winner_team
                        winner_team_name = final_match.winner_team.name
                        league.winner_team = winner_team
                        league.is_complete = True
                        league.save()
                        data["winner_team"] = winner_team_name
                    else:
                        winner_team1 = final_match.team1
                        winner_team2 = final_match.team2
                        # league.winner_team = None
                        league.is_complete = True
                        league.save()
                        data["winner_team"] = f"{winner_team1.name}, {winner_team2.name}"
                else:
                    pass
            ########### declear winner team and update ##########


            #If Tournament is Group stage or Round Robin
            ############# point table ########################
            all_group_details = RoundRobinGroup.objects.filter(league_for=league)
            for grp in all_group_details:
                teams = grp.all_teams.all()
                group_score_point_table = []
                # print(teams)
                for team in teams:
                    team_score = {}
                    total_match_detals = Tournament.objects.filter(leagues=league, match_type="Round Robin").filter(Q(team1=team) | Q(team2=team))
                    completed_match_details = total_match_detals.filter(is_completed=True)
                    win_match_details = completed_match_details.filter(winner_team=team).count()
                    loss_match_details = completed_match_details.filter(loser_team=team).count()
                    drow_match = len(completed_match_details) - (win_match_details + loss_match_details)
                    match_list = list(total_match_detals.values_list("id", flat=True))
                    for_score = 0
                    aginst_score = 0
                    for sc in match_list:
                        co_team_position = Tournament.objects.filter(id=sc).first()
                        set_score = TournamentSetsResult.objects.filter(tournament_id=sc)
                        if co_team_position.team1 == team:
                           for_score = for_score + sum(list(set_score.values_list("team1_point", flat=True)))
                           aginst_score = aginst_score + sum(list(set_score.values_list("team2_point", flat=True)))
                        else:
                            for_score = for_score + sum(list(set_score.values_list("team2_point", flat=True)))
                            aginst_score = aginst_score + sum(list(set_score.values_list("team1_point", flat=True)))
                    
                    point = (win_match_details * 3) + (drow_match * 1)
                    team_score["uuid"], team_score["secret_key"] = team.uuid, team.secret_key
                    team_score["name"], team_score["completed_match"] = team.name, len(completed_match_details)
                    team_score["win_match"], team_score["loss_match"] = win_match_details, loss_match_details
                    team_score["drow_match"], team_score["for_score"] = drow_match, for_score
                    team_score["aginst_score"], team_score["point"] = aginst_score, point
                    group_score_point_table.append(team_score)
                # Append team details to group data
                tournament_details_group = Tournament.objects.filter(leagues=league,group=grp).values("id","uuid","secret_key","team1__name","team2__name","leagues__name","match_type","is_completed","group__court","play_ground_name","playing_date_time","group_id")
                for k_ in tournament_details_group:
                    round_robin_group_detals = RoundRobinGroup.objects.filter(league_for=league, id=k_["group_id"]).first()
                    k_["sets"] = round_robin_group_detals.number_sets
                    k_["court"] = round_robin_group_detals.court
                    k_["score"] = list(TournamentSetsResult.objects.filter(tournament_id=k_["id"]).values())
                
                group_score_point_table = sorted(group_score_point_table, key=lambda x: (x['point'], x['for_score']), reverse=True)
                # print(group_score_point_table)

                ###### tournament winning team update and declare
                if play_type_check_win == "Round Robin":
                    total_tournament = Tournament.objects.filter(leagues=check_leagues.first(),match_type="Round Robin",leagues__play_type="Round Robin")
                    completed_tournament = total_tournament.filter(is_completed=True)
                    if total_tournament.count() == completed_tournament.count():
                        winner_team = Team.objects.filter(uuid=group_score_point_table[0]["uuid"]).first()
                        winner_team_name = winner_team.name
                        league.winner_team = winner_team
                        league.is_complete = True
                        league.save()
                        data["winner_team"] = winner_team_name
                grp_data = {
                    "id": grp.id,
                    "court": grp.court,
                    "league_for_id": grp.league_for_id,
                    "all_games_status": grp.all_games_status,
                    "all_tems": group_score_point_table,
                    "tournament": tournament_details_group,
                    "seleced_teams_id": grp.seleced_teams_id
                }
                data['point_table'].append(grp_data)

            all_team = check_leagues.first().registered_team.all()
            ############# point table ########################


            ######### Tornament all teams details ############
            teams = []
            for t in all_team:
                team_d = Team.objects.filter(id=t.id).values()
                teams.append(team_d[0])
            for im in teams:
                if im["team_image"] != "":
                    img_str = im["team_image"]
                    im["team_image"] = f"{media_base_url}{img_str}"
            
            data['teams'] = teams
            ######### Tornament all teams details ############
            
            
            data["create_group_status"] = get_user.is_organizer and check_leagues.first().created_by == get_user
            data["status"], data["message"] = status.HTTP_200_OK, "League data"
        else:
            data["status"], data['data'], data["message"] = status.HTTP_404_NOT_FOUND, [],  "User or League not found."
    except Exception as e :
        data['status'], data['message'] = status.HTTP_400_BAD_REQUEST, f"{e}"
    return Response(data)



@api_view(('GET',))
def get_organizer_details(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_admin or get_user.is_organizer:
                data['data'] = list(User.objects.filter(is_organizer=True).values('id','uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code'))
                data['message'] = "Data found"
                data['status'] = status.HTTP_200_OK
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "User is not an organizer or admin"
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)
 

@api_view(('GET',))
def get_sponsor_details(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_admin == True:
                data['data'] = list(User.objects.filter(is_sponsor=True).values('uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code','fb_link','twitter_link','youtube_link','instagram_link'))
                data['message'] = "Data found"
                data['status'] = status.HTTP_200_OK
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "User is not a sponsor"
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('GET',))
def get_admin_details(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_admin == True:
                data['data'] = list(User.objects.filter(is_admin=True).values('uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code','fb_link','twitter_link','youtube_link','instagram_link'))
                data['message'] = "Data found"
                data['status'] = status.HTTP_200_OK
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "User is not admin."
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('GET',))
def get_ambassador_details(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.GET.get('user_uuid')
        user_secret_key = request.GET.get('user_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        if check_user.exists():
            get_user = check_user.first()
            if get_user.is_admin == True:
                data['data'] = list(User.objects.filter(is_ambassador=True).values('uuid','secret_key','username','first_name','last_name','email','phone','gender','user_birthday','role','rank','image','street','city','state','country','postal_code','fb_link','twitter_link','youtube_link','instagram_link'))
                data['message'] = "Data found"
                data['status'] = status.HTTP_200_OK
            else:
                data['status'] = status.HTTP_404_NOT_FOUND
                data['message'] = "User is not an ambassador."
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('POST',))
def remove_organizer(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.POST.get('user_uuid')
        user_secret_key = request.POST.get('user_secret_key')
        r_uuid = request.POST.get('r_uuid')
        r_secret_key = request.POST.get('r_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        r_user = User.objects.filter(uuid=r_uuid, secret_key=r_secret_key)
        if check_user.exists() and r_user.exists() and check_user.first().is_admin:
            r_user.update(is_organizer=False)
            data['message'] = "Remove from organizer"
            data['status'] = status.HTTP_200_OK
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)

    
@api_view(('POST',))
def remove_sponsor(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.POST.get('user_uuid')
        user_secret_key = request.POST.get('user_secret_key')
        r_uuid = request.POST.get('r_uuid')
        r_secret_key = request.POST.get('r_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        r_user = User.objects.filter(uuid=r_uuid, secret_key=r_secret_key)
        if check_user.exists() and r_user.exists():
            IsSponsorDetails.objects.filter(sponsor=r_user.first()).delete()
            r_user.update(is_sponsor=False, role="",is_verified=False)
            data['message'] = "Remove from Sponsor"
            data['status'] = status.HTTP_200_OK
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)


@api_view(('POST',))
def remove_admin(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.POST.get('user_uuid')
        user_secret_key = request.POST.get('user_secret_key')
        r_uuid = request.POST.get('r_uuid')
        r_secret_key = request.POST.get('r_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        r_user = User.objects.filter(uuid=r_uuid, secret_key=r_secret_key)
        if check_user.exists() and r_user.exists() and check_user.first().is_admin:
            r_user.update(is_admin=False)
            data['message'] = "Remove from admin"
            data['status'] = status.HTTP_200_OK
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)

    
@api_view(('POST',))
def remove_ambassador(request):
    data = {'status':'', 'message':''}
    try:        
        user_uuid = request.POST.get('user_uuid')
        user_secret_key = request.POST.get('user_secret_key')
        r_uuid = request.POST.get('r_uuid')
        r_secret_key = request.POST.get('r_secret_key')
        check_user = User.objects.filter(uuid=user_uuid, secret_key=user_secret_key)
        r_user = User.objects.filter(uuid=r_uuid, secret_key=r_secret_key)
        if check_user.exists() and r_user.exists() and check_user.first().is_admin:
            r_user.update(is_ambassador=False)
            data['message'] = "Remove from ambassador"
            data['status'] = status.HTTP_200_OK
        else:
            data['status'] = status.HTTP_404_NOT_FOUND
            data['message'] = "User not found."
        return Response(data)
    except Exception as e:
        data['status'] = status.HTTP_400_BAD_REQUEST
        data['message'] = f"{e}"
    return Response(data)



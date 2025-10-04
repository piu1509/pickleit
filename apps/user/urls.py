from django.urls import path
from apps.user import views
from apps.user import subcription_view as views2
from apps.user import twilloview as views3


urlpatterns = [
    path('7b87ea396289adfe5b192307cff9bd4a4e6512779efe14114f655363c17c3b20/', views.user_login_api, name="user_login_api"),
    path('fd65514d783d0427c58482473b207b5eb5f92d864a738ccdd1f109c53ac9ca8a/', views.get_user_access_token, name="get_user_access_token"),
    path('4eec011f0e4da0f19f576ac581ae8d77cd0191e51925c59ba843219390f205c9/', views.user_signup_api, name="user_signup_api"),
    path('74185382c74df4e92e609012006dc3d549c6cef9a7d85039d16788adbde777c6/', views.user_signup_email_check_api, name="user_signup_email_check_api"),
    path('0792cc3f8c0f0322e9dcc248587fddac570aa0da6e202c392c77ce3537b76618/', views.send_email_verification, name="send_email_verification"),
    path('3342cb68e59a46aa0d8be6504ee298446bf1caff5aeae202ddec86de1e38436c/<str:uuid>/<str:skey>/<str:otp>/', views.verification_link, name="verification_link"),
    path('cb8e4acdfbbe2c496ce12cb7a34df298addd8626412be65eeace8ce1cdd8f124/', views.forgot_password, name="forgot_password"),
    path('1edc89fdde56d7d70adbfce09c10409cafca6e0316d6f0ba47787b0a3faf8e15/', views.change_password, name="change_password"),
    path('38aa6895e95e351773fdf450c13e8d44d6576a40463bb8f5ac083e917b6ff414/', views.email_send_forgot_password, name="email_send_forgot_password"),
    path('b095a3eac89a23ec5372b756f14d22c6e227c58c0800cddd0d29b8530ae4a99e/', views.add_admin, name="add_admin"),
    path('c24d06eb8ed088c69d2dd828dba2bdc6bb06fd006d70d8befbbd961cfb7baa2b/', views.edit_admin, name="edit_admin"),
    path('e18e5cc5bff847c4a90892960319b58a6df56f9a93f4c22cb7864d75db47ce27/', views.list_admin, name="list_admin"),
    path('9112016c3f8db1f36285b40f642444aef83b3e10cc20b43fb76fad55a7f4e95d/', views.send_admin_password_email, name="send_admin_password_email"),
    path('8e3c5dd921d7d9b2505348f5da640b11c199803e1bb75517bfde34cc50d906d5/', views.list_user, name="list_user"),
    path('9b863d70f1aae62436c7cee0ad1984a1faa3f0d6176ff669e92f6100e62bbab4/', views.add_user, name="add_user"),
    path('89b449c603286a42377df664f16d7a2c9f5c5624250cadfacb1e0747c3e3f77d/', views.user_profile_view_api, name="user_profile_view_api"),
    # pagination for post and ads
    path('89dddfbcb975451261a35fae9abf10ce42da6227b92e2176ca435b1a2b373555/', views.user_profile_view_using_pagination, name="user_profile_view_using_pagination"),
    path('ed9b3852580d7da0fab6f3550acae26ee1ec94618a1fa74bddc62f9e892f3400/', views.user_profile_edit_api, name="user_profile_edit_api"),
    # path('get_all_user/', views.get_all_user, name="get_all_user"),
    path('28cd4daaa7fc9842416efdeb35de0022536f91371a28278c05d9158534bb4768/', views.delete_user_profile, name="delete_user_profile"),
    path('1ed694c4fcdc2043149f325fc4f371bf95c00b462e92e2a101bbedcc25b864f7/', views.update_notification_status, name="update_notification_status"),
    path('e01c2fce94ed9a03e42d63e9889af5788b8a20ee118e30f2b9e51ec2ba031910/', views.delete_all_notifications_for_user, name="delete_all_notifications_for_user"),

    path('2bff6ae866b25793517455017fe8965e79d7c210310711fa96a32496ad0d1e86/', views.get_update_responce, name="get_update_responce"),
    path('aa78414f71f9a413c69e9af59e5ae2f8a66a5b06fa5bd804cee98925fd812bf5/', views.app_update, name="app_update"),


    # app version
    path('9d4d1272f978d2ab8142ec24f2bd21832887db263c4e333d79778b279006f0ae/', views.app_version_post, name="app_version_post"),
    path('264e4c4094c27aa7aca632069e73624779d2ff94414962305a5510fd1919fc92/', views.get_api_version, name="get_api_version"),

    # path('2bff6ae866b25793517455017fe8965e79d7c210310711fa96a32496ad0d1e86/', views.get_update_responce, name="get_update_responce"),
    # path('aa78414f71f9a413c69e9af59e5ae2f8a66a5b06fa5bd804cee98925fd812bf5/', views.app_update, name="app_update"),
    #show screen
    path('8424bddbcf4b9b29372da22637c44f225054aa9af9c9d7917f6d0a36fe5acb38/', views.post_user_show_screen, name="post_user_show_screen"),

    # self-ranking
    path('5f9a2c9246e8665a3be27ed90fc1280178abb8e8b399555eaa5c39fad3628774/', views.get_user_questions, name="get_user_questions"),
    path('0cc13d9503bf698ebc0942e531aace29abdb7b6c19da8dfb74d701daa0f9f38d/', views.update_rank, name="update_rank"),
    path('0e139a35a2c52325e25dbd1b381477673bbe0c963928b5c459bf2f841f57124f/', views.delete_self_ranking_answers_per_user, name="delete_self_ranking_answers_per_user"),

    #export file
    path('e7eef5cb738fea637f6c565d557cb6c288a13c6c94f58a94ef6d7c3441350281/<str:leaug_uuid>/<str:user_uuid>', views.show_pdf, name="show_pdf"),

    # matching players
    # matching players
    path('b2928233f1289f89722a278be440f66238e1093d102dd87fd084903b7fb8a242/', views.user_update_details, name="user_update_details"),
    path('40d298f89a5e0fe2b46ef3a1077932e1e18f42e5ac90bf3375f958fe496c7f89/', views.update_user_details, name="update_user_details"),
    path('bd2654cea102244ea9e79b236ccf0e3bc11e50d5a39cfbb4413b4c558538e553/', views.update_user_search_preference, name="update_user_search_preference"),
    path('bf3db0a260497d3253136eceac398d15aac0580026649e325bd2052fabfb66c6/', views.view_matching_player, name="view_matching_player"),
    path('2b4fea4949e393a905e2b5ad80bec87b4276e8ebcb891a9c212e6ae4f7c1b3a2/', views.get_matching_users, name="get_matching_users"),
    path('ea83b26c9ef25ddd0b4f32d7962cf6450ad32bd022719263f2a98fb5d9668a6a/', views.get_open_play_team, name="get_open_play_team"),
    path('ec552cb2400b5e6c3a5296447549ad87efe31e43fec7d4f16d0c2b1b441f0bbe/', views.create_open_play, name="create_open_play"),
    
    path('cf896e2993859bb9e363fe7374462c9f3b0284dd422cd519b4584c463b5b1c11/', views.create_teams_and_open_play, name="create_teams"),
    #edit open_play
    path('90ec1e12a667ec8b3bccca267766b0e7b02416d35e774d1cf63799c4b9df1348/', views.get_open_play_details, name="get_open_play_details"),
    path('5c8c937bdbfd4425345cd7166675ddecec637c839f4e4e4461b0da51161f769c/', views.edit_open_play_tournament, name="edit_open_play_tournament"),

    # FCM Token
    path('17c5dca8e378b4c6892d31038c47833ed01b1ea1e9ea549e4c5afe3da79a1eee/', views.fcm_token_store, name="fcm_token_store"),
    path('e7ea0710df3369ef9a67fc0cfcd9a38aa5a13d1e88600707c1c402d325ddd105/', views.delete_fcm_token_at_logout, name="delete_fcm_token_at_logout"),
    path('c303644d18db116ecdfc8f1392771363c3bc0ca3df46336aea7eee5cff14fc74/', views.edit_profile_, name="edit_profile"),
    path('5a3775687e938ab9f9242fdf44d779abf915982e33143725b69a3b898daae2e0/', views.check_update_status, name="check_update_status"),
    path('23a8648e31374d325b00ccc7f65b45b8bdbbd650fd91824952404e74644c4de1/', views.update_version, name="update_version"),
    path('08bc449c35a83013fb348bd43d1819ba5afb9b98c24a188d1d415e9c3042f343/', views.location_update_alert, name='location_update_alert'),
    path('f568583ac433f6fab22fea90553f686bf2d3bda2803b87d59e258fd6c2c89a4f/', views.update_location, name='update_location'),


    path('dbb6d176341d5d81bdee8a28f0a05d304cc8cdc9e9b2ec2ec24300f5152c9fb7/', views.get_wallet_details, name='get_wallet_details'),
    path('1e7de31e7ed580d28d4c228896ee0ec78cdf986b20600da93177d418951bf2ed/', views.add_money_to_wallet, name='add_money_to_wallet'),
    path('285631b6075a10ddfc536d3d9be994d05a932abc3d6f091fabe8e7aa77ccfd25/<str:payment_for>/<str:encoded_data>/<str:checkout_session_id>/', views.payment_for_adding_money_to_wallet, name='payment_for_adding_money_to_wallet'),
    path('1da6ebc0ac3470221ba64945ed545846258eff24ceed59f9f55f1e39767fe846/', views.get_all_wallet_transactions, name="get_all_wallet_transactions"),
    path('da29d8d1ee85757c5874ee8ca386d55d6a280605b9a90d12d0e650b9b8c90133/', views.create_withdrawal_request, name='create_withdrawal_request'),
    path('fcd146d98382e46e214953efcf8ba98d4a88dc393e5d6fa180f8437ea2866111/', views.withdrawal_request_list, name="withdrawal_request_list"),
    path('73d830035fdcba90fdbe3d4a7e4f4ad07a047e50bd244904fd9751eb95050840/', views.deactivate_account, name='deactivate_acount'),


    #subcription
    # subcription model
    #subcription
    path('validate-iap/', views2.validate_iap, name='validate_iap'),
    path('subscription-plans/', views2.get_subscription_plans, name='get_subscription_plans'),
    path('next-plans/', views2.get_next_plans, name='get_next_plans'),
    path('get_user_subcription_permition/', views2.get_user_subcription_permition, name="get_user_subcription_permition"),

    ###subcription using stripe
    path('get_user_subscription_details/', views2.get_subscription_payment_link, name="get_subscription_payment_link"),
    path('plan/subscription/payment/<str:encoded_data>/<str:session_id>/', views2.get_subscription_payment_link_verify, name="get_subscription_payment_link_verify"),
    path('plan/subscription/cancel/', views2.get_subscription_payment_cancel, name="get_subscription_payment_cancel"),



    # twillo 
    path("send-otp/",  views3.SendOTPView.as_view(), name="send-otp"),
    path("verify-otp/", views3.VerifyOTPView.as_view(), name="verify-otp"),

    #live stream
    path('check_player/', views.check_player, name="check_player"),
    path('get_stream_token/', views.get_stream_token, name="get_stream_token"),
    path('close_stream_token/', views.close_stream_token, name="close_stream_token"),
    path('delete_stream/', views.delete_stream, name="delete_stream"),
    path('get_call_token/', views.get_call_token, name="get_call_token"),
    path('get_my_call/', views.get_my_call, name="get_my_call"),
    path('get_video_link/', views.get_video_link, name="get_video_link"),


    ##map
    path('find_nearby_places/', views.find_nearby_places, name="find_nearby_places"),

    #add promo code
    path('get_promo_codes/', views.get_promo_codes, name="get_promo_codes"),



    ##map
    path('del_user_stripe/', views.del_user_stripe_id, name="del_user_stripe_id"),

]
from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="dashboard"),
    path('login/',views.login, name='user_login'),
    path('logout/',views.logout_view, name='logout'),
    
    #player
    path("player_list_/", views.player_list_, name="player_list_"),
    path("create_player_/", views.create_player_, name="create_player_"),
    path("player_view_/<int:user_id>/", views.player_view, name="player_view"),
    path("edit_player_/<int:user_id>/", views.edit_player, name="edit_player"),
    path("delete_player_/<int:user_id>/", views.delete_player, name="delete_player"),
    
    #merchant request
    path("merchant_request_list/", views.merchant_request_list, name="merchant_request_list"),

    # team
    path("team_list_for_admin/", views.team_list_for_admin, name="team_list_for_admin"),
    path('get_players_by_team_type/', views.get_players_by_team_type, name='get_players_by_team_type'),

    path("create_team_/", views.create_team_, name="create_team_"),
    path("edit_team_/<int:team_id>", views.edit_team_, name="edit_team_"),
    path("delete_team_/<int:team_id>", views.delete_team_, name="delete_team_"),
    path("view_team_/<int:team_id>", views.view_team_, name="view_team_"),  
    
    #user not using
    path('create_user_/', views.create_user, name="create_user"),
    path('user_list_/<str:filter_by>', views.user_list, name="user_list"),
    path('view_user_/<int:user_id>/', views.view_user, name="view_user"),
    path('edit_user_/<int:user_id>/', views.edit_user, name="edit_user"),
    path('delete_user_/<int:user_id>/', views.delete_user, name="delete_user"),

    path("tournamnet_list/<str:filter_by>", views.tournament_list, name="tournamnet_list"),
    path("view_tournament/<int:tour_id>/", views.view_tournament, name="view_tournament"),
    path("hit_start_tournamnet/<int:tour_id>/", views.hit_start_tournamnet, name="hit_start_tournamnet"),
    path("create_tournamnet/", views.create_tournamnet, name="create_tournamnet"),
   
    path("update_match/<int:set_score_id>/", views.update_match, name="update_match"),
    path("edit_tournament/<int:tour_id>/", views.edit_tournament, name="edit_tournament"),
    path("edit_matches__score/<int:tour_id>/", views.edit_matches__, name="edit_matches__score"),
    path('update-match-order/', views.update_match_order, name='update_match_order'),
    path("submit_score/<int:tour_id>/", views.submit_score, name="submit_score"),
    path("delete_tournament/<int:tour_id>/", views.delete_tournament, name="delete_tournament"),
    path('join_team_event/<int:tour_id>/', views.join_team_tournament, name="join_team_event"),
    path("confirm-payment/", views.confirm_payment, name="confirm_payment"),
    path("initiate-stripe-payment/", views.initiate_stripe_payment, name="initiate_stripe_payment"),
    path('stripe_success/<int:event_id>/<str:team_ids>/<str:checkout_session_id>/', views.stripe_success, name='stripe_success'),

    path('get-cancellation-policy/', views.get_cancellation_policy, name='get_cancellation_policy'),
    path('remove-team-from-league/', views.remove_team_from_league, name='remove_team_from_league'),


    path("advertisement_list_/<str:filter_type>", views.advertisement_list, name="advertisement_list"),
    path("advertisement_view_/<int:ad_id>/", views.advertisement_view, name="advertisement_view"),
    path("advertisement_approve_/<int:ad_id>/", views.ad_approve, name="advertisement_approve"),
    path("advertisement_reject_/<int:ad_id>/", views.ad_reject, name="advertisement_reject"),
    path("ambassador_post_list_/", views.ambassador_post_list, name="ambassador_post_list"),
    path("ambassador_post_approve_/<int:post_id>/", views.ambassador_post_approve, name="ambassador_post_approve"),
    path("ambassador_post_reject_/<int:post_id>/", views.ambassador_post_reject, name="ambassador_post_reject"),
    
    path("admin_profile/", views.admin_profile, name="admin_profile"),
   
    
    path("create_open_play/", views.create_open_play, name="create_open_play"),
    path('open_play_list/<str:filter_by>', views.open_play_list, name='open_play_list'),
    path('search-players/', views.search_players, name="search-players"),
    path("view_open_play/<int:tour_id>/", views.view_open_play, name="view_open_play"),
    path("start_open_play/<int:tour_id>/", views.start_open_play, name="start_open_play"),
   
    path("update_match_open_play/<int:set_score_id>/", views.update_match_open_play, name="update_match_open_play"),
    path("edit_open_play/<int:tour_id>/", views.edit_open_play, name="edit_open_play"),
    path("edit_matches_open_play/<int:tour_id>/", views.edit_matches_open_play, name="edit_matches_open_play"),
    path('update-match-order-open-play/', views.update_match_order_open_play, name='update_match_order_open_play'),
    path("submit_score_open_play/<int:tour_id>/", views.submit_score_open_play, name="submit_score_open_play"),
    path("delete_open_play/<int:tour_id>/", views.delete_open_play, name="delete_open_play"),


    path("add_product/", views.add_product, name="add_product"),
    path("product_list/", views.product_list, name="product_list"),
    path('cart-count/', views.cart_count, name='cart_count_for_admin'),
    path('pending-order-count/', views.pending_received_order_count, name='pending_received_order_count_for_admin'),
    path("view_product/<int:product_id>/", views.view_product, name="view_product"),
    path('get_specification_data/', views.get_specification_data, name='get_specification_data'),
    path('load-single-variation-edit/<int:product_id>/', views.load_single_variation_edit, name='load_single_variation_edit'),
    path('load-multiple-variation-edit/<int:product_id>/', views.load_multiple_variation_edit, name='load_multiple_variation_edit'),
    path("edit_product/<int:product_id>/", views.edit_product, name="edit_product"),
    path("delete_product/<int:product_id>/", views.delete_product, name="delete_product"),

    path('my_received_orders/', views.my_received_orders, name='my_received_orders'),
    path('my_placed_orders/', views.my_placed_orders, name='my_placed_orders'),
    path('change-order-status/<int:order_id>/', views.change_order_status, name='change_order_status'),
    path('add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('add-to-wishlist/', views.add_to_wishlist, name='add_to_wishlist'),
    path('buy-now/', views.buy_now, name='buy_now'),
    path('checkout_summary/<int:order_id>/', views.checkout_summary, name='checkout_summary'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('cart/', views.cart, name="cart"),
    path('update_cart', views.update_cart, name='update_cart'),
    path('cart-remove-item/', views.remove_cart_item, name='remove_cart_item'),
    path('apply_coupon/', views.apply_coupon, name='apply_coupon'),

    path('select-address/', views.select_address, name='select_address'),
    path('add-address-ajax/', views.add_address_ajax, name='add_address_ajax'),

    path('cart_payment_gateway/', views.cart_payment_gateway, name='cart_payment_gateway'),
    path('create_cart_checkout_session/', views.create_cart_checkout_session, name='create_cart_checkout_session'),
    path('cart_payment_success/', views.cart_payment_success, name='cart_payment_success'),
    path('cart_payment_cancel/', views.cart_payment_cancel, name='cart_payment_cancel'),
    path('cart/webhook/', views.stripe_cart_webhook, name='stripe_cart_webhook'),
    path('buy_now_payment_gateway/', views.buy_now_payment_gateway, name='buy_now_payment_gateway'),
    path('select_address_buy_now/', views.select_address_buy_now, name='select_address_buy_now'),
    path('create_buy_now_checkout_session/', views.create_buy_now_checkout_session, name='create_buy_now_checkout_session'),
    path('buy_now_payment_success/', views.buy_now_payment_success, name='buy_now_payment_success'),
    path('buy_now_payment_cancel/', views.buy_now_payment_cancel, name='buy_now_payment_cancel'),
    path('add_review', views.add_review, name="add_review"),

    path("send_universal_notification/", views.send_universal_notification, name="send_universal_notification"),
    path("payment_table/", views.payment_table, name="payment_table"),

    path("merchant_request_list/",views.merchant_request_list, name="merchant_request_list"),
    path("app_update/", views.app_update, name="app_update"),
    path("version_update_list/", views.version_update_list, name="version_update_list"),
    path("update_version/", views.version_update, name="update_version"),
    
    path("read_notification/", views.mark_notifications_as_read, name="mark_notifications_as_read"),
    path('delete_notification/', views.delete_notification, name='delete_notification'),


    #social feed
    path("social_feed_list/", views.social_feed_list, name="social_feed_list"),
    path("add_social_feed/", views.add_social_feed, name="add_social_feed"),
    path("social_feed_view/<int:post_id>/", views.social_feed_view, name="social_feed_view"),
    path("edit_social_feed/<int:post_id>/", views.edit_social_feed, name="edit_social_feed"),
    path("delete_file/<int:file_id>/", views.delete_file, name="delete_file"),
    path('block_social_feed/<int:post_id>/', views.block_social_feed, name='block_social_feed'),

    path('club_list/<str:filter_type>', views.club_list, name="club_list"),
    path('fetch_google_clubs/', views.fetch_google_clubs, name='fetch_google_clubs'),
    path('add_club/', views.club_add, name='add_club'),
    path('edit_club/<int:club_id>/', views.edit_club, name='edit_club'),
    path('view_club/<int:club_id>/', views.view_club, name='view_club'),
    path('delete_club/<int:club_id>/', views.delete_club, name='delete_club'),

    path('court_list/', views.court_list, name="court_list"),
    path('fetch_pickleball_courts/', views.fetch_pickleball_courts, name='fetch_pickleball_courts'),
    path('add_court/', views.add_court, name='add_court'),
    path('view_court/<int:court_id>/', views.view_court, name='view_court'),
    path('edit_court/<int:court_id>/', views.edit_court, name='edit_court'),
    path('delete_court/<int:court_id>/', views.delete_court, name='delete_court'),

    path('subscription-plans/<str:plan_name>/', views.subscription_plan_users, name='subscription_plan_users'),
    path('wallet-details/', views.wallet_details, name='wallet_details'),
    path('get_transaction_details/<int:transaction_id>/', views.get_transaction_details, name='get_transaction_details'),


    
]
from django.urls import path
from apps.clubs.views import *


urlpatterns = [
    path("add-club/", add_club, name="add_club"),
    path("my-clubs/", my_club_list, name="my_clubs"),
    path("view-club/<int:club_id>/", view_club, name="view_club"),
    path("edit-club/", edit_club, name="edit_club"),
    path("add-rating/", add_rating, name="add_rating"),

    path('add_package_for_myclub/', add_package_for_myclub, name="add_package_for_myclub"),
    path("club_packages_list/<int:club_id>/", club_packages_list, name="club_packages_list"),
    path("view_club_package/<int:package_id>/", view_club_package, name="view_club_package"),
    path("edit_club_package/<int:package_id>/", edit_club_package, name="edit_club_package"),
    path("deactivate_club_package/<int:package_id>/", deactivate_club_package, name="deactivate_club_package"),

    path("book_club/", book_club, name="book_club"),
    path('store/book/club/stripe/payement/<str:stripe_fee>/<str:my_data>/<str:checkout_session_id>/', store_book_club_stripe_payement, name="store_join_club_stripe_payement"),
    ## club wonner show the booking club wise 
    path("club_booking_list/", club_booking_list, name="club_booking_list"),
    path("user_club_join_list/", user_club_join_list, name="user_club_join_list"),
    #user can show won booking list
    path("user_booking_list/", user_booking_list, name="user_booking_list"),

    #join club
    path("join_club/", join_club, name="join_club"),
    path('store/join/club/stripe/payement/<str:stripe_fee>/<str:my_data>/<str:checkout_session_id>/', store_join_club_stripe_payement, name="store_join_club_stripe_payement"),
    path("club_join_user_list/<int:club_id>/", club_join_user_list, name="club_join_user_list"),
    
    ###search club location and keyword wise
    path("search-clubs/", ClubSearchAPIView.as_view(), name="search-clubs"),


    #dashboard api
    path("weekly_booking_details/", weekly_booking_details, name="weekly_booking_details"),
    path("weekly_join_details/", weekly_join_details, name="weekly_join_details"),
    path("club_transection_list/", club_transection_list, name="club_transection_list"),

    #scanning qr code
    path("club_qr_code_scanning/", club_qr_code_scanning, name="club_qr_code_scanning"),
]
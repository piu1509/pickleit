from django.urls import path
from . import views
urlpatterns = [
    path('add_court/', views.add_court, name="add_court"),
    path('my_courts_list/', views.found_my_courts_list, name="my_courts_list"),
    path('find_nearby_court_list/', views.found_courts_list, name="find_nearby_court_list"),
    path('court_details/<int:court_id>/', views.court_details, name="court_details")
]
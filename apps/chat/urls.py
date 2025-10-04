from django.urls import path
from . import views


urlpatterns = [
    path('6a718e7164a587c105106342bb18ec50a034a0854ddc49f4ffb571eeb79199ea/', views.chat_user_details, name="chat_user_details"),
    path('10b52a019c8ba09bcb8d65340e34808b06b4211373d31e5ff6b2c6cb98100f81/', views.chat_list, name="chat_list"),
    path('a66ff4d19715790748d52bc90ffb9ab31a779c6ddaa07c5d29783f3f4683d43b/', views.chat_list_using_pagination, name="chat_list_using_pagination"),
    
    path("6626829e840eb07406be20c2501a77e733ea5b2bd77016e8217f6508c98962de/", views.user_chat_list, name="user_chat_list"),
    path("64743355d8fbeba657a087fc386bc2faef4a70f57ebc711eeb78c51a953f2a05/", views.chat_user_list, name="chat_user_list"),
    path('1eda0f0d25d5d2597ba503f24a94419d0a6108d24d3c4fcfb9559bb172e55316/', views.unread_chat_users, name="unread_chat_users"),
    path('cc450ba718d0c868196a7649ca2019976e1301435faaa476cee2feb11978b4d9/', views.block_or_unblock_chat_user, name="block_or_unblock_chat_user"),
    path('4d4cdd5a76f7a2e973d5abef6ba8b2a67fc4537243fb345dfdbdf677aa190a7c/', views.continue_chat_with_user, name="continue_chat_with_user"),
    path('dea9b1c83b207758a9f7895a36c9cd3e4ecbb7635d571b26f84ae2b2f3c3a20f/', views.report_chat_user, name="report_chat_user"),
    # path("<str:room_name>/", views.room, name="room"),
    # path("<str:natificatio_name>/", views.natificatio_name, name="natificatio_name"),

    path('df225338df37a2d169a8438f8a1d4837752f5ee278e01d42eb97ce349e59b7ff/', views.search_chat_user_by_name, name='search_chat_user_by_name'),
    path('98dbfe0c27e09f22fb8804841d774a05194ba5822ff938fe6b01e40dc2c48375/', views.create_chat_room, name='create_chat_room'),
    path('90b91c2d3d44924670acbb2485e4e54847eab86c14b94202bb5fc4a2e79f446b/', views.mark_msgs_as_read, name='mark_msgs_as_read'),
    path('ea7f409b7bec1b4d9c81f346a3aa4320dde219fd9b52287caa649259587c4366/', views.get_room_user_status, name='get_room_user_status'),


    path('get_user_search/', views.get_user_search, name="get_user_search"),

]
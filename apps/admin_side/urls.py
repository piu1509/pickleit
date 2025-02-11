from django.urls import path
from apps.admin_side import views

app_name = "dashboard"

urlpatterns = [
    path("test/", views.test, name="test"),
    path("", views.index, name="dashboard"),
    path("download-logs/", views.download_logs_csv, name="download_logs"),
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
    path("create_team_/", views.create_team_, name="create_team_"),
    path("edit_team_/<int:team_id>", views.edit_team_, name="edit_team_"),
    path("delete_team_/<int:team_id>", views.delete_team_, name="delete_team_"),
    path("view_team_/<int:team_id>", views.view_team_, name="view_team_"),  
    
    #user
    path('create_user_/', views.create_user, name="create_user"),
    path('user_list_/<str:filter_by>', views.user_list, name="user_list"),
    path('view_user_/<int:user_id>/', views.view_user, name="view_user"),
    path('edit_user_/<int:user_id>/', views.edit_user, name="edit_user"),
    path('delete_user_/<int:user_id>/', views.delete_user, name="delete_user"),

    #tournament
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

    #advertisement
    path("advertisement_list_/", views.advertisement_list, name="advertisement_list"),
    path("advertisement_view_/<int:ad_id>/", views.advertisement_view, name="advertisement_view"),
    path("advertisement_approve_/<int:ad_id>/", views.ad_approve, name="advertisement_approve"),
    path("advertisement_reject_/<int:ad_id>/", views.ad_reject, name="advertisement_reject"),
    
    #ambassador post
    path("ambassador_post_list_/", views.ambassador_post_list, name="ambassador_post_list"),
    path("ambassador_post_approve_/<int:post_id>/", views.ambassador_post_approve, name="ambassador_post_approve"),
    path("ambassador_post_reject_/<int:post_id>/", views.ambassador_post_reject, name="ambassador_post_reject"),
    
    path("admin_profile/", views.admin_profile, name="admin_profile"),
   
    path("app_update/", views.app_update, name="app_update"),
    path("create_open_play/", views.create_open_play, name="create_open_play"),
    path("add_product/", views.add_product, name="add_product"),
    path("product_list/", views.product_list, name="product_list"),
    path("view_product/<int:product_id>/", views.view_product, name="view_product"),
    path("edit_product/<int:product_id>/", views.edit_product, name="edit_product"),
    path("delete_product/<int:product_id>/", views.delete_product, name="delete_product"),
    
    path("send_universal_notification/", views.send_universal_notification, name="send_universal_notification"),
    path("payment_table/", views.payment_table, name="payment_table"),

    path("merchant_request_list/",views.merchant_request_list, name="merchant_request_list"),
    path("version_update_list/", views.version_update_list, name="version_update_list"),
    path("update_version/", views.version_update, name="update_version"),
      

    # path("charts/", views.charts, name="charts"),
    # path("widgets/", views.widgets, name="widgets"),
    # path("grid/", views.grid, name="grid"),
    # path("form-basic/", views.form_basic, name="form-basic"),
    # path("form-wizard/", views.form_wizard, name="form-wizard"),
    # path("buttons/", views.buttons, name="buttons"),
    # path("icon-material/", views.icon_material, name="icon-material"),
    # path("icon-fontawesome/", views.icon_fontawesome, name="icon-fontawesome"),
    # path("elements/", views.elements, name="elements"),
    # path("gallery/", views.gallery, name="gallery"),
    # path("invoice/", views.invoice, name="invoice"),
    # path("chat/", views.chat, name="chat"),
]
from django.urls import path
from apps.pickleitcollection import views


urlpatterns = [
    #used api urls
    path('f1918c2695c6912e1bb23e8dc82b8e2bbea40ab3915ba49f41ab1ab93abb849b/', views.advertisement_rate_list, name='advertisement_rate_list'),
    path('de87afae922fcc9bda9722f6ae4899b1e1c97d40cf544675760f28a34d56c28c/', views.advertisement_add, name='advertisement_add'),
    path('aba97dd0cccde47371ac92197491a84aa60ae487fa3e5bde82e360f8eda27879/', views.list_advertisement, name="list_advertisement"),
    path('ae35895453a924b6d8931bf5c43e1dc0b50da42e10f1875106ea289b73765741/', views.list_advertisement_for_app, name="list_advertisement_for_app"),
    path('8a568ce2ff3dcd44588b7a9d7735016863742b231f427b5c3dde9e34565c7ace/', views.view_advertisement, name="view_advertisement"),
    path('41ede13267de030694be2e2e83a1029ca38d2a56f417ed6abf0887bff2528f52/', views.edit_advertisement, name="edit_advertisement"),
    path('618c2e4f8a60dbfe19569d241f5929e9a452b201631d79ccf7d45b6dd7527e7c/', views.repromote_advertisement, name="repromote_advertisement"),
    path('43616def4c4d066e2f91814ddce5e8e8b48ed665465460afc0db53042b40b1cc/', views.delete_advertisement, name="delete_advertisement"),
    path('ae17d7f687a0e35eab20437fde4e408a26508eef44d14f454b0a597f8e6e654c/', views.advertisement_approved_by_admin, name="advertisement_approved_by_admin"),
    
    #search tags
    path('search_tags/', views.tag_search, name="search_tags"),



    # not used api urls
    path('19a18a717c4ee1807e2748cd8a374baeacbc3e4d542a4767c8720e83572e09e5/', views.screen_type_list, name="screen_type_list"),
    path('fcd47604f8505aedf9ea937eb75828995d766a3e27be9a60198585d29e4fcefe/', views.add_advertisement, name="add_advertisement"),
    path('0a17353ad39c003075afffecbfe253e381bc9c331fb1b06a0ac18a7734116f98/', views.create_advertisement, name="craete_advertisement"),
    path('9671103725bb2e332ec083861133f7c0dad8e72b039e76bcdff4a102d453b66a/<str:charge_for>/<str:my_data>/<str:checkout_session_id>/', views.payment_for_advertisement, name="payment_for_advertisement"),
    path('9b431a292d0a18597a33e64d24a9dcec284e4cbfd6fae40a5a2410e61f897808/', views.add_charge_amount, name="add_charge_amount"),
    path('1fc6d6c3cb40877310bc9b6f2686ba5bfcfa8e76363a2422161f668b18c7f29a/', views.list_charge_amount, name="list_charge_amount"),
    path('2dad6f72222cefc6737454b3b7e828a24576395bbd2aac30d8f0e059d15b9252/', views.view_charge_amount, name="view_charge_amount"),
    path('434707f123e5ed9dc8974c27fe8e87748a0c7af7cc3f5ed332d88c59188ebba0/', views.edit_charge_amount, name="view_charge_amount"),
    path('1d46a750176f3c2d4a0c31fac7e1579dbd8b102b7aaa2caecdd83bba6a8389e5/', views.allow_to_make_organizer, name="allow_to_make_organizer"),
    path('a5845a43900377965b468e181e6215b911c39d91f547b54215e4e8b3fb0c051a/', views.list_payments, name="list_payments"),
    path('c7761e58969f7edd498186641b2021e8477e1bcd230de4cf3435242da4a40d14/', views.checkout, name="checkout"),
    path('040ffd5925d40e11c67b7238a7fc9957850b8b9a46e9729fab88c24d6a98aff2/<str:charge_for>/<str:checkout_session_id>/', views.payment, name="payment"),
    path('576d775a6b0da447c7bf79a1bff13098357dbafc0a2fd82eb3e192225b833ad4/', views.show_notifications, name="show_notifications"),
    path('2b677406c367bf091bd726cdf8a7b0ea1f517fc730c864dc09c8fc1632a387bc/', views.update_notifications, name="update_notifications"),
    path('5900b44497b17085c3877cf81bf6cc1a5def1d234fdaec174e2a8afffdd1fee4/', views.allow_to_make_ambassador, name="allow_to_make_ambassador"),
    path('997a873e4701d0e77a7f5daa83acaecd86f4d6ac5cd6d20c6ddae11d6ae24fdf/', views.ambassador_list, name="ambassador_list"),
    path('7118b97e4abf7ba24f186e726078aebc56c01ebcd229d5f02678aaa1fc09ee4f/', views.ambassador_profile_view, name="ambassador_profile_view"),
    # path('eb35a300315bbc654886d89bb21464b756e0dffa924aa31f594baf26f1ae3079/', views.ambassadors_create_post, name="ambassadors_create_post"),
    path('b2ef0471e3ec9cac1a9cee8e003016fd2df0b1a03a6fca983c52057bcb2894ae/', views.allow_to_make_ambassador_to_player, name="allow_to_make_ambassador_to_player"),
    # path('6122c7562764ec30328dd65c8bc38f13d19f827465c83ae0a8ca096a3a4f6a1e/', views.ambassadors_view, name="ambassadors_view"),
    # path('11200503c744f1c654cae555821fcd629753bd1918647145aa9bf740cac01859/', views.ambassadors_edit_post, name="ambassadors_edit_post"),
    # path('6aa655d15032b879c635696440ea6be70e266dc286c52b4732017e7551bcc6ca/<del_id>', views.ambassadors_delete_post, name="ambassadors_delete_post"),
    path('349622ad9fe46f5e54ec6cb8f0c2d4d60b199b3d1b20aebba1f461793723506a/', views.admin_allow_ambassadors_post, name="admin_allow_ambassadors_post"),
    # path('d787487951b801bf71b50ebb932b8588b762a9baad80c5e7db48fa8736945e6e/', views.ambassadors_view_all_allow_post, name="ambassadors_view_all_allow_post"),
    path('a4ecb8aba7087ba80a6482c6456443f693e57021a02aca9e4bb3e5068e3857c5/', views.ambassador_follow_or_unfollow, name="ambassador_follow_unfollow"),
    path('5100320b960b20b89093b66cc9f75b971916adaaeb02c83e92b030d731c80ccc/', views.check_ambassador_following_or_not, name="check_ambassador_following_or_not"),
    path('bccd11555e01236e30cd83b102468efb1fac9a94f878ffa415cfde7a513dd269/', views.add_advertiser_facility, name='add_advertiser_facility'),
    path('014de00d30c252365c1cad4bfb9e3a324eb09d991f3dfaa67f7bdef1c1ae3f54/', views.edit_advertiser_facility, name='edit_advertiser_facility'),
    path('e4311d8adde4474b8d2ec95bf65de32147dd9be2d8ba164167b0d8da8c675748/', views.delete_advertiser_facility, name='delete_advertiser_facility'),
    path('a2b51b99225382203c162467b2ad218250e08daf49556189a6901cfd1307f3f8/', views.advertiser_facility_list, name='advertiser_facility_list'),
    path('47934d738322309c5d315ea529f56af1060b130cc30ffda0ea3969a28fe7d9ac/', views.view_advertiser_facility, name="view_advertiser_facility"),
    path('980bd155f9ebe499beb96494ab6cc4e16df6e92b6d0c7b4129bdb95c685db2bd/', views.delete_facility_image, name='delete_facility_image'),
    path('561b99502eed6266370e55a61a644a8a29964713f114f66dedda77857377a6f5/', views.advertiser_facility_list_for_all, name="advertiser_facility_list_for_all"),
    path('c1a8d430388c1f522f509af3d395ecf49070ff79b8fe1bbd78f2faf2114d5fd4/', views.ambassador_post_like_dislike, name="ambassador_post_like_dislike"),
    path('6cdf210339d0397a8fedb681659bf38b7206a863675d1c72ee99ff9d115c06f6/', views.chech_post_liked_or_not, name="chech_post_liked_or_not"),

    path('eb35a300315bbc654886d89bb21464b756e0dffa924aa31f594baf26f1ae3079/', views.create_post, name="create_post"),
    path('d787487951b801bf71b50ebb932b8588b762a9baad80c5e7db48fa8736945e6e/', views.post_list, name="post_list"),
    path('6122c7562764ec30328dd65c8bc38f13d19f827465c83ae0a8ca096a3a4f6a1e/', views.view_post, name="view_post"),
    path('dd56eddb026eb541aca298960cd8d8052cf34a833c20877cdd8d6b5f804a6f06/', views.my_post_list, name="my_post_list"),
    path('11200503c744f1c654cae555821fcd629753bd1918647145aa9bf740cac01859/', views.edit_post, name="edit_post"),
    path('6aa655d15032b879c635696440ea6be70e266dc286c52b4732017e7551bcc6ca/', views.delete_post, name="delete_post"),

    path('6aa49ba2554e3742034751b2e688b556f623ca9905f3f9a002bd072586dceace/', views.generate_video_presigned_url, name='generate_presigned_urls'),
    path('26b99028da8c679dbb5ba91583a37272c0978a9c0e942a9bc1cea6f7f8225f45/', views.generate_thumbnail_presigned_url, name='generate_thumbnail_presigned_url'),
    path('d62284d28918d2d7c3df50a0fbb4ff323e3355de878a5ffec8ee44f5127098d1/', views.create_post_new, name='create_post_new'),

    
]
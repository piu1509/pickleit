from django.urls import path

from apps.store import views

urlpatterns = [
        # Delivery Address
    path('e29ae6cf70258895fcc0d369c92368be4e65521fbeaf63f129b2cbce8699df66/', views.store_product_love_byUser, name="store_product_love_byUser"),
    path('1b90716282eaebaa0a4244e24c52bc67711de99c32e45001162c6e077a9308e6/', views.user_add_delivery_address, name="user_add_delivery_address"),
    path('d051f9831dd1b28b35a8e14d67b773a683c91e51b7ae193483ab553450d85afa/', views.user_edit_delivery_address, name="user_edit_delivery_address"),
    path('d7887b9d09956be166bd2e8aa1ac41ac2c98eb4e69f91e10170e7be152a1cdf0/', views.user_delivery_address, name="user_delivery_address"),
    path('b1d147cfe77d3d0af1fdefc98037a9070883caf1dd927c71a53e578502dd7fc9/', views.user_delivery_address_change, name="user_delivery_address_change"),

    # Merchandise Store
    path('c3ac6106fdf446f22fb9a7a40ef5f53b2b4ba932fcfa040d44d5e0118a7eb799/', views.store_category_add, name="store_category_add"),
    path('2e7a9372dface2b67fabd1b06ca5ee76abd142ce93497a79023226ce033a8f3d/', views.store_category_edit, name="store_category_edit"),
    path('c32543cf729d1ebcb8b7efe98918cc287b269676db52579abdd7b87aa3820690/', views.store_category_list, name="store_category_list"),
    path('317920220d2d47dfd06a78afef71e5e3b078f0738d8eb531cd37aa3e0b90dce0/', views.store_category_view, name="store_category_view"),
    
    path('ecf5996e26df82090bded2677435fd055b406d213919763606e1e34698f4f74e/', views.store_product_add, name="store_product_add"),
    path('094f7cc88d10be9061913e637d58a6c6cf81d125c101ec88a2646aa03b8017ea/', views.store_product_delete, name="store_product_delete"),
    path('615256f796aa2143421c3764c25acc20d478868e891f64a1af2fa01e8659fb8f/', views.store_product_edit, name="store_product_edit"),
    path('d3c3b488f32fd3c34fee5613c03da4fb5ec02daae27efb478a8f6859649cdad9/', views.store_product_list, name="store_product_list"),
    path('82708a7905621c6069cc592debc1a1eebce89f372d4a73daf79617408870bfe7/', views.my_store_product_list, name="my_store_product_list"),
    path('fbce2ffcbd4f246eb04fc0c9c4f9a6e15e206854cc05bfc6b812c354bf6a0f83/', views.store_product_view, name="store_product_view"),
    path('5457cf58bfb70977bca564f3b9a6fe5efbe71d713d73f57f10594518ff3fbfba/', views.category_wise_product_filter, name="category_wise_product_filter"),
    path('ff4001a548eff92079e17f6a6a1a10daa2f552acb1242eb9f0200313df8cdc3f/', views.search_wise_product_filter, name="search_wise_product_filter"),
    
    # Merchandise Store Payment
    path('a6ec72178c4e6c9fba52aabe8049093276cf37204057624d355afea7772be9bf/', views.buy_now_product, name="buy_now_product"),
    path('694b0ce98afc6fa28631622bc70971b3ca40d25490634a60dcd53a5ff04843f3/<str:charge_for>/<int:cart_id>/<str:checkout_session_id>/', views.buy_now_product_payment, name="buy_now_product_payment"),
    path('9307db8a741165b375126dd0e03710cf8158cfda4d10e2b23c2e17dd903bd278/', views.buy_all_cart_product, name="buy_all_cart_product"),
    path('7417d36367fa2fab97cf476a626b989b2fb842eddc47f55b50e877bd57c97a00/<str:charge_for>/<str:checkout_session_id>/', views.buy_all_cart_product_payment, name="buy_all_cart_product_payment"),
    
    # Cart section
    path('a4609a04ea5881df062f06f0d03d653606b972e9fd94eb8c00dd32641fea511d/', views.product_add_to_cart, name="product_add_to_cart"),
    path('e2134b0a04ee5fb97af0f2bd38c21f42edf027429f1dc8152c43df7c903d69cc/', views.cart_list, name="cart_list"),
    path('399c6d6d6d1a5174fb4fdbb931c06fadb40faa377e0e16f7cb83f492bee755d0/', views.cart_edit, name="cart_edit"),
    path('ad6afd93709535a40ff40f1690c505695085de1b9dbfc153caccddb31eabdb18/', views.cart_delete, name="cart_delete"),
    path('ab2fce6098b4f5e2e1609e50be8d788086de4f31752154595af4921518384cfa/', views.MyOrderActive.as_view(), name="my_order_active"),
    path('0d092a521176631ad7f54dfe07cd18a9a9d2f3c9ca3a72387bf5c419f456c094/', views.MyOrderCompleted.as_view(), name="my_order_completed"),
    # Store
    path('be80c96ee1ee2b5740b16ab2bd83df9807ba36563996ebaec4f391e291b6beb4/', views.check_store_product_liked_or_not, name="check_store_product_liked_or_not"),
    path('44fa83b26ca103757133c3c51e16837d34a072592ab65ad249b0dfc39ad2ccdb/', views.wishlisted_products, name="wishlisted_products"),
    path('0aa6998dfe603cf9723b393ee94cd2d902b13b5f8f402d0aa655da96fd350b6d/', views.filtered_product_list, name="filtered_product_list"),
    path('12bf1648707891bf113ac4ffd866cc86c451b66b15b45ab6f7ace0918750964f/', views.category_details, name="category_details"),
    path('c894d0e5f50e543aaf26d64eb91ffbccd867a19d29a3b188d14f38ef79e2c1f2/', views.rate_product, name="rate_product"),

    path('4d17b6fcf4965d4f264eecec9102f78f5481039e296e3659397626f9395d9d0f/', views.cart_list_new, name='cart_list_new'),
    path('e5acb69c91826a0d40c4978ad41435ba89dbc18c00a4fa7853e8d4a56daa2546/', views.sorted_product_list, name="sorted_product_list"),
    path('30ec4397af849b63d7bee6b91b5f5fbd1814d2683c4547f54650de78766f0310/', views.store_product_edit_new, name="store_product_edit_new"),
    path('baa906dc5d9037e2ec4dfab69ac05d20c21f9aeef182e738018b74438fa7f808/', views.top_discount_products, name="top_discount_products"),
    path('a7bbbfd6a3d114eaa54da65db2034f637a18cb8dd7a2afeea14e60378a208e1b/', views.top_rated_products, name="top_rated_products"),
    path('ff29075325860ec97d0d436fdc9e88f54392759453980d9983a5aea8d8a965dc/', views.most_searched_products, name="most_searched_products"),
    path('840f06c0f81edcfc56e3c78e043d5235a2f11cb45f2ec3facfa4570f946ba729/', views.top_discount_product_ad_images, name='top_discount_product_ad_images'),
    
]

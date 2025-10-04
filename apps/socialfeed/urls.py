from django.urls import path
from . import views

urlpatterns = [
    path('post_social_feed/', views.post_social_feed, name='post_social_feed'),
    path('my_social_feed/', views.my_social_feed, name='post_social_feed'),
    path('edit_social_feed/', views.edit_social_feed, name='edit_social_feed'),
    path('delete_social_feed/', views.delete_social_feed, name='delete_social_feed'),
    path('social-feed/', views.social_feed_list, name='social-feed-list'),
    path('social-feed/<int:pk>/', views.social_feed_detail, name='social-feed-detail'),
    path('social-feed/<int:pk>/comments/', views.comment_list, name='comment-list'),
    path('social-feed/<int:pk>/likes/', views.like_user_list, name='like-user-list'),
    path('social-feed/comments/', views.post_comment, name='post-comment'),
    path('social-feed/likes/', views.post_like, name='post-like'),
    path('social-feed/report_feed/', views.report_post, name='report_post'),
]
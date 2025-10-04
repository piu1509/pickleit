from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
import random
from math import radians, sin, cos, sqrt, atan2
from apps.socialfeed.models import *
from apps.socialfeed.serializers import *
from apps.user.models import User
###social feed

class SocialFeedPagination(PageNumberPagination):
    page_size = 5  # Default items per page
    page_size_query_param = 'per_page'  # Allow clients to set page size via query param
    max_page_size = 100  # Maximum items per page

    def get_paginated_response(self, data):
        # Get next and previous links
        next_link = self.get_next_link()
        previous_link = self.get_previous_link()
        
        # Force HTTPS in links if they exist
        if next_link:
            next_link = next_link.replace('http://', 'https://')
        if previous_link:
            previous_link = previous_link.replace('http://', 'https://')
        
        return Response({
            'count': self.page.paginator.count,
            'next': next_link,
            'previous': previous_link,
            'results': data
        })

@api_view(['GET'])
def social_feed_list(request):
    user_uuid = request.GET.get("user_uuid", None)
    feeds = socialFeed.objects.filter(block=False).order_by('-created_at')
    serializer = SocialFeedSerializer(feeds, many=True, context={'user_uuid': user_uuid})
    data = serializer.data
    paginator = SocialFeedPagination()
    paginated_data = paginator.paginate_queryset(data, request)
    return paginator.get_paginated_response(paginated_data)

@api_view(['POST'])
def edit_social_feed(request):
    try:
        data = request.POST
        user= get_object_or_404(User, uuid=data.get("user_uuid"))
        feed = get_object_or_404(socialFeed, id=data.get("feed_id"))
        if feed.user != user:
            return Response(
                {
                "msg":"Unauthorized access", 
                "status": status.HTTP_400_BAD_REQUEST
                }
                )
        feed.text = data.get("text", feed.text)
        removing_files = data.getlist("removing_files", [])
        if removing_files:
            for file_id in removing_files:
                try:
                    file_to_remove = FeedFile.objects.get(id=file_id, post=feed)
                    file_to_remove.delete()
                except FeedFile.DoesNotExist:
                    return Response(
                        {
                        "msg":"File not found", 
                        "status": status.HTTP_404_NOT_FOUND
                        }
                        )
        post_files = request.FILES.getlist("post_files")
        if post_files:
            for post_file in post_files:
                save_file = FeedFile(post=feed, file=post_file)
                save_file.save()
        feed.save()

        return Response(
                        {
                        "msg":"Successfully update your feed!", 
                        "status": status.HTTP_201_CREATED
                        }
                        )
    except Exception as e:
        return Response(
                        {
                        "msg":str(e), 
                        "status": status.HTTP_400_BAD_REQUEST
                        })




@api_view(['GET'])
def my_social_feed(request):
    user_uuid = request.GET.get("user_uuid", None)
    user = get_object_or_404(User, uuid=user_uuid)
    feeds = socialFeed.objects.filter(user=user).order_by('-created_at')
    serializer = SocialFeedSerializer(feeds, many=True, context={'user_uuid': user_uuid})
    data = serializer.data
    # random.shuffle(data)
    paginator = SocialFeedPagination()
    paginated_data = paginator.paginate_queryset(data, request)
    return paginator.get_paginated_response(paginated_data)
   

@api_view(['POST'])
def delete_social_feed(request):
    try:
        data = request.POST
        user_uuid = data.get("user_uuid")
        feed_id = data.get("feed_id")
        user = get_object_or_404(User, uuid=user_uuid)
        feed = socialFeed.objects.get(id=feed_id)
        if feed.user != user:
            return Response({"error": "You are not authorized to edit this feed."}, status=status.HTTP_403_FORBIDDEN)
        feed.delete()
        return Response({"success": "Feed deleted successfully."}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
def social_feed_detail(request, pk):
    feed = get_object_or_404(socialFeed, pk=pk)
    serializer = socialFeedDetailsSerializer(feed)
    return Response(serializer.data)

@api_view(['POST'])
def post_social_feed(request):
    try:
        data = request.POST
        user_uuid = data.get("user_uuid")
        user = User.objects.filter(uuid=user_uuid)
        if not user.exists():
            return Response(
                {
                "msg":"Unauthorized access", 
                "status": status.HTTP_400_BAD_REQUEST
                }
                )
        
        get_user = user.first()
        text = data.get("text")
        post_files = request.FILES.getlist("post_files")

        feed = socialFeed(text=text, user=get_user)
        feed.save()

        for post_file in post_files:
            save_file = FeedFile(post=feed, file=post_file)
            save_file.save()
        from apps.chat.views import notify_all_users
        titel = "New Post"
        message = "New post added by " + str(get_user.first_name) + " " + str(get_user.last_name)
        if titel and message:
            notify_all_users(titel, message)
        return Response(
                        {
                        "msg":"Successfully posted your feed!", 
                        "status": status.HTTP_201_CREATED
                        }
                        )
    except Exception as e:
        return Response(
                        {
                        "msg":str(e), 
                        "status": status.HTTP_400_BAD_REQUEST
                        })


@api_view(['POST'])
def post_comment(request):
    user_uuid = request.data.get("user_uuid")
    post_id = request.data.get("post_id")
    text = request.data.get("text")
    parent_comment_id = request.data.get("parent_comment_id", None)

    # Fetch user by UUID
    user = User.objects.filter(uuid=user_uuid).first()
    if not user:
        return Response({"msg": "Unauthorized access", "status": status.HTTP_400_BAD_REQUEST})

    # Fetch post by ID
    post = socialFeed.objects.filter(id=post_id).first()
    if not post:
        return Response({"msg": "This is not a valid post", "status": status.HTTP_400_BAD_REQUEST})

    # Create a new comment
    save_comment = CommentFeed(user=user, post=post, comment_text=text)

    # If there is a parent comment ID, set it
    if parent_comment_id not in [None, "None"]:
        try:
            parent_comment = CommentFeed.objects.get(id=parent_comment_id)
            save_comment.parent_comment = parent_comment
        except CommentFeed.DoesNotExist:
            return Response({"msg": "Parent comment not found", "status": status.HTTP_400_BAD_REQUEST})

    save_comment.save()

    return Response({"msg": "Post your comment", "status": status.HTTP_200_OK})

@api_view(['POST'])
def post_like(request):
    try:
        user_uuid = request.data.get("user_uuid")
        post_id = request.data.get("post_id")

        # Validate user
        user = User.objects.filter(uuid=user_uuid).first()
        if not user:
            return Response({"msg": "Unauthorized access", "status": status.HTTP_400_BAD_REQUEST})

        # Validate post
        post = socialFeed.objects.filter(id=post_id).first()
        if not post:
            return Response({"msg": "This is not a valid post", "status": status.HTTP_400_BAD_REQUEST})

        # Check if the user has already liked the post
        existing_like = LikeFeed.objects.filter(post=post, user=user).first()
        if existing_like:
            # If like exists, remove it (dislike)
            existing_like.delete()
            total_likes = LikeFeed.objects.filter(post=post).count()
            return Response({"msg": "Unlike", "total_like": total_likes, "status": status.HTTP_200_OK})
        else:
            # If like does not exist, create it
            LikeFeed.objects.create(post=post, user=user)
            total_likes = LikeFeed.objects.filter(post=post).count()
            return Response({"msg": "Like", "total_like": total_likes, "status": status.HTTP_200_OK})
    except Exception as e:
        return Response({"msg": str(e), "status": status.HTTP_400_BAD_REQUEST})


@api_view(['GET'])
def like_user_list(request, pk):
    post = get_object_or_404(socialFeed, pk=pk)
    likes = LikeFeed.objects.filter(post=post)
    serializer = LikeFeedSerializer(likes, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def comment_list(request, pk):
    post = get_object_or_404(socialFeed, pk=pk)
    comments = CommentFeed.objects.filter(post=post)
    serializer = CommentFeedSerializer(comments, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def report_post(request):
    try:
        user_uuid = request.data.get("user_uuid")
        post_id = request.data.get("post_id")

        user = User.objects.filter(uuid=user_uuid).first()
        if not user:
            return Response({"msg": "Unauthorized access", "status": status.HTTP_400_BAD_REQUEST})

        post = socialFeed.objects.filter(id=post_id).first()
        if not post:
            return Response({"msg": "This is not a valid post", "status": status.HTTP_400_BAD_REQUEST})

        existing_report = FeedReport.objects.filter(feed=post, user=user).first()
        if existing_report:
            return Response({"msg": "Already reported", "status": status.HTTP_200_OK})
        else:
            FeedReport.objects.create(feed=post, user=user)  # Fixed missing object creation
            return Response({"msg": "Successfully reported the post to admin", "status": status.HTTP_200_OK})
    except Exception as e:
        return Response({"msg": str(e), "status": status.HTTP_400_BAD_REQUEST})
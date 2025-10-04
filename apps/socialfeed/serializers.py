from rest_framework import serializers
from .models import *
from apps.user.models import User

class UserSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["username", "image"]

    def get_username(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

class FeedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedFile
        fields = ['id', 'file']

class CommentFeedSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = CommentFeed
        fields = ['id', 'post', 'user', 'comment_text', 'parent_comment', 'created_at']

class LikeFeedSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = LikeFeed
        fields = ['id', 'post', 'user', 'created_at']

class SocialFeedSerializer(serializers.ModelSerializer):
    post_file = FeedFileSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)  # Nested user serializer
    is_liked = serializers.SerializerMethodField()  # Field to check if the user liked the post

    class Meta:
        model = socialFeed
        fields = ['id', 'user', 'text', 'number_comment', 'number_like', 'created_at', 'post_file', 'is_liked']

    def get_is_liked(self, obj):
        """Check if the user with given user_uuid has liked the post"""
        user_uuid = self.context.get('user_uuid')
        
        if user_uuid:
            user = User.objects.filter(uuid=user_uuid).first()
            if user:
                like = LikeFeed.objects.filter(post=obj, user=user)
                return like.exists()
        return False


class MysocialFeedSerializer(serializers.ModelSerializer):
    post_file = FeedFileSerializer(many=True, read_only=True)

    class Meta:
        model = socialFeed
        fields = ["id", "user", "text", "block", "block_by", "about_block", "number_comment", "number_like", "created_at", "post_file"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.block:  # If block is False
            data["block_by"] = None
            data["about_block"] = None
        return data

class socialFeedDetailsSerializer(serializers.ModelSerializer):
    post_file = FeedFileSerializer(many=True, read_only=True)
    comments = CommentFeedSerializer(many=True, read_only=True, source="post_comment")
    likes = LikeFeedSerializer(many=True, read_only=True, source="post_like")

    class Meta:
        model = socialFeed
        fields = [
            'id',
            'user',
            'text',
            'number_comment',
            'number_like',
            'created_at',
            'post_file',
            'comments',
            'likes',
        ]

from django.db import models
from apps.user.models import User

class socialFeed(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_user")
    text = models.TextField()
    block = models.BooleanField(default=False)
    block_by = models.CharField(max_length=5, default="Admin")
    about_block = models.TextField(null=True, blank=True)
    number_comment = models.IntegerField(default=0)
    number_like = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Ensure to call the parent class save method
        super().save(*args, **kwargs)

    def update_comment_count(self):
        self.number_comment = self.post_comment.count()
        self.save(update_fields=['number_comment'])

    def update_like_count(self):
        """Update the like count based on actual like entries."""
        self.number_like = self.post_like.count()
        self.save(update_fields=['number_like'])

class FeedFile(models.Model):
    post = models.ForeignKey(socialFeed, on_delete=models.CASCADE, related_name="post_file")
    file = models.FileField(upload_to="social_feed/", blank=True, null=True)

class CommentFeed(models.Model):
    post = models.ForeignKey(socialFeed, on_delete=models.CASCADE, related_name="post_comment")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comment_user")
    comment_text = models.TextField()
    parent_comment = models.ForeignKey("CommentFeed", on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Increase like count when a like is added."""
        super().save(*args, **kwargs)
        self.post.update_comment_count()

    def delete(self, *args, **kwargs):
        """Decrease like count when a like is removed."""
        super().delete(*args, **kwargs)
        self.post.update_comment_count()

class LikeFeed(models.Model):
    post = models.ForeignKey(socialFeed, on_delete=models.CASCADE, related_name="post_like")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="like_user")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Increase like count when a like is added."""
        super().save(*args, **kwargs)
        self.post.update_like_count()

    def delete(self, *args, **kwargs):
        """Decrease like count when a like is removed."""
        super().delete(*args, **kwargs)
        self.post.update_like_count()

class FeedReport(models.Model):
    feed = models.ForeignKey(socialFeed, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.feed} {self.user.username}"


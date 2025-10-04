from django.contrib import admin
from .models import socialFeed, FeedFile, CommentFeed, LikeFeed, FeedReport

class FeedFileInline(admin.TabularInline):
    model = FeedFile
    extra = 1  # Allows adding files directly from the post admin

class CommentFeedInline(admin.TabularInline):
    model = CommentFeed
    extra = 1  # Allows adding comments directly from the post admin
    fields = ("user", "comment_text", "created_at")
    readonly_fields = ("created_at",)

class LikeFeedInline(admin.TabularInline):
    model = LikeFeed
    extra = 0  # Shows only existing likes
    fields = ("user", "created_at")
    readonly_fields = ("created_at",)

@admin.register(socialFeed)
class socialFeedAdmin(admin.ModelAdmin):
    list_display = ("user", "text", "number_comment", "number_like", "created_at")
    search_fields = ("user__username", "text")
    readonly_fields = ("number_comment", "number_like", "created_at")
    inlines = [FeedFileInline, CommentFeedInline, LikeFeedInline]

@admin.register(CommentFeed)
class CommentFeedAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "comment_text", "created_at")
    search_fields = ("user__username", "post__text", "comment_text")
    readonly_fields = ("created_at",)
    list_filter = ("created_at",)

@admin.register(LikeFeed)
class LikeFeedAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")
    search_fields = ("user__username", "post__text")
    readonly_fields = ("created_at",)
    list_filter = ("created_at",)

@admin.register(FeedFile)
class FeedFileAdmin(admin.ModelAdmin):
    list_display = ("post", "file")
    search_fields = ("post__text",)


admin.site.register(FeedReport)
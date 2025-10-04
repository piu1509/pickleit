"""
URL configuration for pickleball project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from apps.user.views import account_deletion_request
from apps.team import views
from apps.socialfeed.models import socialFeed, FeedFile
from django.shortcuts import render
from apps.user.views import event_matches_table
from apps.user.models import User
from datetime import datetime
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db.models import Prefetch


def account_deletion_requestweb(request):
    context = {"message": None}
    try:
        if request.method == "POST":
        
            email = request.POST.get('email')
            reason = request.POST.get('reason', None)  # Get reason for deletion
            user_ins = User.objects.filter(email=email)
            
            if not user_ins.exists():
                context["message"] = "not find user"
                return render(request, 'email/deletion_request.html', context)
            user = user_ins.first()
            # Prepare email content
            context = {
                "full_name": f"{user.first_name} {user.last_name}",
                "user_email": email,
                "reason": reason,
                "date_now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Render HTML email
            html_content = render_to_string('email/delete_request.html', context)
            text_content = strip_tags(html_content)  # Plain text version

            # Send email
            subject = "Request for Account Deletion"
            from_email = email  # The user's email address
            # recipient_list = ["joinpickleit@gmail.com"]  # Admin email
            recipient_list = ["joinpickleit@gmail.com"]

            email_message = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
            email_message.attach_alternative(html_content, "text/html")
            email_message.send()

            return render(request, 'email/deletion_request.html', context)
        else:
            return render(request, 'email/deletion_request.html', context)
    except Exception as e:
        context["message"] = str(e)
        return render(request, 'email/deletion_request.html', context)

def index(req):
    posts = socialFeed.objects.filter(block=False).order_by('-created_at').only(
        'id', 'user_id', 'text', 'created_at', 'number_comment', 'number_like'
    ).prefetch_related(
        Prefetch(
            'post_file',
            queryset=FeedFile.objects.order_by('id')[:1],  # Get only the first file per post
            to_attr='first_file'
        )
    )[:4]
    return render(req, "index/index.html", {"posts":posts})

def privacy_policy(req):
    return render(req, "index/privacy-policy.html")

def terms_conditions(req):
    return render(req, "index/terms-conditions.html")

urlpatterns = [
    path('', index, name="index"),
    path('privacy_policy/', privacy_policy, name="privacy_policy"),
    path('terms_conditions/', terms_conditions, name="terms_conditions"),
    path('pickleit-admin-main/', admin.site.urls),
    path('user/', include('apps.user.urls')),
    path('team/', include('apps.team.urls')),
    path('accessories/', include('apps.pickleitcollection.urls')),
    path('chat/', include('apps.chat.urls')),
    path('admin/', include('apps.admin_side.urls')),
    path('accessories/', include('apps.store.urls')),
    path('court/', include('apps.courts.urls')),
    path('socialfeed/', include('apps.socialfeed.urls')),
    path('clubs/', include('apps.clubs.urls')),
    path('user_side/', include('apps.user_side.urls')),
    path('requestdeletion1/', account_deletion_request, name="account_deletion_request"),
    path('requestdeletion/', account_deletion_requestweb, name="account_deletion_requestweb"),
    path('events/matches/table/', event_matches_table, name="event_matches_table"),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
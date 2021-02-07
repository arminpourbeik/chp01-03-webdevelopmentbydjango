from django.urls import path

from . import views
from .feeds import LatestPostsFeed

app_name = 'blog'

urlpatterns = [
    path('', views.PostListView.as_view(), name='post-list'),
    path('tag/<slug:tag_slug>/', views.PostListViewByTag.as_view(), name='post-list-by-tag'),
    path('<int:pk>/', views.PostDetail.as_view(), name='post-detail', ),
    path('<int:post_id>/share/', views.PostShare.as_view(), name='post-share'),
    path('search/', views.PostSearch.as_view(), name='post-search'),
    path('feed/', LatestPostsFeed(), name='posts-feed')
]

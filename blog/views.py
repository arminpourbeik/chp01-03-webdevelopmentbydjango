from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormView
from django.urls import reverse
from django.db.models import Count
from django.core.mail import send_mail

from taggit.models import Tag

from .models import Post
from .forms import CommentForm, EmailPostForm, SearchForm


class PostListView(ListView):
    queryset = Post.published.all()
    template_name = 'blog/post/post-list.html'
    paginate_by = 2


class PostListViewByTag(SingleObjectMixin, PostListView):
    template_name = 'blog/post/post-list.html'
    paginate_by = 2
    slug_url_kwarg = 'tag_slug'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object(queryset=Tag.objects.all())
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return Post.published.filter(tags__in=[self.object])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tag'] = self.object
        return context


class PostListView(ListView):
    queryset = Post.published.all()
    context_object_name = 'posts'
    template_name = 'blog/post/post-list.html'
    paginate_by = 2


class PostDisplay(DetailView):
    model = Post
    template_name = 'blog/post/post-detail.html'

    def get_similar_posts(self):
        post_tags_id = self.object.tags.values_list('id', flat=True)
        similar_posts = self.model.published.filter(
            tags__in=post_tags_id
        ).exclude(id=self.object.id)
        similar_posts = similar_posts.annotate(same_tags=Count('tags')).order_by('-same_tags', '-publish')[:4]
        return similar_posts

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CommentForm()
        context['similar_posts'] = self.get_similar_posts()
        context['comments'] = self.object.comments.filter(active=True)
        return context


class PostComment(SingleObjectMixin, FormView):
    template_name = 'blog/post/post-detail.html'
    form_class = CommentForm
    model = Post

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        new_comment = form.save(commit=False)
        new_comment.post = self.object
        new_comment.save()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:post-detail', args=[self.object.pk])


class PostDetail(View):
    def get(self, request, *args, **kwargs):
        view = PostDisplay.as_view()
        return view(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        view = PostComment.as_view()
        return view(request, *args, **kwargs)


class PostShare(SingleObjectMixin, FormView):
    form_class = EmailPostForm
    model = Post
    template_name = 'blog/post/post_share.html'

    def get_success_url(self):
        return reverse('blog:post-share', kwargs={'post_id': self.get_object().id})

    def get_object(self, queryset=None):
        self.object = Post.published.get(pk=self.kwargs.get('post_id'), status='published')
        return self.object

    @staticmethod
    def send_email(subject, message, recipient, from_email='admin_blog'):
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient]
        )

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        cd = form.cleaned_data
        post_url = self.request.build_absolute_uri(self.get_object().get_absolute_url())
        subject = f"{cd['name']} recommends you read {self.object.title}"
        message = f"Read {self.object.title} at {post_url} \n \n {cd['name']}'s comments: {cd['comments']}"
        self.send_email(subject=subject, message=message, recipient=cd['to'])
        return self.render_to_response(
            self.get_context_data(sent=True)
        )

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        context = super().get_context_data(**kwargs)
        return context


class PostSearch(FormView):
    form_class = SearchForm
    template_name = 'blog/post/post-search.html'
    query = None

    def get(self, request, *args, **kwargs):
        if 'query' in request.GET:
            self.query = request.GET.get('query')
            form_cls = self.get_form_class()
            form = form_cls(data=request.GET)
            if form.is_valid():
                return self.form_valid(form=form)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        query = form.cleaned_data["query"]
        search_vector = SearchVector("title", weight="A") + SearchVector(
            "body", weight="B"
        )
        search_query = SearchQuery(query)
        results = (
            Post.published.annotate(
                rank=SearchRank(search_vector, search_query))
                .filter(rank__gte=0.3)
                .order_by("-rank")
        )
        return self.render_to_response(
            self.get_context_data(results=results, query=self.query)
        )

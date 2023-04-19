import tempfile

from faker import Faker

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.conf import settings

from ..models import Group, Post, Comment

fake = Faker()
User = get_user_model()
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostCreateFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = Group.objects.create(
            title=fake.text(),
            slug='test_slug',
            description=fake.text()
        )
        cls.test_user = User.objects.create_user(username='test_user')
        cls.user2 = User.objects.create_user(username='ArtemXXXL')

        cls.post = Post.objects.create(
            text=fake.text(),
            author=cls.test_user,
            group=cls.group,
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.test_user)

    def test_post(self):
        """Тестирование создания Post"""
        post_count = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        form_data = {
            'text': fake.text(),
            'group': self.group.id,
            'image': uploaded,
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        new_post = Post.objects.first()
        self.assertRedirects(response, reverse(
            'posts:profile', args=(new_post.author,)))
        self.assertEqual(Post.objects.count(), post_count + 1)
        self.assertTrue(
            Post.objects.filter(
                text=new_post.text,
                image=new_post.image
            ).exists
        )
        self.assertEqual(form_data['text'], new_post.text)
        self.assertEqual(self.test_user, new_post.author)
        self.assertEqual(self.group, new_post.group)

    def test_not_create_post_no_authorized_client(self):
        """Неавторизованный клиент, не может создать
        пост и переадресовывается на страницу логина"""
        form_data = {
            'text': fake.text(),
            'group': self.group.id,
        }
        post_count = Post.objects.count()
        response = self.client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        login_url = reverse('users:login')
        create_url = reverse('posts:post_create')
        self.assertRedirects(response, f'{login_url}?next={create_url}')
        self.assertEqual(post_count, Post.objects.count())

    def test_post_edit_by_non_author(self):
        '''Редактирование поста не автором, редирект на текст поста'''
        self.authorized_client.logout()
        new_user = get_user_model().objects.create_user(
            username='new_user',
            email='new_user@mail.com',
            password='12345',
        )
        self.authorized_client.force_login(new_user)
        post_edit_url = reverse('posts:post_edit', args=[self.post.id])
        response = self.authorized_client.get(post_edit_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response,
                             reverse('posts:post_detail',
                                     kwargs={'post_id': self.post.id}))

    def test_post_edit_by_author(self):
        '''Редактирование поста автором'''
        edit_url = reverse('posts:post_edit', kwargs={'post_id': self.post.id})
        new_text = 'New Test Post'
        response = self.authorized_client.post(edit_url,
                                               {'text': new_text,
                                                'group': self.group.id})
        self.assertRedirects(response,
                             reverse('posts:post_detail',
                                     kwargs={'post_id': self.post.id}))
        self.post.refresh_from_db()
        self.assertEqual(self.post.text, new_text)


class CommentsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='auth',
            email='test@test.ru',
            password='test',
        )
        cls.group = Group.objects.create(
            title=fake.text(),
            slug='first-slug',
            description=fake.text(),
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text=fake.text(),
            group=cls.group,
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(CommentsTests.user)

    def test_add_comments(self):
        """Тест добавления Comments если форма Валидная."""
        comments_count = Comment.objects.count()
        form_data = {
            'text': fake.text(),
        }
        response = self.authorized_client.post(
            reverse('posts:add_comment', args=(self.post.id,)),
            data=form_data,
            follow=True
        )
        comment = Comment.objects.latest('created')
        self.assertEqual(Comment.objects.count(), comments_count + 1)
        self.assertRedirects(response, reverse(
            'posts:post_detail',
            args=(self.post.id,)))
        self.assertEqual(form_data['text'], comment.text)
        self.assertEqual(self.user, comment.author)
        self.assertEqual(self.post, comment.post)

    def test_add_comment_by_not_authorized_client(self):
        """Неавторизованный клиент не может создать
        комментарий и перенаправляется на страницу авторизации."""
        comments_count = Comment.objects.count()
        comment_data = {
            'text': fake.text(),
        }
        response = self.client.post(
            reverse('posts:add_comment', args=(self.post.id,)),
            data=comment_data, follow=True
        )
        redirect_address = reverse(
            'users:login') + '?next=' + reverse(
            'posts:add_comment', args=(self.post.id,))
        self.assertRedirects(response, redirect_address)
        self.assertEqual(Comment.objects.count(), comments_count)

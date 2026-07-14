import json
from decimal import Decimal
from io import StringIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation

from .admin import ProductAdmin
from .models import Category, Product, ProductMedia, ProductRating, Review


class ProductRatingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='Phones', slug='rating-phones')
        cls.product = Product.objects.create(category=category, name='Rating Phone', slug='rating-phone', sku='RATING-1', description='Test', price=Decimal('999.00'))
        cls.product.status = 'active'
        cls.product.is_active = cls.product.is_published = True
        cls.product.save()
        ProductMedia.objects.create(product=cls.product, image_file='product_uploads/rating.webp', source_url='https://example.com/rating', licence_note='Test', image_sha256='a' * 64, is_verified=True, is_primary=True)
        cls.user = get_user_model().objects.create_user(username='rater', password='test-password')
        cls.other_user = get_user_model().objects.create_user(username='other-rater', password='test-password')

    def setUp(self):
        self.rating_url = reverse('rate_product', kwargs={'slug': self.product.slug})

    def ajax_post(self, data, client=None):
        return (client or self.client).post(self.rating_url, data, HTTP_ACCEPT='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_create_rating_updates_accurate_summary(self):
        self.client.force_login(self.user)
        response = self.ajax_post({'rating': '5'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(response.json()['user_rating'], 5)
        self.assertEqual(response.json()['average'], 5.0)
        self.assertEqual(response.json()['count'], 1)
        self.assertTrue(response.json()['message'])
        self.assertEqual(ProductRating.objects.get().rating, 5)
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_average, Decimal('5.0'))
        self.assertEqual(self.product.rating_count, 1)
        self.assertEqual(self.product.review_count, 0)

    def test_browser_json_transport_and_no_javascript_form_fallback(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.rating_url,
            data=json.dumps({'rating': '5'}),
            content_type='application/json',
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user_rating'], 5)

        fallback = self.client.post(self.rating_url, {'rating': '4'})
        self.assertEqual(fallback.status_code, 302)
        self.assertEqual(ProductRating.objects.get().rating, 4)

        script = (Path(__file__).resolve().parents[1] / 'static' / 'store.js').read_text(encoding='utf-8')
        self.assertIn('const selectedRating = ratingForm.querySelector', script)
        self.assertIn('JSON.stringify({ rating: selectedRating.value })', script)
        self.assertIn('Content-Type', script)
        self.assertNotIn('new FormData(ratingForm)', script)

    def test_repeat_vote_updates_without_duplicate(self):
        self.client.force_login(self.user)
        self.ajax_post({'rating': '2'})
        response = self.ajax_post({'rating': '4'})
        self.assertEqual(ProductRating.objects.count(), 1)
        self.assertEqual(ProductRating.objects.get().rating, 4)
        self.assertEqual(response.json()['average'], 4.0)

    def test_average_counts_each_user_once(self):
        self.client.force_login(self.user)
        self.ajax_post({'rating': '5'})
        other = Client()
        other.force_login(self.other_user)
        response = self.ajax_post({'rating': '3'}, other)
        self.assertEqual(response.json()['average'], 4.0)
        self.assertEqual(response.json()['count'], 2)

    def test_invalid_values_are_rejected_server_side(self):
        self.client.force_login(self.user)
        for payload in ({}, {'rating': 'x'}, {'rating': '0'}, {'rating': '6'}):
            with self.subTest(payload=payload):
                self.assertEqual(self.ajax_post(payload).status_code, 400)
        self.assertFalse(ProductRating.objects.exists())

    def test_guest_ajax_gets_401_and_html_redirects(self):
        ajax = self.ajax_post({'rating': '5'})
        html = self.client.post(self.rating_url, {'rating': '5'})
        self.assertEqual(ajax.status_code, 401)
        self.assertIn(reverse('login'), ajax.json()['login_url'])
        login_next = parse_qs(urlparse(ajax.json()['login_url']).query)['next'][0]
        self.assertEqual(login_next, reverse('product', kwargs={'slug': self.product.slug}))
        self.assertEqual(html.status_code, 302)
        html_next = parse_qs(urlparse(html.url).query)['next'][0]
        self.assertEqual(html_next, reverse('product', kwargs={'slug': self.product.slug}))

    def test_post_only_and_csrf_protected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.rating_url).status_code, 405)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.user)
        response = secure.post(self.rating_url, {'rating': '5'}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 403)

    def test_database_constraints_enforce_range_and_uniqueness(self):
        ProductRating.objects.create(product=self.product, user=self.user, rating=3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductRating.objects.create(product=self.product, user=self.user, rating=4)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductRating.objects.create(product=self.product, user=self.other_user, rating=6)

    def test_page_has_accessible_radios_and_no_fake_empty_rating(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('product', kwargs={'slug': self.product.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-product-rating')
        self.assertContains(response, 'name=' + chr(39) + 'rating' + chr(39), count=5)
        self.assertContains(response, 'data-rating-average>—</strong>')
        self.assertContains(response, 'data-rating-count>0</span>')
        self.assertNotContains(response, 'aggregateRating')

    def test_vote_is_checked_and_copy_is_localized(self):
        ProductRating.objects.create(product=self.product, user=self.user, rating=4)
        self.client.force_login(self.user)
        expected = {'en': 'Rate this product', 'ka': 'შეაფასე პროდუქტი', 'ru': 'Оцените товар'}
        for language, phrase in expected.items():
            with self.subTest(language=language), translation.override(language):
                response = self.client.get(reverse('product', kwargs={'slug': self.product.slug}))
                self.assertContains(response, phrase)
                self.assertContains(response, 'value=' + chr(39) + '4' + chr(39) + ' required checked')

    def test_non_object_oversize_and_wrong_content_json_are_rejected(self):
        self.client.force_login(self.user)
        invalid_json = self.client.post(
            self.rating_url, data=json.dumps([5]), content_type='application/json',
            HTTP_ACCEPT='application/json',
        )
        oversized = self.client.post(
            self.rating_url,
            data=json.dumps({'rating': 5, 'padding': 'x' * 5000}),
            content_type='application/json', HTTP_ACCEPT='application/json',
        )
        wrong_content = self.client.post(
            self.rating_url, data=json.dumps({'rating': 5}), content_type='text/plain',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(invalid_json.status_code, 400)
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(wrong_content.status_code, 415)
        self.assertFalse(ProductRating.objects.exists())

    def test_review_and_star_vote_stay_synchronized_with_separate_counts(self):
        review = Review.objects.create(
            product=self.product, user=self.user, rating=2,
            body='Detailed review', is_approved=False,
        )
        vote = ProductRating.objects.get(product=self.product, user=self.user)
        self.product.refresh_from_db()
        self.assertEqual(vote.rating, 2)
        self.assertEqual(self.product.rating_count, 1)
        self.assertEqual(self.product.review_count, 0)

        review.rating = 4
        review.is_approved = True
        review.save()
        vote.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(vote.rating, 4)
        self.assertEqual(self.product.rating, Decimal('4.0'))
        self.assertEqual(self.product.rating_count, 1)
        self.assertEqual(self.product.review_count, 1)

        vote.rating = 5
        vote.save()
        review.refresh_from_db()
        self.assertEqual(review.rating, 5)

        review.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_count, 1)
        self.assertEqual(self.product.review_count, 0)

    def test_direct_rating_update_delete_and_user_cascade_recompute_cache(self):
        vote = ProductRating.objects.create(product=self.product, user=self.user, rating=2)
        self.product.refresh_from_db()
        self.assertEqual((self.product.rating, self.product.rating_count), (Decimal('2.0'), 1))
        vote.rating = 5
        vote.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating, Decimal('5.0'))
        vote.delete()
        self.product.refresh_from_db()
        self.assertEqual(
            (self.product.rating, self.product.rating_average, self.product.rating_count),
            (Decimal('0.0'), Decimal('0.0'), 0),
        )
        ProductRating.objects.create(product=self.product, user=self.other_user, rating=3)
        self.other_user.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_count, 0)

    def test_review_form_submission_updates_authoritative_star_vote(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('add_review', kwargs={'slug': self.product.slug}),
            {'rating': '3', 'title': 'Good', 'body': 'A useful review.'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductRating.objects.get(product=self.product, user=self.user).rating, 3)
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_count, 1)
        self.assertEqual(self.product.review_count, 0)

    def test_repair_command_restores_all_rating_and_review_caches(self):
        ProductRating.objects.create(product=self.product, user=self.user, rating=5)
        Review.objects.create(
            product=self.product, user=self.other_user, rating=3,
            body='Approved', is_approved=True,
        )
        Product.objects.filter(pk=self.product.pk).update(
            rating=1, rating_average=1, rating_count=99, review_count=99,
        )
        output = StringIO()
        call_command('repair_product_ratings', stdout=output)
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating, Decimal('4.0'))
        self.assertEqual(self.product.rating_average, Decimal('4.0'))
        self.assertEqual(self.product.rating_count, 2)
        self.assertEqual(self.product.review_count, 1)
        self.assertIn('2 ratings', output.getvalue())

    def test_admin_cache_fields_are_read_only(self):
        readonly = ProductAdmin(Product, admin.site).get_readonly_fields(None, self.product)
        self.assertTrue(
            {'rating', 'rating_average', 'rating_count', 'review_count'}.issubset(set(readonly))
        )

    def test_empty_cards_and_catalog_sync_never_show_or_seed_fake_ratings(self):
        response = self.client.get(reverse('shop'))
        self.assertNotContains(response, 'aria-label=' + chr(34) + '0.0 rating')
        source = Path(__file__).with_name('management').joinpath(
            'commands', 'sync_wikidata_catalog.py'
        ).read_text(encoding='utf-8')
        self.assertNotIn(chr(34) + 'rating_average' + chr(34) + ': rating', source)
        self.assertNotIn(chr(34) + 'rating' + chr(34) + ': rating', source)

    def test_json_ld_uses_rating_count_and_keeps_review_count_separate(self):
        ProductRating.objects.create(product=self.product, user=self.user, rating=4)
        response = self.client.get(reverse('product', kwargs={'slug': self.product.slug}))
        self.assertContains(response, chr(34) + 'ratingCount' + chr(34) + ':' + chr(34) + '1' + chr(34))
        self.assertNotContains(response, chr(34) + 'reviewCount' + chr(34) + ':' + chr(34) + '1' + chr(34))

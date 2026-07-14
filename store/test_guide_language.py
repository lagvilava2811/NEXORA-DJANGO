from django.test import SimpleTestCase

from .views import _guide_response_language


class GuideLanguageTests(SimpleTestCase):
    def test_detects_shopper_language(self):
        self.assertEqual(_guide_response_language('მირჩიე კარგი ტელეფონი', 'en'), 'ka')
        self.assertEqual(_guide_response_language('Посоветуй хороший телефон', 'en'), 'ru')
        self.assertEqual(_guide_response_language('Recommend a good phone', 'ka'), 'ka')

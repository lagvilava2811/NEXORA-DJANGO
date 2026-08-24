from django.conf import settings
from django.test import SimpleTestCase


class HomePerformanceTests(SimpleTestCase):
    def test_heavy_home_modules_are_loaded_through_lazy_bootstrap(self):
        html = (settings.BASE_DIR / "templates" / "home.html").read_text(encoding="utf-8")
        self.assertIn("home-experience-loader.js", html)
        self.assertIn("data-hero-module-url=", html)
        self.assertIn("data-morph-module-url=", html)
        self.assertNotIn('<script type="module" src="{% static \'hero3d/home-hero.js\'', html)
        self.assertNotIn('<script type="module" src="{% static \'nexora-morph-hero.js\'', html)
        self.assertNotIn("?v=20260820", html)

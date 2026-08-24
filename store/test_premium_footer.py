from django.test import TestCase, override_settings


@override_settings(
    NEXORA_FACEBOOK_URL="https://www.facebook.com/nexora.store",
    NEXORA_X_URL="https://x.com/nexora_store",
    NEXORA_INSTAGRAM_URL="https://www.instagram.com/nexora.store",
    NEXORA_TIKTOK_URL="https://www.tiktok.com/@nexora.store",
)
class PremiumFooterTests(TestCase):
    def test_footer_exposes_configured_social_destinations(self):
        response = self.client.get("/en/")

        self.assertContains(response, 'class="site-footer premium-footer"')
        self.assertContains(response, 'href="https://www.facebook.com/nexora.store"')
        self.assertContains(response, 'href="https://x.com/nexora_store"')
        self.assertContains(response, 'href="https://www.instagram.com/nexora.store"')
        self.assertContains(response, 'href="https://www.tiktok.com/@nexora.store"')

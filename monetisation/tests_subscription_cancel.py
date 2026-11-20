"""Résiliation différée d'abonnement : l'utilisateur garde le plan payant
jusqu'à end_date, puis retour automatique au gratuit (pas de reconduction
automatique dans ce système, donc l'expiration est vérifiée à la lecture)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from monetisation.models import Subscription, Wallet
from monetisation.quota import get_limits_for_user
from monetisation.utils import sync_subscription_expiry

User = get_user_model()


def set_sub(user, **fields):
    """Le signal post_save(User) crée déjà une Subscription (plan=free) :
    on la met à jour plutôt que d'en recréer une (contrainte OneToOne)."""
    Subscription.objects.filter(user=user).update(**fields)
    return Subscription.objects.get(user=user)


class SyncSubscriptionExpiryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("expiry-user", password="testpass")

    def test_future_end_date_is_untouched(self):
        sub = set_sub(self.user, plan="pro", end_date=timezone.now().date() + timedelta(days=5))
        sync_subscription_expiry(sub)
        self.assertEqual(sub.plan, "pro")

    def test_past_end_date_reverts_to_free(self):
        sub = set_sub(
            self.user, plan="pro", end_date=timezone.now().date() - timedelta(days=1),
            cancel_at_period_end=True,
        )
        sync_subscription_expiry(sub)
        self.assertEqual(sub.plan, "free")
        self.assertIsNone(sub.end_date)
        self.assertFalse(sub.cancel_at_period_end)
        sub.refresh_from_db()
        self.assertEqual(sub.plan, "free")

    def test_expires_even_without_explicit_cancellation(self):
        """Pas de reconduction automatique : un plan payé qui n'a jamais été
        renouvelé expire quand même, résiliation explicite ou non."""
        sub = set_sub(
            self.user, plan="basic", end_date=timezone.now().date() - timedelta(days=1),
            cancel_at_period_end=False,
        )
        sync_subscription_expiry(sub)
        self.assertEqual(sub.plan, "free")

    def test_free_plan_untouched(self):
        sub = set_sub(self.user, plan="free", end_date=None)
        sync_subscription_expiry(sub)
        self.assertEqual(sub.plan, "free")

    def test_quota_reflects_expired_plan(self):
        set_sub(self.user, plan="pro", end_date=timezone.now().date() - timedelta(days=1))
        _, plan = get_limits_for_user(self.user)
        self.assertEqual(plan, "free")


class WebSubscriptionCancelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("web-cancel-user", password="testpass")
        self.client.force_login(self.user)

    def test_cancel_keeps_plan_until_end_date(self):
        end_date = timezone.now().date() + timedelta(days=10)
        set_sub(self.user, plan="pro", end_date=end_date)
        response = self.client.post(reverse("monetisation:monetisation_abonnement"), {"action": "cancel_at_period_end"})
        self.assertEqual(response.status_code, 302)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, "pro")
        self.assertEqual(sub.end_date, end_date)
        self.assertTrue(sub.cancel_at_period_end)

    def test_cancel_rejected_for_free_plan(self):
        set_sub(self.user, plan="free")
        response = self.client.post(reverse("monetisation:monetisation_abonnement"), {"action": "cancel_at_period_end"})
        self.assertContains(response, "Aucun abonnement payant actif")
        self.assertFalse(Subscription.objects.get(user=self.user).cancel_at_period_end)

    def test_reactivate_clears_flag(self):
        set_sub(
            self.user, plan="pro", end_date=timezone.now().date() + timedelta(days=10),
            cancel_at_period_end=True,
        )
        response = self.client.post(reverse("monetisation:monetisation_abonnement"), {"action": "reactivate"})
        self.assertEqual(response.status_code, 302)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, "pro")
        self.assertFalse(sub.cancel_at_period_end)

    def test_immediate_downgrade_clears_cancel_flag(self):
        set_sub(
            self.user, plan="pro", end_date=timezone.now().date() + timedelta(days=10),
            cancel_at_period_end=True,
        )
        self.client.post(reverse("monetisation:monetisation_abonnement"), {"plan": "free"})
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, "free")
        self.assertFalse(sub.cancel_at_period_end)


class MobileSubscriptionCancelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("mobile-cancel-user", password="testpass")
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_cancel_keeps_plan_until_end_date(self):
        end_date = timezone.now().date() + timedelta(days=10)
        set_sub(self.user, plan="basic", end_date=end_date)
        response = self.client.post(
            reverse("mobile_monetisation_cancel_subscription"), {"cancel": True}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["plan"], "basic")
        self.assertTrue(data["cancel_at_period_end"])
        self.assertEqual(data["end_date"], end_date.isoformat())

    def test_cancel_rejected_for_free_plan(self):
        set_sub(self.user, plan="free")
        response = self.client.post(
            reverse("mobile_monetisation_cancel_subscription"), {"cancel": True}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_reactivate(self):
        set_sub(
            self.user, plan="pro", end_date=timezone.now().date() + timedelta(days=10),
            cancel_at_period_end=True,
        )
        response = self.client.post(
            reverse("mobile_monetisation_cancel_subscription"), {"cancel": False}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["cancel_at_period_end"])

    def test_dashboard_reflects_expiry_and_cancel_flag(self):
        set_sub(
            self.user, plan="pro", end_date=timezone.now().date() + timedelta(days=10),
            cancel_at_period_end=True,
        )
        response = self.client.get(reverse("mobile_monetisation_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["subscription"]["cancel_at_period_end"])

    def test_dashboard_auto_reverts_expired_plan(self):
        set_sub(self.user, plan="pro", end_date=timezone.now().date() - timedelta(days=1))
        response = self.client.get(reverse("mobile_monetisation_dashboard"))
        self.assertEqual(response.json()["subscription"]["plan"], "free")

    def test_upgrade_clears_cancel_flag(self):
        set_sub(
            self.user, plan="pro", end_date=timezone.now().date() + timedelta(days=10),
            cancel_at_period_end=True,
        )
        Wallet.objects.filter(user=self.user).update(balance=100)
        response = self.client.post(
            reverse("mobile_monetisation_upgrade"), {"plan": "pro"}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Subscription.objects.get(user=self.user).cancel_at_period_end)

"""Tests du parrainage : commission de 5 % en points (1 000 points = 1 €),
pas d'auto-parrainage, conversion à partir de 1 000 points, nettoyage."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from monetisation.models import Referral, ReferralTransaction, Wallet, Transaction
from monetisation.utils import award_referral_commission, convert_referral_points

User = get_user_model()


class ReferralCommissionTest(TestCase):
    def setUp(self):
        self.parrain = User.objects.create_user(username="parrain", password="p")
        self.filleul = User.objects.create_user(username="filleul", password="p")

    def test_commission_is_5_percent_in_points(self):
        Referral.objects.create(referrer=self.parrain, referred=self.filleul, code="c1")
        tx = award_referral_commission(self.filleul, 10, "Commission sur recharge de filleul")
        self.assertEqual(tx.amount, 500)  # 5 % de 10 € = 0,50 € = 500 points

    def test_no_commission_on_self_referral(self):
        Referral.objects.create(referrer=self.filleul, referred=self.filleul, code="c2")
        self.assertIsNone(award_referral_commission(self.filleul, 10, "x"))
        self.assertFalse(ReferralTransaction.objects.exists())

    def test_no_commission_without_referrer(self):
        Referral.objects.create(referrer=None, referred=self.filleul, code="c3")
        self.assertIsNone(award_referral_commission(self.filleul, 10, "x"))
        self.assertIsNone(award_referral_commission(self.parrain, 10, "x"))  # aucune ligne Referral
        self.assertFalse(ReferralTransaction.objects.exists())

    def test_admin_refuses_self_referral(self):
        ref = Referral(referrer=self.filleul, referred=self.filleul, code="c4")
        with self.assertRaises(ValidationError):
            ref.clean()


class ReferralConversionTest(TestCase):
    def setUp(self):
        self.parrain = User.objects.create_user(username="parrain2", password="p")
        self.filleul = User.objects.create_user(username="filleul2", password="p")
        self.ref = Referral.objects.create(referrer=self.parrain, referred=self.filleul, code="c5")

    def _points(self, amount):
        ReferralTransaction.objects.create(referral=self.ref, amount=amount, description="t")

    def test_conversion_requires_1000_points(self):
        self._points(999.5)
        with self.assertRaises(ValueError):
            convert_referral_points(self.parrain)
        self.assertEqual(Wallet.objects.get(user=self.parrain).balance, 0)

    def test_conversion_credits_wallet_once_and_keeps_history(self):
        self._points(500)
        self._points(750)

        points, euros = convert_referral_points(self.parrain)

        self.assertEqual((points, euros), (1250, 1.25))
        self.assertEqual(Wallet.objects.get(user=self.parrain).balance, 1.25)
        self.assertTrue(Transaction.objects.filter(user=self.parrain, amount=1.25).exists())
        # Historique conservé : les montants ne sont plus remis à 0
        self.assertEqual(sorted(ReferralTransaction.objects.values_list("amount", flat=True)), [500, 750])
        with self.assertRaises(ValueError):  # rien à reconvertir (double clic)
            convert_referral_points(self.parrain)
        self.assertEqual(Wallet.objects.get(user=self.parrain).balance, 1.25)

    def test_web_conversion_view(self):
        self._points(2000)
        self.client.force_login(self.parrain)
        resp = self.client.post("/monetisation/convert-commission/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Wallet.objects.get(user=self.parrain).balance, 2.0)

    def test_referral_page_rounds_points(self):
        self._points(0.15000000000000002)
        self.client.force_login(self.parrain)
        resp = self.client.get("/monetisation/referrals/")
        self.assertNotContains(resp, "0,15000000000000002")
        self.assertContains(resp, "au moins 1000 points")


class CleanSelfReferralsCommandTest(TestCase):
    def test_dry_run_then_apply(self):
        moi = User.objects.create_user(username="moi", password="p")
        autre = User.objects.create_user(username="autre", password="p")
        self_ref = Referral.objects.create(referrer=moi, referred=moi, code="c6")
        ReferralTransaction.objects.create(referral=self_ref, amount=500, description="auto")
        ReferralTransaction.objects.create(referral=self_ref, amount=100, description="déjà convertie", converted=True)
        orphan_ref = Referral.objects.create(referrer=None, referred=autre, code="c7")
        ReferralTransaction.objects.create(referral=orphan_ref, amount=0.15, description="orpheline")

        out = StringIO()
        call_command("clean_self_referrals", stdout=out)
        self.assertIn("moi est son propre parrain", out.getvalue())
        self.assertEqual(ReferralTransaction.objects.count(), 3, "la simulation ne change rien")

        call_command("clean_self_referrals", "--apply", stdout=StringIO())
        self_ref.refresh_from_db()
        self.assertIsNone(self_ref.referrer)
        self.assertEqual(list(ReferralTransaction.objects.values_list("description", flat=True)), ["déjà convertie"])

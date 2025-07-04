from paypal.standard.models import ST_PP_COMPLETED
from paypal.standard.ipn.signals import valid_ipn_received
from django.dispatch import receiver
from .models import UserSubscription, SubscriptionPlan
from django.contrib.auth.models import User
from datetime import datetime, timedelta

@receiver(valid_ipn_received)
def paypal_payment_received(sender, **kwargs):
    ipn_obj = sender
    if ipn_obj.payment_status == ST_PP_COMPLETED:
        custom = ipn_obj.custom
        user_id, plan_id = custom.split(':')
        user = User.objects.get(id=user_id)
        plan = SubscriptionPlan.objects.get(id=plan_id)
        UserSubscription.objects.update_or_create(
            user=user,
            defaults={
                'plan': plan,
                'active': True,
                'start_date': datetime.now(),
                'end_date': datetime.now() + timedelta(days=30)
            }
        )

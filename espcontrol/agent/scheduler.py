"""
Simple scheduler helpers for Founatek agent.

This module provides a small helper to run the agent periodically.
In production it's recommended to use Celery beat or an external cron to enqueue
the agent run for each user.

Usage examples:
- `python manage.py run_agent` (already provided) for a synchronous run
- Configure Celery and call `enqueue_agent_for_all_users()` from a beat schedule
"""
from django.contrib.auth import get_user_model

from espcontrol.agent.agent import FounatekAgent


def enqueue_agent_for_all_users(enqueue_func=None):
	"""Run agent for all active users.

	If `enqueue_func` is provided, it will be called with a callable for each user
	(useful to enqueue Celery tasks). If not provided the agent is executed synchronously.
	"""
	User = get_user_model()
	for user in User.objects.filter(is_active=True):
		agent = FounatekAgent(user)
		if enqueue_func:
			enqueue_func(agent.run)
		else:
			agent.run()

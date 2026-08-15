from django.contrib.auth import get_user_model
from espcontrol.agent.agent import FounatekAgent
from espcontrol.models import Device


def enqueue_agent_for_all_users(enqueue_func=None):
    """
    Run agent for all active users.
    Can be sync or async (Celery / scheduler).
    """

    User = get_user_model()

    users = User.objects.filter(
        is_active=True,
        devices__isnull=False
    ).distinct()

    for user in users:
        agent = FounatekAgent(user)

        if enqueue_func:
            enqueue_func(agent.run)
        else:
            result = agent.run()
            print(
                f"Agent exécuté pour {user.username} → "
                f"{len(result.get('results', [])) if result else 0}"
            )
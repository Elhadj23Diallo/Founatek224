from .models import TechNotification, TechMessage

def badging(request):
    if request.user.is_authenticated:
        # Compter les notifications non lues
        notif_count = TechNotification.objects.filter(receiver=request.user, is_read=False).count()
        
        # Compter les messages non lus
        msg_count = TechMessage.objects.filter(receiver=request.user, is_read=False).count()
        
        return {
            'badge_notif_count': notif_count,
            'badge_msg_count': msg_count,
        }
    return {}
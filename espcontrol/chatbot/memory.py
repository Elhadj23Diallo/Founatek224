from espcontrol.models import ChatMemory


class ChatMemoryService:

    @staticmethod
    def get(user):
        memory, _ = ChatMemory.objects.get_or_create(user=user)
        return memory

    @staticmethod
    def remember(user, **kwargs):
        memory = ChatMemoryService.get(user)

        for key, value in kwargs.items():
            if hasattr(memory, key):
                setattr(memory, key, value)

        memory.save()
        return memory

    @staticmethod
    def clear(user):
        ChatMemory.objects.filter(user=user).delete()

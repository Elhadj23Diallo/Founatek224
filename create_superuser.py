import os
import sys

sys.path.append(r'c:\Users\Admin\Documents\Founatek_c')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monappli.settings')

import django
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
username = 'elhadj'
email = 'isaac@gmail.com'
password = '1234'

user = User.objects.filter(username=username).first()
if user:
    print('exists', user.username)
else:
    User.objects.create_superuser(username=username, email=email, password=password)
    print('created', username)

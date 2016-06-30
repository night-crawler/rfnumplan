from django.conf import settings

MAX_PREFIX_LENGTH = getattr(settings, 'RFNUMPLAN_MAX_PREFIX_LENGTH', 5)

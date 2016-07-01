from django.conf import settings

MAX_PREFIX_LENGTH = getattr(settings, 'RFNUMPLAN_MAX_PREFIX_LENGTH', 5)
PAGE_SIZE = getattr(settings, 'RFNUMPLAN_PAGE_SIZE', 20)

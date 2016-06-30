import phonenumbers

from django.utils.translation import activate
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.core.management.base import BaseCommand
from django.utils import termcolors
from django.core.management import color


def color_style():
    style = color.color_style()
    style.SECTION = termcolors.make_style(fg='yellow', opts=('bold',))
    style.SUCCESS = termcolors.make_style(fg='green', opts=('bold',))
    style.ERROR = termcolors.make_style(fg='red', opts=('bold',))
    style.INFO = termcolors.make_style(fg='blue', opts=('bold',))
    return style


class Command(BaseCommand):
    help = str(_('Shows operators, num plan ranges, etc. Example:\n python manage.py rfnumplan 79251234567'))

    results = ''
    requires_model_validation = False
    can_import_settings = True

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.style = color_style()

        activate(settings.LANGUAGE_CODE)

    def log(self, msg, clr='SECTION', ending=None):
        self.stdout.write(getattr(self.style, clr)(msg), ending=ending)
        self.stdout.flush()

    def err(self, msg, clr='ERROR', ending=None):
        self.stderr.write(getattr(self.style, clr)(msg), ending=ending)
        self.stderr.flush()

    def add_arguments(self, parser):
        parser.add_argument('--update', action='store_true', default=False,
                            help=str(_('fetch numbering plan\'s data from urls')))
        parser.add_argument('--force', action='store_true', default=False,
                            help=str(_('force numbering plans update')))
        parser.add_argument('--clear', action='store_true', default=False,
                            help=str(_('clear all numbering plans content')))
        parser.add_argument('--prefixes', action='store_true', default=False,
                            help=str(_('show all plan range prefixes')))
        parser.add_argument('phones', nargs='*', default=[], type=str,
                            help=str(_('phones to check')))

    def handle_update(self, force=False):
        from rfnumplan.models import NumberingPlan
        for np in NumberingPlan.objects.all():
            self.log(_('%(force)sLoading `%(name)s` numbering plan...') % {
                'force': _('[FORCE] ') if force else '',
                'name': np,
            })
            objects = np.do_import(force=force)
            self.log(_('Loaded %s objects') % len(objects), clr='SUCCESS')

    def handle_clear(self):
        import rfnumplan.models as m
        self.log(_('Removing all data'), clr='ERROR')
        m.Region.objects.all().delete()
        m.Operator.objects.all().delete()
        m.NumberingPlanRange.objects.all().delete()
        # m.NumberingPlan.objects.all().delete()
        self.log(_('Removed all data'), clr='SUCCESS')

    @staticmethod
    def get_phone_info(num) -> dict:
        from rfnumplan.models import NumberingPlanRange
        n = phonenumbers.parse(num, region='RU')
        res = {
            'num': num,
            'e164': phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164),
            'possible': phonenumbers.is_possible_number(n),
            'valid': phonenumbers.is_valid_number(n),
            'info': []
        }

        if res['valid']:
            res['info'] = NumberingPlanRange.find(res['e164'])

        return res

    def handle_prefixes(self):
        from rfnumplan.models import NumberingPlanRange
        self.log('All plan range prefixes')
        prev_prefix = ''
        for prefix, cnt in NumberingPlanRange.range_prefixes():
            if prev_prefix and prev_prefix[0] != str(prefix)[0]:
                ending = '\n-----------------------------------\n'
            else:
                ending = '\n'
            prev_prefix = str(prefix)

            self.log('%s x%s' % (prefix, cnt), ending=ending)

    def handle_find_num_ranges(self, phones: list):
        self.log(_('Found numbering plan ranges:'))
        for num in phones:
            fi = self.get_phone_info(num)
            for nr in fi['info']:
                self.log(fi['e164'], clr='ERROR', ending='\t')
                self.log('+%s (%s) [%s - %s] x%s' % (
                    nr.numbering_plan.prefix,
                    nr.prefix,
                    str(nr.range_start)[1:],
                    str(nr.range_end)[1:],
                    nr.range_capacity
                ), ending='\n\t')
                self.log(nr.operator, clr='SUCCESS', ending='\n\t')
                self.log(nr.region, clr='SUCCESS', ending='\n')

    def handle(self, *args, **options):
        activate(settings.LANGUAGE_CODE)
        if options.get('prefixes'):
            self.handle_prefixes()
            return

        if options.get('clear'):
            self.handle_clear()

        if options.get('update'):
            self.handle_update(force=options.get('force'))
            return

        if options.get('phones'):
            self.handle_find_num_ranges(options.get('phones'))
            return


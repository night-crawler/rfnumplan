import phonenumbers

from terminaltables import SingleTable

from django.db.models import Q
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
    style.DEFAULT = termcolors.make_style()
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
        parser.add_argument('--operator', action='append', default=[],
                            help=str(_('Filter --plan with operator name(s)')))
        parser.add_argument('--region', action='append', default=[],
                            help=str(_('Filter --plan with region name(s)')))
        parser.add_argument('--plan', default='',
                            help=str(_('Show ranges for plan (id|name)')))
        parser.add_argument('--list-plans', action='store_true', default=False,
                            help=str(_('show numbering plans')))
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

    def handle_list_plans(self):
        from rfnumplan.models import NumberingPlan
        fields = ['id', 'name', 'prefix', 'loaded', 'last_modified']
        header = [_('id'), _('name'), _('prefix'), _('loaded'), _('last modified')]
        data = [header, *NumberingPlan.objects.values_list(*fields)]
        self.log(SingleTable(data, title=str(_('Numbering plans'))).table, clr='DEFAULT')

    def handle_list_plan_ranges(self, args, options):
        from rfnumplan.models import NumberingPlan
        plan_id_or_name, operators, regions = options.get('plan'), options.get('operator'), options.get('region')
        if plan_id_or_name.isdigit():
            plan = NumberingPlan.objects.get(pk=plan_id_or_name)
        else:
            plan = NumberingPlan.objects.get(name=plan_id_or_name)

        ranges = plan.ranges.all()
        if operators:
            filters = Q()
            for operator in operators:
                filters |= Q(operator__name__icontains=operator)
            ranges = ranges.filter(filters)
        if regions:
            filters = Q()
            for region in regions:
                filters |= Q(region__name__icontains=region)
            ranges = ranges.filter(filters)

        fields = ['prefix', 'range_start', 'range_end', 'range_capacity', 'operator__name', 'region__name']
        header = [_('prefix'), _('start'), _('end'), _('capacity'), _('operator'), _('region')]
        ranges_data = []
        for r in ranges.values(*fields):
            r['range_start'] = str(r['range_start'])[1:]
            r['range_end'] = str(r['range_end'])[1:]
            ranges_data.append([r[field] for field in fields])

        data = [header, *ranges_data]
        self.log(SingleTable(data, title=str(_('Numbering plan ranges [x%s]')) % len(ranges_data)).table, clr='DEFAULT')

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
        if options.get('plan'):
            self.handle_list_plan_ranges(args, options)
            return

        if options.get('list_plans'):
            self.handle_list_plans()
            return

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


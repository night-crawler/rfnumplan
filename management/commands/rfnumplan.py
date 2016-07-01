import sys
import phonenumbers
import csv

from django.template.defaultfilters import truncatechars
from terminaltables import SingleTable

from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.translation import activate
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.core.management.base import BaseCommand
from django.utils import termcolors
from django.core.management import color


try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs):
        return iterable


def op(c, v1, v2):
    if c is '&':
        return v1 & v2
    elif c is '|':
        return v1 | v2
    return v1 | v2


def color_style():
    style = color.color_style()
    style.SECTION = termcolors.make_style(fg='yellow', opts=('bold',))
    style.SUCCESS = termcolors.make_style(fg='green', opts=('bold',))
    style.ERROR = termcolors.make_style(fg='red', opts=('bold',))
    style.INFO = termcolors.make_style(fg='blue', opts=('bold',))
    style.DEFAULT = termcolors.make_style()
    return style


sentinel = object()


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
        parser.add_argument('--locale', '-l', default=getattr(settings, 'LANGUAGE_CODE', 'ru'), dest='locale',
                            help=str(_('Set locale LOCALE')))
        parser.add_argument('--p', '--page', '-p', default=0, dest='page',
                            help=str(_('Show page with PAGE number')))
        parser.add_argument('--page-size', '-s', default=20, dest='page_size',
                            help=str(_('Set page size for tables')))
        parser.add_argument('--operator', '-o', dest='operator', action='append', default=[],
                            help=str(_('Filter --plan with operator name(s)')))
        parser.add_argument('--region', '-r', dest='region', action='append', default=[],
                            help=str(_('Filter --plan with region name(s)')))
        parser.add_argument('--exclude-region', action='append', default=[],
                            help=str(_('Exclude region from --plan output')))
        parser.add_argument('--exclude-operator', action='append', default=[],
                            help=str(_('Exclude region from --plan output')))
        parser.add_argument('--plan', '-n', dest='plan', default='',
                            help=str(_('Show ranges for plan (id|name)')))
        parser.add_argument('--list-plans', action='store_true', default=False,
                            help=str(_('Show numbering plans')))
        parser.add_argument('--prefixes', action='store_true', default=False,
                            help=str(_('Converts ranges into prefixes')))
        parser.add_argument('--csv', type=str,
                            help=str(_('Output --prefixes and save it to csv if filepath specified')))
        parser.add_argument('--cost', type=float,
                            help=str(_('Add cost into csv output')))
        parser.add_argument('--price', type=float,
                            help=str(_('Add price into csv output')))
        parser.add_argument('--update', action='store_true', default=False,
                            help=str(_('Fetch numbering plan\'s data from urls')))
        parser.add_argument('--force', action='store_true', default=False,
                            help=str(_('Force numbering plans update')))
        parser.add_argument('--clear', action='store_true', default=False,
                            help=str(_('Clear all numbering plans content')))
        parser.add_argument('--range-summary', action='store_true', default=False,
                            help=str(_('Show plan range prefixes summary')))
        parser.add_argument('phones', nargs='*', default=[], type=str,
                            help=str(_('Phones to check')))

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

    def paginated(self, queryset, options):
        page_num = int(options.get('page'))
        if page_num:
            per_page = options.get('page_size', 0) or settings.PAGE_SIZE
        else:
            page_num = 1
            per_page = sys.maxsize

        p = Paginator(queryset, per_page)
        page = p.page(page_num)

        return page

    def handle_list_plans(self):
        from rfnumplan.models import NumberingPlan
        fields = ['id', 'name', 'prefix', 'loaded', 'last_modified']
        header = [_('ID'), _('Name'), _('Prefix'), _('Loaded'), _('Last modified')]
        data = [header, *NumberingPlan.objects.values_list(*fields)]
        self.log(SingleTable(data, title=str(_('Numbering plans'))).table, clr='DEFAULT')

    def get_plans_qs(self, options):
        from rfnumplan.models import NumberingPlan
        plan_id_or_name = options.get('plan')
        if plan_id_or_name == '*':
            return NumberingPlan.objects.all()
        if plan_id_or_name.isdigit():
            return NumberingPlan.objects.filter(pk=plan_id_or_name)
        return NumberingPlan.objects.filter(name=plan_id_or_name)

    def get_plan_ranges_queryset(self, options):
        from rfnumplan.models import NumberingPlanRange
        return NumberingPlanRange.objects.filter(numbering_plan__in=self.get_plans_qs(options))

    def filter_plan_ranges_queryset(self, ranges, options):
        operators, regions, exclude_operators, exclude_regions = \
            options.get('operator'), options.get('region'), \
            options.get('exclude_operator'), options.get('exclude_region')
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
        if exclude_operators:
            filters = Q()
            for operator in exclude_operators:
                filters |= Q(operator__name__icontains=operator)
            ranges = ranges.exclude(filters)
        if exclude_regions:
            filters = Q()
            for region in exclude_regions:
                filters |= Q(region__name__icontains=region)
            ranges = ranges.exclude(filters)

        return ranges.select_related('numbering_plan', 'operator', 'region')

    def handle_list_plan_ranges(self, args, options):
        ranges = self.get_plan_ranges_queryset(options)
        ranges = self.filter_plan_ranges_queryset(ranges, options)

        fields = ['numbering_plan__prefix', 'prefix', 'range_start', 'range_end', 'range_capacity', 'operator__name',
                  'region__name']
        header = [_('#'), _('###'), _('Start'), _('End'), _('Capacity'), _('Operator'), _('Region')]
        ranges_data = []

        page = self.paginated(ranges.values(*fields), options)
        for r in page.object_list:
            r['range_start'] = str(r['range_start'])[1:]
            r['range_end'] = str(r['range_end'])[1:]
            r['operator__name'] = truncatechars(r['operator__name'], 40)
            ranges_data.append([r[field] for field in fields])

        data = [header, *ranges_data]
        if not options.get('page'):
            title = str(_('Numbering plan ranges [x%s]')) % page.paginator.count
        else:
            title = str(_('Numbering plan ranges [x%(count)s], page %(page)s of %(num_pages)s')) % {
                'count': page.paginator.count,
                'page': options.get('page'),
                'num_pages': page.paginator.num_pages
            }

        self.log(SingleTable(data, title=title).table, clr='DEFAULT')

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

    def handle_range_summary(self, options):
        header = [_('Numbering plan'), _('#'), _('###'), _('Count')]
        ranges_info = []
        for np in self.get_plans_qs(options):
            for rp in sorted(np.range_prefixes(), reverse=True, key=lambda tup: tup[1]):
                ranges_info.append([np.name, np.prefix, rp[0], rp[1]])

        data = [header, *ranges_info]
        title = str(_('Plan range prefixes summary'))
        self.log(SingleTable(data, title=title).table, clr='DEFAULT')

    def write_csv_ranges(self, ranges, options):
        field_names = ['prefix', 'operator', 'region']
        cost, price = options.get('cost'), options.get('price')
        if cost:
            field_names.append('cost')
        if price:
            field_names.append('price')

        counter = 0
        csv_file_path = options.get('csv')
        with open(csv_file_path, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names)
            writer.writeheader()

            for nr in tqdm(ranges):
                for prefix in nr.to_prefix_list():
                    bundle = {
                        'prefix': prefix,
                        'operator': nr.operator.name,
                        'region': nr.region.name
                    }
                    if cost:
                        bundle['cost'] = cost
                    if price:
                        bundle['price'] = price
                    writer.writerow(bundle)
                    counter += 1
            self.log(_('%(count)s rows written into %(file)s') % {'count': counter, 'file': csv_file_path})

    def handle_prefixes(self, options):
        ranges = self.get_plan_ranges_queryset(options)
        ranges = self.filter_plan_ranges_queryset(ranges, options)

        if options.get('csv'):
            self.write_csv_ranges(ranges, options)
            return

        for nr in ranges:
            self.err(nr.get_display(), ending='\t')
            self.log('%s %s ' % (nr.operator.name, nr.region.name), clr='DEFAULT', ending='\n\t')
            self.log(', '.join(nr.to_prefix_list()), clr='SUCCESS', ending='\n')

    def handle_find_num_ranges(self, phones: list):
        self.log(_('Found numbering plan ranges:'))
        for num in phones:
            fi = self.get_phone_info(num)
            for nr in fi['info']:
                self.log(fi['e164'], clr='ERROR', ending='\t')
                self.log(nr.get_display(), ending='\n\t')
                self.log(nr.operator, clr='SUCCESS', ending='\n\t')
                self.log(nr.region, clr='SUCCESS', ending='\n')
                # self.log(', '.join(nr.to_prefix_list()), clr='SUCCESS', ending='\n\t')

    def handle(self, *args, **options):
        activate(options.get('locale'))

        if options.get('prefixes'):
            self.handle_prefixes(options)
            return

        if options.get('range_summary'):
            self.handle_range_summary(options)
            return

        if options.get('plan'):
            self.handle_list_plan_ranges(args, options)
            return

        if options.get('list_plans'):
            self.handle_list_plans()
            return

        if options.get('clear'):
            self.handle_clear()

        if options.get('update'):
            self.handle_update(force=options.get('force'))
            return

        if options.get('phones'):
            self.handle_find_num_ranges(options.get('phones'))
            return


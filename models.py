import phonenumbers
import requests
import dateutil.parser

from django.core.files.temp import NamedTemporaryFile
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.forms import model_to_dict

from rfnumplan.utils import read_csv_num_plan, map_instances_by_name
from model_utils.models import TimeStampedModel
from django.utils.translation import ugettext_lazy as _

from .settings import MAX_PREFIX_LENGTH


class ModelDiffMixin(object):
    """
    A model mixin that tracks model fields' values and provide some useful api
    to know what fields have been changed.
    """

    def __init__(self, *args, **kwargs):
        super(ModelDiffMixin, self).__init__(*args, **kwargs)
        self.__initial = self._dict

    @property
    def diff(self):
        d1 = self.__initial
        d2 = self._dict
        diffs = [(k, (v, d2[k])) for k, v in d1.items() if v != d2[k]]
        return dict(diffs)

    @property
    def has_changed(self):
        return bool(self.diff)

    @property
    def changed_fields(self):
        return self.diff.keys()

    def get_field_diff(self, field_name):
        """
        Returns a diff for field if it's changed and None otherwise.
        """
        return self.diff.get(field_name, None)

    def save(self, *args, **kwargs):
        """
        Saves model and set initial state.
        """
        super(ModelDiffMixin, self).save(*args, **kwargs)
        self.__initial = self._dict

    @property
    def _dict(self):
        return model_to_dict(self, fields=[field.name for field in self._meta.fields])


class Operator(models.Model):
    name = models.CharField(_('operator name'), max_length=255, unique=True)

    class Meta:
        verbose_name = _('operator')
        verbose_name_plural = _('operators')
        ordering = ['name']

    def __str__(self):
        return self.name


class Region(models.Model):
    name = models.CharField(_('region name'), max_length=255, unique=True)

    class Meta:
        verbose_name = _('region')
        verbose_name_plural = _('regions')
        ordering = ['name']

    def __str__(self):
        return self.name


class NumberingPlan(ModelDiffMixin, models.Model):
    name = models.CharField(_('numbering plan'), max_length=128, help_text=_('e.g. rossviaz 4xx'))
    prefix = models.PositiveIntegerField(_('prefix'), help_text=_('e.g. 7'))
    plan_uri = models.URLField(_('url'), blank=True)
    loaded = models.BooleanField(_('loaded'), default=False)
    last_modified = models.DateTimeField(_('last modified'), blank=True, null=True)

    class Meta:
        verbose_name = _('numbering plan')
        verbose_name_plural = _('numbering plans')
        ordering = ['name']

    def __str__(self):
        return self.name

    def do_import(self, force=False):
        head = requests.head(self.plan_uri).headers
        lm = dateutil.parser.parse(head.get('Last-Modified'))
        if self.last_modified and self.last_modified >= lm and not force and self.loaded:
            return []

        response = requests.get(self.plan_uri)
        tmp = NamedTemporaryFile(delete=True)
        tmp.write(response.content)
        tmp.flush()

        parsed = read_csv_num_plan(tmp.name)
        operators = map_instances_by_name(Operator, parsed['operators'])
        regions = map_instances_by_name(Region, parsed['regions'])
        NumberingPlanRange.objects.filter(numbering_plan=self).delete()

        bulk = []
        for bundle in parsed['data']:
            bulk.append(
                NumberingPlanRange(
                    numbering_plan=self,
                    prefix=bundle['prefix'],
                    range_start='1%s' % bundle['range_start'],
                    range_end='1%s' % bundle['range_end'],
                    range_capacity=bundle['range_capacity'],
                    operator=operators[bundle['operator']],
                    region=regions[bundle['region']],
                )
            )

        self.last_modified = lm
        self.loaded = True
        return NumberingPlanRange.objects.bulk_create(bulk)

    def save(self, *args, **kwargs):
        cf = self.changed_fields
        res = super(NumberingPlan, self).save()

        if not self.loaded or self.plan_uri in cf:
            self.do_import()
            self.save()

        return res


class NumberingPlanRange(models.Model):
    numbering_plan = models.ForeignKey(NumberingPlan, verbose_name=_('numbering plan'))
    prefix = models.PositiveIntegerField(_('prefix'), help_text=_('e.g. 495'))
    range_start = models.PositiveIntegerField(_('range start'), help_text=_('`1`-prefixed range start'))
    range_end = models.PositiveIntegerField(_('range end'), help_text=_('`1`-prefixed range end'))
    range_capacity = models.PositiveIntegerField(_('range capacity'))

    operator = models.ForeignKey(Operator, verbose_name=_('operator'))
    region = models.ForeignKey(Region, verbose_name=_('region'))

    class Meta:
        verbose_name = _('numbering plan range')
        verbose_name_plural = _('numbering plan ranges')
        ordering = ['numbering_plan_id']

    def __str__(self):
        return '%s [%s; %s]' % (self.numbering_plan.name, str(self.range_start)[1:], str(self.range_end)[1:])

    @staticmethod
    def find(phone_number: str):
        """
        7 9 252123399
        7 92 52123399
        7 925 2123399
        7 9252 123399
        79 2 52123399
        79 25 2123399
        79 252 123399
        79 2521 23399
        792 5 2123399
        792 52 123399
        792 521 23399
        792 5212 3399
        7925 2 123399
        7925 21 23399
        7925 212 3399
        7925 2123 399
        :param phone_number:
        :return:
        """

        number = phonenumbers.parse(phone_number, region='RU')
        if not phonenumbers.is_valid_number(number):
            raise ValueError(_('Wrong number %s') % phone_number)

        e164_number = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164).lstrip('+')

        lookup = models.Q()

        for i in range(1, min(MAX_PREFIX_LENGTH, len(e164_number))):
            plan_prefix = e164_number[:i]
            rest = e164_number[i:]

            for j in range(1, min(MAX_PREFIX_LENGTH, len(rest))):
                pr_prefix = rest[:j]
                local_phone = rest[j:]
                lookup |= models.Q(
                    numbering_plan__prefix=plan_prefix, prefix=pr_prefix,
                    range_start__lte='1%s' % local_phone, range_end__gte='1%s' % local_phone
                )
        return NumberingPlanRange.objects.filter(lookup).select_related('operator', 'region')

    @staticmethod
    def range_prefixes():
        return NumberingPlanRange.objects.values_list('prefix').annotate(cnt=models.Count('prefix'))

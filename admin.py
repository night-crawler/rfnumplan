# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import Operator, Region, NumberingPlan, NumberingPlanRange


class OperatorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
admin.site.register(Operator, OperatorAdmin)


class RegionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
admin.site.register(Region, RegionAdmin)


class NumberingPlanAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'prefix',
        'plan_uri',
        'loaded',
        'last_modified',
    )
    list_filter = ('last_modified', 'loaded')
    search_fields = ('name',)
admin.site.register(NumberingPlan, NumberingPlanAdmin)


class NumberingPlanRangeAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'numbering_plan',
        'prefix',
        'range_start',
        'range_end',
        'range_capacity',
        'operator',
        'region',
    )
    raw_id_fields = ('numbering_plan', 'operator', 'region')

    list_filter = ('numbering_plan__name',)

    def get_queryset(self, request):
        return super(NumberingPlanRangeAdmin, self).get_queryset(request).select_related('region', 'operator')

admin.site.register(NumberingPlanRange, NumberingPlanRangeAdmin)

import csv


FIELDS = [
    'prefix',
    'range_start',
    'range_end',
    'range_capacity',
    'operator',
    'region'
]


def read_csv_num_plan(filepath: str) -> dict:
    reader = csv.reader(open(filepath, 'r', encoding='cp1251'), delimiter=';')
    res = {
        'data': [],
        'operators': set(),
        'regions': set(),
    }
    reader.__next__()
    for row in reader:
        if not row:
            continue

        row = [c.strip() for c in row]
        bundle = dict(zip(FIELDS, row))
        res['data'].append(bundle)
        res['operators'].add(bundle['operator'])
        res['regions'].add(bundle['region'])

    return res


def map_instances_by_name(model_class, items_names: list) -> dict:
    existent_item_names = model_class.objects.filter(name__in=items_names).values_list('name', flat=True)
    missing = set(items_names) - set(existent_item_names)
    model_class.objects.bulk_create(model_class(name=name) for name in missing)
    return {item.name: item for item in model_class.objects.filter(name__in=items_names)}

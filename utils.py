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


def range_to_prefix(a, b):
    def inner(aa, bb, p):
        if p == 1:
            if a <= aa <= b:
                yield aa
            return

        for d in range(aa, bb + 1, p):
            if a <= d and d + p - 1 <= b:
                yield d // p
            elif not (bb < a or aa > b):
                for i in range(10):
                    yield from inner(d + i * p // 10, d + (i + 1) * p // 10 - 1, p // 10)

    a, b = int(a), int(b)
    p = 10**(max(len(str(x)) for x in (a, b)) - 1)
    yield from inner(a // p * p, b // p * p + p - 1, p)

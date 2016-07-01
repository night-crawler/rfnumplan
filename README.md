## rfnumplan
Django-батарейка для поиска диапазонов по плану нумерации http://www.rossvyaz.ru/activity/num_resurs/registerNum/

#### Dependencies
- phonenumbers
- requests
- django
- python-dateutil
- terminaltables

---

##### Поиск диапазонов и операторов по номерам
```
$ ./manage.py rfnumplan +79251234567 84955071234
```
![Поиск по диапазону номеров](https://cloud.githubusercontent.com/assets/1235203/16502381/c48d5f02-3f16-11e6-84a4-5d63949d7c67.png)

---

##### Список префиксов с количеством диапазонов в них

```
$ ./manage.py rfnumplan --prefixes
```

![Список всех префиксов планов нумерации](https://cloud.githubusercontent.com/assets/1235203/16502630/0c31bbf4-3f18-11e6-9ea9-6f130b56b50d.png)

---
##### Обновление с сайта Россвязи

```
./manage.py rfnumplan --update --force
```

![Загрузка плана нумерации с сайта rossvyaz](https://cloud.githubusercontent.com/assets/1235203/16502698/5674eaa6-3f18-11e6-8765-6821782313cc.png)

---
##### Поиск диапазонов по региону и оператору

```
./manage.py rfnumplan --plan=9xx --operator=Т2 --region=Москва
./manage.py rfnumplan --plan=9xx --operator="Мобильные ТелеСистемы"
./manage.py rfnumplan --plan=9xx --region=Москва --region=Петербург --operator=скар

```
![Поиск диапазонов по региону и оператору](https://cloud.githubusercontent.com/assets/1235203/16522216/fe590f90-3fa4-11e6-95ab-c38c757337ca.png)

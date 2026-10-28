# ITMO Highload — TASK1 (этапы 1 и 2)

**Java 21, Spring Boot 3.5.16, Tomcat, Micrometer и Docker Compose.**

Это **полный проект** для замены файлов в корне `itmo-highload-task1`.
Его файлы должны находиться непосредственно в корне проекта (`compose.yaml`, `app/`),
а не во вложенной папке с названием архива. Архив не содержит `.git`,
поэтому существующие Git-ветки, история и remote сохраняются.

## Запуск

В терминале, находясь в корне своего проекта:

```bash
docker compose down
docker compose up --build
```

При сборке Dockerfile выполняет `mvn -B -ntp verify`: **компиляцию и JUnit-тесты**.
Первый запуск может скачивать зависимости Maven.

После сообщения `Started ItemsApplication` открой второй терминал из корня проекта:

```bash
bash check-stage2.sh
```

В конце должно появиться `SUCCESS: TASK1 stages 1 and 2 are operational`.

## Маршруты

| Метод | URL | Назначение |
|---|---|---|
| POST | `/items` | Создать запись в памяти; JSON `{"name":"Item"}`, HTTP 201 |
| GET | `/items/{id}` | Получить запись; 404 при отсутствии |
| PUT | `/items/{id}` | Изменить запись; 404 при отсутствии |
| GET | `/health` | Возвращает `OK` |
| GET | `/handlers` | Реально зарегистрированные маршруты Spring MVC |
| GET | `/metrics` | Метрики Prometheus в текстовом формате |

## Метрики

- `app_http_requests_total` — монотонный счётчик запросов.
- `app_http_request_duration_seconds_bucket` — накопительные buckets гистограммы времени ответа.
- `app_http_request_duration_seconds_count` и `_sum` — количество и сумма длительностей.
- Метки: `pod`, `dc`, `method`, `route`, `status`.
- `route` содержит шаблон `/items/{id}`, а не конкретный ID.
- `POD_ID` и `DATACENTER` задаются переменными окружения Docker Compose.

Примеры будущих PromQL-запросов для Grafana:

```promql
sum(rate(app_http_requests_total[1m]))
sum by (status) (rate(app_http_requests_total{status=~"4..|5.."}[1m]))
histogram_quantile(0.95, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))
```

**Важно:** перцентили по нескольким экземплярам рассчитываются после
суммирования `*_bucket` по `le`, а не через усреднение локальных p95.

## Как намеренно получить ошибки

```bash
# Реальная клиентская ошибка 404
curl -i http://127.0.0.1:8080/items/999999999

# Демонстрационный ответ 500: только при APP_DEMO_FAILURES_ENABLED=true
curl -i -X POST http://127.0.0.1:8080/items \
  -H 'Content-Type: application/json' -H 'X-Demo-Error: 500' \
  -d '{"name":"Synthetic Error"}'
```

Синтетическая ошибка отключена по умолчанию в `application.properties`
и включена исключительно в локальном `compose.yaml` для последующего нагрузочного теста.

## Что намеренно не входит

Этап 3 (два контейнера приложения, Prometheus и Grafana),
генерация дашбордов и генератор нагрузки будут добавлены дальше.
Пока это только **первый и второй этапы** проекта.

## Почему /metrics сделан собственным контроллером

В прежнем варианте `/metrics` был endpoint Actuator, который не появлялся
в тестовом MVC-контексте, и тесты падали на 404. Теперь `/metrics` — обычный
`@GetMapping`, зарегистрированный Spring MVC точно так же, как `/health`.
Контроллер вызывает `PrometheusMeterRegistry.scrape()` напрямую.
Один и тот же registry используется и фильтром, и контроллером, и в тестах.

#!/usr/bin/env bash
set -euo pipefail

# Проверка готовности.
curl -i http://localhost:8080/health

# Создание записи. Ожидаем HTTP 201 и id=1.
curl -i -X POST http://localhost:8080/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"First item"}'

# Чтение существующей записи. Ожидаем HTTP 200.
curl -i http://localhost:8080/items/1

# Обновление существующей записи. Ожидаем HTTP 200.
curl -i -X PUT http://localhost:8080/items/1 \
  -H 'Content-Type: application/json' \
  -d '{"name":"Updated item"}'

# Чтение отсутствующей записи. Ожидаем HTTP 404.
curl -i http://localhost:8080/items/999999

package ru.itmo.highload.items;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@Service
public class ItemService {
    private final ConcurrentHashMap<Long, Item> items = new ConcurrentHashMap<>();
    // Потокобезопасный счётчик для выдачи уникальных идентификаторов. Подсказака нейронки, что и такое существует.
    // Не знал до выполнения проекта
    private final AtomicLong nextId = new AtomicLong(0);

    public Item create(String name) {
        // Мы не хотим, чтобы оба получили одинаковый ID, поэтому используем incrementAndGet.
        // Правда в случае с 2 экземплярами, как понимаю, он нас все равно от одинаковых ID не защитит.
        long id = nextId.incrementAndGet();

        Item item = new Item(id, name);
        items.put(id, item);
        return item;
    }

    public Item findById(long id) {
        Item item = items.get(id);
        if (item == null) {
            // Spring преобразует исключение в HTTP 404
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Item not found");
        }
        return item;
    }

    public Item update(long id, String name) {
        // Замена атомарна для данного ключа: обновляем только существующую запись
        Item updated = items.computeIfPresent(
                id, (key, previous) -> new Item(key, name)
        );
        if (updated == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Item not found");
        }
        return updated;
    }
}

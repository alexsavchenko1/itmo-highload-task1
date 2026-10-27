package ru.itmo.highload.items;

import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.net.URI;

@RestController
@RequestMapping("/items")
public class ItemController {
    private final ItemService itemService;

    public ItemController(ItemService itemService) {
        this.itemService = itemService;
    }

    @PostMapping
    public ResponseEntity<Item> create(@Valid @RequestBody ItemRequest request) {
        // POST /items -> 201 Created и адрес созданной записи в Location.
        Item created = itemService.create(request.name());
        return ResponseEntity.created(URI.create("/items/" + created.id())).body(created);
    }

    @GetMapping("/{id}")
    public Item get(@PathVariable long id) {
        // GET /items/42 -> запись либо 404, если её нет.
        return itemService.findById(id);
    }

    @PutMapping("/{id}")
    public Item update(@PathVariable long id, @Valid @RequestBody ItemRequest request) {
        // PUT /items/42 -> обновлённая запись либо 404.
        return itemService.update(id, request.name());
    }
}

package ru.itmo.highload.items;

import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;

@RestController
@RequestMapping("/items")
public class ItemController {
    private final ItemService itemService;
    private final boolean demoFailuresEnabled;

    public ItemController(ItemService itemService,
            @Value("${app.demo-failures-enabled:false}") boolean demoFailuresEnabled) {
        this.itemService = itemService;
        this.demoFailuresEnabled = demoFailuresEnabled;
    }

    @PostMapping
    public ResponseEntity<Item> create(@Valid @RequestBody ItemRequest request,
            @RequestHeader(value = "X-Demo-Error", required = false) String demoError) {
        // Только для локального нагрузочного теста: имитация HTTP 500 без нового маршрута.
        if (demoFailuresEnabled && "500".equals(demoError)) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "Intentional 500 for metrics testing");
        }
        Item created = itemService.create(request.name());
        return ResponseEntity.created(URI.create("/items/" + created.id())).body(created);
    }

    @GetMapping("/{id}")
    public Item get(@PathVariable long id) {
        return itemService.findById(id);
    }

    @PutMapping("/{id}")
    public Item update(@PathVariable long id, @Valid @RequestBody ItemRequest request) {
        return itemService.update(id, request.name());
    }
}

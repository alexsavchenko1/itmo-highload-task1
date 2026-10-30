package ru.itmo.highload.items;

import jakarta.validation.constraints.NotBlank;

// JSON-тело запроса при создании и обновлении записи.
public record ItemRequest(
        @NotBlank String name
) {}

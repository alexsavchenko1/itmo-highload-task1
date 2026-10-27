package ru.itmo.highload.items;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {
    @GetMapping("/health")
    public String health() {
        // Служебный маршрут: HTTP 200 означает, что приложение отвечает.
        return "OK";
    }
}

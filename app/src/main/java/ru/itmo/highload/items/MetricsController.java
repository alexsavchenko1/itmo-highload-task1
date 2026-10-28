package ru.itmo.highload.items;

import io.micrometer.prometheusmetrics.PrometheusMeterRegistry;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** HTTP-экспорт метрик; Prometheus будет опрашивать GET /metrics. */
@RestController
public class MetricsController {
    private final PrometheusMeterRegistry registry;

    public MetricsController(PrometheusMeterRegistry registry) {
        this.registry = registry;
    }

    @GetMapping(value = "/metrics", produces = MediaType.TEXT_PLAIN_VALUE)
    public String metrics() {
        // Экспортируем именно байтовый текстовый формат Prometheus,
        // а не JSON со значениями метрик.
        return registry.scrape();
    }
}

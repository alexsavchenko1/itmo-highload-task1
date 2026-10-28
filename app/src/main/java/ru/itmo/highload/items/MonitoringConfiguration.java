package ru.itmo.highload.items;

import io.micrometer.prometheusmetrics.PrometheusConfig;
import io.micrometer.prometheusmetrics.PrometheusMeterRegistry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Один Prometheus-реестр на экземпляр приложения.
 * Он создаётся одинаково и при реальном запуске, и в @SpringBootTest.
 */
@Configuration
public class MonitoringConfiguration {
    @Bean
    public PrometheusMeterRegistry prometheusMeterRegistry() {
        return new PrometheusMeterRegistry(PrometheusConfig.DEFAULT);
    }
}

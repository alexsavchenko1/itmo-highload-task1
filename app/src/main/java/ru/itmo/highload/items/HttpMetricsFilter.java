package ru.itmo.highload.items;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Timer;
import io.micrometer.prometheusmetrics.PrometheusMeterRegistry;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.servlet.HandlerMapping;

import java.io.IOException;
import java.time.Duration;
import java.util.concurrent.TimeUnit;

/**
 * Считает запросы и их длительность с нормализованными метками.
 * Никаких сырых URL с ID в labels (иначе неконтролируемая cardinality).
 */
@Component
public class HttpMetricsFilter extends OncePerRequestFilter {
    private final PrometheusMeterRegistry registry;
    private final String pod;
    private final String datacenter;

    public HttpMetricsFilter(PrometheusMeterRegistry registry,
            @Value("${POD_ID:local}") String pod,
            @Value("${DATACENTER:local}") String datacenter) {
        this.registry = registry;
        this.pod = pod;
        this.datacenter = datacenter;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        long start = System.nanoTime();
        boolean uncaughtError = false;
        try {
            chain.doFilter(request, response);
        } catch (IOException | ServletException | RuntimeException | Error error) {
            uncaughtError = true;
            throw error;
        } finally {
            String route = matchedRoute(request);
            String method = normalizedMethod(request.getMethod());
            String status = Integer.toString(uncaughtError ? 500 : response.getStatus());
            long elapsed = System.nanoTime() - start;

            Counter.builder("app.http.requests")
                    .description("Completed HTTP requests")
                    .tags("pod", pod, "dc", datacenter,
                            "method", method, "route", route, "status", status)
                    .register(registry)
                    .increment();

            // В Prometheus это app_http_request_duration_seconds_bucket.
            // Границы одинаковы у всех экземпляров => корректная агрегация.
            Timer.builder("app.http.request.duration")
                    .description("Duration of HTTP requests")
                    .tags("pod", pod, "dc", datacenter,
                            "method", method, "route", route, "status", status)
                    .publishPercentileHistogram()
                    .minimumExpectedValue(Duration.ofMillis(1))
                    .maximumExpectedValue(Duration.ofSeconds(5))
                    .serviceLevelObjectives(
                            Duration.ofMillis(5), Duration.ofMillis(10),
                            Duration.ofMillis(25), Duration.ofMillis(50),
                            Duration.ofMillis(100), Duration.ofMillis(250),
                            Duration.ofMillis(500), Duration.ofSeconds(1),
                            Duration.ofSeconds(2), Duration.ofSeconds(5))
                    .register(registry)
                    .record(elapsed, TimeUnit.NANOSECONDS);
        }
    }

    private static String matchedRoute(HttpServletRequest request) {
        Object pattern = request.getAttribute(HandlerMapping.BEST_MATCHING_PATTERN_ATTRIBUTE);
        if (pattern instanceof String route && !route.isBlank()
                && !"/**".equals(route) && !"/*".equals(route)) {
            return route;
        }
        return "UNMATCHED";
    }

    private static String normalizedMethod(String method) {
        return switch (method) {
            case "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS" -> method;
            default -> "OTHER";
        };
    }
}

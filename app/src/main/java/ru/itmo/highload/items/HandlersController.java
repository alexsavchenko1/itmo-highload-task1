package ru.itmo.highload.items;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.RequestMappingInfo;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;

import java.util.Comparator;
import java.util.List;
import java.util.Set;

/**
 * GET /handlers сообщает о фактически зарегистрированных MVC-маршрутах.
 * Список не зашит в код: контроллер читает реестр Spring MVC.
 */
@RestController
public class HandlersController {
    private final RequestMappingHandlerMapping handlerMapping;

    public HandlersController(RequestMappingHandlerMapping handlerMapping) {
        this.handlerMapping = handlerMapping;
    }

    @GetMapping("/handlers")
    public List<HandlerDescription> handlers() {
        return handlerMapping.getHandlerMethods().keySet().stream()
                .flatMap(info -> describe(info).stream())
                .filter(handler -> !handler.route().equals("/error"))
                .distinct()
                .sorted(Comparator.comparing(HandlerDescription::route)
                        .thenComparing(HandlerDescription::method))
                .toList();
    }

    private static List<HandlerDescription> describe(RequestMappingInfo info) {
        Set<RequestMethod> methods = info.getMethodsCondition().getMethods();
        List<String> methodNames = methods.isEmpty()
                ? List.of("ANY")
                : methods.stream().map(RequestMethod::name).sorted().toList();

        return info.getPatternValues().stream()
                .flatMap(route -> methodNames.stream()
                        .map(method -> new HandlerDescription(method, route)))
                .toList();
    }

    public record HandlerDescription(String method, String route) {}
}

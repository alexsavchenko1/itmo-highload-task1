package ru.itmo.highload.items;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class ItemsApplication {
    public static void main(String[] args) {
        // Запускает Spring Boot и встроенный HTTP-сервер.
        SpringApplication.run(ItemsApplication.class, args);
    }
}

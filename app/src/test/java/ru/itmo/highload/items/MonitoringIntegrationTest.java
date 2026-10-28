package ru.itmo.highload.items;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Тестирует обычный MVC-маршрут /metrics, а не Actuator в отдельном контексте. */
@SpringBootTest(properties = {
        "POD_ID=test-pod-1",
        "DATACENTER=test-dc",
        "app.demo-failures-enabled=true"
})
@AutoConfigureMockMvc
class MonitoringIntegrationTest {
    @Autowired private MockMvc mockMvc;

    @Test
    void registeredRoutesAreDiscoveredRatherThanHardcoded() throws Exception {
        mockMvc.perform(get("/handlers"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("\"route\":\"/metrics\"")))
                .andExpect(content().string(containsString("\"route\":\"/items/{id}\"")))
                .andExpect(content().string(containsString("\"route\":\"/health\"")));
    }

    @Test
    void crudAndMetricsWorkWithNormalizedLabelsAndErrorStatuses() throws Exception {
        mockMvc.perform(get("/health"))
                .andExpect(status().isOk())
                .andExpect(content().string("OK"));

        mockMvc.perform(post("/items")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"Test\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.name").value("Test"));

        mockMvc.perform(get("/items/1"))
                .andExpect(status().isOk());

        mockMvc.perform(put("/items/1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"Updated\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.name").value("Updated"));

        mockMvc.perform(get("/items/987654321"))
                .andExpect(status().isNotFound());

        mockMvc.perform(post("/items")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"\"}"))
                .andExpect(status().isBadRequest());

        mockMvc.perform(post("/items")
                        .header("X-Demo-Error", "500")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"Synthetic Error\"}"))
                .andExpect(status().isInternalServerError());

        mockMvc.perform(get("/metrics"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("app_http_requests_total")))
                .andExpect(content().string(containsString("app_http_request_duration_seconds_bucket")))
                .andExpect(content().string(containsString("route=\"/items/{id}\"")))
                .andExpect(content().string(containsString("status=\"404\"")))
                .andExpect(content().string(containsString("status=\"500\"")))
                .andExpect(content().string(containsString("pod=\"test-pod-1\"")))
                .andExpect(content().string(containsString("dc=\"test-dc\"")));
    }
}

# Stage 1: compile and run tests. Failing tests stop the Docker build.
FROM maven:3.9.11-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
COPY src ./src
RUN --mount=type=cache,target=/root/.m2/repository mvn -B -ntp verify

# Stage 2: the runtime image does not need Maven or Java sources.
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/target/task1-items-0.1.0.jar /app/app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

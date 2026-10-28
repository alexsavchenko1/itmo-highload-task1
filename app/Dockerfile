# исполняемый JAR из исходников Java.
FROM maven:3.9.11-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
COPY src ./src
RUN mvn -B -DskipTests package

# готовое приложение, без Maven.
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/target/task1-items-0.1.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

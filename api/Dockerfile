# temp container to build using gradle
FROM gradle:6.5.0-jdk11 AS TEMP_BUILD_IMAGE
COPY --chown=gradle:gradle . /home/gradle/src
WORKDIR /home/gradle/src
RUN gradle clean bootJar

FROM adoptopenjdk:11-jre-hotspot as builder
WORKDIR application
ARG JAR_FILE=/home/gradle/src/build/libs/*.jar
COPY --from=TEMP_BUILD_IMAGE ${JAR_FILE} application.jar
RUN java -Djarmode=layertools -jar application.jar extract

FROM adoptopenjdk:11-jre-hotspot
WORKDIR application
COPY --from=builder application/dependencies/ ./
COPY --from=builder application/snapshot-dependencies/ ./
COPY --from=builder application/spring-boot-loader/ ./
COPY --from=builder application/application/ ./

EXPOSE 8080
ENTRYPOINT ["java", "org.springframework.boot.loader.JarLauncher"]

#FROM openjdk:11-jre-slim
#ENV ARTIFACT_NAME=trailsinthedatabase-1.0.0.jar
#COPY --from=TEMP_BUILD_IMAGE /home/gradle/src/build/libs /usr/src/trailsinthedatabase
#WORKDIR /usr/src/trailsinthedatabase

#EXPOSE 8080
#ENTRYPOINT exec java -jar ${ARTIFACT_NAME}
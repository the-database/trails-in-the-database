//package com.database.trailsinthedatabase.config;
//
//import com.database.trailsinthedatabase.converter.CsvEncoder;
//import com.fasterxml.jackson.databind.ObjectMapper;
//import org.springframework.beans.factory.annotation.Autowired;
//import org.springframework.context.annotation.Configuration;
//import org.springframework.http.codec.ServerCodecConfigurer;
//import org.springframework.web.reactive.config.WebFluxConfigurer;
//
//@Configuration
//public class CsvConfig implements WebFluxConfigurer {
//
//    @Autowired
//    private ObjectMapper objectMapper;
//
//    CsvConfig(ObjectMapper objectMapper) {
//        this.objectMapper = objectMapper;
//    }
//
//    @Override
//    public void configureHttpMessageCodecs(ServerCodecConfigurer configurer) {
//        configurer.customCodecs().register(new CsvEncoder<>(objectMapper));
//    }
//}

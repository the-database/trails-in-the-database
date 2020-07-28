package com.database.trailsinthedatabase;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class TrailsinthedatabaseApplication {

	public static void main(String[] args) {
		SpringApplication.run(TrailsinthedatabaseApplication.class, args);
	}

	@Bean
	public OpenAPI customOpenAPI() {
		return new OpenAPI()
				.components(new Components())
				.info(new Info().title("Trails in the Database API").description(
						"The Trails in the Database API is a set of REST services that provide an interface with the " +
								"Trails series scripts and other related data."));
	}
}

package com.database.trailsinthedatabase;

import com.database.trailsinthedatabase.controller.ScriptController;
import com.database.trailsinthedatabase.model.Script;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.web.server.LocalServerPort;

import static org.assertj.core.api.Assertions.assertThat;


@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class TrailsinthedatabaseApplicationTests {

	@LocalServerPort
	private int port;

	@Autowired
	private TestRestTemplate restTemplate;

	@Autowired
	private ScriptController scriptController;

	@Test
	void contextLoads() {
		assertThat(scriptController).isNotNull();
	}

	@Test
	void queryOK() {
		assertThat(this.restTemplate.getForObject("http://localhost:" + port + "/?q=test",
				Script.class));
	}

	@Test
	void chrOK() {
		this.restTemplate.getForObject("http://localhost:" + port + "/?chr[]=one&chr[]=two", Script.class);
	}

	@Test
	void gameIdOK() {
		this.restTemplate.getForObject("http://localhost:" + port + "/?game_id=4", Script.class);
	}
}

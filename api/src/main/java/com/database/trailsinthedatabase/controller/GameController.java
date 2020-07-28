package com.database.trailsinthedatabase.controller;

import com.database.trailsinthedatabase.model.Game;
import com.database.trailsinthedatabase.repository.GameRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

@Tag(name = "Game API")
@RestController
public class GameController {

    @Autowired
    GameRepository gameRepository;

    @Operation(summary = "Get all games")
    @GetMapping(value = "/api/game")
    public Flux<Game> getGames() {
        return gameRepository.findAllFast();
    }
}

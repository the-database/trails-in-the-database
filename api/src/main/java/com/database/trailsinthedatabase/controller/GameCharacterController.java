package com.database.trailsinthedatabase.controller;

import com.database.trailsinthedatabase.model.GameCharacter;
import com.database.trailsinthedatabase.model.Sort;
import com.database.trailsinthedatabase.model.Stat;
import com.database.trailsinthedatabase.repository.GameCharacterRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.Optional;

@Tag(name = "Character API")
@RestController
public class GameCharacterController {

    Logger log = LoggerFactory.getLogger(GameCharacterController.class);

    private static final String DEFAULT_PAGE_SIZE = "20";

    @Autowired
    private GameCharacterRepository gameCharacterRepository;

    @Operation(summary = "Get all character names")
    @GetMapping("/api/chr")
    public Flux<GameCharacter> getCharacters() {
        return gameCharacterRepository.findAllCharacters();
    }

    @Operation(summary = "Search character names by string")
    @GetMapping(value = "/api/chr", params = {"chr"})
    public Flux<GameCharacter> getCharacters(@RequestParam("chr") String chr) {
        return gameCharacterRepository.findCharactersByName(chr);
    }

    @Operation(summary = "Get character details, optionally filtered by game")
    @GetMapping("/api/chr/detail")
    public Flux<GameCharacter> getCharacterDetails(
            @RequestParam(value = "page_number", required = false, defaultValue = "1") int pageNumber,
            @RequestParam(value = "page_size", required = false, defaultValue = DEFAULT_PAGE_SIZE) int pageSize,
            @RequestParam(value = "sort", required = false, defaultValue = "rows") Sort sort,
            @RequestParam(value = "asc", required = false, defaultValue = "0") boolean asc,
            @RequestParam(value = "game_id") Optional<Integer> gameId) {
        int offset = (pageNumber - 1) * pageSize;
        log.debug("sort = " + sort);
        if (gameId.isPresent()) {
            return gameCharacterRepository.findCharactersByGame(gameId.get(), offset, pageSize, sort, asc);
        }
        return gameCharacterRepository.findAllCharacterDetailsFast(offset, pageSize, sort, asc);
    }

    @Operation(summary = "Get total number of characters, optionally filtered by game")
    @GetMapping("/api/chr/detail/stat")
    public Mono<Stat> getCharacterDetailsStats(@RequestParam("game_id") Optional<Integer> gameId) {
        if (gameId.isPresent()) {
            return gameCharacterRepository.countCharactersByGame(gameId.get());
        }
        return gameCharacterRepository.countCharacters();
    }
}

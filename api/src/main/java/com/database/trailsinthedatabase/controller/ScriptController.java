package com.database.trailsinthedatabase.controller;

import com.database.trailsinthedatabase.model.Script;
import com.database.trailsinthedatabase.model.Stat;
import com.database.trailsinthedatabase.repository.ScriptRepository;
import com.database.trailsinthedatabase.repository.StatRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

import javax.validation.constraints.Min;
import javax.validation.constraints.Size;
import java.util.Optional;
import java.util.Set;

@Tag(name = "Script API")
@RestController
@Validated
@RequestMapping(value = "/api/script")
public class ScriptController {

    Logger log = LoggerFactory.getLogger(ScriptController.class);

    public static final String DEFAULT_PAGE_SIZE = "100";

    @Autowired
    private ScriptRepository scriptRepository;

    @Autowired
    private StatRepository statRepository;

    @Operation(summary = "Get script for a given game and script filename")
    @GetMapping("/detail/{gameId}/{fname}")
    public Flux<Script> getDetail(@PathVariable("gameId") Integer gameId, @PathVariable("fname") String fname) {
        return scriptRepository.findByGameIdAndFnameOrderByRowAsc(gameId, fname);
    }

    @Operation(summary = "Search scripts by query text, character, game")
    @GetMapping("/search")
    public Flux<Script> search(
            @RequestParam(value = "q") Optional<@Size(min = 1) String> q,
            @RequestParam(value = "chr[]") Optional<@Size(min = 1) Set<String>> chr,
            @RequestParam(value = "game_id") Optional<Integer> gameId,
            @RequestParam(value = "strict_search", defaultValue = "0") Boolean strictSearch,
            @RequestParam(value = "page_number", defaultValue = "1") @Min(1)  Integer pageNumber,
            @RequestParam(value = "page_size", defaultValue = DEFAULT_PAGE_SIZE) @Min(1) Integer pageSize) {

        Optional<Integer> sanitizedGameId = gameId;

        if (gameId.isPresent() && gameId.get() < 1) {
            sanitizedGameId = Optional.empty();
        }

        Integer offset = (pageNumber - 1) * pageSize;

        if (strictSearch) {
            return scriptRepository.searchAdvancedStrict(q, chr, sanitizedGameId, offset, pageSize);
        }

        return scriptRepository.searchAdvanced(q, chr, sanitizedGameId, offset, pageSize);
    }

    @Operation(summary = "Get number of results, grouped by game, for a search script query")
    @GetMapping("/search/stat")
    public Flux<Stat> count(
            @RequestParam(value = "q") Optional<@Size(min = 1) String> q,
            @RequestParam(value = "chr[]") Optional<@Size(min = 1) Set<String>> chr,
            @RequestParam(value = "game_id") Optional<Integer> gameId,
            @RequestParam(value = "strict_search", defaultValue = "0") Boolean strictSearch) {

        Optional<Integer> sanitizedGameId = gameId;

        if (gameId.isPresent() && gameId.get() < 1) {
            sanitizedGameId = Optional.empty();
        }

        if (strictSearch) {
            return statRepository.countAdvancedStrict(q, chr, sanitizedGameId);
        }

        return statRepository.countAdvanced(q, chr, sanitizedGameId);
    }
}
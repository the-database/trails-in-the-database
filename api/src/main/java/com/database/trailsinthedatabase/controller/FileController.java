package com.database.trailsinthedatabase.controller;

import com.database.trailsinthedatabase.model.File;
import com.database.trailsinthedatabase.repository.FileRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

import java.util.Optional;

@Tag(name = "Script File API")
@RestController
public class FileController {
    @Autowired
    FileRepository fileRepository;

    @Operation(summary = "Get metadata about one or all script files for a game")
    @GetMapping("/api/file")
    Flux<File> getFileByGameId(@RequestParam("game_id") Integer gameId,
                               @RequestParam("fname") Optional<String> fname) {

        if (fname.isPresent()) {
            return fileRepository.findFilesByGameIdAndFile(gameId, fname.get());
        }

        return fileRepository.findFilesByGameId(gameId);
    }
}

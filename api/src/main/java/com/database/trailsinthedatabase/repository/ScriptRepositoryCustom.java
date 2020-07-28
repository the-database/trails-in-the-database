package com.database.trailsinthedatabase.repository;

import com.database.trailsinthedatabase.model.Script;
import reactor.core.publisher.Flux;

import java.util.Optional;
import java.util.Set;

public interface ScriptRepositoryCustom {
    public Flux<Script> searchAdvanced(Optional<String> queryText, Optional<Set<String>> chr, Optional<Integer> gameId,
                                       int offset, int limit);

    public Flux<Script> searchAdvancedStrict(Optional<String> q, Optional<Set<String>> chr, Optional<Integer>
            sanitizedGameId, int offset, int limit);
}

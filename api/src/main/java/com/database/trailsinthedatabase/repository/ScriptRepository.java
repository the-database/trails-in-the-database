package com.database.trailsinthedatabase.repository;

import com.database.trailsinthedatabase.model.Script;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;

@Repository
public interface ScriptRepository extends ReactiveCrudRepository<Script, Long>, ScriptRepositoryCustom {
    Flux<Script> findByGameIdAndFnameOrderByRowAsc(Integer gameId, String fname);
}

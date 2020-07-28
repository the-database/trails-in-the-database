package com.database.trailsinthedatabase.repository;

import com.database.trailsinthedatabase.model.Game;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;

@Repository
public class GameRepository {

    @Autowired
    DatabaseClient client;

    public Flux<Game> findAllFast() {
        return client.execute("SELECT * FROM game_stat_mv")
                .as(Game.class)
                .fetch()
                .all();
    }
}

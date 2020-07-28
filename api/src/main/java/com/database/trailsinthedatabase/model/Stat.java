package com.database.trailsinthedatabase.model;

import org.springframework.data.annotation.Id;

public class Stat {
    @Id
//    private Integer gameId; // null: all games / total count
    private Game game;
    private Integer rows;

//    public Integer getGameId() {
//        return gameId;
//    }


    public Game getGame() {
        return game;
    }

    public Integer getRows() {
        return rows;
    }
}

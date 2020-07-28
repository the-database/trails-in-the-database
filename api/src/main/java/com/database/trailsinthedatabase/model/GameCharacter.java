package com.database.trailsinthedatabase.model;

import java.util.Set;

public class GameCharacter {

//    @Id
//    private String chrName;

    private String engChrName;
    private String jpnChrName;
    Set<Integer> gameId;
    Long rows;

//    public String getChrName() {
//        return chrName;
//    }

    public String getEngChrName() {
        return engChrName;
    }

    public String getJpnChrName() {
        return jpnChrName;
    }

    public Set<Integer> getGameId() {
        return gameId;
    }

    public Long getRows() {
        return rows;
    }
}

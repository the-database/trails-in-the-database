package com.database.trailsinthedatabase.model;

import java.util.Set;

public class File {
    private Integer gameId;
    private String fname;
    private Long rows;
    private Set<String> engPlaceNames;
    private Set<String> jpnPlaceNames;
    private Set<String> engChrNames;
    private Set<String> jpnChrNames;

    public Integer getGameId() {
        return gameId;
    }

    public String getFname() {
        return fname;
    }

    public Long getRows() {
        return rows;
    }

    public Set<String> getEngPlaceNames() {
        return engPlaceNames;
    }

    public Set<String> getJpnPlaceNames() {
        return jpnPlaceNames;
    }

    public Set<String> getEngChrNames() {
        return engChrNames;
    }

    public Set<String> getJpnChrNames() {
        return jpnChrNames;
    }
}

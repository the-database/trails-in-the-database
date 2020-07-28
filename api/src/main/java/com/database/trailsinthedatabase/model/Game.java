package com.database.trailsinthedatabase.model;

import org.springframework.data.annotation.Id;

public class Game {

    @Id
    private Integer id;

    private String titleEng;
    private String titleJpnRoman;
    private String titleJpn;

    private Integer rows;

    public Integer getId() {
        return id;
    }

    public String getTitleEng() {
        return titleEng;
    }

    public String getTitleJpnRoman() {
        return titleJpnRoman;
    }

    public String getTitleJpn() {
        return titleJpn;
    }

    public Integer getRows() {
        return rows;
    }
}

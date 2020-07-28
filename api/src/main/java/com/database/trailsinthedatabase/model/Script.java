package com.database.trailsinthedatabase.model;

import com.fasterxml.jackson.annotation.JsonIgnore;
import org.springframework.data.annotation.Id;


public class Script {
    @Id
    private Long id;

    private Integer gameId;
    private String fname;
    private String scene;
    private Long row;
    private String engChrName;
    private String engSearchText;
    private String engHtmlText;
    private String jpnChrName;
    private String jpnSearchText;
    private String jpnHtmlText;
    private String opName;
    private String pcIconHtml;
    private String evoIconHtml;

    @JsonIgnore
    public Long getId() {
        return id;
    }

    public Integer getGameId() {
        return gameId;
    }

    public String getFname() {
        return fname;
    }

    public String getScene() {
        return scene;
    }

    public Long getRow() {
        return row;
    }

    public String getEngChrName() {
        return engChrName;
    }

    public String getEngSearchText() {
        return engSearchText;
    }

    public String getEngHtmlText() {
        return engHtmlText;
    }

    public String getJpnChrName() {
        return jpnChrName;
    }

    public String getJpnSearchText() {
        return jpnSearchText;
    }

    public String getJpnHtmlText() {
        return jpnHtmlText;
    }

    public String getOpName() {
        return opName;
    }

    public String getPcIconHtml() {
        return pcIconHtml;
    }

    public String getEvoIconHtml() {
        return evoIconHtml;
    }
}

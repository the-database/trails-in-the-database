package com.database.trailsinthedatabase.model;

public enum Sort {
    engChrName {
        @Override
        public String toString() {
            return "eng_chr_name";
        }
    }, jpnChrName {
        @Override
        public String toString() {
            return "jpn_chr_name";
        }
    }, rows
}

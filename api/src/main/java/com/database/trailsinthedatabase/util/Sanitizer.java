package com.database.trailsinthedatabase.util;

import org.springframework.stereotype.Component;

@Component
public class Sanitizer {
    public String sanitizeSqlLike(String text) {
        return text
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_");
    }
}

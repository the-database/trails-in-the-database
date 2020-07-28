package com.database.trailsinthedatabase.util;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
public class SanitizerTests {

    @Autowired
    Sanitizer sanitizer;

    @Test
    void sanitizePercentOK() {
        assertThat(sanitizer.sanitizeSqlLike("%")).isEqualTo("\\%");
    }

    @Test
    void sanitizeUnderscoreOK() {
        assertThat(sanitizer.sanitizeSqlLike("_")).isEqualTo("\\_");
    }

    @Test
    void sanitizeBackslashOK() {
        assertThat(sanitizer.sanitizeSqlLike("\\")).isEqualTo("\\\\");
    }
}

package com.database.trailsinthedatabase.repository;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.Optional;
import java.util.Set;

@SpringBootTest
public class ScriptRepositoryCustomImplTests {
    @Autowired
    private ScriptRepositoryCustomImpl scriptRepositoryCustom;

    @Test
    void queryOK() {
        scriptRepositoryCustom.searchAdvanced(
                Optional.of("test"),
                Optional.empty(),
                Optional.empty(),
                1,
                10);
    }

    @Test
    void chrOK() {
        scriptRepositoryCustom.searchAdvanced(
                Optional.empty(),
                Optional.of(Set.of("one", "two")),
                Optional.empty(),
                1,
                10
        );
    }

    @Test
    void gameIdOK() {
        scriptRepositoryCustom.searchAdvanced(
                Optional.empty(),
                Optional.empty(),
                Optional.of(5),
                1,
                10
        );
    }
}

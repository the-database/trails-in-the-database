package com.database.trailsinthedatabase.repository;

import com.database.trailsinthedatabase.model.Stat;
import com.database.trailsinthedatabase.util.Sanitizer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.r2dbc.core.DatabaseClient;
import org.springframework.data.util.Pair;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import static com.database.trailsinthedatabase.repository.ScriptRepositoryCustomImpl.*;

@Repository
public class StatRepository {

    Logger log = LoggerFactory.getLogger(StatRepository.class);

    private static final String BASE_QUERY_START = "SELECT c.rows, game_id, g.title_eng game_title_eng, " +
            "g.title_jpn game_title_jpn, g.title_jpn_roman game_title_jpn_roman " +
            "FROM (SELECT count(*) as rows, game_id FROM script s WHERE ";

//    private static final String QUERY_TEXT_CLAUSE = "( to_tsvector('english_nostop', s.eng_search_text) @@ websearch_to_tsquery('english_nostop', :queryText) " +
//            "OR to_tsvector('simple', s.jpn_search_text) @@ websearch_to_tsquery('simple', :queryText) ) ";
//    private static final String QUERY_CHR_CLAUSE = "( s.eng_chr_name IN (:chr) OR s.jpn_chr_name IN (:chr) ) ";
//    private static final String QUERY_GAME_ID_CLAUSE = "(game_id = :gameId) ";

    private static final String BASE_QUERY_END = "GROUP BY ROLLUP(game_id) " +
            "ORDER BY game_id) as c " +
            "LEFT JOIN game g on c.game_id = g.id";

    @Autowired
    DatabaseClient client;

    @Autowired
    Sanitizer sanitizer;

    public Flux<Stat> countAdvanced(Optional<String> queryText, Optional<Set<String>> chr, Optional<Integer> gameId) {

        StringBuilder sql = new StringBuilder(BASE_QUERY_START);

        List<String> clauses = new ArrayList<>();
        List<Pair<String, Object>> params = new ArrayList<>();

        if (queryText.isPresent()) {
            if (ALPHA_PATTERN.matcher(queryText.get()).find()) {
                if (queryText.get().contains("\"")) {
                    clauses.add(QUERY_TEXT_ENG_STRICT_CLAUSE);
                } else {
                    clauses.add(QUERY_TEXT_ENG_LOOSE_CLAUSE);
                }
            } else {
                clauses.add(QUERY_TEXT_JPN_CLAUSE);
            }

            params.add(Pair.of("queryText", queryText.get()));
        }

        if (chr.isPresent()) {
            clauses.add(QUERY_CHR_CLAUSE);
            params.add(Pair.of("chr", chr.get()));
        }

        if (gameId.isPresent()) {
            clauses.add(QUERY_GAME_ID_CLAUSE);
            params.add(Pair.of("gameId", gameId.get()));
        }

        sql.append(String.join(" AND ", clauses));
        sql.append(BASE_QUERY_END);

        DatabaseClient.GenericExecuteSpec bindings = client.execute(sql.toString());

        for (Pair<String, Object> param : params) {
            bindings = bindings.bind(param.getFirst(), param.getSecond());
        }

        return bindings
                .as(Stat.class)
                .fetch()
                .all();
    }

    public Flux<Stat> countAdvancedStrict(Optional<String> queryText, Optional<Set<String>> chr, Optional<Integer> gameId) {
        StringBuilder sql = new StringBuilder(BASE_QUERY_START);

        List<String> clauses = new ArrayList<>();
        List<Pair<String, Object>> params = new ArrayList<>();

        if (queryText.isPresent()) {
            if (ALPHA_PATTERN.matcher(queryText.get()).find()) {
                clauses.add("lower(s.eng_search_text) LIKE lower(:queryText) ");
            } else {
                clauses.add("lower(s.jpn_search_text) LIKE lower(:queryText) ");
            }

            params.add(Pair.of("queryText", "%" + sanitizer.sanitizeSqlLike(queryText.get()) + "%"));
        }

        if (chr.isPresent()) {
            clauses.add(QUERY_CHR_CLAUSE);
            params.add(Pair.of("chr", chr.get()));
        }

        if (gameId.isPresent()) {
            clauses.add(QUERY_GAME_ID_CLAUSE);
            params.add(Pair.of("gameId", gameId.get()));
        }

        sql.append(String.join(" AND ", clauses));
        sql.append(BASE_QUERY_END);

        log.debug(sql.toString());

        DatabaseClient.GenericExecuteSpec bindings = client.execute(sql.toString());

        for (Pair<String, Object> param : params) {
            log.debug("binding " + param.getFirst() + ": " + param.getSecond());
            bindings = bindings.bind(param.getFirst(), param.getSecond());
        }

        return bindings
                .as(Stat.class)
                .fetch()
                .all();
    }
}

package com.database.trailsinthedatabase.repository;

import com.database.trailsinthedatabase.model.Script;
import com.database.trailsinthedatabase.util.Sanitizer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.r2dbc.core.DatabaseClient;
import org.springframework.data.util.Pair;
import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;

public class ScriptRepositoryCustomImpl implements ScriptRepositoryCustom {

    Logger log = LoggerFactory.getLogger(ScriptRepositoryCustomImpl.class);

    private static final String BASE_QUERY_START = "SELECT * FROM script s WHERE ";

//    public static final String QUERY_TEXT_CLAUSE = "( to_tsvector('english_nostop', s.eng_search_text) @@ websearch_to_tsquery('english_nostop', :queryText) " +
//            "OR to_tsvector('simple', s.jpn_search_text) @@ websearch_to_tsquery('simple', :queryText) ) ";
    public static final String QUERY_TEXT_ENG_STRICT_CLAUSE = "to_tsvector('simple', s.eng_search_text) @@ websearch_to_tsquery('simple', :queryText) ";
    public static final String QUERY_TEXT_ENG_LOOSE_CLAUSE = "to_tsvector('english_nostop', s.eng_search_text) @@ websearch_to_tsquery('english_nostop', :queryText) ";
    public static final String QUERY_TEXT_JPN_CLAUSE = "s.jpn_search_text LIKE concat('%',:queryText,'%')  ";
    public static final String QUERY_CHR_CLAUSE = "( s.eng_chr_name IN (:chr) OR s.jpn_chr_name IN (:chr) ) ";
    public static final String QUERY_GAME_ID_CLAUSE = "(game_id = :gameId) ";

    private static final String BASE_QUERY_END = "ORDER BY game_id, fname, row " +
            "OFFSET :offset LIMIT :limit";

    public static final Pattern ALPHA_PATTERN = Pattern.compile("[a-zA-Z.,:;'%_]");

    @Autowired
    DatabaseClient client;

    @Autowired
    Sanitizer sanitizer;

    @Override
    public Flux<Script> searchAdvanced(Optional<String> queryText, Optional<Set<String>> chr, Optional<Integer> gameId,
                                       int offset, int limit) {

        StringBuilder sql = new StringBuilder(BASE_QUERY_START);

        List<String> clauses = new ArrayList<>();
        List<Pair<String, Object>> params = new ArrayList<>();

        if (queryText.isPresent()) {
            if (ALPHA_PATTERN.matcher(queryText.get()).find()) {
                if (queryText.get().contains("\"")) {
                    log.debug("ENG STRICT");
                    clauses.add(QUERY_TEXT_ENG_STRICT_CLAUSE);
                } else {
                    log.debug("ENG LOOSE");
                    clauses.add(QUERY_TEXT_ENG_LOOSE_CLAUSE);
                }
            } else {
                log.debug("JPN LOOSE");
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
            log.debug("binding " + param.getFirst() + ": " + param.getSecond());
            bindings = bindings.bind(param.getFirst(), param.getSecond());
        }

        return bindings
                .bind("offset", offset)
                .bind("limit", limit)
                .as(Script.class)
                .fetch()
                .all();
    }

    @Override
    public Flux<Script> searchAdvancedStrict(Optional<String> queryText, Optional<Set<String>> chr,
                                             Optional<Integer> gameId, int offset, int limit) {
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
                .bind("offset", offset)
                .bind("limit", limit)
                .as(Script.class)
                .fetch()
                .all();
    }
}

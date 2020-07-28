package com.database.trailsinthedatabase.repository;

import com.database.trailsinthedatabase.model.GameCharacter;
import com.database.trailsinthedatabase.model.Sort;
import com.database.trailsinthedatabase.model.Stat;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.Set;

@Repository
public class GameCharacterRepository {

    @Autowired
    DatabaseClient client;

    private static final Set<String> SORT_COLUMNS = Set.of("rows", "eng_chr_name", "jpn_chr_name");

    private static final String BASE_QUERY = "SELECT distinct array_agg(distinct s.game_id) as game_id,\n" +
            "eng_chr_name, jpn_chr_name\n" +
            "FROM script s \n" +
            "LEFT JOIN file f ON s.game_id = f.game_id AND s.fname = f.fname \n" +
            "WHERE f.place_name_eng IS NOT NULL AND place_name_eng != '' AND place_name_eng != 'map1' ";

    private static final String CHR_CLAUSE = "AND (lower(eng_chr_name) LIKE lower(:chr) OR jpn_chr_name LIKE :chr) ";
    private static final String GROUP_ORDER_BY = "GROUP BY eng_chr_name, jpn_chr_name " +
            "ORDER BY eng_chr_name, jpn_chr_name";

    private static final String DETAIL_BASE_QUERY = "SELECT array_agg(distinct s.game_id), s.eng_chr_name, " +
            "s.jpn_chr_name, count(*) as rows FROM script s \n" +
            "WHERE fname NOT LIKE 'a%' AND (game_id, fname) NOT IN (SELECT game_id, fname FROM file " +
            "WHERE place_name_eng LIKE 'map%') \n";

    private static final String DETAIL_GROUP_ORDER_BY = "GROUP BY s.eng_chr_name, s.jpn_chr_name ORDER BY rows desc";

    private static final String FIND_ALL_CHARACTERS = BASE_QUERY + GROUP_ORDER_BY;
    private static final String FIND_BY_NAME_CONTAINS = BASE_QUERY + CHR_CLAUSE + GROUP_ORDER_BY;
    private static final String FINAL_ALL_CHARACTER_DETAILS = DETAIL_BASE_QUERY + DETAIL_GROUP_ORDER_BY;

    public Flux<GameCharacter> findAllCharacters() {
        return client.execute(FIND_ALL_CHARACTERS)
                .as(GameCharacter.class)
                .fetch()
                .all();
    }

    public Flux<GameCharacter> findCharactersByName(String character) {
        return client.execute(FIND_BY_NAME_CONTAINS)
                .bind("chr", String.format("%%%s%%", character))
                .as(GameCharacter.class)
                .fetch()
                .all();
    }

    public Flux<GameCharacter> findAllCharacterDetails() {
        return client.execute(FINAL_ALL_CHARACTER_DETAILS)
                .as(GameCharacter.class)
                .fetch()
                .all();
    }

    public Flux<GameCharacter> findAllCharacterDetailsFast(int offset, int limit, Sort sort, boolean asc) {
        return client.execute(String.format("SELECT * FROM chr_detail_mv " +
                "ORDER BY %s %s " +
                "OFFSET :offset LIMIT :limit",
                sort.toString(),
                asc ? "ASC" : "DESC"))
                .bind("offset", offset)
                .bind("limit", limit)
                .as(GameCharacter.class)
                .fetch()
                .all();
    }

    public Flux<GameCharacter> findCharactersByGame(int gameId, int offset, int limit, Sort sort, boolean asc) {
        return client.execute(String.format("SELECT array_agg(distinct s.game_id) as game_id, s.eng_chr_name, s.jpn_chr_name, count(*) as rows FROM " +
                "(SELECT * FROM script s1 WHERE game_id = :gameId) s " +
                "WHERE fname NOT LIKE 'a%%' AND (game_id, fname) NOT IN (SELECT game_id, fname FROM file WHERE place_name_eng LIKE 'map%%') " +
                "GROUP BY s.eng_chr_name, s.jpn_chr_name ORDER BY %s %s " +
                "OFFSET :offset LIMIT :limit", sort.toString(), asc ? "ASC" : "DESC"))
                .bind("gameId", gameId)
                .bind("offset", offset)
                .bind("limit", limit)
                .as(GameCharacter.class)
                .fetch()
                .all();
    }

    public Mono<Stat> countCharacters() {
        return client.execute("SELECT count(*) as rows FROM chr_detail_mv")
                .as(Stat.class)
                .fetch()
                .one();
    }

    public Mono<Stat> countCharactersByGame(int gameId) {
        return client.execute("SELECT count(*) as rows FROM " +
                "(SELECT DISTINCT s.eng_chr_name, s.jpn_chr_name FROM " +
                "(SELECT * FROM script s1 WHERE s1.game_id = :gameId) s " +
                "WHERE fname NOT LIKE 'a%' AND (game_id, fname) NOT IN (SELECT game_id, fname FROM file WHERE place_name_eng LIKE 'map%'" +
                ")) sx")
                .bind("gameId", gameId)
                .as(Stat.class)
                .fetch()
                .one();
    }
}

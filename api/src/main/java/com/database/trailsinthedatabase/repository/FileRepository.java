package com.database.trailsinthedatabase.repository;

import com.database.trailsinthedatabase.model.File;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;

@Repository
public class FileRepository {

    @Autowired
    DatabaseClient client;

    private static final String BASE_QUERY = "select s.game_id, s.fname, s.rows, \n" +
            "string_agg(distinct place_name_eng, ',' order by place_name_eng) as eng_place_names, \n" +
            "string_agg(distinct place_name_jpn, ',' order by place_name_jpn) as jpn_place_names,\n" +
            "s.eng_chr_names, s.jpn_chr_names\n" +
            "from (select s1.game_id, s1.fname, count(row) as rows, string_agg(distinct eng_chr_name, ',' order by eng_chr_name) as eng_chr_names, string_agg(distinct jpn_chr_name, ',' order by jpn_chr_name) as jpn_chr_names  from script s1 group by s1.game_id, s1.fname) s \n" +
            "left join file f on s.game_id = f.game_id and s.fname = f.fname\n";

    private static final String GAME_ID_CLAUSE = "where s.game_id = :game_id\n";
    private static final String FNAME_CLAUSE = "AND s.fname = :fname\n";
    private static final String GROUP_ORDER_BY = "group by s.game_id, s.fname, s.rows, s.eng_chr_names, s.jpn_chr_names " +
            "ORDER BY s.game_id, s.fname";

    private static final String FIND_BY_GAME_ID_QUERY = BASE_QUERY
            + GAME_ID_CLAUSE
            + GROUP_ORDER_BY;

    private static final String FIND_BY_GAME_AND_FNAME_QUERY = BASE_QUERY
            + GAME_ID_CLAUSE
            + FNAME_CLAUSE
            + GROUP_ORDER_BY;

    public Flux<File> findFilesByGameId(Integer gameId) {
        return client.execute(FIND_BY_GAME_ID_QUERY)
                .bind("game_id", gameId)
                .as(File.class)
                .fetch()
                .all();
    }

    public Flux<File> findFilesByGameIdAndFile(Integer gameId, String fname) {
        return client.execute(FIND_BY_GAME_AND_FNAME_QUERY)
                .bind("game_id", gameId)
                .bind("fname", fname)
                .as(File.class)
                .fetch()
                .all();
    }
}

package com.database.trailsinthedatabase.controller;

import com.database.trailsinthedatabase.repository.ScriptRepository;
import com.database.trailsinthedatabase.repository.StatRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ScriptController.class)
public class ScriptControllerTests {
    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ScriptRepository scriptRepository;

    @MockBean
    private StatRepository statRepository;

    void searchQueryOK() throws Exception {
        mockMvc.perform(get("/search?q=test")).andExpect(status().isOk());
    }

    void searchChrOK() throws Exception {
        mockMvc.perform(get("/search?q=chr[]=one&chr[]=two")).andExpect(status().isOk());
    }

    void searchGameOK() throws Exception {
        mockMvc.perform(get("/search?game_id=6")).andExpect(status().isOk());
    }

    void searchPagingOK() throws Exception {
        mockMvc.perform(get("/search?q=test&page_number=4&page_size=10")).andExpect(status().isOk());
    }

    void statQueryOK() throws Exception {
        mockMvc.perform(get("/search/stat?q=test")).andExpect(status().isOk());
    }

    void statChrOK() throws Exception {
        mockMvc.perform(get("/search/stat?q=chr[]=one&chr[]=two")).andExpect(status().isOk());
    }

    void statGameOK() throws Exception {
        mockMvc.perform(get("/search/stat?game_id=6")).andExpect(status().isOk());
    }
}

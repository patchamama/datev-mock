package com.elo.datevmock.config;

import com.elo.datevmock.store.StoredRecordStore;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.nio.file.Path;

/**
 * Wires the SB4 {@link StoredRecordStore} as an application-wide singleton
 * bean, backed by a SQLite file in the working directory (gitignored),
 * mirroring FastAPI's own {@code datev_mock.db} convention.
 */
@Configuration
public class StoreConfig {

    @Bean
    public StoredRecordStore storedRecordStore() {
        return new StoredRecordStore(Path.of("datev_mock.db"));
    }
}

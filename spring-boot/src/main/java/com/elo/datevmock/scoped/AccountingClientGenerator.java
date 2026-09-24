package com.elo.datevmock.scoped;

import com.elo.datevmock.model.AccountingClient;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.UUID;

/**
 * Ports {@code app/data_store.py::list_accounting_clients} (indirectly
 * exercised via {@code app/routers/accounting.py::get_accounting_clients}):
 * a small, fixed-count, unscoped dataset generated once at startup — the
 * accounting {@code GET .../clients} list is not fiscal-year-scoped, unlike
 * every resource {@link ScopedDataService} serves.
 */
@Component
public class AccountingClientGenerator {

    private static final int CLIENT_COUNT = 10;

    private final List<AccountingClient> clients;

    public AccountingClientGenerator() {
        Random rng = new Random(4211);
        List<AccountingClient> records = new ArrayList<>();
        for (int index = 0; index < CLIENT_COUNT; index++) {
            int number = 10000 + index;
            records.add(new AccountingClient(
                    String.valueOf(number),
                    UUID.randomUUID().toString(),
                    "Mandant " + (index + 1),
                    number,
                    null,
                    null,
                    null,
                    null));
        }
        this.clients = List.copyOf(records);
    }

    public List<AccountingClient> clients() {
        return clients;
    }
}

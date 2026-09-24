package com.elo.datevmock.masterdata;

import com.elo.datevmock.model.Addressee;
import com.elo.datevmock.model.Bank;
import com.elo.datevmock.model.ClientResource;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.UUID;

/**
 * Ports the shape (not the exact values — different PRNGs, never the goal;
 * see {@code ScopeSeed}'s javadoc for why) of
 * {@code app/fake_data.py::_generate_client_resources}/
 * {@code _generate_addressees}/{@code _generate_banks}: a small, fixed-count,
 * deterministic-for-the-JVM's-lifetime dataset generated once at startup —
 * unlike SB3's fiscal-year-scoped generation, master-data has no scope to
 * key off, matching {@code app/data_store.py}'s own flat, unscoped module-
 * level lists.
 */
@Component
public class MasterDataGenerator {

    private static final int CLIENT_COUNT = 18;
    private static final int ADDRESSEE_COUNT = 8;
    private static final int BANK_COUNT = 6;

    private final List<ClientResource> clientResources;
    private final List<Addressee> addressees;
    private final List<Bank> banks;

    public MasterDataGenerator() {
        Random random = new Random(fixedSeed());
        this.clientResources = generateClientResources(random);
        this.addressees = generateAddressees(random);
        this.banks = generateBanks();
    }

    public List<ClientResource> clientResources() {
        return List.copyOf(clientResources);
    }

    public List<Addressee> addressees() {
        return List.copyOf(addressees);
    }

    public List<Bank> banks() {
        return List.copyOf(banks);
    }

    private static long fixedSeed() {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest("master-data-fixed-dataset".getBytes(StandardCharsets.UTF_8));
            long seed = 0L;
            for (int i = 0; i < 8; i++) {
                seed = (seed << 8) | (hash[i] & 0xFF);
            }
            return seed;
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 must be available on every JVM", e);
        }
    }

    private static List<ClientResource> generateClientResources(Random random) {
        List<ClientResource> result = new ArrayList<>();
        String now = Instant.now().toString();
        for (int i = 0; i < CLIENT_COUNT; i++) {
            boolean legalPerson = random.nextBoolean();
            result.add(new ClientResource(
                    UUID.randomUUID().toString(),
                    null, null, null,
                    "2020-01-01T00:00:00+01:00", null,
                    null, "Client " + i,
                    null, null, null, null,
                    null, null, null,
                    null, null, null,
                    null, null,
                    legalPerson ? UUID.randomUUID().toString() : null,
                    "Client " + i,
                    legalPerson ? null : UUID.randomUUID().toString(),
                    null,
                    1000 + i,
                    null, null, null, null,
                    null, null, null, null,
                    "active", null, now,
                    null, null, null,
                    legalPerson ? "legal_person" : "natural_person"
            ));
        }
        return result;
    }

    private static List<Addressee> generateAddressees(Random random) {
        List<Addressee> result = new ArrayList<>();
        String now = Instant.now().toString();
        for (int i = 0; i < ADDRESSEE_COUNT; i++) {
            boolean legalPerson = i % 2 == 0;
            if (legalPerson) {
                result.add(new Addressee(
                        UUID.randomUUID().toString(), "legal_person", "active", now,
                        null, null,
                        "Short " + i, null, null,
                        null, null, null, null, null, null, null,
                        "Company " + i, null, "2010-01-01T00:00:00+01:00",
                        UUID.randomUUID().toString(), null));
            } else {
                result.add(new Addressee(
                        UUID.randomUUID().toString(), "natural_person", "active", now,
                        null, null,
                        "Short " + i, null, null,
                        "1980-01-01T00:00:00+01:00", null, "First" + i,
                        random.nextBoolean() ? "male" : "female", "Last" + i, null, null,
                        null, null, null, null, null));
            }
        }
        return result;
    }

    private static List<Bank> generateBanks() {
        List<Bank> result = new ArrayList<>();
        String now = Instant.now().toString();
        for (int i = 0; i < BANK_COUNT; i++) {
            result.add(new Bank(
                    UUID.randomUUID().toString(),
                    String.format("%08d", 10000000 + i),
                    "BANKDE" + (10 + i) + "XXX",
                    "City " + i,
                    "DE",
                    "Bank " + i,
                    i == 0,
                    now));
        }
        return result;
    }
}

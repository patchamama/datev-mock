package com.elo.datevmock.store;

import java.lang.reflect.Constructor;
import java.lang.reflect.RecordComponent;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Ports {@code app/db.py::record_to_dataclass}/{@code merge_with_stored}:
 * builds a typed Java {@code record} instance from a stored (validated) data
 * map via reflection over its record components, and unions "fake"
 * (generated) records with whatever's been written to SQLite for the same
 * resource type -- a stored record whose id matches a fake one *replaces*
 * it (PUT-over-fake semantics); a stored record with a new id is appended.
 */
public final class RecordMapper {

    private RecordMapper() {
    }

    /**
     * @param fieldMap  maps a source key in {@code data} to the record
     *                  component name it should populate, only where they
     *                  differ -- a component with no entry pointing at it
     *                  is read from {@code data} under its own name.
     * @param nilFields component names forced to {@code null} regardless of
     *                  what {@code data} holds (nested fields with no
     *                  dedicated sub-rendering support yet, same rationale
     *                  as the FastAPI reference).
     */
    public static <T extends Record> T fromStored(
            Class<T> type, Map<String, Object> data, Map<String, String> fieldMap, Set<String> nilFields) {
        RecordComponent[] components = type.getRecordComponents();
        Class<?>[] paramTypes = new Class<?>[components.length];
        Object[] args = new Object[components.length];

        for (int i = 0; i < components.length; i++) {
            RecordComponent component = components[i];
            paramTypes[i] = component.getType();
            String name = component.getName();

            if (nilFields.contains(name)) {
                args[i] = null;
                continue;
            }

            String sourceKey = sourceKeyFor(name, fieldMap);
            if (data.containsKey(sourceKey)) {
                args[i] = data.get(sourceKey);
            } else {
                // Falls back to the snake_case spelling of the component name --
                // every write body arrives as raw (unmapped) JSON keys matching
                // this project's snake_case convention (e.g. "long_name"), while
                // Java record components are camelCase ("longName"). An explicit
                // fieldMap entry (checked above) still wins when a name genuinely
                // differs beyond casing (e.g. ClientResource's PascalCase XML names).
                String snakeKey = toSnakeCase(name);
                if (data.containsKey(snakeKey)) {
                    args[i] = data.get(snakeKey);
                } else {
                    args[i] = defaultForType(component.getType());
                }
            }
        }

        try {
            Constructor<T> constructor = type.getDeclaredConstructor(paramTypes);
            constructor.setAccessible(true);
            return constructor.newInstance(args);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("failed to build " + type.getSimpleName() + " from stored data", e);
        }
    }

    private static String toSnakeCase(String camelCase) {
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < camelCase.length(); i++) {
            char c = camelCase.charAt(i);
            if (Character.isUpperCase(c)) {
                result.append('_').append(Character.toLowerCase(c));
            } else {
                result.append(c);
            }
        }
        return result.toString();
    }

    private static String sourceKeyFor(String componentName, Map<String, String> fieldMap) {
        for (Map.Entry<String, String> entry : fieldMap.entrySet()) {
            if (entry.getValue().equals(componentName)) {
                return entry.getKey();
            }
        }
        return componentName;
    }

    private static Object defaultForType(Class<?> type) {
        if (type.equals(String.class)) {
            return "";
        }
        if (type.equals(int.class) || type.equals(Integer.class)) {
            return 0;
        }
        if (type.equals(long.class) || type.equals(Long.class)) {
            return 0L;
        }
        if (type.equals(double.class) || type.equals(Double.class)) {
            return 0.0;
        }
        if (type.equals(boolean.class) || type.equals(Boolean.class)) {
            return false;
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private static <T extends Record> Object componentValue(T instance, String componentName) {
        for (RecordComponent component : instance.getClass().getRecordComponents()) {
            if (component.getName().equals(componentName)) {
                try {
                    return component.getAccessor().invoke(instance);
                } catch (ReflectiveOperationException e) {
                    throw new IllegalStateException("failed to read " + componentName + " from " + instance, e);
                }
            }
        }
        throw new IllegalArgumentException("no such record component: " + componentName);
    }

    /**
     * Unions {@code fakeRecords} with every stored record for
     * {@code resourceType} (optionally scoped by {@code clientId}/
     * {@code fiscalYearId}, forwarded to {@link StoredRecordStore#listRecords}
     * so a caller's stored records never leak across scopes).
     */
    public static <T extends Record> List<T> mergeWithStored(
            List<T> fakeRecords,
            String resourceType,
            Class<T> type,
            String idField,
            Map<String, String> fieldMap,
            Set<String> nilFields,
            StoredRecordStore store,
            String clientId,
            String fiscalYearId) {
        List<Map<String, Object>> stored = store.listRecords(resourceType, clientId, fiscalYearId);

        Map<Object, T> storedInstances = new LinkedHashMap<>();
        for (Map<String, Object> row : stored) {
            T instance = fromStored(type, row, fieldMap, nilFields);
            storedInstances.put(componentValue(instance, idField), instance);
        }

        List<T> merged = new ArrayList<>();
        for (T fake : fakeRecords) {
            if (!storedInstances.containsKey(componentValue(fake, idField))) {
                merged.add(fake);
            }
        }
        merged.addAll(storedInstances.values());
        return merged;
    }
}

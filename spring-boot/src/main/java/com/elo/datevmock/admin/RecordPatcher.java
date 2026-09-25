package com.elo.datevmock.admin;

import java.lang.reflect.Constructor;
import java.lang.reflect.RecordComponent;
import java.util.Map;

/**
 * Applies a partial field-overrides map (admin-panel PascalCase keys, e.g.
 * {@code {"Name": "..."}} from the browser's edit-row prompt) onto an
 * existing record instance, keeping every other field's current value --
 * mirrors Python's {@code dataclasses.replace(record, **fields)} used by
 * {@code app/data_store.py::update_master_data}/{@code update_accounting_client}.
 */
final class RecordPatcher {

    private RecordPatcher() {
    }

    @SuppressWarnings("unchecked")
    static <T extends Record> T patch(T record, Map<String, Object> fields) {
        try {
            Class<T> type = (Class<T>) record.getClass();
            RecordComponent[] components = type.getRecordComponents();
            Class<?>[] paramTypes = new Class<?>[components.length];
            Object[] args = new Object[components.length];
            for (int i = 0; i < components.length; i++) {
                RecordComponent component = components[i];
                paramTypes[i] = component.getType();
                String camelName = component.getName();
                String pascalName = Character.toUpperCase(camelName.charAt(0)) + camelName.substring(1);
                if (fields.containsKey(pascalName)) {
                    args[i] = fields.get(pascalName);
                } else if (fields.containsKey(camelName)) {
                    args[i] = fields.get(camelName);
                } else {
                    args[i] = component.getAccessor().invoke(record);
                }
            }
            Constructor<T> ctor = type.getDeclaredConstructor(paramTypes);
            ctor.setAccessible(true);
            return ctor.newInstance(args);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("failed to patch " + record.getClass().getSimpleName(), e);
        }
    }
}

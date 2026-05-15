-- Добавить уникальное ограничение для shipment_items (shipment_id, barcode)
-- Это необходимо для работы UPSERT (ON CONFLICT DO UPDATE)

-- Проверяем, существует ли уже ограничение
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'shipment_items'
        AND constraint_type = 'UNIQUE'
        AND constraint_name = 'shipment_items_shipment_id_barcode_unique'
    ) THEN
        -- Сначала удалим дубликаты если есть (оставляем последнюю запись)
        DELETE FROM shipment_items a USING (
            SELECT MAX(id) as id, shipment_id, barcode
            FROM shipment_items
            GROUP BY shipment_id, barcode
            HAVING COUNT(*) > 1
        ) b
        WHERE a.shipment_id = b.shipment_id
        AND a.barcode = b.barcode
        AND a.id < b.id;
        
        -- Добавляем уникальное ограничение
        ALTER TABLE shipment_items
        ADD CONSTRAINT shipment_items_shipment_id_barcode_unique
        UNIQUE (shipment_id, barcode);
        
        RAISE NOTICE 'Добавлено уникальное ограничение shipment_items_shipment_id_barcode_unique';
    ELSE
        RAISE NOTICE 'Ограничение shipment_items_shipment_id_barcode_unique уже существует';
    END IF;
END $$;

-- Проверяем результат
SELECT constraint_name, table_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name IN ('shipment_items', 'box_items', 'boxes')
AND constraint_type = 'UNIQUE'
ORDER BY table_name, constraint_name;

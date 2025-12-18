CREATE VIEW aliases AS
    SELECT 'LOCATION' AS entity_type, location_id AS entity_id, alias, normalized
      FROM location_aliases
    UNION ALL
    SELECT 'REGION', region_id, alias, normalized
      FROM region_aliases
    UNION ALL
    SELECT 'GROUP', group_id, alias, normalized
      FROM group_aliases
    UNION ALL
    SELECT 'DIRECTION', direction_id, alias, normalized
      FROM direction_aliases;

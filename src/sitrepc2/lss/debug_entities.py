# src/sitrepc2/lss/debug_entities.py
from __future__ import annotations

from sitrepc2.lss.ruler import _load_aliases_by_entity, _load_locale_aliases_by_cid
from sitrepc2.util.normalize import normalize_location_key

def debug_entity_patterns():
    """Debug what patterns are actually loaded from the database."""
    
    print("="*60)
    print("DATABASE ENTITY ALIAS DEBUG")
    print("="*60)
    
    # Load aliases
    aliases_by_entity = _load_aliases_by_entity()
    
    print("\n📊 Alias counts by entity type:")
    for entity_type, aliases in aliases_by_entity.items():
        print(f"  {entity_type}: {len(aliases)} aliases")
        # Show first 10 examples
        for alias in list(aliases)[:10]:
            print(f"    - '{alias}'")
        if len(aliases) > 10:
            print(f"    ... and {len(aliases) - 10} more")
    
    # Check for specific entities
    test_entities = ["DPR", "Russian Armed Forces", "Kharkiv", "Zaporizhia"]
    
    print("\n🔍 Checking specific entities:")
    for entity in test_entities:
        found = False
        norm = normalize_location_key(entity)
        for entity_type, aliases in aliases_by_entity.items():
            if norm in aliases or entity in aliases:
                print(f"  ✓ '{entity}' found as {entity_type.upper()}")
                found = True
                break
        if not found:
            print(f"  ✗ '{entity}' NOT FOUND in database")
    
    print("="*60)

if __name__ == "__main__":
    debug_entity_patterns()
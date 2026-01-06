# DOM Persistence Model (Authoritative)

## Structural Layer (Immutable)
- dom_post
- dom_node
- dom_node_provenance

Created once by `dom_ingest()`.

## Snapshot Layer (Append-Only)
- dom_snapshot
- dom_node_state
- dom_context
- dom_actor
- dom_location_candidate
- dom_commit_eligibility

Snapshots are immutable once created.

## Persistence Rules
- Structure is never modified
- Review changes update snapshot-scoped tables
- Lifecycle advancement creates a new snapshot
- State is cloned forward, never mutated backward

## Canonical Functions
- dom_ingest()
- persist_dom_tree()
- materialize_dom_context()
- advance_dom_snapshot()
- recompute_commit_eligibility()

## Mental Model
- dom_node = directory tree
- dom_snapshot = filesystem snapshot
- snapshot tables = inode metadata
